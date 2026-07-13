# -*- coding: utf-8 -*-
"""Health check dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QLabel, QAbstractItemView
)


class HealthCheckDialog(QDialog):
    def __init__(self, checks, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Health Check / Sistem Kontrolu")
        self.setMinimumWidth(720)
        self.setMinimumHeight(480)

        layout = QVBoxLayout(self)
        intro = QLabel("Runtime readiness checks for safer drafting sessions.")
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        table = QTableWidget(0, 4, self)
        table.setHorizontalHeaderLabels(["Check", "Status", "Value", "Hint"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        table.setAccessibleName("PlanX CAD runtime health checks")
        table.setAccessibleDescription(
            "Read-only table of runtime checks, status values, and remediation hints."
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(checks))

        for i, row in enumerate(checks):
            table.setItem(i, 0, QTableWidgetItem(str(row.get("check", ""))))
            table.setItem(i, 1, QTableWidgetItem(str(row.get("status", ""))))
            table.setItem(i, 2, QTableWidgetItem(str(row.get("value", ""))))
            table.setItem(i, 3, QTableWidgetItem(str(row.get("hint", ""))))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
