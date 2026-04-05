# -*- coding: utf-8 -*-
"""
planX CAD — Kavşak Oluşturma Aracı (Gelişmiş)
NetCAD tarzı kavşak çözümü:
 - Dış kaldırımlar: düz çizgi ile kırma (chamfer)
 - İç kaldırımlar: radius ile yay (fillet) bağlantısı
 - Kavşak adası: yuvarlak veya su damlası

Oluşturulan katmanlar:
 - kavsak (LineString): kırma ve bağlantı çizgileri
 - kavsak_ada (Polygon): kavşak adaları
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
    """Kavşak oluşturma aracı.

    İş akışı:
    1. Dialog açılır → parametreler girilir
    2. Kavşak merkezi tıklanır
    3. Otomatik olarak:
       a) Etki yarıçapı içindeki çizgiler trimlenir
       b) Dış kaldırım köşeleri düz çizgi ile kırılır (chamfer)
       c) İç kaldırım köşeleri radius ile bağlanır (fillet)
       d) Kavşak adası oluşturulur (yuvarlak/su damlası)
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
        if dlg.exec_() != JunctionDialog.Accepted:
            self.sketcher_message.emit("🔵 Kavşak — İptal edildi")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self._step = 1
        self.sketcher_message.emit(
            f"🔵 Kavşak (R={self.params['radius']}m, "
            f"Kırma={self.params['chamfer_dist']}m, "
            f"Fillet R={self.params['fillet_radius']}m) — "
            f"Kavşak merkezini tıklayın"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        super().deactivate()

    def canvasPressEvent(self, event):
        if self._step != 1 or event.button() != Qt.LeftButton:
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

        # Daire önizleme
        pts = self._make_circle(point, self.params["radius"], 48)
        self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
        for pt in pts:
            self.preview_rb.addPoint(pt)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
            self.preview_rb = None
            self.sketcher_message.emit("🔵 Kavşak — İptal edildi")
            self.sketcher_finished.emit()

    # ════════════════════════════════════════════════════════════════════════
    # Kavşak Oluşturma
    # ════════════════════════════════════════════════════════════════════════

    def _create_junction(self, center):
        """Ana kavşak oluşturma işlemi."""
        p = self.params
        radius = p["radius"]
        chamfer_dist = p["chamfer_dist"]
        fillet_radius = p["fillet_radius"]
        ada_tipi = p["ada_tipi"]
        ada_radius = p["ada_radius"]

        center_geom = QgsGeometry.fromPointXY(center)
        junction_buffer = center_geom.buffer(radius, 48)

        # ── Katmanları hazırla ───────────────────────────────────────────
        kavsak_line_layer = get_road_platform_layer()
        kavsak_ada_layer = self._get_kavsak_ada_layer()

        if not kavsak_line_layer or not kavsak_ada_layer:
            self.sketcher_message.emit("⚠️ Kavşak — Katmanlar oluşturulamadı")
            return

        kavsak_id = self._next_id(kavsak_line_layer, "yol_id")

        # ── 1. Tüm çizgi katmanlarını trimle ────────────────────────────
        trimmed_count = 0
        cut_endpoints = []  # Trimlenen çizgilerin kesilme noktalarını topla

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

            if not layer.isEditable():
                layer.startEditing()

            for feat in features_hit:
                geom = feat.geometry()
                
                # 1 Metrelik split özelliği eklendi:
                # Dış yollar (R + 1m den başlayan) ve 1m'lik parçalar (R ile R+1 arası)
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
                    # Kesilme noktalarını union üzerinden bul
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

                    # Geometrileri parça parça ekle/güncelle
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

            layer.commitChanges()
            layer.triggerRepaint()

        # Endpoint'leri bileşenlerine göre ayır (ep, yol_id) formatında
        kaldirim_pts = []
        refuj_pts = []
        for point, bilesen, yol_id in cut_endpoints:
            if not bilesen or bilesen == "kaldirim":
                kaldirim_pts.append((point, yol_id))
            elif bilesen == "refuj":
                refuj_pts.append((point, yol_id))

        # ── 2. Dış kaldırım kırma çizgileri (chamfer) ───────────────────
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

        # ── 3. İç kaldırım bağlantı yayları (fillet) ────────────────────
        # Eğre dış kırma yapılacaksa iç bağlantıya gerek yok (kullanıcı talebi)
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

        # ── 3.5 Refüj Kapatma Yayları (Yuvarlak kavşaklar için) ─────────
        if ada_tipi != "yok" and refuj_pts:
            refuj_caps = self._create_refuj_caps(center, refuj_pts)
            for cap_line in refuj_caps:
                feat = QgsFeature(kavsak_line_layer.fields())
                feat.setGeometry(cap_line)
                feat.setAttribute("yol_id", kavsak_id)
                feat.setAttribute("yol_tipi", "kavsak")
                feat.setAttribute("bilesen", "refuj_baglanti")
                feat.setAttribute("gorunur", 1)  # Kapatma için görünür
                kavsak_line_layer.addFeature(feat)

        kavsak_line_layer.commitChanges()
        kavsak_line_layer.triggerRepaint()

        # ── 4. Kavşak adası ──────────────────────────────────────────────
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

        # ── Sonuç ────────────────────────────────────────────────────────
        msg = (
            f"✅ Kavşak — {trimmed_count} çizgi trimlendi | "
            f"{len(chamfer_lines)} kırma + {len(fillet_arcs)} bağlantı"
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

    # ════════════════════════════════════════════════════════════════════════
    # Geometri İşlemleri
    # ════════════════════════════════════════════════════════════════════════

    def _find_cut_endpoints(self, original_geom, trimmed_geom, buffer_geom):
        """Trimlenen çizginin kesilme noktalarını bul.

        Returns:
            list[QgsPointXY] — kavşak alanı sınırındaki kesilme noktaları
        """
        endpoints = []

        # Trimlenmiş geometrinin uç noktalarını al
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

        # Sadece kavşak sınırına yakın olanları filtrele
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
        """Dış kaldırım kırma çizgileri oluştur.

        Karşılıklı uç noktaları düz çizgi ile bağla (chamfer).
        Merkezden daha uzak olan nokta çiftleri dış kaldırıma ait.
        """
        if len(endpoints) < 2:
            return []

        chamfer_lines = []
        
        groups_dict = {}
        for pt, y_id in endpoints:
            angle = math.atan2(pt.y() - center.y(), pt.x() - center.x())
            dist = center.distance(pt)
            item = (angle, dist, pt, y_id)
            # None yol_id'leri ayrı gruplamak için angle bazlı geçici ID
            safe_id = y_id if y_id is not None else f"unknown_{round(angle, 1)}"
            if safe_id not in groups_dict:
                groups_dict[safe_id] = []
            groups_dict[safe_id].append(item)

        groups = self._order_groups_circularly(groups_dict)

        # Her kolun ucundaki en dıştaki noktaları bul
        outer_points = []
        for group in groups:
            if len(group) >= 2:
                # En uzak noktaları al (dış kaldırım)
                group.sort(key=lambda x: x[1], reverse=True)
                outer_points.append(group[0][2])
                if len(group) >= 2:
                    outer_points.append(group[1][2])

        # Komşu kol dışları arasına chamfer çizgileri
        if len(groups) >= 2:
            for i in range(len(groups)):
                g1 = groups[i]
                g2 = groups[(i + 1) % len(groups)]

                # Her grup çiftinden en yakın dış noktaları bul
                best_pair = self._find_closest_pair_between_groups(g1, g2)
                if best_pair:
                    p1, p2 = best_pair
                    line_geom = QgsGeometry.fromPolylineXY([p1, p2])
                    chamfer_lines.append(line_geom)

        return chamfer_lines

    def _create_fillet_arcs(self, center, endpoints, fillet_radius):
        """İç kaldırım bağlantı yayları oluştur.

        Merkezden daha yakın olan nokta çiftleri iç kaldırıma ait.
        Bunları ark ile bağla.
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

        # Komşu kol içleri arasına fillet yay
        if len(groups) >= 2:
            for i in range(len(groups)):
                g1 = groups[i]
                g2 = groups[(i + 1) % len(groups)]

                # Her grup çiftinden en yakın iç noktaları bul
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
        """Kavşağa giren refüj çizgilerini kapatır."""
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
                # Bir koldan gelen en az 2 refüj ucu varsa onları düz çizgiyle birleştir.
                p1 = group[0][2]
                p2 = group[-1][2]
                caps.append(QgsGeometry.fromPolylineXY([p1, p2]))

        return caps

    def _order_groups_circularly(self, groups_dict):
        """Aynı yol kollarına ait olan noktaları açısal sıraya dizer."""
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
        """İki grup arasındaki en yakın (veya en uzak) nokta çiftini bul."""
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
        """İki nokta arasında doğru teğet arkı (calc_tangent_fillet_arc ile)."""
        # P1 ve P2 kavşak sınırında.
        # Bu noktaların merkezden geliş açısını bulalım ve calc_tangent_fillet_arc kullanalım.
        dir1 = math.atan2(p1.y() - center.y(), p1.x() - center.x())
        dir2 = math.atan2(p2.y() - center.y(), p2.x() - center.x())
        
        # calc_tangent_fillet_arc aslında merkezden uzaklaşan (p1, p2) için.
        # Bizde p1 ve p2 kavşak noktasında bitiyor. Ama sorun değil, fillet arc'yi çizip döndürür.
        # Sanal bir kesişim noktası gerekiyor fillet için!
        # Dış çizgilerin uzantılarının kesişimi neresi?
        # Bu biraz karmaşık olabilir, calc_tangent_fillet_arc direkt olarak intersection point istiyor.
        # Kesişim noktasını bulalım.
        
        # P1'den dir1 yönünde ve P2'den dir2 yönünde giden çizgilerin kesişimi (merkeze doğru)
        # Aslında en basit yöntem, _create_fillet_arcs içinde calc_tangent_fillet_arc kullanmaktır.
        
        # Basitleştirilmiş: Teğet arc çizebilmek için center'ı kullanabiliriz, ama merkezde değil.
        # calc_tangent_fillet_arc(int_pt, angle1, angle2, radius)
        
        # Yolları merkeze doğrultuyoruz
        arc_pts, _ = calc_tangent_fillet_arc(center, dir1, dir2, radius, segments)
        return arc_pts

    def _create_teardrop(self, center, radius, length):
        """Su damlası şeklinde ada oluştur."""
        pts = []
        # Damlacık: yarım daire + sivri uç
        segments = 32

        # Üst yarım daire
        for i in range(segments + 1):
            angle = math.pi / 2 + math.pi * i / segments
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            pts.append(QgsPointXY(x, y))

        # Sivri uç (aşağıda)
        pts.append(QgsPointXY(center.x(), center.y() - length))

        # Kapatma
        pts.append(pts[0])

        return QgsGeometry.fromPolygonXY([pts])

    # ════════════════════════════════════════════════════════════════════════
    # Katman Yönetimi
    # ════════════════════════════════════════════════════════════════════════


    def _get_kavsak_ada_layer(self):
        """kavsak_ada (Polygon) katmanını bul veya oluştur."""
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
