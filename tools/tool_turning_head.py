# -*- coding: utf-8 -*-
"""PlanX CAD Turning Head: a cul-de-sac bulb at a road end."""

from qgis.core import QgsWkbTypes

from .urban_tool_base import urban_output_tool
from ..core.tool_options import FLOAT, OptionSpec
from ..urban.urban_geometry import turning_head


class tool_turning_head(urban_output_tool):
    """Pick a road centreline near the end that needs a turning head.

    A turning circle is centred on that end and joined to the carriageway by
    straight tapers. Output: ``planx_turning_head``.
    """

    INLINE_OPTIONS = (
        OptionSpec("radius", "Turning radius (m)", FLOAT, 10.0, 3.0, 100.0, 2, " m",
                   tooltip="Radius of the turning circle, to the kerb"),
        OptionSpec("road_width", "Road width (m)", FLOAT, 7.0, 2.0, 50.0, 2, " m",
                   tooltip="Carriageway width the tapers start from"),
        OptionSpec("taper_length", "Taper length (m)", FLOAT, 12.0, 0.0, 200.0, 2, " m",
                   tooltip="How far back along the road the widening starts"),
    )

    FIELDS = [("radius_m", "double"), ("road_width_m", "double"), ("area_m2", "double")]

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.radius = 10.0
        self.road_width = 7.0
        self.taper_length = 12.0

    def tool_name(self):
        return "Turning Head"

    def activate(self):
        super().activate()
        self._start("Pick a road centreline near its end")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty() or geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Turning Head — Pick a road centreline")
            self._reset()
            return
        metric_crs = self._metric_crs_for(point, layer.crs())
        if metric_crs is None:
            self.tool_message.emit("⚠️ Turning Head — The line layer needs a valid CRS")
            self._reset()
            return
        bulb, _end = turning_head(
            self._to_metric(geom, layer.crs(), metric_crs),
            self._point_to_metric(point, layer.crs(), metric_crs),
            self.radius, self.road_width, self.taper_length,
        )
        if bulb is None:
            self.tool_message.emit("⚠️ Turning Head — The road end has no direction")
            self._reset()
            return
        written = self._write("planx_turning_head", layer.crs(), self.FIELDS, [(
            self._from_metric(bulb, metric_crs, layer.crs()),
            {"radius_m": self.radius, "road_width_m": self.road_width,
             "area_m2": round(bulb.area(), 2)},
        )])
        if written is None:
            self.tool_message.emit("⚠️ Turning Head — The output layer could not be written")
        else:
            self.tool_message.emit(
                f"✅ Turning Head — R {self.radius:g} m, {bulb.area():,.1f} m² added to planx_turning_head"
            )
        self._reset()

    def _reset(self):
        super()._reset()
        self.tool_message.emit("Turning Head — Pick a road centreline near its end")
