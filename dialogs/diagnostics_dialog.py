# -*- coding: utf-8 -*-
"""Diagnostics dialog for PlanX CAD."""

from datetime import datetime

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout, QApplication
)


class DiagnosticsDialog(QDialog):
    def __init__(self, report_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Diagnostics")
        self.setMinimumWidth(760)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)
        intro = QLabel("Copy this report when sharing support details.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        self.report_box = QPlainTextEdit(self)
        self.report_box.setReadOnly(True)
        self.report_box.setPlainText(report_text)
        self.report_box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.report_box)

        row = QHBoxLayout()
        copy_btn = QPushButton("Copy Report")
        copy_btn.clicked.connect(self._copy_report)
        row.addWidget(copy_btn)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._stamp_label = QLabel(f"Generated: {ts}")
        self._stamp_label.setStyleSheet("color: #64748b;")
        row.addWidget(self._stamp_label, alignment=Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)

    def _copy_report(self):
        QApplication.clipboard().setText(self.report_box.toPlainText())
