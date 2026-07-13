# -*- coding: utf-8 -*-
"""Quick start onboarding dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton


class QuickStartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Quick Start")
        self.setMinimumWidth(620)
        self.setMinimumHeight(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        body = QLabel(
            "<h3>5-step startup workflow</h3>"
            "<ol>"
            "<li><b>Select target vector layer</b> and make it editable (Edit ON/OFF).</li>"
            "<li><b>Run Preflight</b> to verify vector + editable state.</li>"
            "<li><b>Use Find tool</b> or Command Palette (Ctrl+Alt+P) to activate command.</li>"
            "<li><b>Draw/Edit with snapping enabled</b> and monitor Tip/Layer state panel.</li>"
            "<li><b>Use Repeat/Recent</b> for speed, then cancel the active tool safely (Ctrl+Alt+C).</li>"
            "</ol>"
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setStyleSheet("color: #1e293b; padding: 6px;")
        layout.addWidget(body)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
