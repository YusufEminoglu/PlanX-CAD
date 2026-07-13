# -*- coding: utf-8 -*-
"""Junction-solution parameter dialog."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush


class JunctionDialog(QDialog):
    """Collect curb-corner and traffic-island solution parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔵 Junction Solution Parameters")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        title = QLabel("🔵 Junction Solution")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1a237e; padding: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "Resolve curb corners at road intersections with a straight\n"
            "chamfer or a tangent fillet arc."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(desc)

        # Schematic preview
        self.schema_label = QLabel()
        self.schema_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schema_label.setMinimumHeight(120)
        self._draw_schema()
        layout.addWidget(self.schema_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Junction search area
        radius_group = QGroupBox("Junction Area")
        radius_form = QFormLayout(radius_group)

        self.spn_radius = QDoubleSpinBox()
        self.spn_radius.setRange(3.0, 100.0)
        self.spn_radius.setValue(12.0)
        self.spn_radius.setSuffix(" m")
        self.spn_radius.setSingleStep(1.0)
        self.spn_radius.setToolTip(
            "Radius of the area affected around the junction center"
        )
        radius_form.addRow("Impact radius:", self.spn_radius)

        layout.addWidget(radius_group)

        # Curb-corner solution
        corner_group = QGroupBox("Curb Corner Solution")
        corner_form = QFormLayout(corner_group)

        self.cmb_corner_mode = QComboBox()
        self.cmb_corner_mode.addItems([
            "Straight Chamfer",
            "Tangent Fillet",
        ])
        self.cmb_corner_mode.setToolTip(
            "Corner solution applied at the true intersection of the curb "
            "support lines"
        )
        self.cmb_corner_mode.currentIndexChanged.connect(
            self._on_corner_mode_changed
        )
        corner_form.addRow("Solution type:", self.cmb_corner_mode)

        self.spn_chamfer_dist = QDoubleSpinBox()
        self.spn_chamfer_dist.setRange(0.5, 50.0)
        self.spn_chamfer_dist.setValue(5.0)
        self.spn_chamfer_dist.setSuffix(" m")
        self.spn_chamfer_dist.setSingleStep(0.5)
        self.spn_chamfer_dist.setToolTip(
            "Setback distance for a straight outer-curb chamfer.\n"
            "Each curb is trimmed by this distance from the support-line\n"
            "intersection and connected with a straight segment."
        )
        corner_form.addRow("Chamfer distance:", self.spn_chamfer_dist)

        self.spn_fillet_radius = QDoubleSpinBox()
        self.spn_fillet_radius.setRange(0.5, 50.0)
        self.spn_fillet_radius.setValue(3.0)
        self.spn_fillet_radius.setSuffix(" m")
        self.spn_fillet_radius.setSingleStep(0.5)
        self.spn_fillet_radius.setToolTip(
            "Radius of the tangent arc at the curb support-line intersection."
        )
        corner_form.addRow("Fillet radius:", self.spn_fillet_radius)

        layout.addWidget(corner_group)
        self._on_corner_mode_changed(0)

        # Traffic island
        island_group = QGroupBox("Traffic Island")
        island_form = QFormLayout(island_group)

        self.island_type_combo = QComboBox()
        self.island_type_combo.addItems([
            "None",
            "Round",
            "Teardrop",
        ])
        self.island_type_combo.setCurrentIndex(1)
        self.island_type_combo.currentIndexChanged.connect(
            self._on_island_changed
        )
        island_form.addRow("Island type:", self.island_type_combo)

        self.island_radius_spin = QDoubleSpinBox()
        self.island_radius_spin.setRange(0.5, 30.0)
        self.island_radius_spin.setValue(3.0)
        self.island_radius_spin.setSuffix(" m")
        self.island_radius_spin.setSingleStep(0.5)
        island_form.addRow("Island radius:", self.island_radius_spin)

        self.teardrop_length_spin = QDoubleSpinBox()
        self.teardrop_length_spin.setRange(1.0, 50.0)
        self.teardrop_length_spin.setValue(6.0)
        self.teardrop_length_spin.setSuffix(" m")
        self.teardrop_length_spin.setSingleStep(0.5)
        self.teardrop_length_spin.setEnabled(False)
        island_form.addRow("Teardrop length:", self.teardrop_length_spin)

        layout.addWidget(island_group)

        # Actions
        btn_layout = QHBoxLayout()

        btn_ok = QPushButton("✅ Create Junction")
        btn_ok.setMinimumHeight(40)
        btn_ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 6px; padding: 10px 24px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #283593; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_island_changed(self, index):
        self.island_radius_spin.setEnabled(index > 0)
        self.teardrop_length_spin.setEnabled(index == 2)

    def _on_corner_mode_changed(self, index):
        """Enable only the parameter consumed by the selected solver."""
        self.spn_chamfer_dist.setEnabled(index == 0)
        self.spn_fillet_radius.setEnabled(index == 1)
        self._draw_schema()

    def _draw_schema(self):
        """Draw a compact junction-solution preview."""
        px = QPixmap(380, 110)
        px.fill(QColor(245, 245, 255))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 190, 55

        # Road centerlines
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(40, cy, 340, cy)  # Horizontal road
        p.drawLine(cx, 5, cx, 105)  # Vertical road

        # Curb lines
        p.setPen(QPen(QColor(100, 100, 100), 1, Qt.PenStyle.DashLine))
        for offset in [-18, 18]:
            p.drawLine(40, cy + offset, cx - 30, cy + offset)
            p.drawLine(cx + 30, cy + offset, 340, cy + offset)
        for offset in [-18, 18]:
            p.drawLine(cx + offset, 5, cx + offset, cy - 30)
            p.drawLine(cx + offset, cy + 30, cx + offset, 105)

        mode = (
            self.cmb_corner_mode.currentIndex()
            if hasattr(self, "cmb_corner_mode") else 0
        )
        p.setPen(QPen(QColor(255, 109, 0), 2))
        if mode == 0:
            p.drawLine(cx - 30, cy - 18, cx - 18, cy - 30)
            p.drawLine(cx + 30, cy - 18, cx + 18, cy - 30)
            p.drawLine(cx - 30, cy + 18, cx - 18, cy + 30)
            p.drawLine(cx + 30, cy + 18, cx + 18, cy + 30)
        else:
            p.drawArc(cx - 42, cy - 42, 48, 48, 0, 90 * 16)
            p.drawArc(cx - 6, cy - 42, 48, 48, 90 * 16, 90 * 16)
            p.drawArc(cx - 42, cy - 6, 48, 48, 270 * 16, 90 * 16)
            p.drawArc(cx - 6, cy - 6, 48, 48, 180 * 16, 90 * 16)

        # Island
        p.setPen(QPen(QColor(76, 175, 80), 2))
        p.setBrush(QBrush(QColor(76, 175, 80, 60)))
        p.drawEllipse(cx - 8, cy - 8, 16, 16)

        # Labels
        p.setPen(QColor(255, 109, 0))
        font = QFont("Arial", 7)
        p.setFont(font)
        p.drawText(
            cx - 72, cy - 22,
            "straight chamfer" if mode == 0 else "tangent fillet",
        )

        p.setPen(QColor(76, 175, 80))
        p.drawText(cx + 12, cy + 4, "island")

        p.end()
        self.schema_label.setPixmap(px)

    def get_params(self):
        """Return normalized English parameter keys and values."""
        island_type_map = {0: "none", 1: "round", 2: "teardrop"}
        return {
            "radius": self.spn_radius.value(),
            "corner_mode": (
                "chamfer" if self.cmb_corner_mode.currentIndex() == 0
                else "fillet"
            ),
            "chamfer_dist": self.spn_chamfer_dist.value(),
            "fillet_radius": self.spn_fillet_radius.value(),
            "island_type": island_type_map.get(
                self.island_type_combo.currentIndex(), "none"
            ),
            "island_radius": self.island_radius_spin.value(),
            "teardrop_length": self.teardrop_length_spin.value(),
        }
