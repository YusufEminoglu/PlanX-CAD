# -*- coding: utf-8 -*-
"""planX CAD — Döndür (Rotate) Aracı
Ctrl basılıyken 90° snap desteği.
"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import rotate_geometry, angle_between_points


class tool_rotate(tool_base):
    """Objeyi döndürme aracı.
    1. Objeyi seç | 2. Referans yönü | 3. Hedef açı
    Ctrl basılı tutunca 90° artışlarla (0/90/180/270) snap yapar.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None
        self.ref_angle = None

    def tool_name(self):
        return "Döndür"

    def on_entity_selected(self, layer, feature, point):
        self.center = point
        self._step = 2
        self.tool_message.emit(
            "↻ Döndür — Referans yönünü belirleyin (tıklayın)"
        )

    def on_click(self, point, button):
        if button == Qt.LeftButton:
            if self._step == 2:
                self.ref_angle = angle_between_points(self.center, point)
                self._step = 3
                self.tool_message.emit(
                    "↻ Döndür — Hedef açıyı belirleyin | "
                    "Ctrl: 90° snap"
                )
            elif self._step == 3:
                rotation = self._calc_rotation(point)

                geom = self.selected_feature.geometry()
                rotated = rotate_geometry(geom, self.center, -rotation)

                self._apply_edit(self.selected_layer, self.selected_feature,
                                 rotated)

                angle_deg = abs(rotation)
                self.tool_message.emit(
                    f"✅ Döndür — {angle_deg:.1f}° döndürüldü"
                )
                self.center = None
                self.ref_angle = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            rotation = self._calc_rotation(point)

            geom = self.selected_feature.geometry()
            preview = rotate_geometry(geom, self.center, -rotation)

            self.preview_rb.reset(geom.type())
            self.preview_rb.setToGeometry(preview)

            # Açıyı göster
            angle_deg = rotation
            ctrl = QApplication.keyboardModifiers() & Qt.ControlModifier
            snap_text = " [90° SNAP]" if ctrl else ""
            self.tool_message.emit(
                f"↻ Döndür — Açı: {angle_deg:.1f}°{snap_text} | "
                f"Ctrl: 90° snap"
            )

    def _calc_rotation(self, point):
        """Dönüş açısını hesapla. Ctrl basılıysa 90° snap."""
        target_angle = angle_between_points(self.center, point)
        rotation = target_angle - self.ref_angle

        # Ctrl basılıysa 90° artışlarla snap
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            rotation = round(rotation / 90.0) * 90.0

        return rotation
