# -*- coding: utf-8 -*-
"""Usage statistics dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton
)


class UsageStatsDialog(QDialog):
    def __init__(self, usage_counts, total_activations, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Usage Stats / Kullanim Istatistikleri")
        self.setMinimumWidth(560)
        self.setMinimumHeight(460)

        layout = QVBoxLayout(self)
        intro = QLabel(
            f"Total activations: {int(total_activations)}\n"
            f"Toplam aktivasyon: {int(total_activations)}"
        )
        intro.setStyleSheet("color: #334155; padding: 4px;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        table = QTableWidget(0, 3, self)
        table.setHorizontalHeaderLabels(["Tool", "Count", "Share %"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.horizontalHeader().setStretchLastSection(True)

        total = max(1, int(total_activations))
        rows = sorted((usage_counts or {}).items(), key=lambda kv: kv[1], reverse=True)
        table.setRowCount(len(rows))
        for i, (tool, count) in enumerate(rows):
            c = int(count or 0)
            share = (100.0 * c) / total
            table.setItem(i, 0, QTableWidgetItem(str(tool)))
            table.setItem(i, 1, QTableWidgetItem(str(c)))
            table.setItem(i, 2, QTableWidgetItem(f"{share:.1f}"))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
