# -*- coding: utf-8 -*-
"""Release readiness dialog for PlanX CAD beta gating."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton, QApplication
)


class ReleaseReadinessDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Release Readiness / Surum Hazirlik")
        self.setMinimumWidth(780)
        self.setMinimumHeight(520)
        self._rows = rows or []

        layout = QVBoxLayout(self)
        warn_count = len([r for r in self._rows if str(r.get("status", "")) != "OK"])
        ready = warn_count == 0
        state = "READY" if ready else "NOT READY"
        state_tr = "HAZIR" if ready else "HAZIR DEGIL"
        intro = QLabel(f"Beta release gate checks collected in one place. Result: {state} / {state_tr}")
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        table = QTableWidget(0, 4, self)
        table.setHorizontalHeaderLabels(["Check", "Status", "Value", "Action"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.get("check", ""))))
            table.setItem(i, 1, QTableWidgetItem(str(row.get("status", ""))))
            table.setItem(i, 2, QTableWidgetItem(str(row.get("value", ""))))
            table.setItem(i, 3, QTableWidgetItem(str(row.get("action", ""))))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        copy_btn = QPushButton("Copy Report / Raporu Kopyala")
        copy_btn.clicked.connect(self._copy_report)
        layout.addWidget(copy_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _copy_report(self):
        lines = ["Release Readiness Report", "========================", ""]
        for row in self._rows:
            lines.append(
                f"[{row.get('status', '')}] {row.get('check', '')} | {row.get('value', '')} | {row.get('action', '')}"
            )
        QApplication.clipboard().setText("\n".join(lines))
