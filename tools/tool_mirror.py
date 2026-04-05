# -*- coding: utf-8 -*-
"""planX CAD — Aynala (Mirror) Aracı"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import mirror_geometry


class tool_mirror(tool_base):
    """Objeyi bir çizgiye göre aynalama aracı.
    1. Objeyi seç | 2. Ayna çizgisi başlangıç | 3. Ayna çizgisi bitiş
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.line_start = None

    def tool_name(self):
        return "Aynala"

    def on_entity_selected(self, layer, feature, point):
        self._step = 2
        self.tool_message.emit(
            "⟺ Aynala — Ayna çizgisinin başlangıç noktasını tıklayın"
        )

    def on_click(self, point, button):
        if button == Qt.LeftButton:
            if self._step == 2:
                self.line_start = point
                self._step = 3
                self.tool_message.emit(
                    "⟺ Aynala — Ayna çizgisinin bitiş noktasını tıklayın"
                )
            elif self._step == 3:
                geom = self.selected_feature.geometry()
                mirrored = mirror_geometry(geom, self.line_start, point)

                if mirrored:
                    self._add_feature(self.selected_layer, mirrored,
                                      self.selected_feature)
                    self.tool_message.emit("✅ Aynala — Ayna oluşturuldu")
                else:
                    self.tool_message.emit("⚠️ Aynalama yapılamadı")

                self.line_start = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            geom = self.selected_feature.geometry()
            preview = mirror_geometry(geom, self.line_start, point)
            if preview:
                self.preview_rb.reset(geom.type())
                self.preview_rb.setToGeometry(preview)
