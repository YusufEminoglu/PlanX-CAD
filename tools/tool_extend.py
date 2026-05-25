# -*- coding: utf-8 -*-
"""planX CAD â€” Extend AracÄ±"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import extend_geometry_to_boundary


class tool_extend(tool_base):
    """Ã‡izgiyi sÄ±nÄ±r objesine kadar uzatÄ±r.
    1. SÄ±nÄ±r objesini seÃ§ | 2. UzatÄ±lacak Ã§izgiyi seÃ§
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.boundary_layer = None
        self.boundary_feature = None

    def tool_name(self):
        return "Extend"

    def activate(self):
        super().activate()
        self.tool_message.emit("â†—ï¸ Extend â€” SÄ±nÄ±r objesini seÃ§in")

    def on_entity_selected(self, layer, feature, point):
        self.boundary_layer = layer
        self.boundary_feature = feature
        self._step = 2
        self.tool_message.emit("â†—ï¸ Extend â€” UzatÄ±lacak Ã§izgiyi seÃ§in")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            result = self._pick_feature(self.canvas.mouseLastXY())
            if result:
                layer, feature = result
                target_geom = feature.geometry()
                boundary_geom = self.boundary_feature.geometry()

                new_geom = extend_geometry_to_boundary(target_geom, boundary_geom)
                if new_geom:
                    self._apply_edit(layer, feature, new_geom)
                else:
                    self.tool_message.emit("âš ï¸ Extend â€” Uzatma yapÄ±lamadÄ±")

            self._reset()
            self.boundary_layer = None
            self.boundary_feature = None
