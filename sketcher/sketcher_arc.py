# -*- coding: utf-8 -*-
"""PlanX CAD three-point arc sketcher."""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .sketcher_base import sketcher_base
from ..core.crs_utils import local_metric_crs, transform_point


class sketcher_arc(sketcher_base):
    """Draw an arc through three points.
    First click: start | Second click: intermediate point | Third click: end
    """

    ARC_SEGMENTS = 32

    def tool_name(self):
        return "Arc"

    def geom_type(self):
        return QgsWkbTypes.GeometryType.LineGeometry

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            self.add_vertex(point)
            if len(self.vertices) == 1:
                self.sketcher_message.emit(
                    "✏️ Arc — Click the intermediate point"
                )
            elif len(self.vertices) == 2:
                self.sketcher_message.emit(
                    "✏️ Arc — Click the end point"
                )
            elif len(self.vertices) == 3:
                self._finish()

    def on_move(self, point):
        if len(self.vertices) >= 1 and self.preview_rb:
            if len(self.vertices) == 1:
                self.update_preview(point)
            elif len(self.vertices) == 2:
                pts = self._calc_arc(self.vertices[0], self.vertices[1], point)
                self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)
                for pt in pts:
                    self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if len(self.vertices) == 3:
            pts = self._calc_arc(self.vertices[0], self.vertices[1], self.vertices[2])
            if len(pts) >= 2:
                return QgsGeometry.fromPolylineXY(pts)
        return None

    def _calc_arc(self, p1, p2, p3):
        """Calculate the arc through three points using its circumcircle."""
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = None
        if canvas_crs.isGeographic():
            metric_crs = local_metric_crs(p1, canvas_crs)
            p1 = transform_point(p1, canvas_crs, metric_crs)
            p2 = transform_point(p2, canvas_crs, metric_crs)
            p3 = transform_point(p3, canvas_crs, metric_crs)

        def canvas_points(points):
            if metric_crs is None:
                return points
            return [
                transform_point(point, metric_crs, canvas_crs)
                for point in points
            ]

        ax, ay = p1.x(), p1.y()
        bx, by = p2.x(), p2.y()
        cx, cy = p3.x(), p3.y()

        D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(D) < 1e-10:
            # Collinear input: retain the straight three-point path.
            return canvas_points([p1, p2, p3])

        ux = ((ax * ax + ay * ay) * (by - cy) +
              (bx * bx + by * by) * (cy - ay) +
              (cx * cx + cy * cy) * (ay - by)) / D
        uy = ((ax * ax + ay * ay) * (cx - bx) +
              (bx * bx + by * by) * (ax - cx) +
              (cx * cx + cy * cy) * (bx - ax)) / D

        center = QgsPointXY(ux, uy)
        radius = math.sqrt((ax - ux) ** 2 + (ay - uy) ** 2)

        # Calculate the three radial angles.
        a1 = math.atan2(ay - uy, ax - ux)
        a2 = math.atan2(by - uy, bx - ux)
        a3 = math.atan2(cy - uy, cx - ux)

        # Determine whether the path runs clockwise or counter-clockwise.
        def normalize(a):
            while a < 0:
                a += 2 * math.pi
            while a >= 2 * math.pi:
                a -= 2 * math.pi
            return a

        a1 = normalize(a1)
        a2 = normalize(a2)
        a3 = normalize(a3)

        # Choose the direction from a1 to a3 that passes through a2.
        ccw = self._is_ccw(a1, a2, a3)

        pts = []
        if ccw:
            if a3 < a1:
                a3 += 2 * math.pi
            for i in range(self.ARC_SEGMENTS + 1):
                t = a1 + (a3 - a1) * i / self.ARC_SEGMENTS
                x = ux + radius * math.cos(t)
                y = uy + radius * math.sin(t)
                pts.append(QgsPointXY(x, y))
        else:
            if a3 > a1:
                a3 -= 2 * math.pi
            for i in range(self.ARC_SEGMENTS + 1):
                t = a1 + (a3 - a1) * i / self.ARC_SEGMENTS
                x = ux + radius * math.cos(t)
                y = uy + radius * math.sin(t)
                pts.append(QgsPointXY(x, y))

        return canvas_points(pts)

    def _is_ccw(self, a1, a2, a3):
        """Return whether the a1→a2→a3 sequence is counter-clockwise."""
        def normalize(a):
            return a % (2 * math.pi)

        d12 = normalize(a2 - a1)
        d13 = normalize(a3 - a1)
        return d12 < d13
