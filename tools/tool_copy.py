# -*- coding: utf-8 -*-
"""planX CAD â€” Kopyala (Copy) AracÄ±"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry
from .tool_base import tool_base


class tool_copy(tool_base):
    """Objeyi kopyalama aracÄ±.
    1. Objeyi seÃ§ | 2. BaÅŸlangÄ±Ã§ noktasÄ± | 3. Hedef nokta
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.base_point = None

    def tool_name(self):
        return "Kopyala"

    def on_entity_selected(self, layer, feature, point):
        self.base_point = point
        self._step = 2
        self.tool_message.emit("âŽ˜ Kopyala â€” Hedef noktayÄ± tÄ±klayÄ±n")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            dx = point.x() - self.base_point.x()
            dy = point.y() - self.base_point.y()

            new_geom = QgsGeometry(self.selected_feature.geometry())
            new_geom.translate(dx, dy)

            self._add_feature(self.selected_layer, new_geom,
                              self.selected_feature)
            self.tool_message.emit("âœ… Kopyala â€” Obje kopyalandÄ±")
            self.base_point = None
            self._reset()

    def on_move(self, point):
        if self._step == 2 and self.preview_rb and self.selected_feature:
            dx = point.x() - self.base_point.x()
            dy = point.y() - self.base_point.y()

            preview = QgsGeometry(self.selected_feature.geometry())
            preview.translate(dx, dy)

            self.preview_rb.reset(self.selected_feature.geometry().type())
            self.preview_rb.setToGeometry(preview)
