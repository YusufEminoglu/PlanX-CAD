# -*- coding: utf-8 -*-
"""planX CAD â€” Ã‡okgen (Polygon) Sketcher"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from qgis.PyQt.QtWidgets import QInputDialog
from .sketcher_base import sketcher_base


class sketcher_polygon(sketcher_base):
    """DÃ¼zgÃ¼n N-gen Ã§izer.
    1. tÄ±k: Merkez | 2. tÄ±k: YarÄ±Ã§ap ve yÃ¶n
    BaÅŸlangÄ±Ã§ta kenar sayÄ±sÄ± sorulur.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.sides = 6
        self.center = None

    def tool_name(self):
        return "Ã‡okgen"

    def geom_type(self):
        return QgsWkbTypes.PolygonGeometry

    def activate(self):
        super().activate()
        # Kenar sayÄ±sÄ± sor
        n, ok = QInputDialog.getInt(
            self.iface.mainWindow(), "Ã‡okgen", "Kenar sayÄ±sÄ±:", self.sides, 3, 100
        )
        if ok:
            self.sides = n
        self.sketcher_message.emit(
            f"âœï¸ Ã‡okgen ({self.sides} kenar) â€” Merkez noktasÄ±nÄ± tÄ±klayÄ±n"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self.center is None:
                self.center = point
                self.add_vertex(point)
                self.sketcher_message.emit(
                    f"âœï¸ Ã‡okgen â€” YarÄ±Ã§apÄ± belirlemek iÃ§in tÄ±klayÄ±n"
                )
            else:
                self.add_vertex(point)
                self._finish()

    def on_move(self, point):
        if self.center is not None and self.preview_rb:
            pts = self._calc_polygon(self.center, point)
            self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
            for pt in pts:
                self.preview_rb.addPoint(pt)

    def build_geometry(self):
        if self.center and len(self.vertices) >= 2:
            pts = self._calc_polygon(self.center, self.vertices[1])
            return QgsGeometry.fromPolygonXY([pts])
        return None

    def _calc_polygon(self, center, edge_point):
        """Regular polygon noktalarÄ±nÄ± hesapla."""
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
            pts.append(QgsPointXY(x, y))
        return pts

    def _cancel(self):
        self.center = None
        super()._cancel()

    def _cleanup(self):
        self.center = None
        super()._cleanup()
