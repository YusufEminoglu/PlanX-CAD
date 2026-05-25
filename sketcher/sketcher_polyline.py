# -*- coding: utf-8 -*-
"""planX CAD â€” Polyline Sketcher"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from .sketcher_base import sketcher_base


class sketcher_polyline(sketcher_base):
    """Ã‡oklu baÄŸlÄ± Ã§izgi segmentleri Ã§izer.
    Sol tÄ±k: Nokta ekle | SaÄŸ tÄ±k / Enter: Bitir
    """

    def tool_name(self):
        return "Polyline"

    def geom_type(self):
        return QgsWkbTypes.LineGeometry

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            self.add_vertex(point)
        elif button == Qt.MouseButton.RightButton:
            if len(self.vertices) >= 2:
                self._finish()

    def on_move(self, point):
        self.update_preview(point)

    def build_geometry(self):
        if len(self.vertices) >= 2:
            return QgsGeometry.fromPolylineXY(self.vertices)
        return None
