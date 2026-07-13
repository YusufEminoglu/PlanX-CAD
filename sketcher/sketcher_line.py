# -*- coding: utf-8 -*-
"""PlanX CAD line sketcher."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from .sketcher_base import sketcher_base


class sketcher_line(sketcher_base):
    """Draw a straight line between two points."""

    def tool_name(self):
        return "Line"

    def geom_type(self):
        return QgsWkbTypes.GeometryType.LineGeometry

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            self.add_vertex(point)
            if len(self.vertices) == 2:
                self._finish()

    def on_move(self, point):
        self.update_preview(point)

    def build_geometry(self):
        if len(self.vertices) >= 2:
            return QgsGeometry.fromPolylineXY(self.vertices)
        return None
