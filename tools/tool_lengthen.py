# -*- coding: utf-8 -*-
"""PlanX CAD Lengthen tool: change a line length by delta, percent, or total."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)
from qgis.core import QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.tool_options import CHOICE, FLOAT, OptionSpec
from ..core.sketcher_utils import lengthen_line
from ..urban.crs_utils import local_metric_crs, transform_geometry


class LengthenDialog(QDialog):
    """Collect the lengthen mode and its value."""

    MODES = (("Delta (add/remove)", "delta"),
             ("Percent of current", "percent"),
             ("Total length", "total"))

    def __init__(self, current_length=0.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lengthen")
        self.setMinimumWidth(340)
        self.setModal(True)
        self._build_ui(current_length)

    def _build_ui(self, current_length):
        layout = QVBoxLayout(self)

        title = QLabel("Lengthen Parameters")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        current = QLabel(f"Current length: {current_length:.3f} m")
        current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(current)

        form = QFormLayout()
        self.cmb_mode = QComboBox()
        for label, _key in self.MODES:
            self.cmb_mode.addItem(label)
        self.cmb_mode.setAccessibleName("Lengthen mode")
        self.cmb_mode.setAccessibleDescription(
            "Delta adds or removes length, Percent scales the current length, "
            "Total sets an absolute length."
        )
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self.cmb_mode)

        self.spn_value = QDoubleSpinBox()
        self.spn_value.setRange(-1000000.0, 1000000.0)
        self.spn_value.setDecimals(3)
        self.spn_value.setSingleStep(1.0)
        self.spn_value.setValue(5.0)
        self.spn_value.setAccessibleName("Lengthen value")
        form.addRow("Value:", self.spn_value)
        layout.addLayout(form)
        self._on_mode_changed(0)

        hint = QLabel(
            "The end you clicked is the end that moves. Negative delta values "
            "shorten the line."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        apply_button = QPushButton("Apply")
        apply_button.setMinimumHeight(30)
        apply_button.setDefault(True)
        apply_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(30)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _on_mode_changed(self, index):
        mode = self.MODES[index][1]
        if mode == "percent":
            self.spn_value.setSuffix(" %")
            self.spn_value.setMinimum(0.001)
        else:
            self.spn_value.setSuffix(" m")
            self.spn_value.setMinimum(
                0.001 if mode == "total" else -1000000.0
            )

    def params(self):
        return {
            "mode": self.MODES[self.cmb_mode.currentIndex()][1],
            "value": self.spn_value.value(),
        }


class tool_lengthen(tool_base):
    """Extend or shorten a line from the end nearest the click."""

    INLINE_OPTIONS = (
        OptionSpec("lengthen_mode", "Mode", CHOICE, "delta",
                   choices=(("delta", "Delta (add/remove)"),
                            ("percent", "Percent of current"),
                            ("total", "Total length"))),
        OptionSpec("lengthen_value", "Value", FLOAT, 5.0, -1000000.0, 1000000.0, 3,
                   tooltip="Metres for Delta and Total; percent for Percent"),
    )
    lengthen_mode = "delta"
    lengthen_value = 5.0

    def tool_name(self):
        return "Lengthen"

    def activate(self):
        super().activate()
        self.tool_message.emit(
            "↔ Lengthen — Click a line near the end you want to change"
        )

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Lengthen — Geometry is empty")
            self._reset()
            return
        if geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit(
                "⚠️ Lengthen — Only line features can be lengthened"
            )
            self._reset()
            return

        metric_crs = self._metric_crs(geom, layer)
        metric_geom = transform_geometry(geom, layer.crs(), metric_crs)
        if metric_geom is None or metric_geom.isEmpty():
            self.tool_message.emit("⚠️ Lengthen — CRS transformation failed")
            self._reset()
            return

        if self.use_inline_options():
            params = {"mode": self.lengthen_mode, "value": self.lengthen_value}
        else:
            dialog = LengthenDialog(metric_geom.length(), self.iface.mainWindow())
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.tool_message.emit("⚠️ Lengthen — Cancelled")
                self._reset()
                return
            params = dialog.params()
            self.lengthen_mode = params["mode"]
            self.lengthen_value = params["value"]
        result = lengthen_line(
            metric_geom, params["mode"], params["value"],
            from_end=self._clicked_end_is_last(geom, point),
        )
        if result is None or result.isEmpty():
            self.tool_message.emit(
                "⚠️ Lengthen — The requested length is not valid for this line"
            )
            self._reset()
            return

        new_geom = transform_geometry(result, metric_crs, layer.crs())
        if new_geom is None or new_geom.isEmpty():
            self.tool_message.emit("⚠️ Lengthen — CRS transformation failed")
            self._reset()
            return
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not new_geom.isMultipart():
            new_geom.convertToMultiType()

        if self._apply_edit(layer, feature, new_geom):
            self.tool_message.emit(
                f"✅ Lengthen — New length {result.length():.3f} m"
            )
        self._reset()

    def _metric_crs(self, geom, layer):
        centroid = geom.centroid()
        anchor = (QgsPointXY(centroid.asPoint()) if centroid and
                  not centroid.isEmpty() else QgsPointXY(0, 0))
        return local_metric_crs(anchor, layer.crs())

    @staticmethod
    def _clicked_end_is_last(geom, point):
        """Return True when the click is nearer the final vertex."""
        if point is None:
            return True
        if geom.isMultipart():
            parts = geom.asMultiPolyline()
            points = list(parts[0]) if parts else []
        else:
            points = list(geom.asPolyline())
        if len(points) < 2:
            return True
        start = QgsPointXY(points[0]).distance(point)
        end = QgsPointXY(points[-1]).distance(point)
        return end <= start

    def on_click(self, point, button):
        """Lengthen completes on selection; further clicks restart the tool."""
        if button == Qt.MouseButton.LeftButton:
            self._reset()
