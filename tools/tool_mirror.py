# -*- coding: utf-8 -*-
"""planX CAD â€” Aynala (Mirror) AracÄ±"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import mirror_geometry


class tool_mirror(tool_base):
    """Objeyi bir Ã§izgiye gÃ¶re aynalama aracÄ±.
    1. Objeyi seÃ§ | 2. Ayna Ã§izgisi baÅŸlangÄ±Ã§ | 3. Ayna Ã§izgisi bitiÅŸ
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.line_start = None

    def tool_name(self):
        return "Aynala"

    def on_entity_selected(self, layer, feature, point):
        self._step = 2
        self.tool_message.emit(
            "âŸº Aynala â€” Ayna Ã§izgisinin baÅŸlangÄ±Ã§ noktasÄ±nÄ± tÄ±klayÄ±n"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.line_start = point
                self._step = 3
                self.tool_message.emit(
                    "âŸº Aynala â€” Ayna Ã§izgisinin bitiÅŸ noktasÄ±nÄ± tÄ±klayÄ±n"
                )
            elif self._step == 3:
                geom = self.selected_feature.geometry()
                mirrored = mirror_geometry(geom, self.line_start, point)

                if mirrored:
                    self._add_feature(self.selected_layer, mirrored,
                                      self.selected_feature)
                    self.tool_message.emit("âœ… Aynala â€” Ayna oluÅŸturuldu")
                else:
                    self.tool_message.emit("âš ï¸ Aynalama yapÄ±lamadÄ±")

                self.line_start = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            geom = self.selected_feature.geometry()
            preview = mirror_geometry(geom, self.line_start, point)
            if preview:
                self.preview_rb.reset(geom.type())
                self.preview_rb.setToGeometry(preview)
