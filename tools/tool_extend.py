# -*- coding: utf-8 -*-
"""planX CAD — Extend Aracı"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import extend_geometry_to_boundary


class tool_extend(tool_base):
    """Çizgiyi sınır objesine kadar uzatır.
    1. Sınır objesini seç | 2. Uzatılacak çizgiyi seç
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.boundary_layer = None
        self.boundary_feature = None

    def tool_name(self):
        return "Extend"

    def activate(self):
        super().activate()
        self.tool_message.emit("↗️ Extend — Sınır objesini seçin")

    def on_entity_selected(self, layer, feature, point):
        self.boundary_layer = layer
        self.boundary_feature = feature
        self._step = 2
        self.tool_message.emit("↗️ Extend — Uzatılacak çizgiyi seçin")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # Sınır objesi dışlanır — çizgi kendi sınırına uzatılamaz
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.boundary_layer, self.boundary_feature),
            )
            if result:
                layer, feature = result
                target_geom = feature.geometry()
                boundary_geom = self.geometry_to_layer_crs(
                    self.boundary_feature.geometry(),
                    self.boundary_layer,
                    layer,
                )

                new_geom = (
                    extend_geometry_to_boundary(target_geom, boundary_geom)
                    if boundary_geom is not None else None
                )
                if new_geom:
                    self._apply_edit(layer, feature, new_geom)
                else:
                    self.tool_message.emit(
                        "⚠️ Extend — Uzatma yapılamadı veya CRS dönüşümü başarısız"
                    )

            self._reset()
            self.boundary_layer = None
            self.boundary_feature = None
