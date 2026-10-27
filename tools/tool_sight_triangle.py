# -*- coding: utf-8 -*-
"""PlanX CAD Sight Triangle: the visibility splay at a street corner."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes

from .urban_tool_base import urban_output_tool
from ..core.tool_options import FLOAT, OptionSpec
from ..urban.urban_geometry import sight_triangle


class tool_sight_triangle(urban_output_tool):
    """Pick two curb lines on the corner's arms to draw its sight triangle.

    The corner is where the curb lines meet, or would meet when the corner is
    rounded. Each leg runs from that corner along the line toward the point
    you clicked on it. Output: ``planx_sight_triangle``.
    """

    INLINE_OPTIONS = (
        OptionSpec("leg_a", "First leg (m)", FLOAT, 10.0, 0.1, 1000.0, 2, " m",
                   tooltip="Measured along the first line from the corner"),
        OptionSpec("leg_b", "Second leg (m)", FLOAT, 10.0, 0.1, 1000.0, 2, " m",
                   tooltip="Measured along the second line from the corner"),
    )

    FIELDS = [("leg_a_m", "double"), ("leg_b_m", "double"), ("area_m2", "double")]

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.leg_a = 10.0
        self.leg_b = 10.0
        self.first_layer = None
        self.first_feature = None
        self.first_point = None

    def tool_name(self):
        return "Sight Triangle"

    def activate(self):
        super().activate()
        self._start("Pick the first curb line on one arm of the corner")

    def on_entity_selected(self, layer, feature, point):
        if feature.geometry().type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Sight Triangle — Pick a line")
            self._reset()
            return
        self.first_layer = layer
        self.first_feature = feature
        self.first_point = point
        self._step = 2
        self.tool_message.emit("Sight Triangle — Pick the second curb line on the other arm")

    def on_click(self, point, button):
        if self._step != 2 or button != Qt.MouseButton.LeftButton:
            return
        result = self._pick_feature(
            self.canvas.mouseLastXY(), exclude=(self.first_layer, self.first_feature)
        )
        if not result:
            self.tool_message.emit("⚠️ Sight Triangle — Second line not found")
            return
        layer, feature = result
        if feature.geometry().type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Sight Triangle — Pick a line")
            return
        # ``point`` is in the first layer's CRS; re-derive it for this layer.
        canvas_point = self.toMapCoordinates(self.canvas.mouseLastXY())
        self._create(layer, feature, self.to_layer_coordinates(canvas_point, layer))

    def _create(self, layer, feature, point):
        crs = self.first_layer.crs()
        metric_crs = self._metric_crs_for(self.first_point, crs)
        if metric_crs is None or not layer.crs().isValid():
            self.tool_message.emit("⚠️ Sight Triangle — Both layers need a valid CRS")
            self._reset()
            return
        triangle, _corner = sight_triangle(
            self._to_metric(self.first_feature.geometry(), crs, metric_crs),
            self._point_to_metric(self.first_point, crs, metric_crs),
            self._to_metric(feature.geometry(), layer.crs(), metric_crs),
            self._point_to_metric(point, layer.crs(), metric_crs),
            self.leg_a, self.leg_b,
        )
        if triangle is None:
            self.tool_message.emit("⚠️ Sight Triangle — The two lines are parallel")
            self._reset()
            return
        written = self._write("planx_sight_triangle", crs, self.FIELDS, [(
            self._from_metric(triangle, metric_crs, crs),
            {"leg_a_m": self.leg_a, "leg_b_m": self.leg_b, "area_m2": round(triangle.area(), 2)},
        )])
        if written is None:
            self.tool_message.emit("⚠️ Sight Triangle — The output layer could not be written")
        else:
            self.tool_message.emit(
                f"✅ Sight Triangle — {self.leg_a:g} m × {self.leg_b:g} m, "
                f"{triangle.area():,.1f} m² added to planx_sight_triangle"
            )
        self._reset()

    def _reset(self):
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        super()._reset()
        self.tool_message.emit("Sight Triangle — Pick the first curb line on one arm of the corner")
