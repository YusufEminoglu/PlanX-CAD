# -*- coding: utf-8 -*-
"""PlanX CAD circle sketcher."""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .sketcher_base import sketcher_base
from ..core.crs_utils import local_metric_crs, transform_geometry, transform_point


class sketcher_circle(sketcher_base):
    """Draw a circle from a centre point and radius.
    First click: centre | Second click: radius
    """

    SEGMENTS = 64  # Number of circle segments

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None

    def tool_name(self):
        return "Circle"

    def geom_type(self):
        return QgsWkbTypes.GeometryType.PolygonGeometry

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self.center is None:
                self.center = point
                self.add_vertex(point)
                self.sketcher_message.emit(
                    "✏️ Circle — Click to set the radius"
                )
            else:
                self.add_vertex(point)
                self._finish()

    def on_move(self, point):
        if self.center is not None and self.preview_rb:
            pts = self._calc_circle(self.center, point)
            self.preview_rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            for pt in pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if self.center and len(self.vertices) >= 2:
            radius_pt = self.vertices[1]
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            if canvas_crs.isGeographic():
                metric_crs = local_metric_crs(self.center, canvas_crs)
                metric_center = transform_point(
                    self.center, canvas_crs, metric_crs
                )
                metric_radius = transform_point(
                    radius_pt, canvas_crs, metric_crs
                )
                radius = math.hypot(
                    metric_radius.x() - metric_center.x(),
                    metric_radius.y() - metric_center.y(),
                )
                circle = QgsGeometry.fromPointXY(metric_center).buffer(
                    radius, self.SEGMENTS
                )
                return transform_geometry(circle, metric_crs, canvas_crs)
            radius = math.sqrt(
                (radius_pt.x() - self.center.x()) ** 2 +
                (radius_pt.y() - self.center.y()) ** 2
            )
            # Build the circle with a point buffer in the canvas CRS.
            center_geom = QgsGeometry.fromPointXY(self.center)
            return center_geom.buffer(radius, self.SEGMENTS)
        return None

    def _calc_circle(self, center, edge_point):
        """Calculate circle points for the live preview."""
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = None
        if canvas_crs.isGeographic():
            metric_crs = local_metric_crs(center, canvas_crs)
            center = transform_point(center, canvas_crs, metric_crs)
            edge_point = transform_point(edge_point, canvas_crs, metric_crs)
        radius = math.sqrt(
            (edge_point.x() - center.x()) ** 2 +
            (edge_point.y() - center.y()) ** 2
        )
        pts = []
        for i in range(self.SEGMENTS + 1):
            angle = 2 * math.pi * i / self.SEGMENTS
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            point = QgsPointXY(x, y)
            pts.append(
                transform_point(point, metric_crs, canvas_crs)
                if metric_crs else point
            )
        return pts

    def _cancel(self):
        self.center = None
        super()._cancel()

    def _cleanup(self):
        self.center = None
        super()._cleanup()
