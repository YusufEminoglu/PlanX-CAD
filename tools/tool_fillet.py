# -*- coding: utf-8 -*-
"""planX CAD — Fillet Aracı
İki çizgi seçerek köşeyi yuvarlatan gelişmiş fillet.
"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_feedback import create_preview_rubberband, COLOR_ACCENT
from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point


class tool_fillet(tool_base):
    """İki kesişen çizgi arasında fillet (yuvarlatma) yapar.
    1. Fillet yarıçapı gir
    2. Birinci çizgiyi seç
    3. İkinci çizgiyi seç
    → Kesişim noktasında yarıçaplı ark oluşturulur
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.radius = 2.0
        self.first_layer = None
        self.first_feature = None
        self.first_point = None

    def tool_name(self):
        return "Fillet"

    def activate(self):
        super().activate()
        r, ok = QInputDialog.getDouble(
            None, "Fillet", "Fillet yarıçapı (m):",
            self.radius, 0.01, 10000.0, 2
        )
        if ok:
            self.radius = r
        self.first_layer = None
        self.first_feature = None
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius}m) — Birinci çizgiyi seçin"
        )

    def on_entity_selected(self, layer, feature, point):
        # Birinci çizgi seçildi
        self.first_layer = layer
        self.first_feature = feature
        self.first_point = point
        self._step = 2
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius}m) — İkinci çizgiyi seçin"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.LeftButton:
            result = self._pick_feature(self.canvas.mouseLastXY())
            if result:
                layer, feature = result
                self._do_fillet(layer, feature, point)
            else:
                self.tool_message.emit("⚠️ Fillet — İkinci obje bulunamadı")
            self._cleanup_fillet()

    def _do_fillet(self, second_layer, second_feature, point):
        """İki çizgi arasında fillet uygula (EasyFillet mimarisi)."""
        geom1 = self.first_feature.geometry()
        geom2 = second_feature.geometry()

        # Fillet matematiğini (Easyfillet Vector Logic) uygula
        fillet_result = create_fillet_and_trims(geom1, geom2, self.radius)
        
        if not fillet_result:
            self.tool_message.emit("⚠️ Fillet — Ark hesaplanamadı (çizgiler paralel veya teğet sığmıyor)")
            return

        arc_geom = fillet_result['arc']
        tp1 = fillet_result['tp1']
        tp2 = fillet_result['tp2']

        # Çizgileri teğet noktalarından kes
        new_geom1 = trim_line_to_point(geom1, tp1)
        new_geom2 = trim_line_to_point(geom2, tp2)

        if new_geom1 and not new_geom1.isEmpty():
            self._apply_edit(self.first_layer, self.first_feature, new_geom1)

        if new_geom2 and not new_geom2.isEmpty():
            self._apply_edit(second_layer, second_feature, new_geom2)

        # Ark'ı çiz — 1. katmana ekle
        if arc_geom and not arc_geom.isEmpty():
            self._add_feature(self.first_layer, arc_geom)

        self.tool_message.emit(
            f"✅ Fillet (R={self.radius}m) — Başarıyla uygulandı"
        )
        
    def on_move(self, point):
        """Fare hareket ettikçe ikinci çizgiyi saptayıp on-the-fly preview (önizleme) oluştur."""
        if self._step == 2:
            self.preview_rb.reset()
            pos = self.canvas.mouseLastXY()
            result = self._pick_feature(pos)
            if result:
                layer, feature = result
                # Kendisi değilse
                if feature.id() != self.first_feature.id():
                    geom1 = self.first_feature.geometry()
                    geom2 = feature.geometry()
                    fillet_result = create_fillet_and_trims(geom1, geom2, self.radius)
                    if fillet_result:
                        arc_geom = fillet_result['arc']
                        self.preview_rb.setToGeometry(arc_geom, None)
                        self.preview_rb.show()

    def _get_line_points(self, geom):
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            if lines:
                return [QgsPointXY(p) for p in lines[0]]
        else:
            return [QgsPointXY(p) for p in geom.asPolyline()]
        return []

    def _find_direction_from_intersection(self, pts, int_pt):
        """Kesişim noktasından uzaklaşan yönü bul."""
        min_dist = float('inf')
        best_idx = 0
        for i, p in enumerate(pts):
            d = int_pt.distance(p)
            if d < min_dist:
                min_dist = d
                best_idx = i

        # Kesişim noktasından uzağa bakan yön
        if best_idx == 0 and len(pts) > 1:
            return math.atan2(pts[0].y() - int_pt.y(), pts[0].x() - int_pt.x())
        elif best_idx == len(pts) - 1 and len(pts) > 1:
            return math.atan2(pts[-1].y() - int_pt.y(), pts[-1].x() - int_pt.x())
        else:
            # Daha uzak uca bakan yön
            d_start = int_pt.distance(pts[0])
            d_end = int_pt.distance(pts[-1])
            if d_start > d_end:
                return math.atan2(pts[0].y() - int_pt.y(), pts[0].x() - int_pt.x())
            else:
                return math.atan2(pts[-1].y() - int_pt.y(), pts[-1].x() - int_pt.x())



    def _trim_line_at_point(self, pts, int_pt, trim_pt):
        """Çizgiyi kesişim noktasından trim noktasına kadar kes."""
        # int_pt'ye en yakın ucu bul
        d_start = int_pt.distance(pts[0])
        d_end = int_pt.distance(pts[-1])

        if d_start < d_end:
            # Başlangıç kesişime yakın → başlangıcı trim_pt ile değiştir
            return [trim_pt] + pts[1:]
        else:
            # Son kesişime yakın → sonu trim_pt ile değiştir
            return pts[:-1] + [trim_pt]

    def _cleanup_fillet(self):
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._reset()
