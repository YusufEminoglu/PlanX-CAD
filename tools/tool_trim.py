# -*- coding: utf-8 -*-
"""planX CAD â€” Trim AracÄ±
Tamamen yeniden yazÄ±ldÄ±: intersection tipinden baÄŸÄ±msÄ±z,
difference() tabanlÄ± gÃ¼venilir trim iÅŸlemi.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base


class tool_trim(tool_base):
    """Kesme sÄ±nÄ±rÄ±na gÃ¶re Ã§izgiyi kÄ±rpar.
    1. Kesme sÄ±nÄ±rÄ±nÄ± seÃ§ | 2. Kesilecek Ã§izginin silinecek tarafÄ±na tÄ±kla
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.cutting_layer = None
        self.cutting_feature = None

    def tool_name(self):
        return "Trim"

    def activate(self):
        super().activate()
        self.tool_message.emit("âœ‚ï¸ Trim â€” Kesme sÄ±nÄ±rÄ±nÄ± seÃ§in")

    def on_entity_selected(self, layer, feature, point):
        self.cutting_layer = layer
        self.cutting_feature = feature
        self._step = 2
        self.tool_message.emit(
            "âœ‚ï¸ Trim â€” Kesilecek Ã§izginin SÄ°LÄ°NECEK tarafÄ±na tÄ±klayÄ±n"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            result = self._pick_feature(self.canvas.mouseLastXY())
            if result:
                layer, feature = result
                self._do_trim(layer, feature, point)
            else:
                self.tool_message.emit("âš ï¸ Trim â€” Obje bulunamadÄ±")

            self._reset()
            self.cutting_layer = None
            self.cutting_feature = None

    def _do_trim(self, layer, feature, click_point):
        """GerÃ§ek trim iÅŸlemi â€” difference tabanlÄ±."""
        target_geom = feature.geometry()
        cutting_geom = self.cutting_feature.geometry()

        # KesiÅŸim kontrolÃ¼
        if not target_geom.intersects(cutting_geom):
            self.tool_message.emit("âš ï¸ Trim â€” KesiÅŸim noktasÄ± bulunamadÄ±")
            return

        # KesiÅŸim noktalarÄ±nÄ± bul (tip ne olursa olsun)
        intersection = target_geom.intersection(cutting_geom)
        if intersection is None or intersection.isEmpty():
            self.tool_message.emit("âš ï¸ Trim â€” KesiÅŸim hesaplanamadÄ±")
            return

        # KesiÅŸim noktalarÄ±nÄ± Ã§Ä±kar
        int_points = self._extract_points(intersection)
        if not int_points:
            self.tool_message.emit("âš ï¸ Trim â€” KesiÅŸim noktasÄ± Ã§Ä±karÄ±lamadÄ±")
            return

        # Hedef Ã§izgiyi noktalardan bÃ¶l
        line_pts = self._get_line_points(target_geom)
        if not line_pts or len(line_pts) < 2:
            self.tool_message.emit("âš ï¸ Trim â€” Ã‡izgi noktalarÄ± okunamadÄ±")
            return

        # KesiÅŸim noktalarÄ±nÄ± Ã§izgi Ã¼zerindeki konumlarÄ±na gÃ¶re sÄ±rala
        locations = []
        for ip in int_points:
            loc = target_geom.lineLocatePoint(QgsGeometry.fromPointXY(ip))
            locations.append((loc, ip))
        locations.sort(key=lambda x: x[0])

        # Ã‡izgiyi segmentlere bÃ¶l
        segments = self._split_line_at_points(target_geom, [p for _, p in locations])

        if not segments or len(segments) < 2:
            # Alternatif: KÃ¼Ã§Ã¼k buffer ile difference
            small_buf = cutting_geom.buffer(0.001, 4)
            diff = target_geom.difference(small_buf)
            if diff and not diff.isEmpty():
                parts = self._explode_multipart(diff)
                if parts:
                    kept = self._keep_farthest(parts, click_point)
                    if kept:
                        self._apply_edit(layer, feature, kept)
                        self.tool_message.emit("âœ… Trim â€” KÄ±rpma uygulandÄ±")
                        return
            self.tool_message.emit("âš ï¸ Trim â€” BÃ¶lme yapÄ±lamadÄ±")
            return

        # TÄ±klanan noktaya en yakÄ±n segmenti bul â†’ onu SÄ°L, kalanlarÄ± birleÅŸtir
        click_geom = QgsGeometry.fromPointXY(click_point)
        min_dist = float('inf')
        remove_idx = 0

        for i, seg in enumerate(segments):
            d = seg.distance(click_geom)
            if d < min_dist:
                min_dist = d
                remove_idx = i

        # Kalan parÃ§alarÄ± al
        remaining = [seg for i, seg in enumerate(segments) if i != remove_idx]

        if remaining:
            if len(remaining) == 1:
                keep_geom = remaining[0]
            else:
                # En bÃ¼yÃ¼k parÃ§ayÄ± tut veya birleÅŸtir
                keep_geom = remaining[0]
                for r in remaining[1:]:
                    combined = keep_geom.combine(r)
                    if combined and not combined.isEmpty():
                        keep_geom = combined

            self._apply_edit(layer, feature, keep_geom)
            self.tool_message.emit("âœ… Trim â€” KÄ±rpma uygulandÄ±")
        else:
            self.tool_message.emit("âš ï¸ Trim â€” Kalan parÃ§a bulunamadÄ±")

    def _extract_points(self, geom):
        """Herhangi bir geometriden nokta listesi Ã§Ä±kar."""
        points = []
        if geom is None or geom.isEmpty():
            return points

        # Multipart'Ä± aÃ§
        if geom.isMultipart():
            parts = geom.asGeometryCollection()
        else:
            parts = [geom]

        for part in parts:
            if part.type() == QgsWkbTypes.PointGeometry:
                if part.isMultipart():
                    for p in part.asMultiPoint():
                        points.append(QgsPointXY(p))
                else:
                    points.append(QgsPointXY(part.asPoint()))
            elif part.type() == QgsWkbTypes.LineGeometry:
                # Ã‡izgi kesiÅŸimleri: uÃ§ noktalarÄ±nÄ± al
                if part.isMultipart():
                    for line in part.asMultiPolyline():
                        for p in line:
                            points.append(QgsPointXY(p))
                else:
                    for p in part.asPolyline():
                        points.append(QgsPointXY(p))
            else:
                # Centroid'i kullan
                c = part.centroid()
                if c and not c.isEmpty():
                    points.append(QgsPointXY(c.asPoint()))

        return points

    def _get_line_points(self, geom):
        """Geometriden Ã§izgi noktalarÄ±nÄ± al."""
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            if lines:
                pts = []
                for line in lines:
                    pts.extend([QgsPointXY(p) for p in line])
                return pts
        else:
            return [QgsPointXY(p) for p in geom.asPolyline()]
        return []

    def _split_line_at_points(self, line_geom, split_points):
        """Ã‡izgiyi verilen noktalarda bÃ¶l."""
        # splitGeometry hem multipoint hem tek point destekler
        geom = QgsGeometry(line_geom)
        all_parts = []

        for sp in split_points:
            # QGIS 3.x returns (OperationResult, new_geoms, topo_pts).
            # Older builds returned 2-tuple â€” handle both via *rest.
            result = geom.splitGeometry([sp], False)
            new_geoms = result[1] if len(result) > 1 else []
            if new_geoms:
                all_parts.extend(new_geoms)

        all_parts.insert(0, geom)  # Ä°lk parÃ§a

        # BoÅŸ parÃ§alarÄ± filtrele
        return [p for p in all_parts if p and not p.isEmpty()]

    def _explode_multipart(self, geom):
        """Multipart geometriyi parÃ§alara ayÄ±r."""
        if geom.isMultipart():
            return geom.asGeometryCollection()
        return [geom]

    def _keep_farthest(self, parts, click_point):
        """TÄ±klanan noktaya en uzak parÃ§ayÄ± dÃ¶ndÃ¼r."""
        click_geom = QgsGeometry.fromPointXY(click_point)
        max_dist = -1
        best = None
        for p in parts:
            d = p.distance(click_geom)
            if d > max_dist:
                max_dist = d
                best = p
        return best
