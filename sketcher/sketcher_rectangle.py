# -*- coding: utf-8 -*-
"""planX CAD — Dikdörtgen (Rectangle) Sketcher"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .sketcher_base import sketcher_base


class sketcher_rectangle(sketcher_base):
    """İki köşe noktasıyla dikdörtgen çizer."""

    def tool_name(self):
        return "Dikdörtgen"

    def geom_type(self):
        return QgsWkbTypes.PolygonGeometry

    def on_click(self, point, button):
        if button == Qt.LeftButton:
            self.add_vertex(point)
            if len(self.vertices) == 2:
                self._finish()

    def on_move(self, point):
        if len(self.vertices) == 1 and self.preview_rb:
            p1 = self.vertices[0]
            rect_pts = [
                p1,
                QgsPointXY(point.x(), p1.y()),
                point,
                QgsPointXY(p1.x(), point.y()),
                p1  # Kapatma
            ]
            self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
            for pt in rect_pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if len(self.vertices) == 2:
            p1 = self.vertices[0]
            p2 = self.vertices[1]
            rect_pts = [
                p1,
                QgsPointXY(p2.x(), p1.y()),
                p2,
                QgsPointXY(p1.x(), p2.y()),
                p1  # Kapatma
            ]
            return QgsGeometry.fromPolygonXY([rect_pts])
        return None
