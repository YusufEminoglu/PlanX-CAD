# -*- coding: utf-8 -*-
"""planX CAD — Çizgi (Line) Sketcher"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from .sketcher_base import sketcher_base


class sketcher_line(sketcher_base):
    """İki noktalı düz çizgi çizer."""

    def tool_name(self):
        return "Çizgi"

    def geom_type(self):
        return QgsWkbTypes.LineGeometry

    def on_click(self, point, button):
        if button == Qt.LeftButton:
            self.add_vertex(point)
            if len(self.vertices) == 2:
                self._finish()

    def on_move(self, point):
        self.update_preview(point)

    def build_geometry(self):
        if len(self.vertices) >= 2:
            return QgsGeometry.fromPolylineXY(self.vertices)
        return None
