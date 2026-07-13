# -*- coding: utf-8 -*-
"""PlanX CAD Fillet tool for tangent rounding between two lines."""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_feedback import create_preview_rubberband, COLOR_ACCENT
from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point
from ..urban.crs_utils import local_metric_crs, transform_geometry


class tool_fillet(tool_base):
    """Create a tangent arc between two intersecting lines.

    1. Enter radius | 2. Select first line | 3. Select second line
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.radius = 2.0
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._activation_cancelled = False

    def tool_name(self):
        return "Fillet"

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        r, ok = QInputDialog.getDouble(
            self.iface.mainWindow(), "Fillet", "Fillet radius (m):",
            self.radius, 0.01, 10000.0, 2
        )
        if ok:
            self.radius = r
        else:
            self._activation_cancelled = True
            self.tool_message.emit("⌒ Fillet — Cancelled")
            return
        self.first_layer = None
        self.first_feature = None
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius} m) — Select the first line"
        )

    def on_entity_selected(self, layer, feature, point):
        # The first line is selected.
        self.first_layer = layer
        self.first_feature = feature
        self.first_point = point
        self._step = 2
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius} m) — Select the second line"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # Exclude the first line; a feature cannot fillet against itself.
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.first_layer, self.first_feature),
            )
            if result:
                layer, feature = result
                self._do_fillet(layer, feature, point)
            else:
                self.tool_message.emit("⚠️ Fillet — Second feature not found")
            self._cleanup_fillet()

    def _do_fillet(self, second_layer, second_feature, point):
        """Apply a metric fillet between two line features."""
        metric_crs, fillet_result = self._metric_fillet_result(
            self.first_feature.geometry(), self.first_layer,
            second_feature.geometry(), second_layer,
        )
        if metric_crs is None or not fillet_result:
            self.tool_message.emit("⚠️ Fillet — CRS transformation failed")
            return

        arc_geom = fillet_result['arc']
        tp1 = fillet_result['tp1']
        tp2 = fillet_result['tp2']
        inter_pt = fillet_result.get('inter_pt')
        metric_geom1 = transform_geometry(
            self.first_feature.geometry(), self.first_layer.crs(), metric_crs
        )
        metric_geom2 = transform_geometry(
            second_feature.geometry(), second_layer.crs(), metric_crs
        )

        new_geom1 = transform_geometry(
            trim_line_to_point(metric_geom1, tp1, inter_pt),
            metric_crs, self.first_layer.crs(),
        )
        new_geom2 = transform_geometry(
            trim_line_to_point(metric_geom2, tp2, inter_pt),
            metric_crs, second_layer.crs(),
        )
        arc_geom = transform_geometry(
            arc_geom, metric_crs, self.first_layer.crs()
        )
        if any(
            geom is None or geom.isEmpty()
            for geom in (new_geom1, new_geom2, arc_geom)
        ):
            self.tool_message.emit("⚠️ Fillet — No valid result geometry was created")
            return

        new_geom1 = self._coerce_for_layer(new_geom1, self.first_layer)
        new_geom2 = self._coerce_for_layer(new_geom2, second_layer)
        arc_geom = self._coerce_for_layer(arc_geom, self.first_layer)
        layers = []
        for layer in (self.first_layer, second_layer):
            if layer not in layers:
                layers.append(layer)
        for layer in layers:
            layer.beginEditCommand("PlanX CAD: fillet")

        arc_feature = QgsFeature(self.first_layer.fields())
        arc_feature.setGeometry(arc_geom)
        for index in range(self.first_layer.fields().count()):
            arc_feature.setAttribute(index, self.first_feature.attribute(index))

        success = (
            self.first_layer.changeGeometry(self.first_feature.id(), new_geom1)
            and second_layer.changeGeometry(second_feature.id(), new_geom2)
            and self.first_layer.addFeature(arc_feature)
        )
        if not success:
            for layer in reversed(layers):
                layer.destroyEditCommand()
            self.tool_message.emit(
                "⚠️ Fillet — Layer write failed; all changes were rolled back"
            )
            return
        for layer in layers:
            layer.endEditCommand()
            layer.triggerRepaint()
        self.tool_message.emit(
            f"✅ Fillet (R={self.radius} m) — Applied successfully"
        )

    def _metric_fillet_result(self, geom1, layer1, geom2, layer2):
        if not layer1.crs().isValid() or not layer2.crs().isValid():
            return None, None
        centroid = geom1.centroid()
        if centroid is None or centroid.isEmpty():
            return None, None
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer1.crs())
        metric_geom1 = transform_geometry(geom1, layer1.crs(), metric_crs)
        metric_geom2 = transform_geometry(geom2, layer2.crs(), metric_crs)
        if (metric_geom1 is None or metric_geom1.isEmpty() or
                metric_geom2 is None or metric_geom2.isEmpty()):
            return None, None
        return metric_crs, create_fillet_and_trims(
            metric_geom1, metric_geom2, self.radius
        )

    @staticmethod
    def _coerce_for_layer(geometry, layer):
        geometry = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
            geometry.convertToMultiType()
        return geometry

    def on_move(self, point):
        """Detect the second line under the cursor and update the preview."""
        if self._step != 2:
            return

        # Recreate the rubber band after a cleanup so previews remain visible.
        if self.preview_rb is None:
            self.preview_rb = create_preview_rubberband(self.canvas)
        self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)

        pos = self.canvas.mouseLastXY()
        result = self._pick_feature(
            pos, exclude=(self.first_layer, self.first_feature)
        )
        if not result:
            return
        layer, feature = result
        metric_crs, fillet_result = self._metric_fillet_result(
            self.first_feature.geometry(), self.first_layer,
            feature.geometry(), layer,
        )
        if not fillet_result:
            return
        arc_geom = transform_geometry(
            fillet_result['arc'], metric_crs, self.first_layer.crs()
        )
        if arc_geom and not arc_geom.isEmpty():
            # Use a strong dashed accent so the preview remains visible.
            self.preview_rb.setColor(COLOR_ACCENT)
            self.preview_rb.setWidth(3)
            self.preview_rb.setLineStyle(Qt.PenStyle.DashLine)
            self.preview_rb.setToGeometry(arc_geom, self.first_layer)
            self.preview_rb.show()

    def _cleanup_fillet(self):
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._reset()
