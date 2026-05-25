# -*- coding: utf-8 -*-
"""
planX CAD â€” KavÅŸak OluÅŸturma AracÄ± (GeliÅŸmiÅŸ)
NetCAD tarzÄ± kavÅŸak Ã§Ã¶zÃ¼mÃ¼:
 - DÄ±ÅŸ kaldÄ±rÄ±mlar: dÃ¼z Ã§izgi ile kÄ±rma (chamfer)
 - Ä°Ã§ kaldÄ±rÄ±mlar: radius ile yay (fillet) baÄŸlantÄ±sÄ±
 - KavÅŸak adasÄ±: yuvarlak veya su damlasÄ±

OluÅŸturulan katmanlar:
 - kavsak (LineString): kÄ±rma ve baÄŸlantÄ± Ã§izgileri
 - kavsak_ada (Polygon): kavÅŸak adalarÄ±
"""

import math
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsFeature,
    QgsProject, QgsVectorLayer
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband, cleanup_sketcher_rubberband, COLOR_ACCENT
)
from ..core.sketcher_layer_utils import get_or_create_layer, get_road_platform_layer
from ..core.sketcher_utils import calc_tangent_fillet_arc
from .junction_dialog import JunctionDialog


class JunctionSketcher(QgsMapTool):
    """KavÅŸak oluÅŸturma aracÄ±.

    Ä°ÅŸ akÄ±ÅŸÄ±:
    1. Dialog aÃ§Ä±lÄ±r â†’ parametreler girilir
    2. KavÅŸak merkezi tÄ±klanÄ±r
    3. Otomatik olarak:
       a) Etki yarÄ±Ã§apÄ± iÃ§indeki Ã§izgiler trimlenir
       b) DÄ±ÅŸ kaldÄ±rÄ±m kÃ¶ÅŸeleri dÃ¼z Ã§izgi ile kÄ±rÄ±lÄ±r (chamfer)
       c) Ä°Ã§ kaldÄ±rÄ±m kÃ¶ÅŸeleri radius ile baÄŸlanÄ±r (fillet)
       d) KavÅŸak adasÄ± oluÅŸturulur (yuvarlak/su damlasÄ±)
    """

    sketcher_finished = pyqtSignal()
    sketcher_message = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.params = None
        self.preview_rb = None
        self._step = 0

    def activate(self):
        super().activate()
        self._step = 0

        # Parametre dialog'u
        dlg = JunctionDialog(self.iface.mainWindow())
        if dlg.exec() != JunctionDialog.Accepted:
            self.sketcher_message.emit("ðŸ”µ KavÅŸak â€” Ä°ptal edildi")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self._step = 1
        self.sketcher_message.emit(
            f"ðŸ”µ KavÅŸak (R={self.params['radius']}m, "
            f"KÄ±rma={self.params['chamfer_dist']}m, "
            f"Fillet R={self.params['fillet_radius']}m) â€” "
            f"KavÅŸak merkezini tÄ±klayÄ±n"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        super().deactivate()

    def canvasPressEvent(self, event):
        if self._step != 1 or event.button() != Qt.MouseButton.LeftButton:
            return

        point = self.toMapCoordinates(event.pos())
        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        self._create_junction(point)

    def canvasMoveEvent(self, event):
        if self._step != 1 or not self.preview_rb:
            return

        point = self.toMapCoordinates(event.pos())
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        # Daire Ã¶nizleme
        pts = self._make_circle(point, self.params["radius"], 48)
        self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
        for pt in pts:
            self.preview_rb.addPoint(pt)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
            self.preview_rb = None
            self.sketcher_message.emit("ðŸ”µ KavÅŸak â€” Ä°ptal edildi")
            self.sketcher_finished.emit()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # KavÅŸak OluÅŸturma
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _create_junction(self, center):
        """Ana kavÅŸak oluÅŸturma iÅŸlemi."""
        p = self.params
        radius = p["radius"]
        chamfer_dist = p["chamfer_dist"]
        fillet_radius = p["fillet_radius"]
        ada_tipi = p["ada_tipi"]
        ada_radius = p["ada_radius"]

        center_geom = QgsGeometry.fromPointXY(center)
        junction_buffer = center_geom.buffer(radius, 48)

        # â”€â”€ KatmanlarÄ± hazÄ±rla â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        kavsak_line_layer = get_road_platform_layer()
        kavsak_ada_layer = self._get_kavsak_ada_layer()

        if not kavsak_line_layer or not kavsak_ada_layer:
            self.sketcher_message.emit("âš ï¸ KavÅŸak â€” Katmanlar oluÅŸturulamadÄ±")
            return

        kavsak_id = self._next_id(kavsak_line_layer, "yol_id")

        # â”€â”€ 1. TÃ¼m Ã§izgi katmanlarÄ±nÄ± trimle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        trimmed_count = 0
        cut_endpoints = []  # Trimlenen Ã§izgilerin kesilme noktalarÄ±nÄ± topla

        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                continue
            if layer.name() in ("kavsak",):
                continue

            features_hit = []
            for feat in layer.getFeatures():
                geom = feat.geometry()
                if geom.isEmpty():
                    continue
                if not geom.intersects(junction_buffer):
                    continue
                features_hit.append(feat)

            if not features_hit:
                continue

            # KullanÄ±cÄ± katmanÄ± zaten edit moddaysa commit'i ona bÄ±rak.
            layer_was_editing = layer.isEditable()
            if not layer_was_editing:
                layer.startEditing()

            for feat in features_hit:
                geom = feat.geometry()
                
                # 1 Metrelik split Ã¶zelliÄŸi eklendi:
                # DÄ±ÅŸ yollar (R + 1m den baÅŸlayan) ve 1m'lik parÃ§alar (R ile R+1 arasÄ±)
                outer_buffer = center_geom.buffer(radius + 1.0, 48)
                trimmed_roads = geom.difference(outer_buffer)
                one_meter_segments = geom.intersection(outer_buffer).difference(junction_buffer)

                parts = []
                if trimmed_roads and not trimmed_roads.isEmpty():
                    if trimmed_roads.isMultipart():
                        parts.extend(trimmed_roads.asGeometryCollection())
                    else:
                        parts.append(trimmed_roads)
                        
                if one_meter_segments and not one_meter_segments.isEmpty():
                    if one_meter_segments.isMultipart():
                        parts.extend(one_meter_segments.asGeometryCollection())
                    else:
                        parts.append(one_meter_segments)

                if parts:
                    # Kesilme noktalarÄ±nÄ± union Ã¼zerinden bul
                    all_trimmed = geom.difference(junction_buffer)
                    if all_trimmed and not all_trimmed.isEmpty():
                        endpoints = self._find_cut_endpoints(
                            geom, all_trimmed, junction_buffer
                        )
                        bilesen = None
                        idx_bil = layer.fields().indexOf("bilesen")
                        if idx_bil >= 0:
                            bilesen = feat.attribute(idx_bil)
                            
                        yol_id = None
                        idx_yol = layer.fields().indexOf("yol_id")
                        if idx_yol >= 0:
                            yol_id = feat.attribute(idx_yol)
                            
                        for ep in endpoints:
                            cut_endpoints.append((ep, bilesen, yol_id))

                    # Geometrileri parÃ§a parÃ§a ekle/gÃ¼ncelle
                    layer.changeGeometry(feat.id(), parts[0])
                    for part in parts[1:]:
                        if part.isEmpty() or part.type() != QgsWkbTypes.LineGeometry:
                            continue
                        new_feat = QgsFeature(layer.fields())
                        new_feat.setGeometry(part)
                        for i in range(layer.fields().count()):
                            new_feat.setAttribute(i, feat.attribute(i))
                        layer.addFeature(new_feat)
                        
                    trimmed_count += 1

            if not layer_was_editing:
                layer.commitChanges()
            layer.triggerRepaint()

        # Endpoint'leri bileÅŸenlerine gÃ¶re ayÄ±r (ep, yol_id) formatÄ±nda
        kaldirim_pts = []
        refuj_pts = []
        for point, bilesen, yol_id in cut_endpoints:
            if not bilesen or bilesen == "kaldirim":
                kaldirim_pts.append((point, yol_id))
            elif bilesen == "refuj":
                refuj_pts.append((point, yol_id))

        # â”€â”€ 2. DÄ±ÅŸ kaldÄ±rÄ±m kÄ±rma Ã§izgileri (chamfer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        chamfer_lines = self._create_chamfer_lines(
            center, kaldirim_pts, chamfer_dist
        )

        kavsak_line_layer.startEditing()
        for cline in chamfer_lines:
            feat = QgsFeature(kavsak_line_layer.fields())
            feat.setGeometry(cline)
            feat.setAttribute("yol_id", kavsak_id)
            feat.setAttribute("yol_tipi", "kavsak")
            feat.setAttribute("bilesen", "dis_kirma")
            kavsak_line_layer.addFeature(feat)

        # â”€â”€ 3. Ä°Ã§ kaldÄ±rÄ±m baÄŸlantÄ± yaylarÄ± (fillet) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # EÄŸre dÄ±ÅŸ kÄ±rma yapÄ±lacaksa iÃ§ baÄŸlantÄ±ya gerek yok (kullanÄ±cÄ± talebi)
        fillet_arcs = []
        if chamfer_dist <= 0:
            fillet_arcs = self._create_fillet_arcs(
                center, kaldirim_pts, fillet_radius
            )
            for farc in fillet_arcs:
                feat = QgsFeature(kavsak_line_layer.fields())
                feat.setGeometry(farc)
                feat.setAttribute("yol_id", kavsak_id)
                feat.setAttribute("yol_tipi", "kavsak")
                feat.setAttribute("bilesen", "ic_baglanti")
                kavsak_line_layer.addFeature(feat)

        # â”€â”€ 3.5 RefÃ¼j Kapatma YaylarÄ± (Yuvarlak kavÅŸaklar iÃ§in) â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if ada_tipi != "yok" and refuj_pts:
            refuj_caps = self._create_refuj_caps(center, refuj_pts)
            for cap_line in refuj_caps:
                feat = QgsFeature(kavsak_line_layer.fields())
                feat.setGeometry(cap_line)
                feat.setAttribute("yol_id", kavsak_id)
                feat.setAttribute("yol_tipi", "kavsak")
                feat.setAttribute("bilesen", "refuj_baglanti")
                feat.setAttribute("gorunur", 1)  # Kapatma iÃ§in gÃ¶rÃ¼nÃ¼r
                kavsak_line_layer.addFeature(feat)

        kavsak_line_layer.commitChanges()
        kavsak_line_layer.triggerRepaint()

        # â”€â”€ 4. KavÅŸak adasÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if ada_tipi != "yok":
            kavsak_ada_layer.startEditing()

            if ada_tipi == "yuvarlak":
                ada_geom = center_geom.buffer(ada_radius, 48)
            elif ada_tipi == "su_damlasi":
                ada_geom = self._create_teardrop(
                    center, ada_radius, p["teardrop_uzunluk"]
                )
            else:
                ada_geom = None

            if ada_geom and not ada_geom.isEmpty():
                feat = QgsFeature(kavsak_ada_layer.fields())
                feat.setGeometry(ada_geom)
                feat.setAttribute("kavsak_id", kavsak_id)
                feat.setAttribute("ada_tipi", ada_tipi)
                feat.setAttribute("ada_radius", ada_radius)
                kavsak_ada_layer.addFeature(feat)

            kavsak_ada_layer.commitChanges()
            kavsak_ada_layer.triggerRepaint()

        # â”€â”€ SonuÃ§ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        msg = (
            f"âœ… KavÅŸak â€” {trimmed_count} Ã§izgi trimlendi | "
            f"{len(chamfer_lines)} kÄ±rma + {len(fillet_arcs)} baÄŸlantÄ±"
        )
        if ada_tipi != "yok":
            msg += f" | Ada: {ada_tipi}"
        self.sketcher_message.emit(msg)

        self.iface.messageBar().pushSuccess("planX CAD", msg)

        # Temizle
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.sketcher_finished.emit()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Geometri Ä°ÅŸlemleri
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _find_cut_endpoints(self, original_geom, trimmed_geom, buffer_geom):
        """Trimlenen Ã§izginin kesilme noktalarÄ±nÄ± bul.

        Returns:
            list[QgsPointXY] â€” kavÅŸak alanÄ± sÄ±nÄ±rÄ±ndaki kesilme noktalarÄ±
        """
        endpoints = []

        # TrimlenmiÅŸ geometrinin uÃ§ noktalarÄ±nÄ± al
        parts = [trimmed_geom]
        if trimmed_geom.isMultipart():
            parts = trimmed_geom.asGeometryCollection()

        for part in parts:
            if part.isEmpty():
                continue

            if part.type() == QgsWkbTypes.LineGeometry:
                if part.isMultipart():
                    for line in part.asMultiPolyline():
                        if line:
                            endpoints.append(QgsPointXY(line[0]))
                            endpoints.append(QgsPointXY(line[-1]))
                else:
                    line = part.asPolyline()
                    if line:
                        endpoints.append(QgsPointXY(line[0]))
                        endpoints.append(QgsPointXY(line[-1]))

        # Sadece kavÅŸak sÄ±nÄ±rÄ±na yakÄ±n olanlarÄ± filtrele
        buffer_boundary = buffer_geom.convertToType(QgsWkbTypes.LineGeometry)
        filtered = []
        for pt in endpoints:
            pt_geom = QgsGeometry.fromPointXY(pt)
            if buffer_boundary:
                dist = pt_geom.distance(buffer_boundary)
            else:
                dist = pt_geom.distance(buffer_geom)
            if dist < 1.0:  # 1m tolerans
                filtered.append(pt)

        return filtered

    def _create_chamfer_lines(self, center, endpoints, chamfer_dist):
        """DÄ±ÅŸ kaldÄ±rÄ±m kÄ±rma Ã§izgileri oluÅŸtur.

        KarÅŸÄ±lÄ±klÄ± uÃ§ noktalarÄ± dÃ¼z Ã§izgi ile baÄŸla (chamfer).
        Merkezden daha uzak olan nokta Ã§iftleri dÄ±ÅŸ kaldÄ±rÄ±ma ait.
        """
        if len(endpoints) < 2:
            return []

        chamfer_lines = []
        
        groups_dict = {}
        for pt, y_id in endpoints:
            angle = math.atan2(pt.y() - center.y(), pt.x() - center.x())
            dist = center.distance(pt)
            item = (angle, dist, pt, y_id)
            # None yol_id'leri ayrÄ± gruplamak iÃ§in angle bazlÄ± geÃ§ici ID
            safe_id = y_id if y_id is not None else f"unknown_{round(angle, 1)}"
            if safe_id not in groups_dict:
                groups_dict[safe_id] = []
            groups_dict[safe_id].append(item)

        groups = self._order_groups_circularly(groups_dict)

        # Her kolun ucundaki en dÄ±ÅŸtaki noktalarÄ± bul
        outer_points = []
        for group in groups:
            if len(group) >= 2:
                # En uzak noktalarÄ± al (dÄ±ÅŸ kaldÄ±rÄ±m)
                group.sort(key=lambda x: x[1], reverse=True)
                outer_points.append(group[0][2])
                if len(group) >= 2:
                    outer_points.append(group[1][2])

        # KomÅŸu kol dÄ±ÅŸlarÄ± arasÄ±na chamfer Ã§izgileri
        if len(groups) >= 2:
            for i in range(len(groups)):
                g1 = groups[i]
                g2 = groups[(i + 1) % len(groups)]

                # Her grup Ã§iftinden en yakÄ±n dÄ±ÅŸ noktalarÄ± bul
                best_pair = self._find_closest_pair_between_groups(g1, g2)
                if best_pair:
                    p1, p2 = best_pair
                    line_geom = QgsGeometry.fromPolylineXY([p1, p2])
                    chamfer_lines.append(line_geom)

        return chamfer_lines

    def _create_fillet_arcs(self, center, endpoints, fillet_radius):
        """Ä°Ã§ kaldÄ±rÄ±m baÄŸlantÄ± yaylarÄ± oluÅŸtur.

        Merkezden daha yakÄ±n olan nokta Ã§iftleri iÃ§ kaldÄ±rÄ±ma ait.
        BunlarÄ± ark ile baÄŸla.
        """
        if len(endpoints) < 2 or fillet_radius <= 0:
            return []

        fillet_arcs = []
        
        groups_dict = {}
        for pt, y_id in endpoints:
            angle = math.atan2(pt.y() - center.y(), pt.x() - center.x())
            dist = center.distance(pt)
            item = (angle, dist, pt, y_id)
            safe_id = y_id if y_id is not None else f"unknown_{round(angle, 1)}"
            if safe_id not in groups_dict:
                groups_dict[safe_id] = []
            groups_dict[safe_id].append(item)

        groups = self._order_groups_circularly(groups_dict)

        # KomÅŸu kol iÃ§leri arasÄ±na fillet yay
        if len(groups) >= 2:
            for i in range(len(groups)):
                g1 = groups[i]
                g2 = groups[(i + 1) % len(groups)]

                # Her grup Ã§iftinden en yakÄ±n iÃ§ noktalarÄ± bul
                pair = self._find_closest_pair_between_groups(
                    g1, g2, prefer_inner=True
                )
                if pair:
                    p1, p2 = pair
                    arc_pts = self._calc_fillet_arc(center, p1, p2, fillet_radius)
                    if arc_pts and len(arc_pts) >= 2:
                        arc_geom = QgsGeometry.fromPolylineXY(arc_pts)
                        fillet_arcs.append(arc_geom)

        return fillet_arcs

    def _create_refuj_caps(self, center, endpoints):
        """KavÅŸaÄŸa giren refÃ¼j Ã§izgilerini kapatÄ±r."""
        caps = []
        if len(endpoints) < 2:
            return caps

        groups_dict = {}
        for pt, y_id in endpoints:
            angle = math.atan2(pt.y() - center.y(), pt.x() - center.x())
            dist = center.distance(pt)
            item = (angle, dist, pt, y_id)
            safe_id = y_id if y_id is not None else f"unknown_{round(angle, 1)}"
            if safe_id not in groups_dict:
                groups_dict[safe_id] = []
            groups_dict[safe_id].append(item)

        groups = self._order_groups_circularly(groups_dict)

        for group in groups:
            if len(group) >= 2:
                # Bir koldan gelen en az 2 refÃ¼j ucu varsa onlarÄ± dÃ¼z Ã§izgiyle birleÅŸtir.
                p1 = group[0][2]
                p2 = group[-1][2]
                caps.append(QgsGeometry.fromPolylineXY([p1, p2]))

        return caps

    def _order_groups_circularly(self, groups_dict):
        """AynÄ± yol kollarÄ±na ait olan noktalarÄ± aÃ§Ä±sal sÄ±raya dizer."""
        groups_list = []
        for y_id, pts in groups_dict.items():
            if not pts: continue
            sum_x = sum(math.cos(p[0]) for p in pts)
            sum_y = sum(math.sin(p[0]) for p in pts)
            avg_a = math.atan2(sum_y, sum_x)
            # Sort individual points inside group by distance from center implicitly, or just by inner/outer
            # We sort them by distance so inner/outer logic works
            pts.sort(key=lambda x: x[1]) 
            groups_list.append((avg_a, pts))
            
        groups_list.sort(key=lambda x: x[0])
        return [g[1] for g in groups_list]

    def _find_closest_pair_between_groups(self, g1, g2, prefer_inner=False):
        """Ä°ki grup arasÄ±ndaki en yakÄ±n (veya en uzak) nokta Ã§iftini bul."""
        best_dist = float('inf')
        best_pair = None

        for _, d1, p1, _ in g1:
            for _, d2, p2, _ in g2:
                d = p1.distance(p2)
                if d < best_dist:
                    best_dist = d
                    best_pair = (p1, p2)

        return best_pair

    def _calc_fillet_arc(self, center, p1, p2, radius, segments=16):
        """Ä°ki nokta arasÄ±nda doÄŸru teÄŸet arkÄ± (calc_tangent_fillet_arc ile)."""
        # P1 ve P2 kavÅŸak sÄ±nÄ±rÄ±nda.
        # Bu noktalarÄ±n merkezden geliÅŸ aÃ§Ä±sÄ±nÄ± bulalÄ±m ve calc_tangent_fillet_arc kullanalÄ±m.
        dir1 = math.atan2(p1.y() - center.y(), p1.x() - center.x())
        dir2 = math.atan2(p2.y() - center.y(), p2.x() - center.x())
        
        # calc_tangent_fillet_arc aslÄ±nda merkezden uzaklaÅŸan (p1, p2) iÃ§in.
        # Bizde p1 ve p2 kavÅŸak noktasÄ±nda bitiyor. Ama sorun deÄŸil, fillet arc'yi Ã§izip dÃ¶ndÃ¼rÃ¼r.
        # Sanal bir kesiÅŸim noktasÄ± gerekiyor fillet iÃ§in!
        # DÄ±ÅŸ Ã§izgilerin uzantÄ±larÄ±nÄ±n kesiÅŸimi neresi?
        # Bu biraz karmaÅŸÄ±k olabilir, calc_tangent_fillet_arc direkt olarak intersection point istiyor.
        # KesiÅŸim noktasÄ±nÄ± bulalÄ±m.
        
        # P1'den dir1 yÃ¶nÃ¼nde ve P2'den dir2 yÃ¶nÃ¼nde giden Ã§izgilerin kesiÅŸimi (merkeze doÄŸru)
        # AslÄ±nda en basit yÃ¶ntem, _create_fillet_arcs iÃ§inde calc_tangent_fillet_arc kullanmaktÄ±r.
        
        # BasitleÅŸtirilmiÅŸ: TeÄŸet arc Ã§izebilmek iÃ§in center'Ä± kullanabiliriz, ama merkezde deÄŸil.
        # calc_tangent_fillet_arc(int_pt, angle1, angle2, radius)
        
        # YollarÄ± merkeze doÄŸrultuyoruz
        arc_pts, _ = calc_tangent_fillet_arc(center, dir1, dir2, radius, segments)
        return arc_pts

    def _create_teardrop(self, center, radius, length):
        """Su damlasÄ± ÅŸeklinde ada oluÅŸtur."""
        pts = []
        # DamlacÄ±k: yarÄ±m daire + sivri uÃ§
        segments = 32

        # Ãœst yarÄ±m daire
        for i in range(segments + 1):
            angle = math.pi / 2 + math.pi * i / segments
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            pts.append(QgsPointXY(x, y))

        # Sivri uÃ§ (aÅŸaÄŸÄ±da)
        pts.append(QgsPointXY(center.x(), center.y() - length))

        # Kapatma
        pts.append(pts[0])

        return QgsGeometry.fromPolygonXY([pts])

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Katman YÃ¶netimi
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•


    def _get_kavsak_ada_layer(self):
        """kavsak_ada (Polygon) katmanÄ±nÄ± bul veya oluÅŸtur."""
        return get_or_create_layer(
            "kavsak_ada",
            geom_type="Polygon",
            fields=[
                ("kavsak_id", "int"),
                ("ada_tipi", "string"),     # yuvarlak / su_damlasi
                ("ada_radius", "double"),
            ]
        )

    def _make_circle(self, center, radius, segments=48):
        pts = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            pts.append(QgsPointXY(x, y))
        return pts

    def _next_id(self, layer, field_name):
        max_id = 0
        idx = layer.fields().indexOf(field_name)
        if idx < 0:
            return 1
        for feat in layer.getFeatures():
            val = feat.attribute(idx)
            if val and int(val) > max_id:
                max_id = int(val)
        return max_id + 1
