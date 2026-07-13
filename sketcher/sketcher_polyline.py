# -*- coding: utf-8 -*-
"""planX CAD — Polyline Sketcher"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from .sketcher_base import sketcher_base


class sketcher_polyline(sketcher_base):
    """Draw a connected sequence of line segments.
    Left click: add a point | Right click or Enter: finish
    """

    def tool_name(self):
        return "Polyline"

    def geom_type(self):
        return QgsWkbTypes.GeometryType.LineGeometry

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
