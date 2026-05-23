# -*- coding: utf-8 -*-
"""Command palette dialog for rapid CAD tool activation."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton
)


class CommandPaletteDialog(QDialog):
    tool_selected = pyqtSignal(str)

    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Command Palette")
        self.setMinimumWidth(520)
        self.setMinimumHeight(500)
        self._shortcuts = shortcuts
        self._items = []
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel("Type command name and press Enter. / Komut adini yazip Enter'a basin.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search command / Komut ara")
        self.search_input.textChanged.connect(self._filter)
        self.search_input.returnPressed.connect(self._activate_current)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget(self)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._activate_current())
        layout.addWidget(self.list_widget)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _populate(self):
        self._items = []
        for key, seq in self._shortcuts:
            self._items.append((key, seq))
        self._render(self._items)

    def _render(self, rows):
        self.list_widget.clear()
        for key, seq in rows:
            item = QListWidgetItem(f"{key}    [{seq}]")
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _filter(self):
        query = (self.search_input.text() or "").strip().lower()
        if not query:
            self._render(self._items)
            return
        rows = [r for r in self._items if query in r[0].lower() or query in r[1].lower()]
        self._render(rows)

    def _activate_current(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        key = item.data(Qt.UserRole)
        if key:
            self.tool_selected.emit(key)
            self.accept()
