# -*- coding: utf-8 -*-
"""planX CAD â€” Array (Rectangular + Polar) tool.

Pick one feature, choose a mode + parameters in a dialog, see a live preview,
then commit: the source feature is duplicated N times along a grid or around a
center point. Attributes are copied; geometries are translated/rotated via the
core sketcher_utils helpers (multipart-safe).
"""
from __future__ import annotations

import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.sketcher_utils import rotate_geometry


class ArrayDialog(QDialog):
    """Dialog asking the user for rectangular or polar array parameters."""

    MODE_RECT = 0
    MODE_POLAR = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("â¹ Array")
        self.setMinimumWidth(340)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("â¹ Array Parameters")
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Rectangular (rows Ã— cols)", "Polar (around center)"])
        layout.addWidget(self.cmb_mode)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._rect_page())
        self.pages.addWidget(self._polar_page())
        layout.addWidget(self.pages)
        self.cmb_mode.currentIndexChanged.connect(self.pages.setCurrentIndex)

        btn_row = QHBoxLayout()
        ok = QPushButton("âœ… Generate")
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

    def _rect_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.spn_rows = QSpinBox()
        self.spn_rows.setRange(1, 500)
        self.spn_rows.setValue(3)
        form.addRow("Rows:", self.spn_rows)

        self.spn_cols = QSpinBox()
        self.spn_cols.setRange(1, 500)
        self.spn_cols.setValue(3)
        form.addRow("Columns:", self.spn_cols)

        self.spn_dx = QDoubleSpinBox()
        self.spn_dx.setRange(-1e6, 1e6)
        self.spn_dx.setValue(10.0)
        self.spn_dx.setSuffix(" m")
        self.spn_dx.setDecimals(2)
        form.addRow("Î”x (column spacing):", self.spn_dx)

        self.spn_dy = QDoubleSpinBox()
        self.spn_dy.setRange(-1e6, 1e6)
        self.spn_dy.setValue(10.0)
        self.spn_dy.setSuffix(" m")
        self.spn_dy.setDecimals(2)
        form.addRow("Î”y (row spacing):", self.spn_dy)
        return w

    def _polar_page(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.spn_count = QSpinBox()
        self.spn_count.setRange(2, 360)
        self.spn_count.setValue(6)
        form.addRow("Number of copies:", self.spn_count)

        self.spn_sweep = QDoubleSpinBox()
        self.spn_sweep.setRange(-360.0, 360.0)
        self.spn_sweep.setValue(360.0)
        self.spn_sweep.setSuffix(" Â°")
        self.spn_sweep.setDecimals(1)
        form.addRow("Total sweep angle:", self.spn_sweep)

        note = QLabel("Click the array center on the canvas after pressing Generate.")
        note.setStyleSheet("color: #64748b; font-style: italic;")
        note.setWordWrap(True)
        form.addRow(note)
        return w

    def params(self) -> dict:
        mode = self.cmb_mode.currentIndex()
        if mode == self.MODE_RECT:
            return {
                "mode": "rect",
                "rows": self.spn_rows.value(),
                "cols": self.spn_cols.value(),
                "dx": self.spn_dx.value(),
                "dy": self.spn_dy.value(),
            }
        return {
            "mode": "polar",
            "count": self.spn_count.value(),
            "sweep": self.spn_sweep.value(),
        }


class tool_array(tool_base):
    """Array map tool.

    Rectangular: select feature -> dialog -> N copies created immediately.
    Polar: select feature -> dialog -> click center -> N copies created.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.params: dict | None = None

    def tool_name(self):
        return "Array"

    def on_entity_selected(self, layer, feature, point):
        dlg = ArrayDialog(self.iface.mainWindow())
        if dlg.exec() != QDialog.Accepted:
            self.tool_message.emit("â¹ Array â€” cancelled")
            self._reset()
            return
        self.params = dlg.params()
        if self.params["mode"] == "rect":
            self._do_rectangular(layer, feature)
            self._reset()
        else:
            self._step = 2
            self.tool_message.emit("â¹ Array (polar) â€” click the center point")

    def on_click(self, point, button):
        if self._step == 2 and self.params and self.params["mode"] == "polar" and button == Qt.MouseButton.LeftButton:
            self._do_polar(self.selected_layer, self.selected_feature, point)
            self._reset()

    def on_move(self, point):
        if self._step == 2 and self.params and self.preview_rb and self.selected_feature:
            self._render_polar_preview(point)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Rectangular â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _do_rectangular(self, layer, feature):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("âš ï¸ Array â€” empty source geometry")
            return

        rows, cols = self.params["rows"], self.params["cols"]
        dx, dy = self.params["dx"], self.params["dy"]
        n_added = 0
        for r in range(rows):
            for c in range(cols):
                if r == 0 and c == 0:
                    continue  # source kept in place
                offset = QgsGeometry(geom)
                offset.translate(c * dx, r * dy)
                self._add_feature(layer, offset, feature)
                n_added += 1
        self.tool_message.emit(f"âœ… Array (rect) â€” {n_added} copies added ({rows}Ã—{cols})")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Polar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _do_polar(self, layer, feature, center: QgsPointXY):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("âš ï¸ Array â€” empty source geometry")
            return

        count = self.params["count"]
        sweep = self.params["sweep"]
        # If sweep is a full circle, do not duplicate at angle=0 (same as source).
        full_circle = abs(abs(sweep) - 360.0) < 1e-3
        steps = count if not full_circle else count
        step_angle = sweep / count if full_circle else sweep / max(count - 1, 1)

        n_added = 0
        for i in range(steps):
            angle = step_angle * (i + 1 if full_circle else i)
            if not full_circle and i == 0:
                continue  # source stays at 0Â°
            rotated = rotate_geometry(geom, center, angle)
            if rotated is not None and not rotated.isEmpty():
                self._add_feature(layer, rotated, feature)
                n_added += 1
        self.tool_message.emit(f"âœ… Array (polar) â€” {n_added} copies around center ({sweep:.0f}Â°)")

    def _render_polar_preview(self, center: QgsPointXY) -> None:
        """Show all rotated copies as a single preview rubberband."""
        if not self.params:
            return
        geom = self.selected_feature.geometry()
        if geom is None or geom.isEmpty():
            return
        count = self.params["count"]
        sweep = self.params["sweep"]
        full_circle = abs(abs(sweep) - 360.0) < 1e-3
        step_angle = sweep / count if full_circle else sweep / max(count - 1, 1)

        # Combine rotated copies into a single geometry collection for the preview.
        pieces = []
        for i in range(count):
            angle = step_angle * (i + 1 if full_circle else i)
            rotated = rotate_geometry(geom, center, angle)
            if rotated is not None and not rotated.isEmpty():
                pieces.append(rotated)
        if not pieces:
            return
        combined = QgsGeometry.unaryUnion(pieces)
        if combined is None or combined.isEmpty():
            return
        self.preview_rb.reset(combined.type())
        self.preview_rb.setToGeometry(combined, None)
