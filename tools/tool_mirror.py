# -*- coding: utf-8 -*-
"""PlanX CAD Mirror tool."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import mirror_geometry


class tool_mirror(tool_base):
    """Mirror a feature across a two-point axis.

    1. Select feature | 2. Axis start | 3. Axis end
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.line_start = None

    def tool_name(self):
        return "Mirror"

    def on_entity_selected(self, layer, feature, point):
        self._step = 2
        self.tool_message.emit(
            "⟺ Mirror — Click the start of the mirror axis"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.line_start = point
                self._step = 3
                self.tool_message.emit(
                    "⟺ Mirror — Click the end of the mirror axis"
                )
            elif self._step == 3:
                geom = self.selected_feature.geometry()
                mirrored = mirror_geometry(
                    geom, self.line_start, point, self.selected_layer.crs()
                )

                if mirrored:
                    added = self._add_feature(
                        self.selected_layer, mirrored, self.selected_feature
                    )
                    if added is not None:
                        self.tool_message.emit("✅ Mirror — Mirrored copy created")
                else:
                    self.tool_message.emit("⚠️ Mirror operation failed")

                self.line_start = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            geom = self.selected_feature.geometry()
            preview = mirror_geometry(
                geom, self.line_start, point, self.selected_layer.crs()
            )
            if preview:
                self.preview_rb.reset(geom.type())
                self.preview_rb.setToGeometry(preview, self.selected_layer)
