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
from ..core.precision_input import PrecisionInputError, looks_like_precision_input


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
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.ref_angle = angle_between_points(self.center, point)
                self._step = 3
                self.tool_message.emit(
                    "↻ Döndür — Hedef açıyı belirleyin | "
                    "Ctrl: 90° snap"
                )
            elif self._step == 3:
                rotation = self._calc_rotation(point)
                self._apply_rotation(rotation)

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            rotation = self._calc_rotation(point)

            geom = self.selected_feature.geometry()
            preview = rotate_geometry(geom, self.center, -rotation)

            self.preview_rb.reset(geom.type())
            self.preview_rb.setToGeometry(preview, self.selected_layer)

            # Açıyı göster
            angle_deg = rotation
            ctrl = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
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
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            rotation = round(rotation / 90.0) * 90.0

        return rotation

    def _apply_rotation(self, rotation):
        geom = self.selected_feature.geometry()
        rotated = rotate_geometry(geom, self.center, -rotation)
        applied = self._apply_edit(
            self.selected_layer, self.selected_feature, rotated
        )
        if applied:
            self.tool_message.emit(
                f"✅ Döndür — {rotation:.1f}° döndürüldü"
            )
        self.center = None
        self.ref_angle = None
        self._reset()

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        if self._step not in (2, 3) or self.center is None:
            self.tool_message.emit(
                "⚠️ Döndür — Hassas açı girmeden önce bir obje seçin"
            )
            return True
        token = (text or "").strip()
        if "," not in token and "@" not in token and "<" not in token:
            try:
                angle = float(token)
                if not math.isfinite(angle):
                    raise ValueError
            except ValueError:
                self.tool_message.emit("⚠️ Döndür — Geçerli bir derece girin")
                return True
            self._apply_rotation(angle)
            return True
        try:
            point = self.resolve_precision_target(
                token, self.center, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Döndür — {error}")
            return True
        self.on_click(point, Qt.MouseButton.LeftButton)
        return True
