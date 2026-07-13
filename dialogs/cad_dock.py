# -*- coding: utf-8 -*-
"""
planX CAD — Main Dockable Panel
Bilingual: English (Primary) and Turkish (Secondary).
Highly compact, space-optimized layout with the official PlanX Teal/Slate theme.
"""
from __future__ import annotations

import os
from contextlib import suppress

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize, QSettings
from qgis.PyQt.QtGui import QIcon, QFont, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout,
    QFrame, QSizePolicy, QToolButton, QButtonGroup,
    QScrollArea, QLineEdit, QCompleter
)


class CadToolButton(QToolButton):
    """Custom compact CAD tool button styled with PlanX Teal accents."""

    def __init__(self, icon_path, tooltip, parent=None):
        super().__init__(parent)
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        self.setToolTip(tooltip)
        # Accessibility: icon-only buttons are announced as a bare "button" by
        # screen readers unless given an explicit name. Use the tool label (the
        # text before the shortcut badge) as the name, full tooltip as detail.
        accessible_name = tooltip.split(" [")[0].strip()
        self.setAccessibleName(accessible_name)
        self.setAccessibleDescription(tooltip)
        self.setIconSize(QSize(22, 22))
        self.setFixedSize(34, 34)
        self.setCheckable(True)
        # Keyboard accessibility: allow tab-navigation to every tool button.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 4px;
                background: transparent;
                padding: 2px;
            }
            QToolButton:hover {
                background: #eef6f4;
                border: 1px solid #bfe8dc;
            }
            QToolButton:focus {
                border: 1px solid #0f766e;
                background: #f0fdfa;
            }
            QToolButton:checked {
                background: #bfe8dc;
                border: 1px solid #0f766e;
            }
            QToolButton:pressed {
                background: #99f6e4;
            }
        """)


class CommandLineEdit(QLineEdit):
    """AutoCAD-style command input.

    Behaves like a normal line edit but adds a recallable command history:
    Up/Down arrows cycle through previously entered commands (newest last),
    exactly like the AutoCAD command line. Enter still fires returnPressed.
    """

    escape_requested = pyqtSignal()

    _MAX_HISTORY = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_index = 0  # points one past the last entry (= live input)

    def add_history(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            self._hist_index = len(self._history)
            return
        # Skip consecutive duplicates so Up doesn't repeat the same entry.
        if not (self._history and self._history[-1].lower() == text.lower()):
            self._history.append(text)
            self._history = self._history[-self._MAX_HISTORY:]
        self._hist_index = len(self._history)

    def history(self) -> list[str]:
        return list(self._history)

    def clear_history(self) -> None:
        """Clear recalled commands and return navigation to the live input."""
        self._history.clear()
        self._hist_index = 0

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.clear()
            self._hist_index = len(self._history)
            self.escape_requested.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Up and self._history:
            self._hist_index = max(0, self._hist_index - 1)
            self.setText(self._history[self._hist_index])
            self.selectAll()
            event.accept()
            return
        if key == Qt.Key.Key_Down and self._history:
            self._hist_index = min(len(self._history), self._hist_index + 1)
            if self._hist_index >= len(self._history):
                self.clear()
            else:
                self.setText(self._history[self._hist_index])
                self.selectAll()
            event.accept()
            return
        super().keyPressEvent(event)


class CollapsibleGroupBox(QGroupBox):
    """Collapsible group box with custom PlanX compact header styling."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._on_toggle)
        self._content_widget = None

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 10px;
                color: #0f766e;
                border: 1px solid #d8e0ea;
                border-radius: 4px;
                margin-top: 5px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 1px 6px;
                background: #eef6f4;
                border-radius: 3px;
            }
            QGroupBox::indicator {
                width: 11px;
                height: 11px;
            }
        """)

    def set_content_widget(self, widget):
        self._content_widget = widget

    def _on_toggle(self, checked):
        if self._content_widget:
            self._content_widget.setVisible(checked)


class CADDockWidget(QDockWidget):
    """planX CAD main dockable panel."""
    _GRID_ROW_SPACING = 2
    _GRID_COL_SPACING = 4

    # Emitted when a tool is activated: (tool_key,)
    tool_activated = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    edit_toggle_requested = pyqtSignal()
    quick_start_requested = pyqtSignal()
    pin_last_requested = pyqtSignal()
    workspace_reset_requested = pyqtSignal()
    tool_help_requested = pyqtSignal(str)
    usage_stats_requested = pyqtSignal()
    health_check_requested = pyqtSignal()
    shortcut_audit_requested = pyqtSignal()
    diagnostics_requested = pyqtSignal()
    docs_requested = pyqtSignal()
    shortcuts_requested = pyqtSignal()

    def __init__(self, iface, icon_dir, parent=None):
        super().__init__("PlanX CAD Toolset", parent)
        self.iface = iface
        self.icon_dir = icon_dir

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setMinimumWidth(160)
        self.setAccessibleName("PlanX CAD Toolset panel")

        self.buttons = {}
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._tool_search_terms = {}
        self._recent_tools = []
        self._recent_buttons = []
        self._favorites = []
        self._favorite_buttons = []
        self._last_activated_key = None
        self._activation_count = 0
        self._tool_usage_counts = {}
        self._precision_input_handler = None
        self._command_enter_handler = None

        self._setup_ui()

    def _icon(self, name):
        """Get icon file absolute path."""
        return os.path.join(self.icon_dir, name)

    # AutoCAD-style command aliases -> internal tool key. Used by the command
    # line (search box) to resolve typed commands on Enter. Short forms mirror
    # AutoCAD muscle memory (L=Line, O=Offset, TR=Trim, CO=Copy, MI=Mirror...).
    _COMMAND_ALIASES = {
        "l": "line", "line": "line",
        "pl": "polyline", "pline": "polyline", "polyline": "polyline",
        "rec": "rectangle", "rectang": "rectangle", "rectangle": "rectangle",
        "pol": "polygon", "polygon": "polygon",
        "c": "circle", "circle": "circle",
        "a": "arc", "arc": "arc",
        "o": "offset", "offset": "offset",
        "tr": "trim", "trim": "trim",
        "ex": "extend", "extend": "extend",
        "f": "fillet", "fillet": "fillet",
        "b": "buffer", "buffer": "buffer",
        "m": "move", "move": "move",
        "co": "copy", "cp": "copy", "copy": "copy",
        "ro": "rotate", "rotate": "rotate",
        "sc": "scale", "scale": "scale",
        "mi": "mirror", "mirror": "mirror",
        "ar": "array", "array": "array",
        "div": "divide", "divide": "divide",
        "j": "join", "join": "join",
        "h": "hatch", "hatch": "hatch",
        "mo": "multi_offset", "moff": "multi_offset",
        "ve": "vertex_edit", "vertex": "vertex_edit",
        "xl": "construction_inf", "xline": "construction_inf", "construction": "construction_inf",
        "ray": "construction_ray",
        "seg": "construction_seg",
        "di": "measure", "dist": "measure", "measure": "measure",
        "aa": "measure_area", "area": "measure_area",
        "msl": "measure_select_line", "measureline": "measure_select_line",
        "msa": "measure_select_area", "measurearea": "measure_select_area",
        "dim": "dimension", "dimension": "dimension",
        "road": "road", "junction": "junction",
        "block": "ada_kirma", "blockchamfer": "ada_kirma",
        "chamfer": "ada_kirma",
    }

    # Tool key -> visible shortcut for tooltip badge. Mirrors main_plugin._SHORTCUTS.
    _SHORTCUT_BADGES = {
        "line":         "Ctrl+Shift+L",
        "polyline":     "Ctrl+Shift+P",
        "rectangle":    "Ctrl+Shift+R",
        "polygon":      "Ctrl+Shift+G",
        "circle":       "Ctrl+Shift+C",
        "arc":          "Ctrl+Shift+A",
        "offset":       "Ctrl+Shift+O",
        "trim":         "Ctrl+Shift+T",
        "extend":       "Ctrl+Shift+E",
        "fillet":       "Ctrl+Shift+F",
        "buffer":       "Ctrl+Shift+B",
        "move":         "Ctrl+Shift+M",
        "array":        "Ctrl+Shift+Y",
        "vertex_edit":      "Ctrl+Shift+V",
        "hatch":            "Ctrl+Shift+H",
        "construction_inf": "Ctrl+Shift+K",
        "construction_ray": "Ctrl+Alt+K",
        "construction_seg": "Ctrl+Alt+L",
        "dimension":        "Ctrl+Shift+D",
        "measure":          "Ctrl+Shift+I",
        "divide":           "Ctrl+Shift+U",
        "multi_offset":     "Ctrl+Shift+X",
        "join":             "Ctrl+Shift+J",
    }
    _TOOL_HINTS = {
        "line": "Line: click the start and end points.",
        "polyline": "Polyline: keep clicking vertices; finish with right-click or Enter.",
        "trim": "Trim: pick the cutting boundary, then the target segment.",
        "extend": "Extend: pick the reference edge, then the line to extend.",
        "fillet": "Fillet: select two edges; use a small radius for tight corners.",
        "construction_inf": "Construction Line: create an infinite axis or grid reference.",
        "construction_ray": "Construction Ray: create a one-way reference.",
        "construction_seg": "Construction Segment: create a bounded reference.",
        "measure": "Measure: snap both endpoints for a reliable distance.",
        "road": "Road: define a clean centerline, then configure the platform.",
    }

    def _add_tool_button(self, grid, row, col, key, icon_file, tooltip):
        """Add tool button to grid and register it in button group."""
        shortcut = self._SHORTCUT_BADGES.get(key)
        full_tip = f"{tooltip} [{shortcut}]" if shortcut else tooltip
        btn = CadToolButton(self._icon(icon_file), full_tip)
        btn.clicked.connect(lambda checked, k=key: self._on_button_clicked(k))
        grid.addWidget(btn, row, col)
        self.buttons[key] = btn
        self.button_group.addButton(btn)
        self._register_tool_terms(key, tooltip)
        return btn

    def _register_tool_terms(self, key, tooltip):
        terms = [key.lower()]
        for part in tooltip.replace("/", " ").replace("-", " ").split():
            terms.append(part.strip().lower())
        self._tool_search_terms[key] = " ".join(terms)

    def _on_button_clicked(self, key):
        self.tool_activated.emit(key)

    def _configure_compact_grid(self, grid: QGridLayout) -> None:
        """Keep the dock compact while preserving clear column separation."""
        grid.setVerticalSpacing(self._GRID_ROW_SPACING)
        grid.setHorizontalSpacing(self._GRID_COL_SPACING)
        grid.setContentsMargins(2, 2, 2, 2)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        main_widget = QWidget()
        main_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        scroll.setWidget(main_widget)
        self.setWidget(scroll)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Header ────────────────────────────────────────────────────────
        header = QLabel("🔧 PlanX CAD Toolset")
        header_font = QFont()
        header_font.setPointSize(9)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            "color: #12343b; padding: 4px 6px; "
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #eef6f4, stop:1 #dce9ed); "
            "border-radius: 4px;"
        )
        layout.addWidget(header)

        self.search_input = CommandLineEdit()
        self.search_input.setPlaceholderText(
            "Command or point: L | x,y | @dx,dy | @d<a"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Command line")
        self.search_input.setAccessibleDescription(
            "AutoCAD-style command line. Type a command or alias (L, O, TR, "
            "F, CO, MI...) or enter x,y, @dx,dy, @distance<angle, or direct "
            "distance for the active drawing tool. Up/Down recalls history."
        )
        self.search_input.setStyleSheet(
            "QLineEdit { border: 1px solid #d8e0ea; border-radius: 4px; padding: 4px 6px; "
            "font-family: 'Consolas','Courier New',monospace; "
            "font-size: 10px; background: white; color: #12343b; }"
            "QLineEdit:focus { border: 1px solid #0f766e; }"
        )
        self.search_input.textChanged.connect(self._apply_tool_filter)
        self.search_input.returnPressed.connect(self._run_command)
        self.search_input.escape_requested.connect(self.cancel_requested.emit)
        layout.addWidget(self.search_input)

        # ── Drawing Tools ─────────────────────────────────────────────────
        draw_group = CollapsibleGroupBox("✏️ Drawing")
        draw_grid = QGridLayout()
        self._configure_compact_grid(draw_grid)

        draw_tools = [
            ("line",      "cad_line.svg",      "Line"),
            ("polyline",  "cad_polyline.svg",  "Polyline"),
            ("rectangle", "cad_rectangle.svg", "Rectangle"),
            ("polygon",   "cad_polygon.svg",   "Regular Polygon"),
            ("circle",    "cad_circle.svg",    "Circle"),
            ("arc",       "cad_arc.svg",       "Arc"),
        ]
        draw_content = QWidget()
        draw_content.setLayout(draw_grid)
        for i, (key, icon, tip) in enumerate(draw_tools):
            self._add_tool_button(draw_grid, i // 3, i % 3, key, icon, tip)

        draw_layout = QVBoxLayout()
        draw_layout.setContentsMargins(4, 4, 4, 4)
        draw_layout.setSpacing(0)
        draw_layout.addWidget(draw_content)
        draw_group.setLayout(draw_layout)
        draw_group.set_content_widget(draw_content)
        layout.addWidget(draw_group)

        # ── Editing Tools ─────────────────────────────────────────────────
        edit_group = CollapsibleGroupBox("🔨 Editing")
        edit_grid = QGridLayout()
        self._configure_compact_grid(edit_grid)

        edit_tools = [
            ("offset",       "cad_offset.svg",       "Offset"),
            ("trim",         "cad_trim.svg",         "Trim"),
            ("extend",       "cad_extend.svg",       "Extend"),
            ("fillet",       "cad_fillet.svg",       "Fillet"),
            ("buffer",       "cad_buffer.svg",       "Buffer"),
            ("array",        "cad_array.svg",        "Array"),
            ("vertex_edit",      "cad_vertex_edit.svg",      "Vertex Edit"),
            ("divide",           "cad_divide.svg",           "Divide"),
            ("multi_offset",     "cad_multi_offset.svg",     "Multi-Offset"),
            ("join",             "cad_join.svg",             "Join"),
            ("hatch",            "cad_hatch.svg",            "Hatch (Pattern Fill)"),
            ("construction_inf", "cad_construction.svg",     "Construction Line"),
            ("construction_ray", "cad_construction.svg",     "Construction Ray"),
            ("construction_seg", "cad_construction.svg",     "Construction Segment"),
        ]
        edit_content = QWidget()
        edit_content.setLayout(edit_grid)
        for i, (key, icon, tip) in enumerate(edit_tools):
            self._add_tool_button(edit_grid, i // 3, i % 3, key, icon, tip)

        edit_layout = QVBoxLayout()
        edit_layout.setContentsMargins(4, 4, 4, 4)
        edit_layout.setSpacing(0)
        edit_layout.addWidget(edit_content)
        edit_group.setLayout(edit_layout)
        edit_group.set_content_widget(edit_content)
        layout.addWidget(edit_group)

        # ── Transform Tools ───────────────────────────────────────────────
        transform_group = CollapsibleGroupBox("🔄 Transform")
        transform_grid = QGridLayout()
        self._configure_compact_grid(transform_grid)

        transform_tools = [
            ("move",    "cad_move.svg",    "Move"),
            ("copy",    "cad_copy.svg",    "Copy"),
            ("rotate",  "cad_rotate.svg",  "Rotate (Ctrl: 90° snap)"),
            ("scale",   "cad_scale.svg",   "Scale"),
            ("mirror",  "cad_mirror.svg",  "Mirror"),
        ]
        transform_content = QWidget()
        transform_content.setLayout(transform_grid)
        for i, (key, icon, tip) in enumerate(transform_tools):
            self._add_tool_button(transform_grid, i // 3, i % 3, key, icon, tip)

        transform_layout = QVBoxLayout()
        transform_layout.setContentsMargins(4, 4, 4, 4)
        transform_layout.setSpacing(0)
        transform_layout.addWidget(transform_content)
        transform_group.setLayout(transform_layout)
        transform_group.set_content_widget(transform_content)
        layout.addWidget(transform_group)

        # ── Measurement Tools ─────────────────────────────────────────────
        measure_group = CollapsibleGroupBox("📐 Measurement")
        measure_grid = QGridLayout()
        self._configure_compact_grid(measure_grid)

        self._add_tool_button(measure_grid, 0, 0, "measure", "cad_measure.svg", "Measure Distance")
        self._add_tool_button(measure_grid, 0, 1, "measure_area", "cad_measure_area.svg", "Measure Area")
        self._add_tool_button(measure_grid, 0, 2, "dimension", "cad_dimension.svg", "Dimension")
        self._add_tool_button(measure_grid, 1, 0, "measure_select_line", "cad_measure_select_line.svg", "Measure Selected Line")
        self._add_tool_button(measure_grid, 1, 1, "measure_select_area", "cad_measure_select_area.svg", "Measure Selected Area")

        measure_content = QWidget()
        measure_content.setLayout(measure_grid)
        
        measure_layout = QVBoxLayout()
        measure_layout.setContentsMargins(4, 4, 4, 4)
        measure_layout.setSpacing(0)
        measure_layout.addWidget(measure_content)
        measure_group.setLayout(measure_layout)
        measure_group.set_content_widget(measure_content)
        layout.addWidget(measure_group)

        # ── Urban Planning Tools ──────────────────────────────────────────
        urban_group = CollapsibleGroupBox("🏙️ Urban Planning")
        urban_grid = QGridLayout()
        self._configure_compact_grid(urban_grid)

        # Draw Road button
        road_btn = QPushButton("🛣️ Draw Road")
        road_btn.setMinimumHeight(26)
        road_btn.setCheckable(True)
        road_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 10px;
                color: #0f766e; background: #eef6f4;
                border: 1px solid #bfe8dc; border-radius: 4px; padding: 4px;
            }
            QPushButton:hover { background: #dce9ed; border-color: #0f766e; }
            QPushButton:checked { background: #0f766e; color: white; border-color: #0f766e; }
        """)
        road_btn.setAccessibleName("Draw Road")
        road_btn.setAccessibleDescription("Interactive road-platform drawing tool")
        road_btn.clicked.connect(lambda: self._on_button_clicked("road"))
        urban_grid.addWidget(road_btn, 0, 0)
        self.buttons["road"] = road_btn
        self.button_group.addButton(road_btn)
        self._register_tool_terms("road", "Draw Road")

        # Junction button
        junction_btn = QPushButton("🔵 Junction")
        junction_btn.setMinimumHeight(26)
        junction_btn.setCheckable(True)
        junction_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 10px;
                color: #0f766e; background: #eef6f4;
                border: 1px solid #bfe8dc; border-radius: 4px; padding: 4px;
            }
            QPushButton:hover { background: #dce9ed; border-color: #0f766e; }
            QPushButton:checked { background: #0f766e; color: white; border-color: #0f766e; }
        """)
        junction_btn.setAccessibleName("Junction")
        junction_btn.setAccessibleDescription("Road-intersection design tool")
        junction_btn.clicked.connect(lambda: self._on_button_clicked("junction"))
        urban_grid.addWidget(junction_btn, 0, 1)
        self.buttons["junction"] = junction_btn
        self.button_group.addButton(junction_btn)
        self._register_tool_terms("junction", "Junction Intersection")

        # Block Chamfer button
        ada_btn = QPushButton("🔶 Block Chamfer")
        ada_btn.setMinimumHeight(26)
        ada_btn.setCheckable(True)
        ada_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 10px;
                color: #b45309; background: #fef3c7;
                border: 1px solid #fde68a; border-radius: 4px; padding: 4px;
            }
            QPushButton:hover { background: #fde68a; border-color: #b45309; }
            QPushButton:checked { background: #b45309; color: white; border-color: #b45309; }
        """)
        ada_btn.setAccessibleName("Block Chamfer")
        ada_btn.setAccessibleDescription("Urban-block corner chamfering tool")
        ada_btn.clicked.connect(lambda: self._on_button_clicked("ada_kirma"))
        urban_grid.addWidget(ada_btn, 1, 0, 1, 2)
        self.buttons["ada_kirma"] = ada_btn
        self.button_group.addButton(ada_btn)
        self._register_tool_terms("ada_kirma", "Block Chamfer")

        urban_content = QWidget()
        urban_content.setLayout(urban_grid)
        
        urban_layout = QVBoxLayout()
        urban_layout.setContentsMargins(4, 4, 4, 4)
        urban_layout.setSpacing(0)
        urban_layout.addWidget(urban_content)
        urban_group.setLayout(urban_layout)
        urban_group.set_content_widget(urban_content)
        layout.addWidget(urban_group)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Quick Actions: 3 × 4 compact grid (fits 160 px minimum dock) ──
        # Each row is a themed group: workflow | docs | diagnostics.
        # Less-frequently-used actions (Key Audit, Help Tool, Reset Filter)
        # remain accessible via the plugin menu and keyboard shortcuts.
        qa_grid = QGridLayout()
        qa_grid.setSpacing(3)
        qa_grid.setContentsMargins(2, 2, 2, 2)
        for _col in range(4):
            qa_grid.setColumnStretch(_col, 1)

        def _mk_qa(label, tip, bg, fg, border, hover_bg):
            b = QPushButton(label)
            b.setToolTip(tip)
            # The tooltip expands terse labels such as "Diag" for screen readers.
            b.setAccessibleName(label.replace("↻ ", "").strip())
            b.setAccessibleDescription(tip)
            b.setMinimumHeight(24)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setStyleSheet(
                f"QPushButton{{background:{bg};color:{fg};font-size:9px;"
                f"border:1px solid {border};border-radius:4px;padding:2px 2px;}}"
                f"QPushButton:hover{{background:{hover_bg};border-color:{border};}}"
                f"QPushButton:focus{{border:1px solid #0f766e;}}"
            )
            return b

        # Row 0 — layer & tool workflow controls
        self.edit_btn = _mk_qa(
            "Edit", "Toggle layer editing [Ctrl+Alt+E]",
            "#eff6ff", "#1d4ed8", "#bfdbfe", "#dbeafe")
        self.edit_btn.clicked.connect(lambda: self.edit_toggle_requested.emit())
        qa_grid.addWidget(self.edit_btn, 0, 0)

        cancel_btn = _mk_qa(
            "Cancel", "Cancel active tool [Ctrl+Alt+C]",
            "#fff1f2", "#9f1239", "#fecdd3", "#ffe4e6")
        cancel_btn.clicked.connect(lambda: self.cancel_requested.emit())
        qa_grid.addWidget(cancel_btn, 0, 1)

        repeat_btn = _mk_qa(
            "↻ Last", "Repeat last tool [Ctrl+Shift+Space]",
            "#eef6f4", "#0f766e", "#bfe8dc", "#dce9ed")
        repeat_btn.clicked.connect(lambda: self.tool_activated.emit("__repeat__"))
        qa_grid.addWidget(repeat_btn, 0, 2)

        preflight_btn = _mk_qa(
            "Preflight", "Run readiness check [Ctrl+Alt+F]",
            "#ecfeff", "#0f766e", "#99f6e4", "#ccfbf1")
        preflight_btn.clicked.connect(self.run_preflight)
        qa_grid.addWidget(preflight_btn, 0, 3)

        # Row 1 — help & onboarding
        docs_btn = _mk_qa(
            "Docs", "Open command reference [Ctrl+Alt+H]",
            "#0f766e", "white", "#0f766e", "#115e59")
        docs_btn.clicked.connect(lambda: self.docs_requested.emit())
        qa_grid.addWidget(docs_btn, 1, 0)

        keys_btn = _mk_qa(
            "Keys", "Open shortcut guide [Ctrl+Shift+/]",
            "#f8fafc", "#0f766e", "#bfe8dc", "#eef6f4")
        keys_btn.clicked.connect(lambda: self.shortcuts_requested.emit())
        qa_grid.addWidget(keys_btn, 1, 1)

        start_btn = _mk_qa(
            "Start", "Open quick-start guide [Ctrl+Alt+Q]",
            "#fef9c3", "#854d0e", "#fde68a", "#fef08a")
        start_btn.clicked.connect(lambda: self.quick_start_requested.emit())
        qa_grid.addWidget(start_btn, 1, 2)

        health_btn = _mk_qa(
            "Health", "Run runtime health check [Ctrl+Alt+W]",
            "#f0fdf4", "#166534", "#bbf7d0", "#dcfce7")
        health_btn.clicked.connect(lambda: self.health_check_requested.emit())
        qa_grid.addWidget(health_btn, 1, 3)

        # Row 2 — diagnostics & workspace
        stats_btn = _mk_qa(
            "Stats", "Open usage statistics [Ctrl+Alt+T]",
            "#eff6ff", "#1e3a8a", "#bfdbfe", "#dbeafe")
        stats_btn.clicked.connect(lambda: self.usage_stats_requested.emit())
        qa_grid.addWidget(stats_btn, 2, 0)

        diag_btn = _mk_qa(
            "Diag", "Open diagnostics report [Ctrl+Alt+D]",
            "#ede9fe", "#5b21b6", "#c4b5fd", "#ddd6fe")
        diag_btn.clicked.connect(lambda: self.diagnostics_requested.emit())
        qa_grid.addWidget(diag_btn, 2, 1)

        pin_btn = _mk_qa(
            "Pin", "Pin last tool to favorites [Ctrl+Alt+Z]",
            "#fef3c7", "#92400e", "#fde68a", "#fde68a")
        pin_btn.clicked.connect(self.pin_last_tool)
        qa_grid.addWidget(pin_btn, 2, 2)

        reset_ws_btn = _mk_qa(
            "Reset WS", "Reset workspace [Ctrl+Alt+R]",
            "#fff7ed", "#9a3412", "#fed7aa", "#ffedd5")
        reset_ws_btn.clicked.connect(lambda: self.workspace_reset_requested.emit())
        qa_grid.addWidget(reset_ws_btn, 2, 3)

        layout.addLayout(qa_grid)

        recent_row = QHBoxLayout()
        recent_label = QLabel("Recent:")
        recent_label.setStyleSheet("color: #64748b; font-size: 9px;")
        recent_row.addWidget(recent_label)
        for _ in range(3):
            b = QPushButton("—")
            b.setEnabled(False)
            b.setMinimumHeight(22)
            b.setStyleSheet(
                "QPushButton { background: #f8fafc; color: #334155; font-size: 9px;"
                "border: 1px solid #d8e0ea; border-radius: 4px; padding: 1px 4px; }"
                "QPushButton:enabled:hover { background: #eef6f4; border-color: #0f766e; }"
            )
            b.clicked.connect(lambda checked=False, btn=b: self._emit_recent(btn))
            self._recent_buttons.append(b)
            recent_row.addWidget(b)
        clear_recent_btn = QPushButton("Clear")
        clear_recent_btn.setToolTip("Clear recent tools")
        clear_recent_btn.setMinimumHeight(22)
        clear_recent_btn.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0f766e; font-size: 9px;"
            "border: 1px solid #d8e0ea; border-radius: 4px; padding: 1px 6px; }"
            "QPushButton:hover { background: #eef6f4; border-color: #0f766e; }"
        )
        clear_recent_btn.clicked.connect(self.clear_recent)
        recent_row.addWidget(clear_recent_btn)
        layout.addLayout(recent_row)

        fav_row = QHBoxLayout()
        fav_label = QLabel("Favorites:")
        fav_label.setStyleSheet("color: #64748b; font-size: 9px;")
        fav_row.addWidget(fav_label)
        for _ in range(3):
            b = QPushButton("—")
            b.setEnabled(False)
            b.setMinimumHeight(22)
            b.setStyleSheet(
                "QPushButton { background: #fffbeb; color: #78350f; font-size: 9px;"
                "border: 1px solid #fde68a; border-radius: 4px; padding: 1px 4px; }"
                "QPushButton:enabled:hover { background: #fef3c7; border-color: #92400e; }"
            )
            b.clicked.connect(lambda checked=False, btn=b: self._emit_favorite(btn))
            self._favorite_buttons.append(b)
            fav_row.addWidget(b)
        layout.addLayout(fav_row)

        hint_box = QFrame()
        hint_box.setStyleSheet(
            "QFrame { background: #f8fafc; border: 1px solid #d8e0ea; border-radius: 4px; }"
            "QLabel { color: #334155; font-size: 9px; padding: 4px 6px; }"
        )
        hint_layout = QVBoxLayout(hint_box)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        self.hint_label = QLabel("Tip: Activate a tool to see best-practice guidance.")
        self.hint_label.setWordWrap(True)
        hint_layout.addWidget(self.hint_label)
        layout.addWidget(hint_box)

        # Compact status strip: layer state (wide) + usage counter (narrow)
        # share one horizontal row instead of two stacked rows.
        status_strip = QHBoxLayout()
        status_strip.setSpacing(4)
        self.layer_state_label = QLabel("Layer: unknown")
        self.layer_state_label.setWordWrap(True)
        self.layer_state_label.setStyleSheet(
            "color: #475569; font-size: 9px; padding: 2px 4px; "
            "background: #f8fafc; border: 1px solid #d8e0ea; border-radius: 3px;"
        )
        self.layer_state_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        status_strip.addWidget(self.layer_state_label, 3)
        self.usage_label = QLabel(self._format_usage(0))
        self.usage_label.setToolTip(
            "Tool activations this session"
        )
        self.usage_label.setAccessibleName("Session tool activation count")
        self.usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.usage_label.setStyleSheet(
            "color: #0f766e; font-size: 9px; padding: 2px 4px; "
            "background: #ecfeff; border: 1px solid #99f6e4; border-radius: 3px;"
        )
        status_strip.addWidget(self.usage_label, 1)
        layout.addLayout(status_strip)

        # ── Live Coordinates Widget ──────────────────────────────────────
        try:
            from .coord_widget import LiveCoordWidget
            self.coord_widget = LiveCoordWidget(self.iface, self)
            layout.addWidget(self.coord_widget)
        except Exception as e:
            print(f"[planX-CAD] LiveCoordWidget load error: {e}")
            self.coord_widget = None

        # ── Status Bar ────────────────────────────────────────────────────
        self.status_label = QLabel(
            "Ready — type a command (L, O, TR…) or use Ctrl+Shift+<letter>"
        )
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #64748b; font-size: 9px; padding: 2px 4px; "
            "background: #f1f5f9; border-radius: 3px;"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()
        self._install_command_completer()
        self._load_state()
        self.refresh_layer_state()

    def _install_command_completer(self):
        """Attach an autocomplete popup to the command line, listing every
        AutoCAD alias plus each canonical tool key (built after buttons exist)."""
        words = sorted(set(self._COMMAND_ALIASES.keys()) | set(self.buttons.keys()))
        completer = QCompleter(words, self.search_input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_input.setCompleter(completer)

    def unload(self):
        self._save_state()
        if hasattr(self, 'coord_widget') and self.coord_widget:
            with suppress(Exception):
                self.coord_widget.unload()

    def set_status(self, message):
        self.status_label.setText(message)

    @staticmethod
    def _format_usage(count):
        """Compact usage-counter text for the narrow status-strip column."""
        return f"Act {int(count)}"

    def register_tool_activation(self, key):
        if key not in self.buttons:
            return

        self.set_active_tool(key)

        if key in self._recent_tools:
            self._recent_tools.remove(key)
        self._recent_tools.insert(0, key)
        self._recent_tools = self._recent_tools[:3]
        self._refresh_recent_buttons()
        self._last_activated_key = key
        self._update_hint(key)
        self.refresh_layer_state()
        self._activation_count += 1
        self._tool_usage_counts[key] = int(self._tool_usage_counts.get(key, 0)) + 1
        self.usage_label.setText(self._format_usage(self._activation_count))

    def set_active_tool(self, key):
        """Synchronize the checked tool without recording an activation."""
        btn = self.buttons.get(key)
        self.button_group.setExclusive(False)
        for button in self.buttons.values():
            button.setChecked(False)
        if btn is not None:
            btn.setChecked(True)
        self.button_group.setExclusive(True)

    def _update_hint(self, key):
        hint = self._TOOL_HINTS.get(
            key,
            "Use snapping, work on editable layers, and verify topology before export."
        )
        self.hint_label.setText(f"Tip: {hint}")

    def _refresh_recent_buttons(self):
        for idx, btn in enumerate(self._recent_buttons):
            if idx < len(self._recent_tools):
                key = self._recent_tools[idx]
                label = key.replace("_", " ")
                if len(label) > 12:
                    label = label[:11] + "…"
                btn.setText(label)
                btn.setToolTip(f"Activate {key}")
                btn.setEnabled(True)
                btn.setProperty("tool_key", key)
            else:
                btn.setText("—")
                btn.setToolTip("")
                btn.setEnabled(False)
                btn.setProperty("tool_key", None)

    def _emit_recent(self, button):
        key = button.property("tool_key")
        if key:
            self.tool_activated.emit(key)

    def _refresh_favorite_buttons(self):
        for idx, btn in enumerate(self._favorite_buttons):
            if idx < len(self._favorites):
                key = self._favorites[idx]
                label = key.replace("_", " ")
                if len(label) > 12:
                    label = label[:11] + "…"
                btn.setText(label)
                btn.setToolTip(f"Activate {key}")
                btn.setEnabled(True)
                btn.setProperty("tool_key", key)
            else:
                btn.setText("—")
                btn.setToolTip("")
                btn.setEnabled(False)
                btn.setProperty("tool_key", None)

    def _emit_favorite(self, button):
        key = button.property("tool_key")
        if key:
            self.tool_activated.emit(key)

    def _apply_tool_filter(self, text):
        query = (text or "").strip().lower()
        for key, btn in self.buttons.items():
            terms = self._tool_search_terms.get(key, key)
            visible = (not query) or (query in terms)
            btn.setVisible(visible)

    def _resolve_command(self, text):
        """Map typed command text to a tool key. AutoCAD alias > exact key >
        fuzzy search-term match. Returns the tool key or None."""
        token = (text or "").strip().lower()
        if not token:
            return None
        key = self._COMMAND_ALIASES.get(token)
        if key and key in self.buttons:
            return key
        if token in self.buttons:
            return token
        for k in self.buttons.keys():
            terms = self._tool_search_terms.get(k, k)
            if token in terms:
                return k
        return None

    def _run_command(self):
        """Resolve and run the command currently typed in the command line.

        AutoCAD command-loop conventions:
          - Empty Enter finishes an in-progress sketch when possible.
          - Otherwise, empty Enter repeats the last activated tool.
          - The input line is cleared after each run so commands can be chained.
        """
        raw = (self.search_input.text() or "").strip()
        if not raw:
            if self._command_enter_handler is not None:
                try:
                    if self._command_enter_handler():
                        self.search_input.clear()
                        return
                except Exception as error:
                    self.search_input.clear()
                    self.set_status(f"Unable to finish the active command: {error}")
                    return
            self.tool_activated.emit("__repeat__")
            return
        self.search_input.add_history(raw)
        if self._precision_input_handler is not None:
            try:
                if self._precision_input_handler(raw):
                    self.search_input.clear()
                    return
            except Exception as error:
                self.search_input.clear()
                self.set_status(
                    f"Precision input failed: {error}"
                )
                return
        key = self._resolve_command(raw)
        self.search_input.clear()
        if key:
            self.set_status(f"> {key.replace('_', ' ').upper()}")
            self.tool_activated.emit(key)
        else:
            self.set_status(f"Unknown command: {raw}")

    def _activate_first_match(self):
        """Backward-compatible alias for the command-line Enter handler."""
        self._run_command()

    def set_precision_input_handler(self, handler):
        """Set the synchronous active-tool precision input dispatcher."""
        self._precision_input_handler = handler if callable(handler) else None

    def set_command_enter_handler(self, handler):
        """Set the handler that may consume Enter for an active command."""
        self._command_enter_handler = handler if callable(handler) else None

    def uncheck_all(self):
        checked = self.button_group.checkedButton()
        if checked:
            self.button_group.setExclusive(False)
            checked.setChecked(False)
            self.button_group.setExclusive(True)

    def focus_search(self):
        if hasattr(self, "search_input"):
            self.search_input.setFocus()
            self.search_input.selectAll()

    def reset_filter(self):
        self.search_input.clear()
        self._apply_tool_filter("")
        self.set_status("Filter reset")

    def clear_recent(self):
        self._recent_tools = []
        self._refresh_recent_buttons()
        self.set_status("Recent tools cleared")

    def pin_last_tool(self):
        if not self._last_activated_key:
            self.set_status("No tool to pin yet")
            return
        key = self._last_activated_key
        if key in self._favorites:
            self._favorites.remove(key)
        self._favorites.insert(0, key)
        self._favorites = self._favorites[:3]
        self._refresh_favorite_buttons()
        self.set_status(f"Pinned: {key}")
        self.pin_last_requested.emit()

    def refresh_layer_state(self):
        layer = self.iface.activeLayer()
        if layer is None:
            self.layer_state_label.setText("Layer: none selected")
            self.edit_btn.setText("Edit")
            self.edit_btn.setEnabled(False)
            self.edit_btn.setToolTip("Select a vector layer to edit")
            self.edit_btn.setAccessibleName("Edit unavailable")
            self.edit_btn.setAccessibleDescription(self.edit_btn.toolTip())
            return

        name = getattr(layer, "name", lambda: "unknown")()
        is_vector = hasattr(layer, "geometryType") and hasattr(layer, "isEditable")
        if not is_vector:
            self.layer_state_label.setText(f"Layer: {name} (not vector)")
            self.edit_btn.setText("Edit")
            self.edit_btn.setEnabled(False)
            self.edit_btn.setToolTip("The active layer is not a vector layer")
            self.edit_btn.setAccessibleName("Edit unavailable")
            self.edit_btn.setAccessibleDescription(self.edit_btn.toolTip())
            return

        editable = getattr(layer, "isEditable", lambda: False)()
        state = "editable" if editable else "read-only"
        self.layer_state_label.setText(f"Layer: {name} ({state})")
        if editable:
            label = "Edit OFF"
            tip = "Stop editing [Ctrl+Alt+E]"
        else:
            label = "Edit ON"
            tip = "Start editing [Ctrl+Alt+E]"
        self.edit_btn.setText(label)
        self.edit_btn.setEnabled(True)
        self.edit_btn.setToolTip(tip)
        self.edit_btn.setAccessibleName(label)
        self.edit_btn.setAccessibleDescription(tip)

    def run_preflight(self):
        layer = self.iface.activeLayer()
        if layer is None:
            self.set_status("Preflight: no active layer")
            return
        is_vector = hasattr(layer, "geometryType")
        editable = getattr(layer, "isEditable", lambda: False)()
        if not is_vector:
            self.set_status("Preflight: the active layer is not a vector layer")
            return
        if not editable:
            self.set_status("Preflight: layer is read-only; use Edit ON")
            return
        self.set_status("Preflight: OK (vector and editable)")

    def _save_state(self):
        s = QSettings("PlanX", "PlanXCAD")
        s.setValue("dock/recent_tools", self._recent_tools)
        s.setValue("dock/favorites", self._favorites)
        # Command text and usage counters describe the current session.  Remove
        # legacy persisted values so an unfinished command cannot hide tools on
        # the next launch and the session counter always starts at zero.
        s.remove("dock/search_text")
        s.remove("dock/activation_count")
        s.remove("dock/tool_usage_counts")

    def _load_state(self):
        s = QSettings("PlanX", "PlanXCAD")
        recent = s.value("dock/recent_tools", [], type=list)
        favs = s.value("dock/favorites", [], type=list)

        self.search_input.clear()
        self._recent_tools = [k for k in (recent or []) if k in self.buttons][:3]
        self._favorites = [k for k in (favs or []) if k in self.buttons][:3]
        self._activation_count = 0
        self._tool_usage_counts = {}
        self._refresh_recent_buttons()
        self._refresh_favorite_buttons()
        self.usage_label.setText(self._format_usage(self._activation_count))

    def diagnostics_snapshot(self):
        layer = self.iface.activeLayer()
        return {
            "search_text": self.search_input.text(),
            "recent_tools": list(self._recent_tools),
            "favorites": list(self._favorites),
            "activation_count": int(self._activation_count),
            "tool_usage_counts": dict(self._tool_usage_counts),
            "active_layer_name": (layer.name() if layer and hasattr(layer, "name") else ""),
            "active_layer_editable": bool(layer.isEditable()) if layer and hasattr(layer, "isEditable") else False,
        }

    def clear_workspace_state(self):
        self.search_input.clear()
        self.search_input.clear_history()
        self._recent_tools = []
        self._favorites = []
        self._last_activated_key = None
        self._activation_count = 0
        self._tool_usage_counts = {}
        self.uncheck_all()
        self._refresh_recent_buttons()
        self._refresh_favorite_buttons()
        self.usage_label.setText(self._format_usage(0))
        self.hint_label.setText("Tip: Activate a tool to see best-practice guidance.")
        self.set_status("Workspace reset complete")
        self._save_state()

    def open_help_for_last_tool(self):
        if not self._last_activated_key:
            self.set_status("No active tool; opening the command reference")
            self.docs_requested.emit()
            return
        self.tool_help_requested.emit(self._last_activated_key)
