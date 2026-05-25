# -*- coding: utf-8 -*-
"""planX CAD â€” Fillet AracÄ±
Ä°ki Ã§izgi seÃ§erek kÃ¶ÅŸeyi yuvarlatan geliÅŸmiÅŸ fillet.
"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_feedback import create_preview_rubberband, COLOR_ACCENT
from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point


class tool_fillet(tool_base):
    """Ä°ki kesiÅŸen Ã§izgi arasÄ±nda fillet (yuvarlatma) yapar.
    1. Fillet yarÄ±Ã§apÄ± gir
    2. Birinci Ã§izgiyi seÃ§
    3. Ä°kinci Ã§izgiyi seÃ§
    â†’ KesiÅŸim noktasÄ±nda yarÄ±Ã§aplÄ± ark oluÅŸturulur
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.radius = 2.0
        self.first_layer = None
        self.first_feature = None
        self.first_point = None

    def tool_name(self):
        return "Fillet"

    def activate(self):
        super().activate()
        r, ok = QInputDialog.getDouble(
            self.iface.mainWindow(), "Fillet", "Fillet yarÄ±Ã§apÄ± (m):",
            self.radius, 0.01, 10000.0, 2
        )
        if ok:
            self.radius = r
        self.first_layer = None
        self.first_feature = None
        self.tool_message.emit(
            f"âŒ’ Fillet (R={self.radius}m) â€” Birinci Ã§izgiyi seÃ§in"
        )

    def on_entity_selected(self, layer, feature, point):
        # Birinci Ã§izgi seÃ§ildi
        self.first_layer = layer
        self.first_feature = feature
        self.first_point = point
        self._step = 2
        self.tool_message.emit(
            f"âŒ’ Fillet (R={self.radius}m) â€” Ä°kinci Ã§izgiyi seÃ§in"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            result = self._pick_feature(self.canvas.mouseLastXY())
            if result:
                layer, feature = result
                self._do_fillet(layer, feature, point)
            else:
                self.tool_message.emit("âš ï¸ Fillet â€” Ä°kinci obje bulunamadÄ±")
            self._cleanup_fillet()

    def _do_fillet(self, second_layer, second_feature, point):
        """Ä°ki Ã§izgi arasÄ±nda fillet uygula (EasyFillet mimarisi)."""
        geom1 = self.first_feature.geometry()
        geom2 = second_feature.geometry()

        # Fillet matematiÄŸini (Easyfillet Vector Logic) uygula
        fillet_result = create_fillet_and_trims(geom1, geom2, self.radius)
        
        if not fillet_result:
            self.tool_message.emit("âš ï¸ Fillet â€” Ark hesaplanamadÄ± (Ã§izgiler paralel veya teÄŸet sÄ±ÄŸmÄ±yor)")
            return

        arc_geom = fillet_result['arc']
        tp1 = fillet_result['tp1']
        tp2 = fillet_result['tp2']

        # Ã‡izgileri teÄŸet noktalarÄ±ndan kes
        new_geom1 = trim_line_to_point(geom1, tp1)
        new_geom2 = trim_line_to_point(geom2, tp2)

        if new_geom1 and not new_geom1.isEmpty():
            self._apply_edit(self.first_layer, self.first_feature, new_geom1)

        if new_geom2 and not new_geom2.isEmpty():
            self._apply_edit(second_layer, second_feature, new_geom2)

        # Ark'Ä± Ã§iz â€” 1. katmana ekle
        if arc_geom and not arc_geom.isEmpty():
            self._add_feature(self.first_layer, arc_geom)

        self.tool_message.emit(
            f"âœ… Fillet (R={self.radius}m) â€” BaÅŸarÄ±yla uygulandÄ±"
        )
        
    def on_move(self, point):
        """Fare hareket ettikÃ§e ikinci Ã§izgiyi saptayÄ±p on-the-fly preview (Ã¶nizleme) oluÅŸtur."""
        if self._step == 2:
            self.preview_rb.reset()
            pos = self.canvas.mouseLastXY()
            result = self._pick_feature(pos)
            if result:
                layer, feature = result
                # Kendisi deÄŸilse
                if feature.id() != self.first_feature.id():
                    geom1 = self.first_feature.geometry()
                    geom2 = feature.geometry()
                    fillet_result = create_fillet_and_trims(geom1, geom2, self.radius)
                    if fillet_result:
                        arc_geom = fillet_result['arc']
                        self.preview_rb.setToGeometry(arc_geom, None)
                        self.preview_rb.show()

    def _cleanup_fillet(self):
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._reset()
