# -*- coding: utf-8 -*-
"""PlanX CAD Multi-Offset tool.

Allows offsetting selected lines/polylines multiple times with custom distances and side settings.
"""
from __future__ import annotations

import math
from contextlib import suppress

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QFormLayout
)
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsWkbTypes, QgsFeature, QgsProject
)
from .tool_base import tool_base
from ..core.sketcher_utils import offset_geometry
from ..urban.crs_utils import local_metric_crs, transform_geometry, transform_point


class MultiOffsetDialog(QDialog):
    """Dialog for entering multiple offset distances and side selection."""

    def __init__(self, parent=None, last_distances="3.0, 6.0", last_side=2):
        super().__init__(parent)
        self.setWindowTitle("Multi-Offset")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._last_distances = last_distances
        self._last_side = last_side
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Multi-Offset Parameters")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self.txt_distances = QLineEdit()
        self.txt_distances.setText(self._last_distances)
        self.txt_distances.setPlaceholderText("e.g. 3.0, 6.0, 9.0")
        self.txt_distances.setToolTip("Enter comma-separated distances")
        form.addRow("Distances (m):", self.txt_distances)

        self.cmb_side = QComboBox()
        self.cmb_side.addItems([
            "Left",
            "Right",
            "Both",
            "Pick Side on Canvas"
        ])
        self.cmb_side.setCurrentIndex(self._last_side)
        form.addRow("Direction:", self.cmb_side)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok = QPushButton("✅ Apply")
        ok.setMinimumHeight(34)
        ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; font-weight: bold;"
            " border-radius: 4px; padding: 6px 16px; }"
            "QPushButton:hover { background: #283593; }"
        )
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setMinimumHeight(34)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def params(self) -> dict:
        return {
            "distances": self.txt_distances.text(),
            "side": self.cmb_side.currentIndex()
        }


class tool_multi_offset(tool_base):
    """Offsets selected line features multiple times simultaneously."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.distances_str = "3.0, 6.0"
        self.side_mode = 2  # default: Both
        self.parsed_distances: list[float] = []

    def tool_name(self):
        return "Multi-Offset"

    def activate(self):
        super().activate()
        self.parsed_distances = []
        self.tool_message.emit("🔧 Multi-Offset — Select a line to offset")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Multi-Offset — Geometry is empty")
            self._reset()
            return

        if geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Multi-Offset — Only line features can be offset")
            self._reset()
            return

        # Open dialog
        dlg = MultiOffsetDialog(self.iface.mainWindow(), self.distances_str, self.side_mode)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.tool_message.emit("⚠️ Multi-Offset — Cancelled")
            self._reset()
            return

        params = dlg.params()
        self.distances_str = params["distances"]
        self.side_mode = params["side"]

        # Parse distances
        raw_vals = [x.strip() for x in self.distances_str.split(",") if x.strip()]
        parsed = []
        for val in raw_vals:
            with suppress(ValueError):
                parsed.append(abs(float(val)))

        if not parsed:
            self.tool_message.emit("⚠️ Multi-Offset — Enter at least one valid distance")
            self._reset()
            return

        self.parsed_distances = parsed

        if self.side_mode == 0:  # Left
            self._apply_offsets(layer, feature, geom, "left")
            self._reset()
        elif self.side_mode == 1:  # Right
            self._apply_offsets(layer, feature, geom, "right")
            self._reset()
        elif self.side_mode == 2:  # Both
            self._apply_offsets(layer, feature, geom, "both")
            self._reset()
        else:  # Clicked Side
            self._step = 2
            self.tool_message.emit(
                "🔧 Multi-Offset — Move the pointer to choose a side, then click"
            )

    def _apply_offsets(self, layer, feature, geom, side):
        metric_crs, metric_geom = self._metric_geometry(geom, layer)
        if metric_geom is None:
            self.tool_message.emit("⚠️ Multi-Offset — Valid source CRS required")
            return
        offset_geoms = []
        if side in ("left", "both"):
            for dist in self.parsed_distances:
                offset_g = offset_geometry(metric_geom, dist, "left")
                if offset_g and not offset_g.isEmpty():
                    offset_geoms.append(offset_g)
        if side in ("right", "both"):
            for dist in self.parsed_distances:
                offset_g = offset_geometry(metric_geom, dist, "right")
                if offset_g and not offset_g.isEmpty():
                    offset_geoms.append(offset_g)

        offset_geoms = [
            transform_geometry(offset_g, metric_crs, layer.crs())
            for offset_g in offset_geoms
        ]
        offset_geoms = [
            offset_g for offset_g in offset_geoms
            if offset_g is not None and not offset_g.isEmpty()
        ]

        if not offset_geoms:
            self.tool_message.emit("⚠️ Multi-Offset — Failed to generate offset geometry")
            return

        added = self._add_features(layer, offset_geoms, feature)
        if not added:
            return
        self.tool_message.emit(
            f"✅ Multi-Offset — Added {len(added)} parallel lines"
        )

    def _get_closer_side(self, geom, point) -> str:
        if not self.parsed_distances:
            return "left"
        metric_crs, metric_geom = self._metric_geometry(geom, self.selected_layer)
        if metric_geom is None:
            return "left"
        metric_point = transform_point(point, self.selected_layer.crs(), metric_crs)
        test_dist = self.parsed_distances[0]
        left_geom = offset_geometry(metric_geom, test_dist, "left")
        right_geom = offset_geometry(metric_geom, test_dist, "right")

        click_geom = QgsGeometry.fromPointXY(metric_point)
        d_left = left_geom.distance(click_geom) if left_geom else float('inf')
        d_right = right_geom.distance(click_geom) if right_geom else float('inf')

        return "left" if d_left < d_right else "right"

    def on_move(self, point):
        if self._step == 2 and self.preview_rb and self.selected_feature:
            geom = self.selected_feature.geometry()
            closer_side = self._get_closer_side(geom, point)
            metric_crs, metric_geom = self._metric_geometry(
                geom, self.selected_layer
            )
            if metric_geom is None:
                return

            offset_geoms = []
            for dist in self.parsed_distances:
                offset_g = offset_geometry(metric_geom, dist, closer_side)
                if offset_g and not offset_g.isEmpty():
                    display_geom = transform_geometry(
                        offset_g, metric_crs, self.selected_layer.crs()
                    )
                    if display_geom is not None and not display_geom.isEmpty():
                        offset_geoms.append(display_geom)

            self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)
            if offset_geoms:
                combined = QgsGeometry.collectGeometry(offset_geoms)
                self.preview_rb.setToGeometry(combined, self.selected_layer)

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            geom = self.selected_feature.geometry()
            closer_side = self._get_closer_side(geom, point)
            self._apply_offsets(self.selected_layer, self.selected_feature, geom, closer_side)
            self._reset()

    @staticmethod
    def _metric_geometry(geometry, layer):
        if layer is None or not layer.crs().isValid():
            return None, None
        centroid = geometry.centroid()
        if centroid is None or centroid.isEmpty():
            return None, None
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer.crs())
        return metric_crs, transform_geometry(geometry, layer.crs(), metric_crs)
