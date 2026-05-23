# -*- coding: utf-8 -*-
"""Shortcut guide dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QPushButton


class ShortcutHelpDialog(QDialog):
    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Shortcut Guide")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self._shortcuts = shortcuts
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Use Ctrl+Shift+S to focus tool search, Ctrl+Shift+Space to repeat last tool.\n"
            "Construction modes: infinite (Ctrl+Shift+K), ray (Ctrl+Alt+K), segment (Ctrl+Alt+L)."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        table = QTableWidget(len(self._shortcuts), 2, self)
        table.setHorizontalHeaderLabels(["Tool Key", "Shortcut"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)

        for row, (tool_key, seq) in enumerate(self._shortcuts):
            table.setItem(row, 0, QTableWidgetItem(tool_key))
            table.setItem(row, 1, QTableWidgetItem(seq))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
