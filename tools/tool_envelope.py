# -*- coding: utf-8 -*-
"""PlanX CAD Buildable Envelope: a parcel minus its front, side and rear setbacks."""

from qgis.core import QgsWkbTypes

from .urban_tool_base import urban_output_tool
from ..core.tool_options import BOOL, FLOAT, OptionSpec
from ..urban.urban_geometry import FRONT, REAR, buildable_envelope


class tool_envelope(urban_output_tool):
    """Click a parcel near its front edge to draw its buildable envelope.

    The edge nearest the click is the front; edges parallel to it in the far
    half are rear; the rest are sides. The result goes to ``planx_envelope``
    with the parcel and envelope areas and the largest footprint allowed by
    an optional site-coverage limit.
    """

    INLINE_OPTIONS = (
        OptionSpec("front", "Front setback (m)", FLOAT, 5.0, 0.0, 1000.0, 2, " m"),
        OptionSpec("side", "Side setback (m)", FLOAT, 3.0, 0.0, 1000.0, 2, " m"),
        OptionSpec("rear", "Rear setback (m)", FLOAT, 3.0, 0.0, 1000.0, 2, " m"),
        OptionSpec("corner_parcel", "Corner parcel", BOOL, False,
                   tooltip="Two fronts: click near the street corner; the neighbouring "
                           "edge nearest the click is the second front"),
        OptionSpec("max_coverage", "Max coverage (%)", FLOAT, 0.0, 0.0, 100.0, 1, " %",
                   tooltip="Site coverage limit used for the max footprint; 0 turns it off"),
    )

    FIELDS = [
        ("parcel_area", "double"),
        ("envelope_area", "double"),
        ("buildable_pct", "double"),
        ("max_footprint", "double"),
        ("front_m", "double"),
        ("side_m", "double"),
        ("rear_m", "double"),
    ]

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.front = 5.0
        self.side = 3.0
        self.rear = 3.0
        self.corner_parcel = False
        self.max_coverage = 0.0

    def tool_name(self):
        return "Buildable Envelope"

    def activate(self):
        super().activate()
        self._start("Click a parcel near its front edge")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty() or geom.type() != QgsWkbTypes.GeometryType.PolygonGeometry:
            self.tool_message.emit("⚠️ Buildable Envelope — Pick a parcel polygon")
            self._reset()
            return
        centroid = geom.centroid()
        metric_crs = None
        if centroid is not None and not centroid.isEmpty():
            metric_crs = self._metric_crs_for(centroid.asPoint(), layer.crs())
        if metric_crs is None:
            self.tool_message.emit("⚠️ Buildable Envelope — The parcel layer needs a valid CRS")
            self._reset()
            return
        parcel = self._to_metric(geom, layer.crs(), metric_crs)
        click = self._point_to_metric(point, layer.crs(), metric_crs)
        envelope, edges = buildable_envelope(
            parcel, click, self.front, self.side, self.rear, self.corner_parcel
        )
        if envelope is None:
            self.tool_message.emit(
                "⚠️ Buildable Envelope — These setbacks leave no buildable area"
            )
            self._reset()
            return

        parcel_area = parcel.area()
        envelope_area = envelope.area()
        max_footprint = envelope_area
        if self.max_coverage > 0:
            max_footprint = min(envelope_area, parcel_area * self.max_coverage / 100.0)
        written = self._write("planx_envelope", layer.crs(), self.FIELDS, [(
            self._from_metric(envelope, metric_crs, layer.crs()),
            {
                "parcel_area": round(parcel_area, 2),
                "envelope_area": round(envelope_area, 2),
                "buildable_pct": round(100.0 * envelope_area / parcel_area, 1) if parcel_area else 0.0,
                "max_footprint": round(max_footprint, 2),
                "front_m": self.front,
                "side_m": self.side,
                "rear_m": self.rear,
            },
        )])
        if written is None:
            self.tool_message.emit("⚠️ Buildable Envelope — The output layer could not be written")
        else:
            fronts = sum(1 for *_ab, role in edges if role == FRONT)
            rears = sum(1 for *_ab, role in edges if role == REAR)
            limit = (f"; max footprint {max_footprint:,.1f} m² at {self.max_coverage:g}% coverage"
                     if self.max_coverage > 0 else "")
            self.tool_message.emit(
                f"✅ Buildable Envelope — {envelope_area:,.1f} m² of {parcel_area:,.1f} m² "
                f"({100.0 * envelope_area / parcel_area:.0f}%), {fronts} front / {rears} rear edge(s)"
                f"{limit}"
            )
        self._reset()

    def _reset(self):
        super()._reset()
        self.tool_message.emit("Buildable Envelope — Click a parcel near its front edge")
