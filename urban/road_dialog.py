# -*- coding: utf-8 -*-
"""Road-platform parameter dialog."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont


class RoadDialog(QDialog):
    """Collect road-platform dimensions and traffic direction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛣️ Road Platform Parameters")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._params = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        title = QLabel("🛣️ Road Platform Parameters")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Road type
        type_group = QGroupBox("Road Type")
        type_layout = QFormLayout(type_group)

        self.road_type_combo = QComboBox()
        self.road_type_combo.addItems([
            "Vehicular Road",
            "Pedestrian Road",
            "Bicycle Road",
            "Collector Road",
            "Arterial Road",
        ])
        type_layout.addRow("Road type:", self.road_type_combo)
        
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Two-way", "One-way"])
        type_layout.addRow("Traffic direction:", self.direction_combo)
        self.direction_combo.currentIndexChanged.connect(
            self._on_direction_changed
        )

        layout.addWidget(type_group)

        # Lane parameters
        lane_group = QGroupBox("Lane Parameters")
        lane_layout = QFormLayout(lane_group)

        self.lane_count_spin = QSpinBox()
        self.lane_count_spin.setRange(1, 8)
        self.lane_count_spin.setValue(2)
        self.lane_count_spin.setSuffix(" (per direction)")
        lane_layout.addRow("Lane count:", self.lane_count_spin)

        self.lane_width_spin = QDoubleSpinBox()
        self.lane_width_spin.setRange(2.0, 10.0)
        self.lane_width_spin.setValue(3.50)
        self.lane_width_spin.setSuffix(" m")
        self.lane_width_spin.setSingleStep(0.25)
        lane_layout.addRow("Lane width:", self.lane_width_spin)

        layout.addWidget(lane_group)

        # Median and sidewalks
        edge_group = QGroupBox("Median & Sidewalks")
        edge_layout = QFormLayout(edge_group)

        self.median_width_spin = QDoubleSpinBox()
        self.median_width_spin.setRange(0.0, 20.0)
        self.median_width_spin.setValue(2.00)
        self.median_width_spin.setSuffix(" m")
        self.median_width_spin.setSingleStep(0.50)
        edge_layout.addRow("Median width:", self.median_width_spin)

        self.left_sidewalk_spin = QDoubleSpinBox()
        self.left_sidewalk_spin.setRange(0.0, 10.0)
        self.left_sidewalk_spin.setValue(2.00)
        self.left_sidewalk_spin.setSuffix(" m")
        self.left_sidewalk_spin.setSingleStep(0.50)
        edge_layout.addRow("Left sidewalk:", self.left_sidewalk_spin)

        self.right_sidewalk_spin = QDoubleSpinBox()
        self.right_sidewalk_spin.setRange(0.0, 10.0)
        self.right_sidewalk_spin.setValue(2.00)
        self.right_sidewalk_spin.setSuffix(" m")
        self.right_sidewalk_spin.setSingleStep(0.50)
        edge_layout.addRow("Right sidewalk:", self.right_sidewalk_spin)

        layout.addWidget(edge_group)

        # Total width summary
        self.total_width_label = QLabel()
        self.total_width_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_width_label.setStyleSheet(
            "font-weight: bold; color: #1a237e; font-size: 12px; "
            "padding: 6px; background: #e8eaf6; border-radius: 4px;"
        )
        layout.addWidget(self.total_width_label)
        self._update_total()

        # Keep the total synchronized with every dimension control.
        self.lane_count_spin.valueChanged.connect(self._update_total)
        self.lane_width_spin.valueChanged.connect(self._update_total)
        self.median_width_spin.valueChanged.connect(self._update_total)
        self.left_sidewalk_spin.valueChanged.connect(self._update_total)
        self.right_sidewalk_spin.valueChanged.connect(self._update_total)

        # Actions
        btn_layout = QHBoxLayout()

        draw_button = QPushButton("✏️ Draw")
        draw_button.setMinimumHeight(36)
        draw_button.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 8px 20px; }"
            "QPushButton:hover { background: #283593; }"
        )
        draw_button.clicked.connect(self.accept)
        btn_layout.addWidget(draw_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(36)
        cancel_button.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_button)

        layout.addLayout(btn_layout)

    def _update_total(self):
        """Calculate and display the complete platform width."""
        lane_count = self.lane_count_spin.value()
        lane_width = self.lane_width_spin.value()
        median_width = self.median_width_spin.value()
        left_sidewalk = self.left_sidewalk_spin.value()
        right_sidewalk = self.right_sidewalk_spin.value()

        one_way = self.direction_combo.currentIndex() == 1
        direction_factor = 1 if one_way else 2
        total_width = (
            direction_factor * lane_count * lane_width
            + (0 if one_way else median_width)
            + left_sidewalk + right_sidewalk
        )
        self.total_width_label.setText(f"Total Width: {total_width:.2f} m")

    def _on_direction_changed(self):
        one_way = self.direction_combo.currentIndex() == 1
        self.median_width_spin.setEnabled(not one_way)
        self.lane_count_spin.setSuffix(
            " (total)" if one_way else " (per direction)"
        )
        self._update_total()

    def get_params(self):
        """Return normalized English parameter keys for the generator."""
        lane_count = self.lane_count_spin.value()
        lane_width = self.lane_width_spin.value()
        median_width = self.median_width_spin.value()
        left_sidewalk = self.left_sidewalk_spin.value()
        right_sidewalk = self.right_sidewalk_spin.value()

        one_way = self.direction_combo.currentIndex() == 1
        direction_factor = 1 if one_way else 2
        total_width = (
            direction_factor * lane_count * lane_width
            + (0 if one_way else median_width)
            + left_sidewalk + right_sidewalk
        )

        return {
            "road_type": self.road_type_combo.currentText(),
            "one_way": one_way,
            "lane_count": lane_count,
            "lane_width": lane_width,
            "median_width": 0.0 if one_way else median_width,
            "left_sidewalk": left_sidewalk,
            "right_sidewalk": right_sidewalk,
            "total_width": total_width,
        }
