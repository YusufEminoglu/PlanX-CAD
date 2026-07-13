# -*- coding: utf-8 -*-
"""planX CAD — Linear Dimension tool.

Pick two points (with snap). The tool creates:
  - A dimension line between them on a dedicated `planx_dimensions` layer
    (auto-created on first use), with the measured distance stored in a
    `distance_m` attribute and the label string in `label`.
  - Output is a memory layer by default; user can save the layer to disk
    via the standard QGIS save-as workflow.
"""
from __future__ import annotations

import math
from contextlib import suppress

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband,
    cleanup_sketcher_rubberband,
    COLOR_ACCENT,
)
from ..core.sketcher_layer_utils import get_or_create_layer, add_feature_to_layer


def _format_distance(meters: float) -> str:
    if meters >= 1000:
        return f"{meters / 1000:.3f} km"
    return f"{meters:.2f} m"


class tool_dimension(QgsMapTool):
    """Linear distance dimension between two clicked points."""

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.first_point: QgsPointXY | None = None
        self.preview_rb = None
        self._dim_count = 0

    def tool_name(self):
        return "Dimension"

    def activate(self):
        super().activate()
        self.first_point = None
        self.preview_rb = create_preview_rubberband(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        if self.preview_rb is not None:
            self.preview_rb.setColor(COLOR_ACCENT)
            self.preview_rb.setWidth(2)
        self.tool_message.emit("📏 Dimension — click the first point")

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        self.first_point = None
        super().deactivate()

    # ───────────────────────── Event handlers ─────────────────────────

    def canvasPressEvent(self, event):
        point = self._snapped_point(event)
        if event.button() == Qt.MouseButton.LeftButton:
            if self.first_point is None:
                self.first_point = point
                self.tool_message.emit("📏 Dimension — click the second point")
            else:
                self._commit_dimension(self.first_point, point)
                self.first_point = None
        elif event.button() == Qt.MouseButton.RightButton:
            self.first_point = None
            self.tool_message.emit(f"📏 Dimension — reset ({self._dim_count} so far)")

    def canvasMoveEvent(self, event):
        if self.first_point is None or self.preview_rb is None:
            return
        point = self._snapped_point(event)
        self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.preview_rb.addPoint(self.first_point)
        self.preview_rb.addPoint(point)
        live = _format_distance(self._measure(self.first_point, point))
        self.tool_message.emit(f"📏 Dimension — live: {live}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.first_point = None
            if self.preview_rb is not None:
                self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self.tool_message.emit("📏 Dimension — cancelled")

    # ───────────────────────── Helpers ─────────────────────────

    def _snapped_point(self, event) -> QgsPointXY:
        point = self.toMapCoordinates(event.pos())
        snapper = self.canvas.snappingUtils()
        if snapper is not None:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                return match.point()
        return point

    def _measure(self, a: QgsPointXY, b: QgsPointXY) -> float:
        da = QgsDistanceArea()
        crs = QgsProject.instance().crs()
        if crs.isValid():
            da.setSourceCrs(crs, QgsProject.instance().transformContext())
            ellipsoid = QgsProject.instance().ellipsoid()
            if ellipsoid:
                da.setEllipsoid(ellipsoid)
        return da.measureLine(a, b)

    def _commit_dimension(self, a: QgsPointXY, b: QgsPointXY) -> None:
        distance_m = self._measure(a, b)
        label = _format_distance(distance_m)

        layer = get_or_create_layer(
            "planx_dimensions",
            geom_type="LineString",
            fields=[
                ("distance_m", "double"),
                ("label", "string"),
                ("from_x", "double"),
                ("from_y", "double"),
                ("to_x", "double"),
                ("to_y", "double"),
            ],
        )
        if layer is None:
            self.tool_message.emit("⚠️ Dimension — could not create layer")
            return

        feat = add_feature_to_layer(
            layer,
            QgsGeometry.fromPolylineXY([a, b]),
            {
                "distance_m": distance_m,
                "label": label,
                "from_x": a.x(),
                "from_y": a.y(),
                "to_x": b.x(),
                "to_y": b.y(),
            },
        )
        if feat is None:
            self.tool_message.emit("⚠️ Dimension — feature could not be saved")
            return
        layer.triggerRepaint()

        # Auto-enable feature labels showing `label` once.
        if layer.customProperty("planx_dim_labels_applied") != "yes":
            settings = layer.labeling()
            # Labeling is a nice-to-have; never block the dimension itself.
            with suppress(Exception):
                from qgis.core import (
                    QgsPalLayerSettings,
                    QgsTextFormat,
                    QgsVectorLayerSimpleLabeling,
                )
                pal = QgsPalLayerSettings()
                pal.fieldName = "label"
                pal.enabled = True
                fmt = QgsTextFormat()
                fmt.setSize(10)
                fmt.setColor(QColor("#1a237e"))
                pal.setFormat(fmt)
                layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
                layer.setLabelsEnabled(True)
                layer.setCustomProperty("planx_dim_labels_applied", "yes")

        self._dim_count += 1
        self.tool_message.emit(
            f"✅ Dimension #{self._dim_count} — {label} | continue or right-click to reset"
        )
