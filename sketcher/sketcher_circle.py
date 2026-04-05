# -*- coding: utf-8 -*-
"""planX CAD — Daire (Circle) Sketcher"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from .sketcher_base import sketcher_base


class sketcher_circle(sketcher_base):
    """Merkez + yarıçap ile daire çizer.
    1. tık: Merkez | 2. tık: Yarıçap
    """

    SEGMENTS = 64  # Daire segment sayısı

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None

    def tool_name(self):
        return "Daire"

    def geom_type(self):
        return QgsWkbTypes.PolygonGeometry

    def on_click(self, point, button):
        if button == Qt.LeftButton:
            if self.center is None:
                self.center = point
                self.add_vertex(point)
                self.sketcher_message.emit(
                    "✏️ Daire — Yarıçapı belirlemek için tıklayın"
                )
            else:
                self.add_vertex(point)
                self._finish()

    def on_move(self, point):
        if self.center is not None and self.preview_rb:
            pts = self._calc_circle(self.center, point)
            self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
            for pt in pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if self.center and len(self.vertices) >= 2:
            radius_pt = self.vertices[1]
            radius = math.sqrt(
                (radius_pt.x() - self.center.x()) ** 2 +
                (radius_pt.y() - self.center.y()) ** 2
            )
            # QgsGeometry.fromPointXY + buffer ile mükemmel daire
            center_geom = QgsGeometry.fromPointXY(self.center)
            return center_geom.buffer(radius, self.SEGMENTS)
        return None

    def _calc_circle(self, center, edge_point):
        """Daire noktalarını hesapla (önizleme için)."""
        radius = math.sqrt(
            (edge_point.x() - center.x()) ** 2 +
            (edge_point.y() - center.y()) ** 2
        )
        pts = []
        for i in range(self.SEGMENTS + 1):
            angle = 2 * math.pi * i / self.SEGMENTS
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            pts.append(QgsPointXY(x, y))
        return pts

    def _cancel(self):
        self.center = None
        super()._cancel()

    def _cleanup(self):
        self.center = None
        super()._cleanup()
