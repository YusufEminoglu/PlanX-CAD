# -*- coding: utf-8 -*-
"""PlanX CAD Copy tool."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry
from .tool_base import tool_base
from ..core.precision_input import PrecisionInputError, looks_like_precision_input


class tool_copy(tool_base):
    """Copy a feature from its picked base point to a target point.

    1. Select feature | 2. Base point | 3. Target point
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.base_point = None

    def tool_name(self):
        return "Copy"

    def on_entity_selected(self, layer, feature, point):
        self.base_point = point
        self._step = 2
        self.tool_message.emit("⎘ Copy — Click the target point")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            dx = point.x() - self.base_point.x()
            dy = point.y() - self.base_point.y()

            new_geom = QgsGeometry(self.selected_feature.geometry())
            new_geom.translate(dx, dy)

            added = self._add_feature(
                self.selected_layer, new_geom, self.selected_feature
            )
            if added is not None:
                self.tool_message.emit("✅ Copy — Feature copied")
            self.base_point = None
            self._reset()

    def on_move(self, point):
        if self._step == 2 and self.preview_rb and self.selected_feature:
            dx = point.x() - self.base_point.x()
            dy = point.y() - self.base_point.y()

            preview = QgsGeometry(self.selected_feature.geometry())
            preview.translate(dx, dy)

            self.preview_rb.reset(self.selected_feature.geometry().type())
            self.preview_rb.setToGeometry(preview, self.selected_layer)

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        if self._step != 2 or self.base_point is None:
            self.tool_message.emit(
                "⚠️ Copy — Select a feature before entering a precise target"
            )
            return True
        try:
            target = self.resolve_precision_target(
                text, self.base_point, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Copy — {error}")
            return True
        self.on_click(target, Qt.MouseButton.LeftButton)
        return True
