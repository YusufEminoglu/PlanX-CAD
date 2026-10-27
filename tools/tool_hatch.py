# -*- coding: utf-8 -*-
"""planX CAD — Hatch / Pattern Fill.

Workflow:
  1. Click a closed polygon feature (or a polyline that closes its own ring).
  2. Choose a hatch pattern + spacing + angle + colour from the dialog.
  3. A new feature is added to an auto-created `planx_hatch` layer; the layer
     gets a categorized line-pattern renderer the first time it is created.

This is a planning-grade visualisation tool. It writes the hatch lines as
geometry (clipped to the source polygon) rather than relying on a fill
symbol — so the result survives export to other GIS or CAD formats.
"""
from __future__ import annotations

import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes,
)

from .tool_base import tool_base
from ..core.tool_options import CHOICE, COLOR, FLOAT, OptionSpec
from ..core.sketcher_layer_utils import get_or_create_layer
from ..urban.crs_utils import local_metric_crs, transform_geometry


HATCH_PATTERNS = (
    ("Parallel lines", "parallel"),
    ("Cross-hatch", "cross"),
    ("Diagonal up", "diag_up"),
    ("Diagonal down", "diag_down"),
)
MAX_HATCH_CANDIDATES = 20_000


def _bbox_corners(geom: QgsGeometry) -> tuple[float, float, float, float]:
    rect = geom.boundingBox()
    return rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()


def _generate_hatch_lines(
    polygon_geom: QgsGeometry,
    spacing: float,
    angle_deg: float,
) -> list[QgsGeometry]:
    """Generate a family of parallel lines crossing the polygon's bbox, then
    clip to the polygon. Returns a list of line geometries (single-part each)."""
    if polygon_geom is None or polygon_geom.isEmpty() or spacing <= 0:
        return []
    xmin, ymin, xmax, ymax = _bbox_corners(polygon_geom)
    diag = math.hypot(xmax - xmin, ymax - ymin) * 1.2 + spacing * 2
    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    a = math.radians(angle_deg)
    # Direction of hatch lines + perpendicular step direction.
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy, dx
    n_steps = int(diag / spacing) + 2
    if 2 * n_steps + 1 > MAX_HATCH_CANDIDATES:
        return []

    lines: list[QgsGeometry] = []
    for k in range(-n_steps, n_steps + 1):
        ox = cx + px * k * spacing
        oy = cy + py * k * spacing
        p1 = QgsPointXY(ox - dx * diag, oy - dy * diag)
        p2 = QgsPointXY(ox + dx * diag, oy + dy * diag)
        line = QgsGeometry.fromPolylineXY([p1, p2])
        clipped = line.intersection(polygon_geom)
        if clipped is None or clipped.isEmpty():
            continue
        # Intersection can be Multi-LineString; split into single-part lines.
        if clipped.isMultipart():
            for part in clipped.asMultiPolyline():
                if len(part) >= 2:
                    lines.append(QgsGeometry.fromPolylineXY(part))
        else:
            if clipped.type() == QgsWkbTypes.GeometryType.LineGeometry:
                lines.append(clipped)
    return lines


class HatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⧗ Hatch / Pattern Fill")
        self.setModal(True)
        self.setMinimumWidth(340)
        self._color = QColor("#1a237e")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("⧗ Hatch / Pattern Fill")
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        self.cmb_pattern = QComboBox()
        self.cmb_pattern.addItems([name for name, _key in HATCH_PATTERNS])
        form.addRow("Pattern:", self.cmb_pattern)

        self.spn_spacing = QDoubleSpinBox()
        self.spn_spacing.setRange(0.01, 1e6)
        self.spn_spacing.setValue(2.0)
        self.spn_spacing.setDecimals(2)
        self.spn_spacing.setSuffix(" m")
        form.addRow("Spacing:", self.spn_spacing)

        self.spn_angle = QDoubleSpinBox()
        self.spn_angle.setRange(-180.0, 180.0)
        self.spn_angle.setValue(45.0)
        self.spn_angle.setDecimals(1)
        self.spn_angle.setSuffix(" °")
        form.addRow("Angle:", self.spn_angle)

        color_row = QHBoxLayout()
        self.lbl_color = QLabel()
        self.lbl_color.setFixedSize(32, 22)
        self._update_color_swatch()
        btn_color = QPushButton("Choose colour…")
        btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.lbl_color)
        color_row.addWidget(btn_color)
        form.addRow("Colour:", color_row)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok = QPushButton("✅ Apply")
        ok.setMinimumHeight(32)
        ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; font-weight: bold;"
            " border-radius: 4px; padding: 6px 16px; }"
            "QPushButton:hover { background: #283593; }"
        )
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setMinimumHeight(32)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Hatch colour")
        if c.isValid():
            self._color = c
            self._update_color_swatch()

    def _update_color_swatch(self):
        self.lbl_color.setStyleSheet(
            f"background: {self._color.name()}; border: 1px solid #555; border-radius: 3px;"
        )

    def params(self) -> dict:
        key = HATCH_PATTERNS[self.cmb_pattern.currentIndex()][1]
        return {
            "pattern": key,
            "spacing": self.spn_spacing.value(),
            "angle": self.spn_angle.value(),
            "color": self._color.name(),
        }


