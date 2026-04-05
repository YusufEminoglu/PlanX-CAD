# -*- coding: utf-8 -*-
"""
planX CAD — Ada Kırma (Köşe Chamfer/Fillet) Aracı

İmar adası köşelerini kırar:
 - İki dış kaldırım çizgisinin kesiştiği köşeye tıkla
 - Çizgiler trimlensin, arasına düz/eğri bağlantı oluşsun
 - Arta kalan kısa parçalar temizlensin
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
    """Ada köşe kırma aracı.

    1. Dialog açılır → kırma tipi (düz/eğri, mesafe) girilir
    2. Köşeye tıkla → iki çizgi bulunur → kırma uygulanır
    3. Sağ tık / Esc ile biter
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
        if dlg.exec_() != AdaKirmaDialog.Accepted:
            self.sketcher_message.emit("🔶 Ada Kırma — İptal edildi")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PointGeometry
        )
        self._step = 1

        tip_text = "Eğri" if self.params["tip"] == "egri" else "Düz"
        self.sketcher_message.emit(
            f"🔶 Ada Kırma ({tip_text}, {self.params['mesafe']}m) — "
            f"Kırılacak köşeye tıklayın | Sağ tık: Bitir"
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

        if event.button() == Qt.LeftButton:
            self._chamfer_corner(point)

        elif event.button() == Qt.RightButton:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"✅ Ada Kırma — {self._corner_count} köşe kırıldı"
                )
            self.sketcher_finished.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"✅ Ada Kırma — {self._corner_count} köşe kırıldı"
                )
            else:
                self.sketcher_message.emit("🔶 Ada Kırma — İptal edildi")
            self.sketcher_finished.emit()

    # ════════════════════════════════════════════════════════════════════════
    # Ana Köşe Kırma İşlemi
    # ════════════════════════════════════════════════════════════════════════

    def _chamfer_corner(self, click_point):
        """Tıklanan noktadaki köşeyi kır."""
        p = self.params
        tolerans = p["tolerans"]
        mesafe = p["mesafe"]
        tip = p["tip"]
        artik_esik = p["artik_esik"]

        # 1. Tıklanan noktanın etrafındaki çizgileri bul
        candidates = self._find_lines_near_point(click_point, tolerans * 3)

        if len(candidates) < 2:
            self.sketcher_message.emit(
                f"⚠️ Ada Kırma — En az 2 çizgi gerekli "
                f"(bulunan: {len(candidates)})"
            )
            return

        # 2. En yakın iki çizgiyi ve kesişim noktasını bul
        pair = self._find_intersecting_pair(candidates, click_point, tolerans)

        if pair is None:
            self.sketcher_message.emit(
                "⚠️ Ada Kırma — Kesişen çizgi çifti bulunamadı"
            )
            return

        layer1, feat1, layer2, feat2, int_point = pair

        # 3. Kırma mesafesi veya yay teğeti hesapla
        geom1 = feat1.geometry()
        geom2 = feat2.geometry()

        # Doğrultuları bulmak için çok küçük bir mesafe kullanıyoruz
        tmp_trim1 = self._trim_line_from_point(geom1, int_point, 0.1)
        tmp_trim2 = self._trim_line_from_point(geom2, int_point, 0.1)
        
        if tmp_trim1 is None or tmp_trim2 is None:
            self.sketcher_message.emit("⚠️ Ada Kırma — Çizgi doğrultusu hesaplanamadı")
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
                self.sketcher_message.emit("⚠️ Ada Kırma — Çizgi kesilemedi")
                return

            trimmed_geom1, cut_pt1 = trim1
            trimmed_geom2, cut_pt2 = trim2
            connection = QgsGeometry.fromPolylineXY([cut_pt1, cut_pt2])
        else:
            # Eğri (Fillet) -> mesafe = Radius
            from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point
            
            fillet_result = create_fillet_and_trims(geom1, geom2, mesafe)
            if not fillet_result:
                self.sketcher_message.emit("⚠️ Ada Kırma — Yay hesaplanamadı")
                return
                
            trimmed_geom1 = trim_line_to_point(geom1, fillet_result['tp1'])
            trimmed_geom2 = trim_line_to_point(geom2, fillet_result['tp2'])
            connection = fillet_result['arc']

        # 5. Geometrileri güncelle
        self._safe_edit(layer1, feat1, trimmed_geom1)
        self._safe_edit(layer2, feat2, trimmed_geom2)

        # 6. Bağlantıyı kaynak katmana ekle
        target_layer = layer1
        if connection and not connection.isEmpty():
            if not target_layer.isEditable():
                target_layer.startEditing()
            new_feat = QgsFeature(target_layer.fields())
            new_feat.setGeometry(connection)
            target_layer.addFeature(new_feat)
            target_layer.commitChanges()
            target_layer.triggerRepaint()

        # 7. Artık kısa parçaları temizle
        if artik_esik > 0:
            cleaned = self._clean_remnants(
                click_point, tolerans * 5, artik_esik
            )
        else:
            cleaned = 0

        # Sonuç
        self._corner_count += 1
        tip_text = "eğri" if tip == "egri" else "düz"
        msg = (
            f"🔶 Köşe #{self._corner_count} — "
            f"{tip_text} kırma uygulandı ({mesafe}m)"
        )
        if cleaned > 0:
            msg += f" | {cleaned} artık temizlendi"
        msg += " | Devam etmek için tıklayın"
        self.sketcher_message.emit(msg)

    # ════════════════════════════════════════════════════════════════════════
    # Çizgi Arama
    # ════════════════════════════════════════════════════════════════════════

    def _find_lines_near_point(self, point, search_radius):
        """Noktanın etrafındaki çizgileri bul.

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

        # Mesafeye göre sırala
        results.sort(key=lambda x: x[2])
        return results

    def _find_intersecting_pair(self, candidates, click_point, tolerans):
        """En yakın kesişen çizgi çiftini bul.

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

                # Kesişim kontrolü
                if not g1.intersects(g2):
                    # Yakınlarsa uzatarak kesişim ara
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
        """Çok yakın ama kesişmeyen çizgilerin sanal kesişimini bul."""
        closest = geom1.nearestPoint(geom2)
        if closest is None or closest.isEmpty():
            return None

        dist = geom1.distance(geom2)
        if dist <= tolerans:
            return QgsPointXY(closest.asPoint())
        return None

    def _extract_nearest_point(self, geom, reference_point):
        """Geometriden referans noktaya en yakın noktayı çıkar."""
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

    # ════════════════════════════════════════════════════════════════════════
    # Geometri İşlemleri
    # ════════════════════════════════════════════════════════════════════════

    def _trim_line_from_point(self, geom, int_point, distance):
        """Çizgiyi kesişim noktasından belirli mesafe geriye kes.

        Returns:
            (trimmed_geom, cut_point) veya None
        """
        # Çizgi noktalarını al
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            pts = []
            for line in lines:
                pts.extend([QgsPointXY(p) for p in line])
        else:
            pts = [QgsPointXY(p) for p in geom.asPolyline()]

        if len(pts) < 2:
            return None

        # Kesişim noktasına en yakın ucu bul
        d_start = int_point.distance(pts[0])
        d_end = int_point.distance(pts[-1])

        if d_start <= d_end:
            # Başlangıç kesişime yakın → baştan kes
            cut_pt = self._point_along_line(pts, distance, from_start=True)
            if cut_pt is None:
                return None
            # Başlangıçtan cut_pt'ye kadar olan kısmı kaldır
            new_pts = self._trim_from_start(pts, cut_pt)
        else:
            # Son kesişime yakın → sondan kes
            cut_pt = self._point_along_line(pts, distance, from_start=False)
            if cut_pt is None:
                return None
            new_pts = self._trim_from_end(pts, cut_pt)

        if new_pts and len(new_pts) >= 2:
            return (QgsGeometry.fromPolylineXY(new_pts), cut_pt)
        return None

    def _point_along_line(self, pts, distance, from_start=True):
        """Çizgi üzerinde belirli mesafedeki noktayı hesapla."""
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
        """Başlangıçtan cut_pt'ye kadar olan kısmı kaldır."""
        # cut_pt'den sonraki noktaları al
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
        """Sondan cut_pt'ye kadar olan kısmı kaldır."""
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
        """Katmanı düzenleyerek geometriyi güncelle."""
        if not layer.isEditable():
            layer.startEditing()
        layer.changeGeometry(feature.id(), new_geom)
        layer.commitChanges()
        layer.triggerRepaint()

    # ════════════════════════════════════════════════════════════════════════
    # Artık Temizleme
    # ════════════════════════════════════════════════════════════════════════

    def _clean_remnants(self, center_point, search_radius, min_length):
        """Kısa artık çizgi parçalarını temizle.

        Returns:
            int — silinen parça sayısı
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
                    # Merkeze yakın mı kontrol et
                    pt_geom = QgsGeometry.fromPointXY(center_point)
                    if geom.distance(pt_geom) <= search_radius:
                        to_delete.append(feat.id())

            if to_delete:
                if not layer.isEditable():
                    layer.startEditing()
                for fid in to_delete:
                    layer.deleteFeature(fid)
                    cleaned += 1
                layer.commitChanges()
                layer.triggerRepaint()

        return cleaned
