# -*- coding: utf-8 -*-
"""planX CAD — Offset Aracı"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_utils import offset_geometry
from ..core.sketcher_feedback import create_preview_rubberband, cleanup_sketcher_rubberband


class tool_offset(tool_base):
    """Seçilen objeyi belirtilen mesafe kadar öteleme yapar."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.distance = 5.0

    def tool_name(self):
        return "Offset"

    def on_entity_selected(self, layer, feature, point):
        # Mesafe sor
        d, ok = QInputDialog.getDouble(
            None, "Offset", "Offset mesafesi (m):",
            self.distance, 0.01, 100000.0, 2
        )
        if ok:
            self.distance = d
            self.tool_message.emit(
                f"🔧 Offset ({self.distance}m) — Hangi tarafa? Sol tık: taraf seçin"
            )
            self._step = 2

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.LeftButton:
            geom = self.selected_feature.geometry()
            # Hangi tarafta olduğunu belirle
            dist_signed = geom.lineLocatePoint(QgsGeometry.fromPointXY(point))
            closest = geom.nearestPoint(QgsGeometry.fromPointXY(point))
            if closest:
                # Soldaki/sağdaki offset
                left = offset_geometry(geom, self.distance, "left")
                right = offset_geometry(geom, self.distance, "right")

                # Hangi taraf tıklanan noktaya daha yakın?
                use_geom = None
                if left and right:
                    d_left = left.distance(QgsGeometry.fromPointXY(point))
                    d_right = right.distance(QgsGeometry.fromPointXY(point))
                    use_geom = left if d_left < d_right else right
                elif left:
                    use_geom = left
                elif right:
                    use_geom = right

                if use_geom:
                    self._add_feature(self.selected_layer, use_geom,
                                      self.selected_feature)
                    self.tool_message.emit("✅ Offset — Tamamlandı")
                else:
                    self.tool_message.emit("⚠️ Offset hesaplanamadı")

            self._reset()

    def on_move(self, point):
        if self._step == 2 and self.preview_rb:
            geom = self.selected_feature.geometry()
            left = offset_geometry(geom, self.distance, "left")
            right = offset_geometry(geom, self.distance, "right")

            self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            best = None
            if left and right:
                d_left = left.distance(QgsGeometry.fromPointXY(point))
                d_right = right.distance(QgsGeometry.fromPointXY(point))
                best = left if d_left < d_right else right
            elif left:
                best = left
            elif right:
                best = right

            if best:
                self.preview_rb.setToGeometry(best)
