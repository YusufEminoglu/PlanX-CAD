# -*- coding: utf-8 -*-
"""PlanX CAD Rotate tool with optional 90-degree snapping."""

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import rotate_geometry, angle_between_points
from ..core.precision_input import PrecisionInputError, looks_like_precision_input


class tool_rotate(tool_base):
    """Rotate a feature around the picked center.

    1. Select feature | 2. Reference direction | 3. Target angle
    Hold Ctrl to snap in 90-degree increments.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None
        self.ref_angle = None

    def tool_name(self):
        return "Rotate"

    def on_entity_selected(self, layer, feature, point):
        self.center = point
        self._step = 2
        self.tool_message.emit(
            "↻ Rotate — Click to define the reference direction"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.ref_angle = angle_between_points(
                    self.center, point, self.selected_layer.crs()
                )
                self._step = 3
                self.tool_message.emit(
                    "↻ Rotate — Define the target angle | "
                    "Ctrl: 90° snap"
                )
            elif self._step == 3:
                rotation = self._calc_rotation(point)
                self._apply_rotation(rotation)

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            rotation = self._calc_rotation(point)

            geom = self.selected_feature.geometry()
            preview = rotate_geometry(
                geom, self.center, -rotation, self.selected_layer.crs()
            )

            self.preview_rb.reset(geom.type())
            self.preview_rb.setToGeometry(preview, self.selected_layer)

            # Show the current angle.
            angle_deg = rotation
            ctrl = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
            snap_text = " [90° SNAP]" if ctrl else ""
            self.tool_message.emit(
                f"↻ Rotate — Angle: {angle_deg:.1f}°{snap_text} | "
                f"Ctrl: 90° snap"
            )

    def _calc_rotation(self, point):
        """Calculate the rotation angle, with optional 90-degree snapping."""
        target_angle = angle_between_points(
            self.center, point, self.selected_layer.crs()
        )
        rotation = target_angle - self.ref_angle

        # Snap to 90-degree increments while Ctrl is held.
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            rotation = round(rotation / 90.0) * 90.0

        return rotation

    def _apply_rotation(self, rotation):
        geom = self.selected_feature.geometry()
        rotated = rotate_geometry(
            geom, self.center, -rotation, self.selected_layer.crs()
        )
        applied = self._apply_edit(
            self.selected_layer, self.selected_feature, rotated
        )
        if applied:
            self.tool_message.emit(
                f"✅ Rotate — Rotated {rotation:.1f}°"
            )
        self.center = None
        self.ref_angle = None
        self._reset()

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        if self._step not in (2, 3) or self.center is None:
            self.tool_message.emit(
                "⚠️ Rotate — Select a feature before entering a precise angle"
            )
            return True
        token = (text or "").strip()
        if "," not in token and "@" not in token and "<" not in token:
            try:
                angle = float(token)
                if not math.isfinite(angle):
                    raise ValueError
            except ValueError:
                self.tool_message.emit("⚠️ Rotate — Enter a valid angle in degrees")
                return True
            self._apply_rotation(angle)
            return True
        try:
            point = self.resolve_precision_target(
                token, self.center, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Rotate — {error}")
            return True
        self.on_click(point, Qt.MouseButton.LeftButton)
        return True
