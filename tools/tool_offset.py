# -*- coding: utf-8 -*-
"""PlanX CAD Offset tool."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_utils import offset_geometry
from ..core.sketcher_feedback import create_preview_rubberband, cleanup_sketcher_rubberband
from ..urban.crs_utils import local_metric_crs, transform_geometry, transform_point


class tool_offset(tool_base):
    """Create a parallel copy at a specified metric distance."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.distance = 5.0

    def tool_name(self):
        return "Offset"

    def on_entity_selected(self, layer, feature, point):
        # Ask for the offset distance.
        d, ok = QInputDialog.getDouble(
            self.iface.mainWindow(), "Offset", "Offset distance (m):",
            self.distance, 0.01, 100000.0, 2
        )
        if ok:
            self.distance = d
            self.tool_message.emit(
                f"🔧 Offset ({self.distance} m) — Click the side to offset"
            )
            self._step = 2

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            geom = self.selected_feature.geometry()
            metric_crs, metric_geom = self._metric_geometry(geom)
            if metric_geom is None:
                self.tool_message.emit("⚠️ Offset — A valid source CRS is required")
                self._reset()
                return
            metric_point = transform_point(
                point, self.selected_layer.crs(), metric_crs
            )
            closest = metric_geom.nearestPoint(
                QgsGeometry.fromPointXY(metric_point)
            )
            if closest:
                # Build both sides and choose the one nearest the click.
                left = offset_geometry(metric_geom, self.distance, "left")
                right = offset_geometry(metric_geom, self.distance, "right")

                use_geom = None
                if left and right:
                    click_geom = QgsGeometry.fromPointXY(metric_point)
                    d_left = left.distance(click_geom)
                    d_right = right.distance(click_geom)
                    use_geom = left if d_left < d_right else right
                elif left:
                    use_geom = left
                elif right:
                    use_geom = right

                if use_geom:
                    use_geom = transform_geometry(
                        use_geom, metric_crs, self.selected_layer.crs()
                    )
                    added = self._add_feature(
                        self.selected_layer, use_geom, self.selected_feature
                    )
                    if added is not None:
                        self.tool_message.emit("✅ Offset — Completed")
                else:
                    self.tool_message.emit("⚠️ Offset could not be calculated")

            self._reset()

    def on_move(self, point):
        if self._step == 2 and self.preview_rb:
            geom = self.selected_feature.geometry()
            metric_crs, metric_geom = self._metric_geometry(geom)
            if metric_geom is None:
                return
            metric_point = transform_point(
                point, self.selected_layer.crs(), metric_crs
            )
            left = offset_geometry(metric_geom, self.distance, "left")
            right = offset_geometry(metric_geom, self.distance, "right")

            self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            best = None
            if left and right:
                click_geom = QgsGeometry.fromPointXY(metric_point)
                d_left = left.distance(click_geom)
                d_right = right.distance(click_geom)
                best = left if d_left < d_right else right
            elif left:
                best = left
            elif right:
                best = right

            if best:
                best = transform_geometry(
                    best, metric_crs, self.selected_layer.crs()
                )
                self.preview_rb.setToGeometry(best, self.selected_layer)

    def _metric_geometry(self, geometry):
        centroid = geometry.centroid()
        layer_crs = self.selected_layer.crs() if self.selected_layer else None
        if (centroid is None or centroid.isEmpty() or layer_crs is None or
                not layer_crs.isValid()):
            return None, None
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer_crs)
        return metric_crs, transform_geometry(geometry, layer_crs, metric_crs)
