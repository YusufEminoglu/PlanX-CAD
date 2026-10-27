# -*- coding: utf-8 -*-
"""PlanX CAD Chamfer tool for straight corner cuts between two lines."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.tool_options import FLOAT, OptionSpec
from ..core.sketcher_feedback import create_preview_rubberband, COLOR_ACCENT
from ..core.sketcher_utils import create_chamfer_and_trims, trim_line_to_point
from ..urban.crs_utils import local_metric_crs, transform_geometry


class ChamferDialog(QDialog):
    """Collect the two cutback distances for a straight chamfer."""

    def __init__(self, first=5.0, second=5.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chamfer")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui(first, second)

    def _build_ui(self, first, second):
        layout = QVBoxLayout(self)

        title = QLabel("Chamfer Distances")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        self.spn_first = QDoubleSpinBox()
        self.spn_first.setRange(0.01, 100000.0)
        self.spn_first.setDecimals(2)
        self.spn_first.setSingleStep(0.5)
        self.spn_first.setSuffix(" m")
        self.spn_first.setValue(first)
        self.spn_first.setAccessibleName("First chamfer distance")
        self.spn_first.setAccessibleDescription(
            "Cutback measured along the first line from the corner."
        )
        form.addRow("First distance:", self.spn_first)

        self.spn_second = QDoubleSpinBox()
        self.spn_second.setRange(0.01, 100000.0)
        self.spn_second.setDecimals(2)
        self.spn_second.setSingleStep(0.5)
        self.spn_second.setSuffix(" m")
        self.spn_second.setValue(second)
        self.spn_second.setAccessibleName("Second chamfer distance")
        self.spn_second.setAccessibleDescription(
            "Cutback measured along the second line from the corner."
        )
        form.addRow("Second distance:", self.spn_second)
        layout.addLayout(form)

        self.chk_equal = QCheckBox("Use the first distance for both lines")
        self.chk_equal.setChecked(abs(first - second) < 1e-9)
        self.chk_equal.setAccessibleName("Equal chamfer distances")
        self.chk_equal.toggled.connect(self._on_equal_toggled)
        layout.addWidget(self.chk_equal)
        self._on_equal_toggled(self.chk_equal.isChecked())
        self.spn_first.valueChanged.connect(self._mirror_first)

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

    def _on_equal_toggled(self, checked):
        self.spn_second.setEnabled(not checked)
        if checked:
            self.spn_second.setValue(self.spn_first.value())

    def _mirror_first(self, value):
        if self.chk_equal.isChecked():
            self.spn_second.setValue(value)

    def params(self):
        second = (
            self.spn_first.value() if self.chk_equal.isChecked()
            else self.spn_second.value()
        )
        return {"first": self.spn_first.value(), "second": second}


class tool_chamfer(tool_base):
    """Cut a straight corner between two intersecting lines.

    1. Enter the distances | 2. Select the first line | 3. Select the second
    """

    INLINE_OPTIONS = (
        OptionSpec("first_distance", "First distance (m)", FLOAT, 5.0, 0.01, 100000.0, 2, " m"),
        OptionSpec("second_distance", "Second distance (m)", FLOAT, 5.0, 0.01, 100000.0, 2, " m"),
    )

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.first_distance = 5.0
        self.second_distance = 5.0
        self.first_layer = None
        self.first_feature = None
        self._activation_cancelled = False

    def tool_name(self):
        return "Chamfer"

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        if not self.use_inline_options():
            dialog = ChamferDialog(
                self.first_distance, self.second_distance, self.iface.mainWindow()
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self._activation_cancelled = True
                self.tool_message.emit("⌐ Chamfer — Cancelled")
                return
            params = dialog.params()
            self.first_distance = params["first"]
            self.second_distance = params["second"]
        self.first_layer = None
        self.first_feature = None
        self.tool_message.emit(
            f"⌐ Chamfer ({self.first_distance} m / {self.second_distance} m) "
            "— Select the first line"
        )

    def on_entity_selected(self, layer, feature, point):
        self.first_layer = layer
        self.first_feature = feature
        self._step = 2
        self.tool_message.emit("⌐ Chamfer — Select the second line")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # A feature cannot be chamfered against itself.
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.first_layer, self.first_feature),
            )
            if result:
                layer, feature = result
                self._do_chamfer(layer, feature)
            else:
                self.tool_message.emit("⚠️ Chamfer — Second feature not found")
            self._cleanup_chamfer()

    def _metric_chamfer_result(self, geom1, layer1, geom2, layer2):
        """Solve the chamfer in a local metre CRS so distances stay true."""
        if not layer1.crs().isValid() or not layer2.crs().isValid():
            return None, None
        centroid = geom1.centroid()
        if centroid is None or centroid.isEmpty():
            return None, None
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer1.crs())
        metric_geom1 = transform_geometry(geom1, layer1.crs(), metric_crs)
        metric_geom2 = transform_geometry(geom2, layer2.crs(), metric_crs)
        if (metric_geom1 is None or metric_geom1.isEmpty() or
                metric_geom2 is None or metric_geom2.isEmpty()):
            return None, None
        return metric_crs, create_chamfer_and_trims(
            metric_geom1, metric_geom2,
            self.first_distance, self.second_distance,
        )

    def _do_chamfer(self, second_layer, second_feature):
        metric_crs, chamfer = self._metric_chamfer_result(
            self.first_feature.geometry(), self.first_layer,
            second_feature.geometry(), second_layer,
        )
        if metric_crs is None or not chamfer:
            self.tool_message.emit(
                "⚠️ Chamfer — The lines do not form a corner for these distances"
            )
            return

        metric_geom1 = transform_geometry(
            self.first_feature.geometry(), self.first_layer.crs(), metric_crs
        )
        metric_geom2 = transform_geometry(
            second_feature.geometry(), second_layer.crs(), metric_crs
        )
        inter_pt = chamfer.get('inter_pt')
        new_geom1 = transform_geometry(
            trim_line_to_point(metric_geom1, chamfer['tp1'], inter_pt),
            metric_crs, self.first_layer.crs(),
        )
        new_geom2 = transform_geometry(
            trim_line_to_point(metric_geom2, chamfer['tp2'], inter_pt),
            metric_crs, second_layer.crs(),
        )
        cut_geom = transform_geometry(
            chamfer['line'], metric_crs, self.first_layer.crs()
        )
        if any(geom is None or geom.isEmpty()
               for geom in (new_geom1, new_geom2, cut_geom)):
            self.tool_message.emit(
                "⚠️ Chamfer — No valid result geometry was created"
            )
            return

        new_geom1 = self._coerce_for_layer(new_geom1, self.first_layer)
        new_geom2 = self._coerce_for_layer(new_geom2, second_layer)
        cut_geom = self._coerce_for_layer(cut_geom, self.first_layer)

        layers = []
        for layer in (self.first_layer, second_layer):
            if layer not in layers:
                layers.append(layer)
        for layer in layers:
            layer.beginEditCommand("PlanX CAD: chamfer")

        cut_feature = QgsFeature(self.first_layer.fields())
        cut_feature.setGeometry(cut_geom)
        for index in range(self.first_layer.fields().count()):
            cut_feature.setAttribute(index, self.first_feature.attribute(index))

        success = (
            self.first_layer.changeGeometry(self.first_feature.id(), new_geom1)
            and second_layer.changeGeometry(second_feature.id(), new_geom2)
            and self.first_layer.addFeature(cut_feature)
        )
        if not success:
            for layer in reversed(layers):
                layer.destroyEditCommand()
            self.tool_message.emit(
                "⚠️ Chamfer — Layer write failed; all changes were rolled back"
            )
            return
        for layer in layers:
            layer.endEditCommand()
            layer.triggerRepaint()
        self.tool_message.emit(
            f"✅ Chamfer ({self.first_distance} m / {self.second_distance} m) "
            "— Applied successfully"
        )

    @staticmethod
    def _coerce_for_layer(geometry, layer):
        geometry = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
            geometry.convertToMultiType()
        return geometry

    def on_move(self, point):
        """Preview the chamfer against the line under the cursor."""
        if self._step != 2:
            return
        if self.preview_rb is None:
            self.preview_rb = create_preview_rubberband(self.canvas)
        self.preview_rb.reset(QgsWkbTypes.GeometryType.LineGeometry)

        result = self._pick_feature(
            self.canvas.mouseLastXY(),
            exclude=(self.first_layer, self.first_feature),
        )
        if not result:
            return
        layer, feature = result
        metric_crs, chamfer = self._metric_chamfer_result(
            self.first_feature.geometry(), self.first_layer,
            feature.geometry(), layer,
        )
        if not chamfer:
            return
        cut_geom = transform_geometry(
            chamfer['line'], metric_crs, self.first_layer.crs()
        )
        if cut_geom and not cut_geom.isEmpty():
            self.preview_rb.setColor(COLOR_ACCENT)
            self.preview_rb.setWidth(3)
            self.preview_rb.setLineStyle(Qt.PenStyle.DashLine)
            self.preview_rb.setToGeometry(cut_geom, self.first_layer)
            self.preview_rb.show()

    def _cleanup_chamfer(self):
        self.first_layer = None
        self.first_feature = None
        self._reset()
