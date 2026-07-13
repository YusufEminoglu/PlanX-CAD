# -*- coding: utf-8 -*-
"""PlanX CAD rectangle sketcher."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .sketcher_base import sketcher_base
from ..core.crs_utils import local_metric_crs, transform_point


class sketcher_rectangle(sketcher_base):
    """Draw a rectangle from two opposite corners."""

    def tool_name(self):
        return "Rectangle"

    def geom_type(self):
        return QgsWkbTypes.PolygonGeometry

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            self.add_vertex(point)
            if len(self.vertices) == 2:
                self._finish()

    def on_move(self, point):
        if len(self.vertices) == 1 and self.preview_rb:
            rect_pts = self._rectangle_points(self.vertices[0], point)
            self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
            for pt in rect_pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if len(self.vertices) == 2:
            rect_pts = self._rectangle_points(
                self.vertices[0], self.vertices[1]
            )
            return QgsGeometry.fromPolygonXY([rect_pts])
        return None

    def _rectangle_points(self, first, opposite):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = None
        if canvas_crs.isGeographic():
            metric_crs = local_metric_crs(first, canvas_crs)
            first = transform_point(first, canvas_crs, metric_crs)
            opposite = transform_point(opposite, canvas_crs, metric_crs)
        points = [
            first,
            QgsPointXY(opposite.x(), first.y()),
            opposite,
            QgsPointXY(first.x(), opposite.y()),
            first,
        ]
        if metric_crs:
            return [
                transform_point(point, metric_crs, canvas_crs)
                for point in points
            ]
        return points
