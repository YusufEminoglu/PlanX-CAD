# -*- coding: utf-8 -*-
"""PlanX CAD Roundabout: concentric roundabout parts at a clicked centre."""

from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsRectangle, QgsVectorLayer, QgsWkbTypes,
)

from .urban_tool_base import urban_output_tool
from ..core.tool_options import BOOL, FLOAT, OptionSpec
from ..urban.urban_geometry import approach_directions, roundabout_parts, splitter_island


class tool_roundabout(urban_output_tool):
    """Click the junction centre (snapping helps) to lay out a roundabout.

    Draws the circulatory carriageway, an optional truck apron and the
    central island. When the active layer is a line layer, every line that
    crosses the outer kerb gets a splitter island on its approach. Output:
    ``planx_roundabout`` with a ``part`` field.
    """

    _SPLIT = ("splitters", True)
    INLINE_OPTIONS = (
        OptionSpec("outer_radius", "Outer radius (m)", FLOAT, 18.0, 5.0, 200.0, 2, " m",
                   tooltip="Inscribed circle radius, measured to the outer kerb"),
        OptionSpec("lane_width", "Circulatory width (m)", FLOAT, 6.0, 3.0, 30.0, 2, " m"),
        OptionSpec("apron_width", "Truck apron (m)", FLOAT, 1.5, 0.0, 10.0, 2, " m",
                   tooltip="Mountable ring inside the carriageway; 0 leaves it out"),
        OptionSpec("splitters", "Splitter islands", BOOL, True,
                   tooltip="One per line of the active layer that crosses the outer kerb"),
        OptionSpec("splitter_length", "Island length (m)", FLOAT, 12.0, 1.0, 100.0, 2, " m",
                   visible_when=_SPLIT),
        OptionSpec("splitter_width", "Island base width (m)", FLOAT, 3.0, 0.5, 20.0, 2, " m",
                   visible_when=_SPLIT),
    )

    FIELDS = [("part", "string"), ("radius_m", "double"), ("width_m", "double")]

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.outer_radius = 18.0
        self.lane_width = 6.0
        self.apron_width = 1.5
        self.splitters = True
        self.splitter_length = 12.0
        self.splitter_width = 3.0

    def tool_name(self):
        return "Roundabout"

    def activate(self):
        super().activate()
        self._step = 1  # every click is a centre; nothing to pick first
        self._start("Click the junction centre")

    def _reset(self):
        super()._reset()
        self._step = 1
        self.tool_message.emit("Roundabout — Click the junction centre")

    def _approach_lines(self, center, crs, metric_crs):
        """Active-layer lines near the centre, in the metric CRS."""
        layer = self.iface.activeLayer()
        if (not self.splitters or not isinstance(layer, QgsVectorLayer) or
                layer.geometryType() != QgsWkbTypes.GeometryType.LineGeometry):
            return []
        reach = self.outer_radius + 1.0
        metric_box = QgsRectangle(center.x() - reach, center.y() - reach,
                                  center.x() + reach, center.y() + reach)
        box = self._from_metric_box(metric_box, metric_crs, layer.crs())
        lines = []
        for feature in layer.getFeatures(QgsFeatureRequest().setFilterRect(box)):
            geom = self._to_metric(feature.geometry(), layer.crs(), metric_crs)
            if geom is not None and not geom.isEmpty():
                lines.append(geom)
        return lines

    def _from_metric_box(self, box, metric_crs, crs):
        return self._from_metric(QgsGeometry.fromRect(box), metric_crs, crs).boundingBox()

    def on_click(self, point, button):
        if button != Qt.MouseButton.LeftButton:
            return
        crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = self._metric_crs_for(point, crs)
        if metric_crs is None:
            self.tool_message.emit("⚠️ Roundabout — The map needs a valid CRS")
            return
        center = QgsPointXY(self._point_to_metric(point, crs, metric_crs))
        parts = roundabout_parts(center, self.outer_radius, self.lane_width, self.apron_width)
        if not parts:
            self.tool_message.emit(
                "⚠️ Roundabout — Circulatory width and apron leave no central island"
            )
            return
        widths = {"circulatory": self.lane_width, "apron": self.apron_width}
        radii = {
            "circulatory": self.outer_radius,
            "apron": self.outer_radius - self.lane_width,
            "central_island": self.outer_radius - self.lane_width - self.apron_width,
        }
        items = [
            (self._from_metric(geom, metric_crs, crs),
             {"part": name, "radius_m": round(radii[name], 2), "width_m": widths.get(name, 0.0)})
            for name, geom in parts
        ]
        directions = approach_directions(center, self.outer_radius,
                                         self._approach_lines(center, crs, metric_crs))
        for direction in directions:
            island = splitter_island(center, self.outer_radius, direction,
                                     self.splitter_length, self.splitter_width)
            if island is not None:
                items.append((self._from_metric(island, metric_crs, crs), {
                    "part": "splitter_island", "radius_m": self.outer_radius,
                    "width_m": self.splitter_width,
                }))
        if self._write("planx_roundabout", crs, self.FIELDS, items) is None:
            self.tool_message.emit("⚠️ Roundabout — The output layer could not be written")
        else:
            legs = f", {len(directions)} splitter island(s)" if directions else ""
            self.tool_message.emit(
                f"✅ Roundabout — R {self.outer_radius:g} m, carriageway {self.lane_width:g} m{legs}"
            )
        self._reset()
