# -*- coding: utf-8 -*-
"""
planX CAD â€” Ada KÄ±rma (KÃ¶ÅŸe Chamfer/Fillet) AracÄ±

Ä°mar adasÄ± kÃ¶ÅŸelerini kÄ±rar:
 - Ä°ki dÄ±ÅŸ kaldÄ±rÄ±m Ã§izgisinin kesiÅŸtiÄŸi kÃ¶ÅŸeye tÄ±kla
 - Ã‡izgiler trimlensin, arasÄ±na dÃ¼z/eÄŸri baÄŸlantÄ± oluÅŸsun
 - Arta kalan kÄ±sa parÃ§alar temizlensin
"""

import math
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsFeature,
    QgsProject, QgsVectorLayer, QgsRectangle
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband, cleanup_sketcher_rubberband,
    create_sketcher_rubberband, COLOR_ACCENT
)
from ..core.sketcher_utils import calc_tangent_fillet_arc
from .ada_kirma_dialog import AdaKirmaDialog


class AdaKirmaSketcher(QgsMapTool):
    """Ada kÃ¶ÅŸe kÄ±rma aracÄ±.

    1. Dialog aÃ§Ä±lÄ±r â†’ kÄ±rma tipi (dÃ¼z/eÄŸri, mesafe) girilir
    2. KÃ¶ÅŸeye tÄ±kla â†’ iki Ã§izgi bulunur â†’ kÄ±rma uygulanÄ±r
    3. SaÄŸ tÄ±k / Esc ile biter
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
        self._corner_count = 0

    def activate(self):
        super().activate()
        self._step = 0
        self._corner_count = 0

        # Dialog
        dlg = AdaKirmaDialog(self.iface.mainWindow())
        if dlg.exec() != AdaKirmaDialog.Accepted:
            self.sketcher_message.emit("ðŸ”¶ Ada KÄ±rma â€” Ä°ptal edildi")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PointGeometry
        )
        self._step = 1

        tip_text = "EÄŸri" if self.params["tip"] == "egri" else "DÃ¼z"
        self.sketcher_message.emit(
            f"ðŸ”¶ Ada KÄ±rma ({tip_text}, {self.params['mesafe']}m) â€” "
            f"KÄ±rÄ±lacak kÃ¶ÅŸeye tÄ±klayÄ±n | SaÄŸ tÄ±k: Bitir"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        super().deactivate()

    def canvasPressEvent(self, event):
        if self._step != 1:
            return

        point = self.toMapCoordinates(event.pos())

        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        if event.button() == Qt.MouseButton.LeftButton:
            self._chamfer_corner(point)

        elif event.button() == Qt.MouseButton.RightButton:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"âœ… Ada KÄ±rma â€” {self._corner_count} kÃ¶ÅŸe kÄ±rÄ±ldÄ±"
                )
            self.sketcher_finished.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"âœ… Ada KÄ±rma â€” {self._corner_count} kÃ¶ÅŸe kÄ±rÄ±ldÄ±"
                )
            else:
                self.sketcher_message.emit("ðŸ”¶ Ada KÄ±rma â€” Ä°ptal edildi")
            self.sketcher_finished.emit()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Ana KÃ¶ÅŸe KÄ±rma Ä°ÅŸlemi
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _chamfer_corner(self, click_point):
        """TÄ±klanan noktadaki kÃ¶ÅŸeyi kÄ±r."""
        p = self.params
        tolerans = p["tolerans"]
        mesafe = p["mesafe"]
        tip = p["tip"]
        artik_esik = p["artik_esik"]

        # 1. TÄ±klanan noktanÄ±n etrafÄ±ndaki Ã§izgileri bul
        candidates = self._find_lines_near_point(click_point, tolerans * 3)

        if len(candidates) < 2:
            self.sketcher_message.emit(
                f"âš ï¸ Ada KÄ±rma â€” En az 2 Ã§izgi gerekli "
                f"(bulunan: {len(candidates)})"
            )
            return

        # 2. En yakÄ±n iki Ã§izgiyi ve kesiÅŸim noktasÄ±nÄ± bul
        pair = self._find_intersecting_pair(candidates, click_point, tolerans)

        if pair is None:
            self.sketcher_message.emit(
                "âš ï¸ Ada KÄ±rma â€” KesiÅŸen Ã§izgi Ã§ifti bulunamadÄ±"
            )
            return

        layer1, feat1, layer2, feat2, int_point = pair

        # 3. KÄ±rma mesafesi veya yay teÄŸeti hesapla
        geom1 = feat1.geometry()
        geom2 = feat2.geometry()

        # DoÄŸrultularÄ± bulmak iÃ§in Ã§ok kÃ¼Ã§Ã¼k bir mesafe kullanÄ±yoruz
        tmp_trim1 = self._trim_line_from_point(geom1, int_point, 0.1)
        tmp_trim2 = self._trim_line_from_point(geom2, int_point, 0.1)
        
        if tmp_trim1 is None or tmp_trim2 is None:
            self.sketcher_message.emit("âš ï¸ Ada KÄ±rma â€” Ã‡izgi doÄŸrultusu hesaplanamadÄ±")
            return
            
        _, pt1_near = tmp_trim1
        _, pt2_near = tmp_trim2
        
        dir1 = math.atan2(pt1_near.y() - int_point.y(), pt1_near.x() - int_point.x())
        dir2 = math.atan2(pt2_near.y() - int_point.y(), pt2_near.x() - int_point.x())

        if tip == "duz":
            trim_dist = mesafe
            trim1 = self._trim_line_from_point(geom1, int_point, trim_dist)
            trim2 = self._trim_line_from_point(geom2, int_point, trim_dist)
            
            if trim1 is None or trim2 is None:
                self.sketcher_message.emit("âš ï¸ Ada KÄ±rma â€” Ã‡izgi kesilemedi")
                return

            trimmed_geom1, cut_pt1 = trim1
            trimmed_geom2, cut_pt2 = trim2
            connection = QgsGeometry.fromPolylineXY([cut_pt1, cut_pt2])
        else:
            # EÄŸri (Fillet) -> mesafe = Radius
            from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point
            
            fillet_result = create_fillet_and_trims(geom1, geom2, mesafe)
            if not fillet_result:
                self.sketcher_message.emit("âš ï¸ Ada KÄ±rma â€” Yay hesaplanamadÄ±")
                return
                
            trimmed_geom1 = trim_line_to_point(geom1, fillet_result['tp1'])
            trimmed_geom2 = trim_line_to_point(geom2, fillet_result['tp2'])
            connection = fillet_result['arc']

        # 5. Geometrileri gÃ¼ncelle
        self._safe_edit(layer1, feat1, trimmed_geom1)
        self._safe_edit(layer2, feat2, trimmed_geom2)

        # 6. BaÄŸlantÄ±yÄ± kaynak katmana ekle (kullanÄ±cÄ±nÄ±n aÃ§Ä±k edit session'Ä±nÄ± koru)
        target_layer = layer1
        if connection and not connection.isEmpty():
            was_editing = target_layer.isEditable()
            if not was_editing:
                target_layer.startEditing()
            new_feat = QgsFeature(target_layer.fields())
            new_feat.setGeometry(connection)
            target_layer.addFeature(new_feat)
            if not was_editing:
                target_layer.commitChanges()
            target_layer.triggerRepaint()

        # 7. ArtÄ±k kÄ±sa parÃ§alarÄ± temizle
        if artik_esik > 0:
            cleaned = self._clean_remnants(
                click_point, tolerans * 5, artik_esik
            )
        else:
            cleaned = 0

        # SonuÃ§
        self._corner_count += 1
        tip_text = "eÄŸri" if tip == "egri" else "dÃ¼z"
        msg = (
            f"ðŸ”¶ KÃ¶ÅŸe #{self._corner_count} â€” "
            f"{tip_text} kÄ±rma uygulandÄ± ({mesafe}m)"
        )
        if cleaned > 0:
            msg += f" | {cleaned} artÄ±k temizlendi"
        msg += " | Devam etmek iÃ§in tÄ±klayÄ±n"
        self.sketcher_message.emit(msg)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Ã‡izgi Arama
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _find_lines_near_point(self, point, search_radius):
        """NoktanÄ±n etrafÄ±ndaki Ã§izgileri bul.

        Returns:
            list[(QgsVectorLayer, QgsFeature, distance)]
        """
        results = []
        search_rect = QgsRectangle(
            point.x() - search_radius, point.y() - search_radius,
            point.x() + search_radius, point.y() + search_radius
        )
        pt_geom = QgsGeometry.fromPointXY(point)

        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                continue

            for feat in layer.getFeatures(search_rect):
                geom = feat.geometry()
                if geom.isEmpty():
                    continue
                dist = geom.distance(pt_geom)
                if dist <= search_radius:
                    results.append((layer, feat, dist))

        # Mesafeye gÃ¶re sÄ±rala
        results.sort(key=lambda x: x[2])
        return results

    def _find_intersecting_pair(self, candidates, click_point, tolerans):
        """En yakÄ±n kesiÅŸen Ã§izgi Ã§iftini bul.

        Returns:
            (layer1, feat1, layer2, feat2, intersection_point) veya None
        """
        best = None
        best_dist = float('inf')

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                l1, f1, _ = candidates[i]
                l2, f2, _ = candidates[j]

                g1 = f1.geometry()
                g2 = f2.geometry()

                # KesiÅŸim kontrolÃ¼
                if not g1.intersects(g2):
                    # YakÄ±nlarsa uzatarak kesiÅŸim ara
                    int_pt = self._find_near_intersection(g1, g2, tolerans)
                    if int_pt is None:
                        continue
                else:
                    intersection = g1.intersection(g2)
                    if intersection is None or intersection.isEmpty():
                        continue
                    int_pt = self._extract_nearest_point(
                        intersection, click_point
                    )

                if int_pt:
                    dist = click_point.distance(int_pt)
                    if dist < best_dist:
                        best_dist = dist
                        best = (l1, f1, l2, f2, int_pt)

        return best

    def _find_near_intersection(self, geom1, geom2, tolerans):
        """Ã‡ok yakÄ±n ama kesiÅŸmeyen Ã§izgilerin sanal kesiÅŸimini bul."""
        closest = geom1.nearestPoint(geom2)
        if closest is None or closest.isEmpty():
            return None

        dist = geom1.distance(geom2)
        if dist <= tolerans:
            return QgsPointXY(closest.asPoint())
        return None

    def _extract_nearest_point(self, geom, reference_point):
        """Geometriden referans noktaya en yakÄ±n noktayÄ± Ã§Ä±kar."""
        if geom.type() == QgsWkbTypes.PointGeometry:
            if geom.isMultipart():
                pts = geom.asMultiPoint()
                if not pts:
                    return None
                best = min(pts, key=lambda p: reference_point.distance(QgsPointXY(p)))
                return QgsPointXY(best)
            else:
                return QgsPointXY(geom.asPoint())
        else:
            c = geom.centroid()
            if c and not c.isEmpty():
                return QgsPointXY(c.asPoint())
        return None

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Geometri Ä°ÅŸlemleri
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _trim_line_from_point(self, geom, int_point, distance):
        """Ã‡izgiyi kesiÅŸim noktasÄ±ndan belirli mesafe geriye kes.

        Returns:
            (trimmed_geom, cut_point) veya None
        """
        # Ã‡izgi noktalarÄ±nÄ± al
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            pts = []
            for line in lines:
                pts.extend([QgsPointXY(p) for p in line])
        else:
            pts = [QgsPointXY(p) for p in geom.asPolyline()]

        if len(pts) < 2:
            return None

        # KesiÅŸim noktasÄ±na en yakÄ±n ucu bul
        d_start = int_point.distance(pts[0])
        d_end = int_point.distance(pts[-1])

        if d_start <= d_end:
            # BaÅŸlangÄ±Ã§ kesiÅŸime yakÄ±n â†’ baÅŸtan kes
            cut_pt = self._point_along_line(pts, distance, from_start=True)
            if cut_pt is None:
                return None
            # BaÅŸlangÄ±Ã§tan cut_pt'ye kadar olan kÄ±smÄ± kaldÄ±r
            new_pts = self._trim_from_start(pts, cut_pt)
        else:
            # Son kesiÅŸime yakÄ±n â†’ sondan kes
            cut_pt = self._point_along_line(pts, distance, from_start=False)
            if cut_pt is None:
                return None
            new_pts = self._trim_from_end(pts, cut_pt)

        if new_pts and len(new_pts) >= 2:
            return (QgsGeometry.fromPolylineXY(new_pts), cut_pt)
        return None

    def _point_along_line(self, pts, distance, from_start=True):
        """Ã‡izgi Ã¼zerinde belirli mesafedeki noktayÄ± hesapla."""
        if from_start:
            remaining = distance
            for i in range(len(pts) - 1):
                seg_len = pts[i].distance(pts[i + 1])
                if remaining <= seg_len:
                    ratio = remaining / seg_len if seg_len > 0 else 0
                    x = pts[i].x() + ratio * (pts[i + 1].x() - pts[i].x())
                    y = pts[i].y() + ratio * (pts[i + 1].y() - pts[i].y())
                    return QgsPointXY(x, y)
                remaining -= seg_len
        else:
            remaining = distance
            for i in range(len(pts) - 1, 0, -1):
                seg_len = pts[i].distance(pts[i - 1])
                if remaining <= seg_len:
                    ratio = remaining / seg_len if seg_len > 0 else 0
                    x = pts[i].x() + ratio * (pts[i - 1].x() - pts[i].x())
                    y = pts[i].y() + ratio * (pts[i - 1].y() - pts[i].y())
                    return QgsPointXY(x, y)
                remaining -= seg_len
        return None

    def _trim_from_start(self, pts, cut_pt):
        """BaÅŸlangÄ±Ã§tan cut_pt'ye kadar olan kÄ±smÄ± kaldÄ±r."""
        # cut_pt'den sonraki noktalarÄ± al
        result = [cut_pt]
        total_to_cut = pts[0].distance(cut_pt)

        accumulated = 0
        for i in range(len(pts) - 1):
            seg_len = pts[i].distance(pts[i + 1])
            accumulated += seg_len
            if accumulated >= total_to_cut:
                result.append(pts[i + 1])

        if len(result) < 2:
            result = [cut_pt, pts[-1]]
        return result

    def _trim_from_end(self, pts, cut_pt):
        """Sondan cut_pt'ye kadar olan kÄ±smÄ± kaldÄ±r."""
        result = []
        total_to_cut = pts[-1].distance(cut_pt)

        accumulated = 0
        for i in range(len(pts) - 1, 0, -1):
            seg_len = pts[i].distance(pts[i - 1])
            accumulated += seg_len
            if accumulated >= total_to_cut:
                result.insert(0, pts[i - 1])

        result.append(cut_pt)

        if len(result) < 2:
            result = [pts[0], cut_pt]
        return result


    def _safe_edit(self, layer, feature, new_geom):
        """KatmanÄ± dÃ¼zenleyerek geometriyi gÃ¼ncelle.

        KullanÄ±cÄ±nÄ±n baÅŸlattÄ±ÄŸÄ± edit session'Ä± varsa commit'i ona bÄ±rakÄ±rÄ±z;
        biz baÅŸlattÄ±ysak burada bitiririz.
        """
        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        layer.changeGeometry(feature.id(), new_geom)
        if not was_editing:
            layer.commitChanges()
        layer.triggerRepaint()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # ArtÄ±k Temizleme
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _clean_remnants(self, center_point, search_radius, min_length):
        """KÄ±sa artÄ±k Ã§izgi parÃ§alarÄ±nÄ± temizle.

        Returns:
            int â€” silinen parÃ§a sayÄ±sÄ±
        """
        cleaned = 0
        search_rect = QgsRectangle(
            center_point.x() - search_radius,
            center_point.y() - search_radius,
            center_point.x() + search_radius,
            center_point.y() + search_radius
        )

        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() != QgsWkbTypes.LineGeometry:
                continue

            to_delete = []
            for feat in layer.getFeatures(search_rect):
                geom = feat.geometry()
                if geom.isEmpty():
                    continue

                length = geom.length()
                if length < min_length:
                    # Merkeze yakÄ±n mÄ± kontrol et
                    pt_geom = QgsGeometry.fromPointXY(center_point)
                    if geom.distance(pt_geom) <= search_radius:
                        to_delete.append(feat.id())

            if to_delete:
                was_editing = layer.isEditable()
                if not was_editing:
                    layer.startEditing()
                for fid in to_delete:
                    layer.deleteFeature(fid)
                    cleaned += 1
                if not was_editing:
                    layer.commitChanges()
                layer.triggerRepaint()

        return cleaned
