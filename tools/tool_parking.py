# -*- coding: utf-8 -*-
"""PlanX CAD Parking Layout: stalls along a curb line."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsWkbTypes

from .urban_tool_base import urban_output_tool
from ..core.sketcher_feedback import cleanup_sketcher_rubberband, create_preview_rubberband
from ..core.tool_options import CHOICE, FLOAT, OptionSpec
from ..urban.urban_geometry import parking_bays

# A layout larger than this is almost certainly a mis-pick (a whole road
# network); refuse it rather than freeze QGIS writing it.
MAX_BAYS = 5000


class tool_parking(urban_output_tool):
    """Pick a curb line, then click the side the stalls go on.

    Stalls follow the line segment by segment and never wrap round a bend.
    A preview follows the pointer until the side is chosen. Output:
    ``planx_parking``, one numbered polygon per stall.
    """

    INLINE_OPTIONS = (
        OptionSpec("angle", "Angle", CHOICE, 90,
                   choices=((90, "90° perpendicular"), (60, "60°"), (45, "45°"),
                            (30, "30°"), (0, "Parallel"))),
        OptionSpec("bay_width", "Stall width (m)", FLOAT, 2.5, 1.5, 10.0, 2, " m"),
        OptionSpec("bay_length", "Stall length (m)", FLOAT, 5.0, 2.0, 20.0, 2, " m",
                   tooltip="Along the stall; for parallel parking this runs along the curb"),
        OptionSpec("start_offset", "Start offset (m)", FLOAT, 0.0, 0.0, 1000.0, 2, " m",
                   tooltip="Gap left at the start of each line segment"),
    )

    FIELDS = [
        ("bay_no", "int"),
        ("angle_deg", "int"),
        ("width_m", "double"),
        ("length_m", "double"),
    ]

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.angle = 90
        self.bay_width = 2.5
        self.bay_length = 5.0
        self.start_offset = 0.0
        self._metric_crs = None
        self._metric_line = None

    def tool_name(self):
        return "Parking Layout"

    def activate(self):
        super().activate()
        self._start("Pick the curb line")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty() or geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Parking Layout — Pick a line")
            self._reset()
            return
        self._metric_crs = self._metric_crs_for(point, layer.crs())
        if self._metric_crs is None:
            self.tool_message.emit("⚠️ Parking Layout — The line layer needs a valid CRS")
            self._reset()
            return
        self._metric_line = self._to_metric(geom, layer.crs(), self._metric_crs)
        self._step = 2
        # The base preview band draws lines; stalls need a filled polygon band.
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = create_preview_rubberband(self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.tool_message.emit("Parking Layout — Move to the side for the stalls, then click")

    def _bays(self, point):
        side = self._point_to_metric(point, self.selected_layer.crs(), self._metric_crs)
        return parking_bays(self._metric_line, side, self.angle, self.bay_width,
                            self.bay_length, self.start_offset)

    def on_move(self, point):
        if self._step != 2 or self._metric_line is None or self.preview_rb is None:
            return
        bays = self._bays(point)[:MAX_BAYS]
        if not bays:
            self.preview_rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            return
        preview = self._from_metric(QgsGeometry.collectGeometry(bays), self._metric_crs,
                                    self.selected_layer.crs())
        self.preview_rb.setToGeometry(preview, self.selected_layer)

    def on_click(self, point, button):
        if self._step != 2 or button != Qt.MouseButton.LeftButton or self._metric_line is None:
            return
        bays = self._bays(point)
        if not bays:
            self.tool_message.emit(
                "⚠️ Parking Layout — No stall fits; the segments are shorter than one stall"
            )
            return
        if len(bays) > MAX_BAYS:
            self.tool_message.emit(
                f"⚠️ Parking Layout — {len(bays):,} stalls exceed the limit of {MAX_BAYS:,}; "
                "pick a shorter line"
            )
            return
        crs = self.selected_layer.crs()
        items = [
            (self._from_metric(bay, self._metric_crs, crs), {
                "bay_no": number,
                "angle_deg": int(self.angle),
                "width_m": self.bay_width,
                "length_m": self.bay_length,
            })
            for number, bay in enumerate(bays, start=1)
        ]
        if self._write("planx_parking", crs, self.FIELDS, items) is None:
            self.tool_message.emit("⚠️ Parking Layout — The output layer could not be written")
        else:
            label = "parallel" if int(self.angle) == 0 else f"{int(self.angle)}°"
            self.tool_message.emit(
                f"✅ Parking Layout — {len(bays)} {label} stalls added to planx_parking"
            )
        self._reset()

    def _reset(self):
        self._metric_crs = None
        self._metric_line = None
        super()._reset()
        self.tool_message.emit("Parking Layout — Pick the curb line")
