# -*- coding: utf-8 -*-
"""Shortcut guide dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QHBoxLayout, QComboBox, QAbstractItemView
)

from ..core.tool_catalog import SECTIONS, TOOL_CATALOG


class ShortcutHelpDialog(QDialog):
    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Shortcut Guide")
        self.setMinimumWidth(700)
        self.setMinimumHeight(560)
        self._shortcuts = shortcuts
        self._rows = []
        self._build_ui()
        self._populate_rows()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Keyboard-first workflow: Ctrl+Shift+S focuses the command line; "
            "Ctrl+Shift+Space repeats the last tool."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search commands or shortcuts")
        self.search_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search_input)

        self.category_combo = QComboBox(self)
        self.category_combo.addItems(["All", *SECTIONS, "System"])
        self.category_combo.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self.category_combo)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Command", "Shortcut", "Category"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setAccessibleName("PlanX CAD keyboard shortcuts")
        self.table.setAccessibleDescription(
            "Read-only, filterable table of CAD commands, shortcuts, and categories."
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate_rows(self):
        names = {
            "line": "Line", "polyline": "Polyline", "rectangle": "Rectangle",
            "polygon": "Regular Polygon", "circle": "Circle", "arc": "Arc",
            "offset": "Offset", "trim": "Trim", "extend": "Extend",
            "fillet": "Fillet", "chamfer": "Chamfer", "break": "Break",
            "lengthen": "Lengthen", "align": "Align", "stretch": "Stretch",
            "explode": "Explode", "buffer": "Buffer", "move": "Move",
            "array": "Array", "copy": "Copy", "rotate": "Rotate", "scale": "Scale",
            "mirror": "Mirror", "vertex_edit": "Vertex Edit", "hatch": "Hatch",
            "construction_inf": "Construction Line", "construction_ray": "Construction Ray",
            "construction_seg": "Construction Segment", "dimension": "Dimension",
            "measure": "Measure Distance", "measure_area": "Measure Area",
            "measure_select_line": "Measure Selected Line",
            "measure_select_area": "Measure Selected Area", "divide": "Divide",
            "multi_offset": "Multi-Offset", "join": "Join", "road": "Draw Road",
            "junction": "Junction", "ada_kirma": "Block Chamfer",
        }

        # Same groups as the dock (core.tool_catalog).
        categories = {entry.key: entry.section for entry in TOOL_CATALOG}

        self._rows = []
        for tool_key, seq in self._shortcuts:
            self._rows.append({
                "command": names.get(tool_key, tool_key.replace("_", " ").title()),
                "shortcut": seq,
                "category": categories.get(tool_key, "System"),
            })

        self._rows.extend([
            {"command": "Repeat Last Tool", "shortcut": "Ctrl+Shift+Space", "category": "System"},
            {"command": "Focus Command Line", "shortcut": "Ctrl+Shift+S", "category": "System"},
            {"command": "Open Shortcut Guide", "shortcut": "Ctrl+Shift+/", "category": "System"},
            {"command": "Open Command Reference", "shortcut": "Ctrl+Alt+H", "category": "System"},
            {"command": "Open Smoke Test Checklist", "shortcut": "Ctrl+Alt+M", "category": "System"},
            {"command": "Open Command Palette", "shortcut": "Ctrl+Alt+P", "category": "System"},
            {"command": "Cancel Active Tool", "shortcut": "Ctrl+Alt+C", "category": "System"},
            {"command": "Toggle Layer Editing", "shortcut": "Ctrl+Alt+E", "category": "System"},
            {"command": "Run Preflight", "shortcut": "Ctrl+Alt+F", "category": "System"},
            {"command": "Open Quick Start", "shortcut": "Ctrl+Alt+Q", "category": "System"},
            {"command": "Open Session Checklist", "shortcut": "Ctrl+Alt+G", "category": "System"},
            {"command": "Pin Last Tool", "shortcut": "Ctrl+Alt+Z", "category": "System"},
            {"command": "Open Diagnostics", "shortcut": "Ctrl+Alt+D", "category": "System"},
            {"command": "Reset Workspace", "shortcut": "Ctrl+Alt+R", "category": "System"},
            {"command": "Open Usage Statistics", "shortcut": "Ctrl+Alt+T", "category": "System"},
            {"command": "Open Health Check", "shortcut": "Ctrl+Alt+W", "category": "System"},
            {"command": "Open Shortcut Audit", "shortcut": "Ctrl+Alt+Y", "category": "System"},
            {"command": "Open Issue Template", "shortcut": "Ctrl+Alt+N", "category": "System"},
            {"command": "Open Release Readiness", "shortcut": "Ctrl+Alt+V", "category": "System"},
            {"command": "Toggle Object Snap", "shortcut": "F3", "category": "System"},
            {"command": "Toggle Ortho Tracking", "shortcut": "F8", "category": "System"},
            {"command": "Toggle Polar Tracking", "shortcut": "F10", "category": "System"},
            {"command": "Toggle Dynamic Input", "shortcut": "F12", "category": "System"},
        ])

        self._render_rows(self._rows)

    def _render_rows(self, rows):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["command"]))
            self.table.setItem(r, 1, QTableWidgetItem(row["shortcut"]))
            self.table.setItem(r, 2, QTableWidgetItem(row["category"]))
        self.table.resizeColumnsToContents()

    def _apply_filter(self):
        query = (self.search_input.text() or "").strip().lower()
        cat = self.category_combo.currentText()
        filtered = []
        for row in self._rows:
            if cat != "All" and row["category"] != cat:
                continue
            blob = f"{row['command']} {row['shortcut']} {row['category']}".lower()
            if query and query not in blob:
                continue
            filtered.append(row)

        self._render_rows(filtered)
