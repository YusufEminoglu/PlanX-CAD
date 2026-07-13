# -*- coding: utf-8 -*-
"""Block-chamfer parameter dialog."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QHBoxLayout, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush


class AdaKirmaDialog(QDialog):
    """Collect straight-chamfer or curved-fillet parameters."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔶 Block Chamfer")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        title = QLabel("🔶 Block Chamfer — Corner Resolution")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #e65100; padding: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "Resolve intersections between outer curb lines and optionally\n"
            "remove short remnants left by the operation."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(desc)

        # Schematic preview
        self.schema_label = QLabel()
        self.schema_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schema_label.setMinimumHeight(130)
        self._draw_schema()
        layout.addWidget(self.schema_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Corner mode
        mode_group = QGroupBox("Corner Mode")
        mode_form = QFormLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Curved (Tangent Fillet)",
            "Straight Chamfer",
        ])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_form.addRow("Corner mode:", self.mode_combo)

        layout.addWidget(mode_group)

        # Parameters
        param_group = QGroupBox("Parameters")
        param_form = QFormLayout(param_group)

        self.distance_spin = QDoubleSpinBox()
        self.distance_spin.setRange(0.5, 50.0)
        self.distance_spin.setValue(5.0)
        self.distance_spin.setSuffix(" m")
        self.distance_spin.setSingleStep(0.5)
        self.distance_spin.setToolTip(
            "Trim back from the intersection by this value.\n"
            "Curved mode uses it as the arc radius; straight mode uses it\n"
            "as the setback on both lines."
        )
        self.distance_label = QLabel("Radius (m):")
        param_form.addRow(self.distance_label, self.distance_spin)

        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.01, 5.0)
        self.tolerance_spin.setValue(0.5)
        self.tolerance_spin.setSuffix(" m")
        self.tolerance_spin.setSingleStep(0.1)
        self.tolerance_spin.setToolTip(
            "Search tolerance for line intersections around the clicked point."
        )
        param_form.addRow("Search tolerance:", self.tolerance_spin)

        self.cleanup_threshold_spin = QDoubleSpinBox()
        self.cleanup_threshold_spin.setRange(0.0, 20.0)
        self.cleanup_threshold_spin.setValue(1.0)
        self.cleanup_threshold_spin.setSuffix(" m")
        self.cleanup_threshold_spin.setSingleStep(0.5)
        self.cleanup_threshold_spin.setToolTip(
            "Automatically remove remnant segments shorter than this length."
        )
        param_form.addRow("Remnant cleanup:", self.cleanup_threshold_spin)

        layout.addWidget(param_group)

        # Actions
        btn_layout = QHBoxLayout()

        btn_ok = QPushButton("✅ Apply")
        btn_ok.setMinimumHeight(40)
        btn_ok.setStyleSheet(
            "QPushButton { background: #e65100; color: white; "
            "font-weight: bold; border-radius: 6px; padding: 10px 24px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #f57c00; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_mode_changed(self, index):
        if index == 0:
            self.distance_label.setText("Radius (m):")
        else:
            self.distance_label.setText("Chamfer distance (m):")

    def _draw_schema(self):
        """Draw the before/after corner schematic."""
        px = QPixmap(380, 120)
        px.fill(QColor(255, 248, 240))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # BEFORE: two lines meet at a sharp corner.
        p.setPen(QPen(QColor(120, 120, 120), 2))
        p.drawLine(20, 100, 90, 30)  # Line 1
        p.drawLine(20, 30, 90, 100)  # Line 2

        # Intersection point
        p.setPen(QPen(QColor(255, 0, 0), 6))
        p.drawPoint(55, 65)

        # Label
        p.setPen(QColor(120, 120, 120))
        font = QFont("Arial", 8, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(30, 115, "BEFORE")

        # Arrow
        p.setPen(QPen(QColor(100, 100, 100), 2))
        p.drawLine(120, 65, 150, 65)
        p.drawLine(145, 60, 150, 65)
        p.drawLine(145, 70, 150, 65)

        # AFTER: straight chamfer.
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(170, 100, 200, 55)  # Trimmed line 1
        p.drawLine(170, 30, 200, 75)  # Trimmed line 2

        # Chamfer segment
        p.setPen(QPen(QColor(255, 109, 0), 3))
        p.drawLine(200, 55, 200, 75)

        font2 = QFont("Arial", 7)
        p.setFont(font2)
        p.setPen(QColor(255, 109, 0))
        p.drawText(204, 68, "straight")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(170, 115, "CHAMFER")

        # AFTER: curved fillet.
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(270, 100, 300, 55)
        p.drawLine(270, 30, 300, 75)

        # Arc
        from qgis.PyQt.QtCore import QRectF
        p.setPen(QPen(QColor(76, 175, 80), 3))
        # Compact illustrative arc
        p.drawArc(QRectF(285, 50, 30, 30).toRect(), 60 * 16, 60 * 16)

        p.setPen(QColor(76, 175, 80))
        p.setFont(font2)
        p.drawText(310, 68, "curved")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(270, 115, "FILLET")

        p.end()
        self.schema_label.setPixmap(px)

    def get_params(self):
        """Return normalized English parameter keys and values."""
        return {
            "mode": "curved" if self.mode_combo.currentIndex() == 0 else "straight",
            "distance": self.distance_spin.value(),
            "tolerance": self.tolerance_spin.value(),
            "cleanup_threshold": self.cleanup_threshold_spin.value(),
        }
