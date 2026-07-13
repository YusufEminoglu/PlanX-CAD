# -*- coding: utf-8 -*-
"""PlanX CAD regular-polygon sketcher."""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from qgis.PyQt.QtWidgets import QInputDialog
from .sketcher_base import sketcher_base
from ..core.crs_utils import local_metric_crs, transform_point


class sketcher_polygon(sketcher_base):
    """Draw a regular polygon with a configurable side count.
    First click: centre | Second click: radius and orientation
    The side count is requested when the tool starts.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.sides = 6
        self.center = None
        self._activation_cancelled = False

    def tool_name(self):
        return "Polygon"

    def geom_type(self):
        return QgsWkbTypes.GeometryType.PolygonGeometry

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        # Ask for the polygon side count.
        n, ok = QInputDialog.getInt(
            self.iface.mainWindow(), "Polygon", "Number of sides:", self.sides, 3, 100
        )
        if ok:
            self.sides = n
        else:
            self._activation_cancelled = True
            self.sketcher_message.emit("✏️ Polygon — Cancelled")
            return
        self.sketcher_message.emit(
            f"✏️ Polygon ({self.sides} sides) — Click the centre point"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self.center is None:
                self.center = point
                self.add_vertex(point)
                self.sketcher_message.emit(
                    "✏️ Polygon — Click to set the radius and orientation"
                )
            else:
                self.add_vertex(point)
                self._finish()

    def on_move(self, point):
        if self.center is not None and self.preview_rb:
            pts = self._calc_polygon(self.center, point)
            self.preview_rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            for pt in pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if self.center and len(self.vertices) >= 2:
            pts = self._calc_polygon(self.center, self.vertices[1])
            return QgsGeometry.fromPolygonXY([pts])
        return None

    def _calc_polygon(self, center, edge_point):
        """Calculate the regular polygon vertices."""
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
        start_angle = math.atan2(
            edge_point.y() - center.y(),
            edge_point.x() - center.x()
        )
        pts = []
        for i in range(self.sides + 1):
            angle = start_angle + (2 * math.pi * i / self.sides)
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
