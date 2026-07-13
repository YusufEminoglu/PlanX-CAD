# -*- coding: utf-8 -*-
"""Command palette dialog for rapid CAD tool activation."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QHBoxLayout, QComboBox
)


class CommandPaletteDialog(QDialog):
    tool_selected = pyqtSignal(str)

    def __init__(self, shortcuts, usage_counts=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Command Palette")
        self.setMinimumWidth(620)
        self.setMinimumHeight(500)
        self._shortcuts = shortcuts
        self._usage_counts = usage_counts or {}
        self._items = []
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel("Type a command name and press Enter.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search commands and aliases")
        self.search_input.textChanged.connect(self._filter)
        self.search_input.returnPressed.connect(self._activate_current)
        layout.addWidget(self.search_input)

        row = QHBoxLayout()
        self.category_combo = QComboBox(self)
        self.category_combo.addItems(["All", "Drawing", "Editing", "Transform", "Measure", "Urban"])
        self.category_combo.currentTextChanged.connect(self._filter)
        row.addWidget(self.category_combo)
        layout.addLayout(row)

        self.list_widget = QListWidget(self)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._activate_current())
        layout.addWidget(self.list_widget)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate(self):
        categories = {
            "line": "Drawing", "polyline": "Drawing", "rectangle": "Drawing", "polygon": "Drawing", "circle": "Drawing", "arc": "Drawing",
            "offset": "Editing", "trim": "Editing", "extend": "Editing", "fillet": "Editing", "buffer": "Editing", "vertex_edit": "Editing",
            "hatch": "Editing", "construction_inf": "Editing", "construction_ray": "Editing", "construction_seg": "Editing",
            "divide": "Editing", "multi_offset": "Editing", "join": "Editing",
            "move": "Transform", "copy": "Transform", "rotate": "Transform", "scale": "Transform", "mirror": "Transform", "array": "Transform",
            "dimension": "Measure", "measure": "Measure", "measure_area": "Measure", "measure_select_line": "Measure", "measure_select_area": "Measure",
            "road": "Urban", "junction": "Urban", "ada_kirma": "Urban",
        }
        display_names = {
            "line": "Line", "polyline": "Polyline", "rectangle": "Rectangle",
            "polygon": "Regular Polygon", "circle": "Circle", "arc": "Arc",
            "offset": "Offset", "trim": "Trim", "extend": "Extend",
            "fillet": "Fillet", "buffer": "Buffer", "vertex_edit": "Vertex Edit",
            "hatch": "Hatch", "construction_inf": "Construction Line",
            "construction_ray": "Construction Ray", "construction_seg": "Construction Segment",
            "divide": "Divide", "multi_offset": "Multi-Offset", "join": "Join",
            "move": "Move", "copy": "Copy", "rotate": "Rotate", "scale": "Scale",
            "mirror": "Mirror", "array": "Array", "dimension": "Dimension",
            "measure": "Measure Distance", "measure_area": "Measure Area",
            "measure_select_line": "Measure Selected Line",
            "measure_select_area": "Measure Selected Area", "road": "Draw Road",
            "junction": "Junction", "ada_kirma": "Block Chamfer",
        }
        aliases = {
            "line": ["segment"], "polyline": ["pline", "connected line"],
            "rectangle": ["box"], "polygon": ["regular polygon"],
            "circle": ["radius"], "arc": ["curve"], "offset": ["parallel"],
            "trim": ["cut"], "extend": ["lengthen"], "fillet": ["round corner"],
            "buffer": ["zone"], "move": ["translate"], "copy": ["duplicate"],
            "rotate": ["turn"], "scale": ["resize"], "mirror": ["reflect"],
            "dimension": ["label distance"], "measure": ["distance"],
            "measure_area": ["area"], "join": ["merge lines"],
            "divide": ["split equally"], "hatch": ["fill pattern"],
            "road": ["street platform"], "junction": ["intersection"],
            "ada_kirma": ["block", "block chamfer", "chamfer"],
        }
        self._items = []
        for key, seq in self._shortcuts:
            self._items.append({
                "key": key,
                "name": display_names.get(key, key.replace("_", " ").title()),
                "shortcut": seq,
                "category": categories.get(key, "Urban" if key in ("road", "junction", "ada_kirma") else "Editing"),
                "aliases": aliases.get(key, []),
                "usage": int(self._usage_counts.get(key, 0)),
            })
        self._items.sort(key=lambda it: (-it["usage"], it["name"]))
        self._render(self._items)

    def _render(self, rows):
        self.list_widget.clear()
        for row in rows:
            key = row["key"]
            name = row["name"]
            seq = row["shortcut"]
            cat = row["category"]
            usage = row["usage"]
            item = QListWidgetItem(f"{name}    [{seq}]    ({cat})    Uses: {usage}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _filter(self):
        query = (self.search_input.text() or "").strip().lower()
        category = self.category_combo.currentText()
        rows = []
        for r in self._items:
            if category != "All" and r["category"] != category:
                continue
            blob = " ".join(
                [r["key"], r["name"], r["shortcut"], r["category"]]
                + r["aliases"]
            ).lower()
            if query and query not in blob:
                continue
            rows.append(r)
        self._render(rows)

    def _activate_current(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self.tool_selected.emit(key)
            self.accept()
