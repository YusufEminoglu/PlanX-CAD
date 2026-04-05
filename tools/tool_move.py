# -*- coding: utf-8 -*-
"""planX CAD — Taşı (Move) Aracı"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_feedback import create_preview_rubberband


class tool_move(tool_base):
    """Objeyi taşıma aracı.
    1. Objeyi seç | 2. Başlangıç noktası | 3. Hedef nokta
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.base_point = None

    def tool_name(self):
        return "Taşı"

    def on_entity_selected(self, layer, feature, point):
        self.base_point = point
        self._step = 2
        self.tool_message.emit("↔️ Taşı — Hedef noktayı tıklayın")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.LeftButton:
            dx = point.x() - self.base_point.x()
            dy = point.y() - self.base_point.y()

            geom = QgsGeometry(self.selected_feature.geometry())
            geom.translate(dx, dy)

            self._apply_edit(self.selected_layer, self.selected_feature, geom)
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
