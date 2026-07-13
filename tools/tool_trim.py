# -*- coding: utf-8 -*-
"""planX CAD — Trim Aracı
Tamamen yeniden yazıldı: intersection tipinden bağımsız,
difference() tabanlı güvenilir trim işlemi.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsFeature, QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base


class tool_trim(tool_base):
    """Kesme sınırına göre çizgiyi kırpar.
    1. Kesme sınırını seç | 2. Kesilecek çizginin silinecek tarafına tıkla
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.cutting_layer = None
        self.cutting_feature = None

    def tool_name(self):
        return "Trim"

    def activate(self):
        super().activate()
        self.tool_message.emit("✂️ Trim — Kesme sınırını seçin")

    def on_entity_selected(self, layer, feature, point):
        self.cutting_layer = layer
        self.cutting_feature = feature
        self._step = 2
        self.tool_message.emit(
            "✂️ Trim — Kesilecek çizginin SİLİNECEK tarafına tıklayın"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # Kesme sınırı dışlanır — sınır kendisiyle kırpılamaz
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.cutting_layer, self.cutting_feature),
            )
            if result:
                layer, feature = result
                # ``point`` is in the first (cutting) layer CRS because
                # tool_base selected that layer first. Convert it to the
                # target feature CRS before distance-based side selection.
                canvas_point = self.to_canvas_coordinates(
                    point, self.cutting_layer
                )
                target_point = self.to_layer_coordinates(canvas_point, layer)
                self._do_trim(layer, feature, target_point)
            else:
                self.tool_message.emit("⚠️ Trim — Obje bulunamadı")

            self._reset()
            self.cutting_layer = None
            self.cutting_feature = None

    def _do_trim(self, layer, feature, click_point):
        """Gerçek trim işlemi — difference tabanlı."""
        target_geom = feature.geometry()
        cutting_geom = self.geometry_to_layer_crs(
            self.cutting_feature.geometry(), self.cutting_layer, layer
        )
        if cutting_geom is None:
            self.tool_message.emit("⚠️ Trim — CRS dönüşümü başarısız")
            return

        # Kesişim kontrolü
        if not target_geom.intersects(cutting_geom):
            self.tool_message.emit("⚠️ Trim — Kesişim noktası bulunamadı")
            return

        # Kesişim noktalarını bul (tip ne olursa olsun)
        intersection = target_geom.intersection(cutting_geom)
        if intersection is None or intersection.isEmpty():
            self.tool_message.emit("⚠️ Trim — Kesişim hesaplanamadı")
            return

        # Kesişim noktalarını çıkar
        int_points = self._extract_points(intersection)
        if not int_points:
            self.tool_message.emit("⚠️ Trim — Kesişim noktası çıkarılamadı")
            return

        # Hedef çizgiyi noktalardan böl
        line_pts = self._get_line_points(target_geom)
        if not line_pts or len(line_pts) < 2:
            self.tool_message.emit("⚠️ Trim — Çizgi noktaları okunamadı")
            return

        # Kesişim noktalarını çizgi üzerindeki konumlarına göre sırala
        locations = []
        for ip in int_points:
            loc = target_geom.lineLocatePoint(QgsGeometry.fromPointXY(ip))
            locations.append((loc, ip))
        locations.sort(key=lambda x: x[0])

        # Çizgiyi segmentlere böl
        segments = self._split_line_at_points(target_geom, [p for _, p in locations])

        if not segments or len(segments) < 2:
            # Alternatif: Küçük buffer ile difference
            small_buf = cutting_geom.buffer(0.001, 4)
            diff = target_geom.difference(small_buf)
            if diff and not diff.isEmpty():
                parts = self._explode_multipart(diff)
                if parts:
                    kept = self._keep_farthest(parts, click_point)
                    if kept:
                        if self._apply_edit(layer, feature, kept):
                            self.tool_message.emit("✅ Trim — Kırpma uygulandı")
                        return
            self.tool_message.emit("⚠️ Trim — Bölme yapılamadı")
            return

        # Tıklanan noktaya en yakın segmenti bul → onu SİL, kalanları birleştir
        click_geom = QgsGeometry.fromPointXY(click_point)
        min_dist = float('inf')
        remove_idx = 0

        for i, seg in enumerate(segments):
            d = seg.distance(click_geom)
            if d < min_dist:
                min_dist = d
                remove_idx = i

        # Kalan parçaları al
        remaining = [seg for i, seg in enumerate(segments) if i != remove_idx]

        if remaining:
            if len(remaining) == 1:
                if self._apply_edit(layer, feature, remaining[0]):
                    self.tool_message.emit("✅ Trim — Kırpma uygulandı")
                return

            if QgsWkbTypes.isMultiType(layer.wkbType()):
                keep_geom = QgsGeometry.collectGeometry(remaining)
                if self._apply_edit(layer, feature, keep_geom):
                    self.tool_message.emit("✅ Trim — Kırpma uygulandı")
            else:
                # A single-part LineString layer cannot accept a disconnected
                # MultiLineString. Keep one part on the original feature and
                # add the other valid parts as features with copied attributes.
                if self._replace_single_part_feature(layer, feature, remaining):
                    self.tool_message.emit("✅ Trim — Kırpma uygulandı")
                else:
                    self.tool_message.emit(
                        "⚠️ Trim — Yazma hatası; tüm değişiklikler geri alındı"
                    )
        else:
            self.tool_message.emit("⚠️ Trim — Kalan parça bulunamadı")

    @staticmethod
    def _replace_single_part_feature(layer, feature, geometries):
        new_features = []
        for geometry in geometries[1:]:
            new_feature = QgsFeature(layer.fields())
            new_feature.setGeometry(geometry)
            for index in range(layer.fields().count()):
                new_feature.setAttribute(index, feature.attribute(index))
            new_features.append(new_feature)

        layer.beginEditCommand("PlanX CAD: trim")
        success = layer.changeGeometry(feature.id(), geometries[0])
        if success and new_features:
            success = layer.addFeatures(new_features)
        if not success:
            layer.destroyEditCommand()
            return False
        layer.endEditCommand()
        layer.triggerRepaint()
        return True

    def _extract_points(self, geom):
        """Herhangi bir geometriden nokta listesi çıkar."""
        points = []
        if geom is None or geom.isEmpty():
            return points

        # Multipart'ı aç
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
                # Çizgi kesişimleri: uç noktalarını al
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
        """Geometriden çizgi noktalarını al."""
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
        """Çizgiyi verilen noktalarda böl."""
        # Apply each split to every current part. splitGeometry mutates only
        # the geometry it is invoked on; the old implementation kept newly
        # created parts aside, so a second intersection falling on one of
        # those parts was silently ignored.
        all_parts = [QgsGeometry(line_geom)]
        for sp in split_points:
            next_parts = []
            for part in all_parts:
                candidate = QgsGeometry(part)
                # QGIS 3/4 returns (OperationResult, new_geoms, topo_pts).
                result = candidate.splitGeometry([sp], False)
                new_geoms = result[1] if len(result) > 1 else []
                next_parts.append(candidate if new_geoms else part)
                next_parts.extend(new_geoms)
            all_parts = next_parts

        # Boş parçaları filtrele
        return [p for p in all_parts if p and not p.isEmpty()]

    def _explode_multipart(self, geom):
        """Multipart geometriyi parçalara ayır."""
        if geom.isMultipart():
            return geom.asGeometryCollection()
        return [geom]

    def _keep_farthest(self, parts, click_point):
        """Tıklanan noktaya en uzak parçayı döndür."""
        click_geom = QgsGeometry.fromPointXY(click_point)
        max_dist = -1
        best = None
        for p in parts:
            d = p.distance(click_geom)
            if d > max_dist:
                max_dist = d
                best = p
        return best