class tool_hatch(tool_base):
    INLINE_OPTIONS = (
        OptionSpec("hatch_pattern", "Pattern", CHOICE, "parallel",
                   choices=tuple((key, name) for name, key in HATCH_PATTERNS)),
        OptionSpec("hatch_spacing", "Spacing (m)", FLOAT, 2.0, 0.01, 1e6, 2, " m"),
        OptionSpec("hatch_angle", "Angle (°)", FLOAT, 45.0, -180.0, 180.0, 1, "°"),
        OptionSpec("hatch_color", "Colour", COLOR, "#1a237e"),
    )

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.require_editable = False  # we write to our own layer
        self.hatch_pattern = "parallel"
        self.hatch_spacing = 2.0
        self.hatch_angle = 45.0
        self.hatch_color = "#1a237e"

    def tool_name(self):
        return "Hatch"

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Hatch — empty geometry")
            self._reset()
            return
        if geom.type() != QgsWkbTypes.GeometryType.PolygonGeometry:
            # Try to close a polyline into a polygon.
            if geom.type() == QgsWkbTypes.GeometryType.LineGeometry:
                from qgis.core import QgsGeometry as _G
                try:
                    converted = _G.fromPolygonXY([geom.asPolyline()]) if not geom.isMultipart() else None
                    if converted is None or converted.isEmpty():
                        self.tool_message.emit("⚠️ Hatch — input must be a polygon")
                        self._reset()
                        return
                    geom = converted
                except Exception:
                    self.tool_message.emit("⚠️ Hatch — input must be a polygon")
                    self._reset()
                    return
            else:
                self.tool_message.emit("⚠️ Hatch — point input not supported")
                self._reset()
                return

        if self.use_inline_options():
            p = {
                "pattern": self.hatch_pattern,
                "spacing": self.hatch_spacing,
                "angle": self.hatch_angle,
                "color": self.hatch_color,
            }
        else:
            dlg = HatchDialog(self.iface.mainWindow())
            if dlg.exec() != QDialog.DialogCode.Accepted:
                self.tool_message.emit("⧗ Hatch — cancelled")
                self._reset()
                return
            p = dlg.params()
            self.hatch_pattern = p["pattern"]
            self.hatch_spacing = p["spacing"]
            self.hatch_angle = p["angle"]
            self.hatch_color = p["color"]
        pattern = p["pattern"]
        spacing = p["spacing"]
        base_angle = p["angle"]

        centroid = geom.centroid()
        if centroid is None or centroid.isEmpty() or not layer.crs().isValid():
            self.tool_message.emit("⚠️ Hatch — valid source CRS required")
            self._reset()
            return
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer.crs())
        metric_geom = transform_geometry(geom, layer.crs(), metric_crs)
        if metric_geom is None or metric_geom.isEmpty():
            self.tool_message.emit("⚠️ Hatch — CRS transform failed")
            self._reset()
            return

        angles: list[float] = []
        if pattern == "parallel":
            angles = [base_angle]
        elif pattern == "diag_up":
            angles = [45.0]
        elif pattern == "diag_down":
            angles = [-45.0]
        elif pattern == "cross":
            angles = [base_angle, base_angle + 90.0]

        lines: list[QgsGeometry] = []
        for ang in angles:
            generated = _generate_hatch_lines(metric_geom, spacing, ang)
            if len(lines) + len(generated) > MAX_HATCH_CANDIDATES:
                self.tool_message.emit(
                    f"⚠️ Hatch — result exceeds {MAX_HATCH_CANDIDATES:,} lines; "
                    "increase spacing"
                )
                self._reset()
                return
            lines.extend(generated)

        lines = [
            transform_geometry(line, metric_crs, layer.crs()) for line in lines
        ]
        lines = [line for line in lines if line is not None and not line.isEmpty()]

        if not lines:
            self.tool_message.emit(
                "⚠️ Hatch — no lines generated; spacing may be too small for the safe limit"
            )
            self._reset()
            return

        hatch_layer = get_or_create_layer(
            "planx_hatch",
            geom_type="LineString",
            crs=layer.crs(),
            fields=[
                ("source_layer", "string"),
                ("pattern", "string"),
                ("spacing_m", "double"),
                ("angle_deg", "double"),
                ("color", "string"),
            ],
        )
        if hatch_layer is None:
            self.tool_message.emit("⚠️ Hatch — could not create layer")
            self._reset()
            return

        was_editing = hatch_layer.isEditable()
        if not was_editing and not hatch_layer.startEditing():
            self.tool_message.emit("⚠️ Hatch — target layer is not editable")
            self._reset()
            return
        features = []
        for line_geom in lines:
            feat = QgsFeature(hatch_layer.fields())
            feat.setGeometry(line_geom)
            feat.setAttribute(hatch_layer.fields().indexOf("source_layer"), layer.name())
            feat.setAttribute(hatch_layer.fields().indexOf("pattern"), pattern)
            feat.setAttribute(hatch_layer.fields().indexOf("spacing_m"), spacing)
            feat.setAttribute(hatch_layer.fields().indexOf("angle_deg"), base_angle)
            feat.setAttribute(hatch_layer.fields().indexOf("color"), p["color"])
            features.append(feat)
        hatch_layer.beginEditCommand("PlanX CAD: hatch")
        if not hatch_layer.addFeatures(features):
            hatch_layer.destroyEditCommand()
            if not was_editing:
                hatch_layer.rollBack()
            self.tool_message.emit("⚠️ Hatch — generated lines could not be added")
            self._reset()
            return
        hatch_layer.endEditCommand()
        if not was_editing and not hatch_layer.commitChanges():
            hatch_layer.rollBack()
            self.tool_message.emit("⚠️ Hatch — target layer could not be saved")
            self._reset()
            return
        hatch_layer.triggerRepaint()

        self.tool_message.emit(
            f"✅ Hatch — {len(lines)} lines added ({pattern}, {spacing} m, {base_angle:.1f}°)"
        )
        self._reset()
