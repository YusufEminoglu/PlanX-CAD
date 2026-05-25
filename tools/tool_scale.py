# -*- coding: utf-8 -*-
"""planX CAD â€” Ã–lÃ§ekle (Scale) AracÄ±"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import scale_geometry, point_distance


class tool_scale(tool_base):
    """Objeyi Ã¶lÃ§ekleme aracÄ±.
    1. Objeyi seÃ§ | 2. Ã–lÃ§ek merkezi |
    3. Referans mesafesi | 4. Hedef mesafesi
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None
        self.ref_distance = None

    def tool_name(self):
        return "Ã–lÃ§ekle"

    def on_entity_selected(self, layer, feature, point):
        self.center = point
        self._step = 2
        self.tool_message.emit(
            "â¤¡ Ã–lÃ§ekle â€” Referans mesafesini belirleyin (tÄ±klayÄ±n)"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.ref_distance = point_distance(self.center, point)
                if self.ref_distance < 0.001:
                    self.tool_message.emit("âš ï¸ Referans mesafesi Ã§ok kÃ¼Ã§Ã¼k")
                    return
                self._step = 3
                self.tool_message.emit(
                    "â¤¡ Ã–lÃ§ekle â€” Hedef mesafeyi belirleyin (tÄ±klayÄ±n)"
                )
            elif self._step == 3:
                target_distance = point_distance(self.center, point)
                factor = target_distance / self.ref_distance

                geom = self.selected_feature.geometry()
                scaled = scale_geometry(geom, self.center, factor)

                if scaled:
                    self._apply_edit(self.selected_layer,
                                     self.selected_feature, scaled)
                else:
                    self.tool_message.emit("âš ï¸ Ã–lÃ§ekleme yapÄ±lamadÄ±")

                self.center = None
                self.ref_distance = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            target_distance = point_distance(self.center, point)
            if self.ref_distance > 0.001:
                factor = target_distance / self.ref_distance
                geom = self.selected_feature.geometry()
                preview = scale_geometry(geom, self.center, factor)
                if preview:
                    self.preview_rb.reset(geom.type())
                    self.preview_rb.setToGeometry(preview)
