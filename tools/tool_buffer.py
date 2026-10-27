# -*- coding: utf-8 -*-
"""PlanX CAD metric Buffer tool with managed output layers."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, QgsFeature, QgsPointXY, Qgis
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QComboBox, QPushButton, QHBoxLayout, QLabel, QGroupBox
)
from qgis.PyQt.QtGui import QFont
from .tool_base import tool_base
from ..core.tool_options import CHOICE, FLOAT, INT, OptionSpec
from ..core.sketcher_layer_utils import get_or_create_layer, add_feature_to_layer
from ..urban.crs_utils import local_metric_crs, transform_geometry


class BufferDialog(QDialog):
    """Collect buffer distance and join-style parameters."""

    def __init__(self, parent=None, default_distance=5.0):
        super().__init__(parent)
        self.setWindowTitle("◎ Buffer Parameters")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._setup_ui(default_distance)

    def _setup_ui(self, default_distance):
        layout = QVBoxLayout(self)

        title = QLabel("◎ Buffer Parameters")
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self.spn_distance = QDoubleSpinBox()
        self.spn_distance.setRange(0.01, 100000.0)
        self.spn_distance.setValue(default_distance)
        self.spn_distance.setSuffix(" m")
        self.spn_distance.setSingleStep(0.5)
        self.spn_distance.setDecimals(2)
        form.addRow("Buffer distance:", self.spn_distance)

        self.cmb_join = QComboBox()
        self.cmb_join.addItems([
            "Round",
            "Bevel",
            "Miter"
        ])
        form.addRow("Join style:", self.cmb_join)

        self.spn_segments = QDoubleSpinBox()
        self.spn_segments.setRange(4, 128)
        self.spn_segments.setValue(16)
        self.spn_segments.setDecimals(0)
        form.addRow("Segments:", self.spn_segments)

        layout.addLayout(form)

        # Dialog buttons.
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("✅ Apply")
        btn_ok.setMinimumHeight(36)
        btn_ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 8px 20px; }"
            "QPushButton:hover { background: #283593; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setMinimumHeight(36)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def get_params(self):
        join_map = {0: 1, 1: 2, 2: 3}  # Round=1, Bevel=2, Miter=3
        return {
            "distance": self.spn_distance.value(),
            "join_style": join_map.get(self.cmb_join.currentIndex(), 1),
            "segments": int(self.spn_segments.value()),
        }


class tool_buffer(tool_base):
    """Create a metric buffer in a plugin-managed output layer."""

    INLINE_OPTIONS = (
        OptionSpec("distance", "Distance (m)", FLOAT, 5.0, 0.01, 100000.0, 2, " m"),
        OptionSpec("join_style", "Join style", CHOICE, 1,
                   choices=((1, "Round"), (2, "Bevel"), (3, "Miter"))),
        OptionSpec("segments", "Segments", INT, 16, 4, 128, 0,
                   tooltip="Segments per quarter circle on round joins"),
    )

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        # The source only needs to be readable; output is written to the
        # plugin-managed planx_buffer layer.
        self.require_editable = False
        self.distance = 5.0
        self.join_style = 1
        self.segments = 16
        self._activation_cancelled = False

    def tool_name(self):
        return "Buffer"

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        accepted = self.use_inline_options()
        if not accepted:
            dlg = BufferDialog(self.iface.mainWindow(), self.distance)
            accepted = dlg.exec() == QDialog.DialogCode.Accepted
            if accepted:
                params = dlg.get_params()
                self.distance = params["distance"]
                self.join_style = params["join_style"]
                self.segments = params["segments"]
        if accepted:
            join_names = {1: "Round", 2: "Bevel", 3: "Miter"}
            self.tool_message.emit(
                f"◎ Buffer ({self.distance} m, {join_names.get(self.join_style, '?')}) "
                "— Select the feature to buffer"
            )
        else:
            self._activation_cancelled = True
            self.tool_message.emit("◎ Buffer — Cancelled")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        centroid = geom.centroid()
        if centroid is None or centroid.isEmpty() or not layer.crs().isValid():
            self.tool_message.emit("⚠️ Buffer — A valid source CRS is required")
            self._reset()
            return
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer.crs())
        metric_geom = transform_geometry(geom, layer.crs(), metric_crs)
        if metric_geom is None or metric_geom.isEmpty():
            self.tool_message.emit("⚠️ Buffer — CRS transformation failed")
            self._reset()
            return

        # QGIS buffer: join_style (1=Round, 2=Bevel, 3=Miter)
        join_enum = Qgis.JoinStyle.Round
        if self.join_style == 2:
            join_enum = Qgis.JoinStyle.Bevel
        elif self.join_style == 3:
            join_enum = Qgis.JoinStyle.Miter

        buffered_metric = metric_geom.buffer(
            self.distance,
            self.segments,
            Qgis.EndCapStyle.Round,
            join_enum,
            2.0  # miter limit
        )
        buffered = transform_geometry(buffered_metric, metric_crs, layer.crs())

        if buffered and not buffered.isEmpty():
            # Plugin-managed output layer.
            buffer_layer = get_or_create_layer(
                "planx_buffer",
                geom_type="Polygon",
                crs=layer.crs(),
                fields=[
                    ("source_layer", "string"),
                    ("buffer_distance", "double"),
                    ("join_style", "string"),
                ]
            )

            if buffer_layer:
                join_names = {1: "round", 2: "bevel", 3: "miter"}
                feat = add_feature_to_layer(buffer_layer, buffered, {
                    "source_layer": layer.name(),
                    "buffer_distance": self.distance,
                    "join_style": join_names.get(self.join_style, "round"),
                })
                if feat is None:
                    self.tool_message.emit("⚠️ Buffer — Feature could not be added")
                    self._reset()
                    return
                buffer_layer.triggerRepaint()

                self.tool_message.emit(
                    f"✅ Buffer ({self.distance} m) — Added to planx_buffer"
                )
            else:
                self.tool_message.emit("⚠️ Buffer — Output layer could not be created")
        else:
            self.tool_message.emit("⚠️ Buffer — Buffer geometry could not be created")

        self._reset()
