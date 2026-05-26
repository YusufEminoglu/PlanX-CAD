# -*- coding: utf-8 -*-
"""Session checklist dialog for PlanX CAD beta workflow."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout


class SessionChecklistDialog(QDialog):
    def __init__(self, run_preflight_cb, run_health_cb, run_audit_cb, parent=None):
        super().__init__(parent)
        self._run_preflight_cb = run_preflight_cb
        self._run_health_cb = run_health_cb
        self._run_audit_cb = run_audit_cb
        self.setWindowTitle("PlanX CAD - Session Checklist / Oturum Kontrol Listesi")
        self.setMinimumWidth(700)
        self.setMinimumHeight(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        text = QLabel(
            "<h3>Beta Session Checklist</h3>"
            "<ol>"
            "<li>Open PlanX CAD dock and select the target vector layer.</li>"
            "<li>Set editing ON for write operations.</li>"
            "<li>Run <b>Preflight</b> and resolve warnings.</li>"
            "<li>Run <b>Health Check</b> and confirm snapping readiness.</li>"
            "<li>Run <b>Shortcut Audit</b> before custom keymap changes.</li>"
            "<li>Use Diagnostics when reporting issues.</li>"
            "</ol>"
            "<p><b>TR:</b> Dock'u acin, hedef vektor katmani secin, duzenlemeyi acin, "
            "Preflight + Health Check calistirin, kisayol degisikligi oncesi Key Audit yapin.</p>"
        )
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setStyleSheet("color: #1e293b; padding: 6px;")
        layout.addWidget(text)

        tools_row = QHBoxLayout()
        preflight_btn = QPushButton("Run Preflight")
        preflight_btn.clicked.connect(self._run_preflight_cb)
        tools_row.addWidget(preflight_btn)
        health_btn = QPushButton("Run Health")
        health_btn.clicked.connect(self._run_health_cb)
        tools_row.addWidget(health_btn)
        audit_btn = QPushButton("Run Key Audit")
        audit_btn.clicked.connect(self._run_audit_cb)
        tools_row.addWidget(audit_btn)
        layout.addLayout(tools_row)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
