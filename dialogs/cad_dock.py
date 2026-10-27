# -*- coding: utf-8 -*-
"""
planX CAD — Main Dockable Panel

Layout, top to bottom:
  prompt line + command line   AutoCAD-style; typing also searches every tool
  Quick strip                  pinned tools first, then recent ones
  tabs: CAD | Measure | Urban  plus a "⋯" menu for help and troubleshooting
  tool list                    CAD = Draw / Modify / Transform sections
  active-command card          the tool's prompt and its settings, inline
  status bar                   layer, OSNAP / ORTHO / POLAR / DYN, coordinates

Tools, names, aliases and groups come from ``core.tool_catalog`` so the dock,
the command palette and the shortcut guide agree.
"""
from __future__ import annotations

import os
from contextlib import suppress

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize, QSettings, QByteArray, QEvent
from qgis.PyQt.QtGui import QIcon, QFont, QColor, QPainter, QPixmap, QPalette, QFontMetrics
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QFrame, QSizePolicy, QToolButton, QPushButton, QButtonGroup,
    QScrollArea, QLineEdit, QCompleter, QTabBar, QStackedWidget, QMenu,
)

try:  # QtSvg ships with QGIS; recolouring icons for dark themes needs it.
    from qgis.PyQt.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - defensive
    QSvgRenderer = None

from ..core.drafting_state import DRAFTING_STATE
from ..core.tool_catalog import TABS, match_tools, tab_of, tool_entry, tools_in_section
from ..core.tool_options import option_values, save_options, set_option
from .option_widgets import make_option_widget

_SETTINGS = ("PlanX", "PlanXCAD")
_QUICK_SLOTS = 6

# Width breakpoints (dock pixels) for the tool grid.
_TWO_COLUMNS_MIN = 270
_LABELS_MIN = 220

# Colour tokens. The light set is the PlanX teal/slate palette; the dark set
# keeps the accent readable on QGIS' "Night Mapping" and other dark themes.
_LIGHT = {
    "accent": "#0f766e", "accent_soft": "#e6f4f1", "accent_mid": "#bfe8dc",
    "muted": "#64748b", "border": "#d8e0ea", "pin": "#b45309", "icon_ink": None,
}
_DARK = {
    "accent": "#2dd4bf", "accent_soft": "#173b37", "accent_mid": "#21564f",
    "muted": "#94a3b8", "border": "#3d4b52", "pin": "#f59e0b", "icon_ink": "#c7d2fe",
}
# Hard-coded navy strokes in icons/*.svg, swapped for a light ink on dark themes.
_ICON_INKS = ("#1a237e", "#283593")


def _is_dark(widget) -> bool:
    return widget.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _load_icon(path: str, ink: str | None, size: int = 20) -> QIcon:
    """Load an SVG icon, recoloured with ``ink`` when given."""
    if not os.path.exists(path):
        return QIcon()
    if ink is None or QSvgRenderer is None:
        return QIcon(path)
    try:
        with open(path, encoding="utf-8") as handle:
            data = handle.read()
    except OSError:
        return QIcon(path)
    for colour in _ICON_INKS:
        data = data.replace(colour, ink).replace(colour.upper(), ink)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    if not renderer.isValid():
        return QIcon(path)
    icon = QIcon()
    for px in (size, size * 2):
        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class ToolRowButton(QPushButton):
    """A labelled tool button with the command alias drawn as a right badge.

    In compact mode (narrow dock) it shrinks to an icon; the name and alias
    stay in the tooltip and the accessible name.
    """

    def __init__(self, key, label, alias, tooltip, parent=None):
        super().__init__(parent)
        self.tool_key = key
        self._label = label
        self._alias = alias
        self._compact = False
        self.alias_color = QColor(_LIGHT["accent"])
        self.setProperty("toolRow", True)
        self.setCheckable(True)
        self.setIconSize(QSize(18, 18))
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(tooltip)
        self.setAccessibleName(label)
        self.setAccessibleDescription(tooltip)
        # Keyboard accessibility: every tool is reachable with Tab.
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setText(label)

    def set_compact(self, compact: bool) -> None:
        self._compact = bool(compact)
        if self._compact:
            self.setFixedSize(34, 30)
        else:
            self.setMinimumSize(0, 26)
            self.setMaximumSize(16777215, 28)
        self._update_text()
        self.update()

    def minimumSizeHint(self):
        # Never let the full label force the dock wider; the text elides.
        if self._compact:
            return QSize(34, 30)
        return QSize(self.iconSize().width() + 40, 26)

    def _alias_font(self) -> QFont:
        font = QFont(self.font())
        size = font.pointSizeF()
        if size > 0:
            font.setPointSizeF(max(6.5, size * 0.82))
        font.setBold(True)
        return font

    def _alias_width(self) -> int:
        if self._compact or not self._alias:
            return 0
        return QFontMetrics(self._alias_font()).horizontalAdvance(self._alias) + 12

    def _update_text(self) -> None:
        if self._compact:
            self.setText("")
            return
        available = self.width() - self.iconSize().width() - 22 - self._alias_width()
        metrics = QFontMetrics(self.font())
        self.setText(metrics.elidedText(self._label, Qt.TextElideMode.ElideRight, max(24, available)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_text()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._compact or not self._alias:
            return
        painter = QPainter(self)
        painter.setFont(self._alias_font())
        painter.setPen(self.alias_color)
        painter.drawText(
            self.rect().adjusted(0, 0, -8, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self._alias,
        )
        painter.end()


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


class CADDockWidget(QDockWidget):
    """planX CAD main dockable panel."""

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
    ortho_toggle_requested = pyqtSignal()
    polar_toggle_requested = pyqtSignal()
    osnap_toggle_requested = pyqtSignal()
    dynamic_input_toggle_requested = pyqtSignal()

    # AutoCAD-style command aliases -> internal tool key. Used by the command
    # line to resolve typed commands on Enter. Short forms mirror AutoCAD
    # muscle memory (L=Line, O=Offset, TR=Trim, CO=Copy, MI=Mirror...).
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
        "cha": "chamfer", "chamfer": "chamfer",
        "br": "break", "break": "break",
        "len": "lengthen", "lengthen": "lengthen",
        "al": "align", "align": "align",
        "s": "stretch", "stretch": "stretch",
        "x": "explode", "explode": "explode",
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
        # CHAMFER is the general two-line command (AutoCAD parity); the urban
        # block-corner tool keeps its own aliases.
        "block": "ada_kirma", "blockchamfer": "ada_kirma",
        "env": "envelope", "envelope": "envelope", "setback": "envelope",
        "sight": "sight_triangle", "st": "sight_triangle",
        "park": "parking", "parking": "parking",
        "rb": "roundabout", "roundabout": "roundabout",
        "cul": "turning_head", "culdesac": "turning_head", "turninghead": "turning_head",
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

    _DRAFTING_CHIPS = (
        ("osnap", "OSNAP", "Object snap [F3]"),
        ("ortho", "ORTHO", "Ortho: lock to 0/90/180/270° [F8]"),
        ("polar", "POLAR", "Polar tracking [F10]"),
        ("dyn", "DYN", "Dynamic input next to the cursor [F12]"),
    )

    def __init__(self, iface, icon_dir, parent=None):
        super().__init__("PlanX CAD Toolset", parent)
        self.iface = iface
        self.icon_dir = icon_dir

        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setMinimumWidth(190)
        self.setAccessibleName("PlanX CAD Toolset panel")

        self.buttons = {}
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._tool_search_terms = {}
        self._recent_tools = []
        self._favorites = []
        self._quick_buttons = []
        self._last_activated_key = None
        self._activation_count = 0
        self._tool_usage_counts = {}
        self._precision_input_handler = None
        self._command_enter_handler = None
        self._card_tool = None
        self._card_key = None
        self._option_rows = []
        self._section_buttons = {}
        self._section_grids = {}
        self._section_headers = {}
        self._search_buttons = []
        self._width_mode = None
        self._theme = dict(_LIGHT)
        self._icon_targets = []  # (widget, icon file) pairs re-tinted on theme change
        self._dark = False

        self._setup_ui()
        DRAFTING_STATE.add_listener(self._on_drafting_changed)
        self._on_drafting_changed(DRAFTING_STATE)

    # ── Construction ────────────────────────────────────────────────────

    def _icon(self, name):
        """Get icon file absolute path."""
        return os.path.join(self.icon_dir, name)

    def _themed_icon(self, name, size=20):
        return _load_icon(self._icon(name), self._theme["icon_ink"], size)

    def _tooltip_for(self, entry):
        shortcut = self._SHORTCUT_BADGES.get(entry.key)
        tip = f"{entry.label}  ({entry.alias})"
        if shortcut:
            tip += f" [{shortcut}]"
        return f"{tip}\n{entry.hint}\nRight-click to pin it to Quick."

    def _setup_ui(self):
        root = QWidget()
        root.setObjectName("planxCadRoot")
        self.setWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Prompt line + command line ─────────────────────────────────
        self.status_label = QLabel(
            "Ready. Type a command (L, O, TR…) or pick a tool."
        )
        self.status_label.setObjectName("promptLine")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Command prompt")
        layout.addWidget(self.status_label)

        self.search_input = CommandLineEdit()
        self.search_input.setObjectName("commandLine")
        self.search_input.setPlaceholderText("Command or point: L | x,y | @dx,dy | @d<a")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Command line")
        self.search_input.setAccessibleDescription(
            "AutoCAD-style command line. Type a command or alias (L, O, TR, "
            "F, CO, MI...) or enter x,y, @dx,dy, @distance<angle, or direct "
            "distance for the active drawing tool. Typing a name lists matching "
            "tools from every tab. Up/Down recalls history."
        )
        self.search_input.textChanged.connect(self._apply_tool_filter)
        self.search_input.returnPressed.connect(self._run_command)
        self.search_input.escape_requested.connect(self.cancel_requested.emit)
        layout.addWidget(self.search_input)

        # ── Quick strip ────────────────────────────────────────────────
        quick_row = QHBoxLayout()
        quick_row.setSpacing(2)
        quick_label = QLabel("Quick")
        self._quick_label = quick_label
        quick_label.setObjectName("metaLabel")
        quick_label.setToolTip("Pinned tools first, then recent ones. Right-click a tool to pin it.")
        quick_row.addWidget(quick_label)
        for _ in range(_QUICK_SLOTS):
            btn = QToolButton()
            btn.setObjectName("quickButton")
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(26, 26)
            btn.setAutoRaise(True)
            btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.clicked.connect(lambda _checked=False, b=btn: self._emit_quick(b))
            btn.customContextMenuRequested.connect(
                lambda pos, b=btn: self._show_tool_menu(b.property("tool_key"), b, pos)
            )
            btn.hide()
            self._quick_buttons.append(btn)
            quick_row.addWidget(btn)
        self._quick_empty = QLabel("Tools you use appear here.")
        self._quick_empty.setObjectName("metaLabel")
        quick_row.addWidget(self._quick_empty)
        quick_row.addStretch(1)
        layout.addLayout(quick_row)

        # ── Tabs + "⋯" menu ────────────────────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(2)
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("toolTabs")
        self.tab_bar.setExpanding(True)
        self.tab_bar.setDrawBase(False)
        self.tab_bar.setUsesScrollButtons(False)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_bar.setAccessibleName("Tool tabs")
        self._tab_ids = []
        for tab_id, title, sections in TABS:
            count = sum(len(tools_in_section(s)) for s in sections)
            index = self.tab_bar.addTab(title)
            self.tab_bar.setTabToolTip(index, f"{title}: {count} tools")
            self._tab_ids.append(tab_id)
        tab_row.addWidget(self.tab_bar, 1)
        tab_row.addWidget(self._build_more_button())
        layout.addLayout(tab_row)

        # ── Tool pages ─────────────────────────────────────────────────
        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        for tab_id, _title, sections in TABS:
            self.pages.addWidget(self._build_tool_page(sections, collapsible=len(sections) > 1))
        self._search_page = self._build_search_page()
        self.pages.addWidget(self._search_page)
        layout.addWidget(self.pages, 1)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)

        # ── Active-command card ────────────────────────────────────────
        layout.addWidget(self._build_active_card())

        # ── Status bar: layer, drafting aids, coordinates ──────────────
        status = QFrame()
        status.setObjectName("statusBar")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(0, 4, 0, 0)
        status_layout.setSpacing(4)

        self.edit_btn = QToolButton()
        self.edit_btn.setObjectName("layerBar")
        self.edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.edit_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit_btn.clicked.connect(self.edit_toggle_requested.emit)
        status_layout.addWidget(self.edit_btn)
        # Backward-compatible name for the layer state text.
        self.layer_state_label = self.edit_btn

        chips = QHBoxLayout()
        chips.setSpacing(3)
        self._chips = {}
        signals = {
            "osnap": self.osnap_toggle_requested,
            "ortho": self.ortho_toggle_requested,
            "polar": self.polar_toggle_requested,
            "dyn": self.dynamic_input_toggle_requested,
        }
        for key, text, tip in self._DRAFTING_CHIPS:
            chip = QToolButton()
            chip.setObjectName("draftChip")
            chip.setText(text)
            chip.setCheckable(True)
            chip.setToolTip(tip)
            chip.setAccessibleName(f"{text} toggle")
            chip.setAccessibleDescription(tip)
            chip.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            chip.setMinimumWidth(36)
            chip.clicked.connect(lambda _checked=False, s=signals[key]: self._on_chip_clicked(s))
            chips.addWidget(chip)
            self._chips[key] = chip
        status_layout.addLayout(chips)

        try:
            from .coord_widget import LiveCoordWidget
            self.coord_widget = LiveCoordWidget(self.iface, self)
            status_layout.addWidget(self.coord_widget)
        except Exception as e:
            print(f"[planX-CAD] LiveCoordWidget load error: {e}")
            self.coord_widget = None
        layout.addWidget(status)

        self._install_command_completer()
        self._apply_theme()
        self._load_state()
        self.refresh_layer_state()
        self._apply_width_mode(force=True)

    def _build_more_button(self):
        more = QToolButton()
        more.setObjectName("moreButton")
        more.setText("⋯")
        more.setToolTip("Help, troubleshooting and workspace")
        more.setAccessibleName("More: help and troubleshooting")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        menu = QMenu(more)
        menu.addSection("Help")
        menu.addAction("Command reference\tCtrl+Alt+H").triggered.connect(self.docs_requested.emit)
        menu.addAction("Help for the active tool").triggered.connect(self.open_help_for_last_tool)
        menu.addAction("Shortcut guide\tCtrl+Shift+/").triggered.connect(self.shortcuts_requested.emit)
        menu.addAction("Quick start\tCtrl+Alt+Q").triggered.connect(self.quick_start_requested.emit)
        menu.addSection("Troubleshooting")
        menu.addAction("Check the active layer\tCtrl+Alt+F").triggered.connect(self.run_preflight)
        menu.addAction("Health check\tCtrl+Alt+W").triggered.connect(self.health_check_requested.emit)
        menu.addAction("Diagnostics\tCtrl+Alt+D").triggered.connect(self.diagnostics_requested.emit)
        menu.addAction("Usage statistics\tCtrl+Alt+T").triggered.connect(self.usage_stats_requested.emit)
        menu.addAction("Shortcut conflicts").triggered.connect(self.shortcut_audit_requested.emit)
        menu.addSection("Workspace")
        menu.addAction("Clear recent tools").triggered.connect(self.clear_recent)
        menu.addAction("Reset workspace…\tCtrl+Alt+R").triggered.connect(self.workspace_reset_requested.emit)
        more.setMenu(menu)
        self._more_menu = menu
        return more

    def _build_tool_page(self, sections, collapsible):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(2)
        for section in sections:
            entries = tools_in_section(section)
            if collapsible:
                header = QToolButton()
                header.setObjectName("sectionHeader")
                header.setText(f"{section.upper()}   {len(entries)}")
                header.setCheckable(True)
                header.setChecked(True)
                header.setArrowType(Qt.ArrowType.DownArrow)
                header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                header.setAutoRaise(True)
                header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                header.setAccessibleName(f"{section} section")
                header.toggled.connect(lambda on, s=section: self._set_section_open(s, on))
                page_layout.addWidget(header)
                self._section_headers[section] = header
            holder = QWidget()
            grid = QGridLayout(holder)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(3)
            grid.setVerticalSpacing(1)
            buttons = []
            for entry in entries:
                btn = ToolRowButton(entry.key, entry.grid_label, entry.alias, self._tooltip_for(entry))
                btn.setAccessibleName(entry.label)
                btn.clicked.connect(lambda _checked=False, k=entry.key: self._on_button_clicked(k))
                btn.customContextMenuRequested.connect(
                    lambda pos, b=btn: self._show_tool_menu(b.tool_key, b, pos)
                )
                self.buttons[entry.key] = btn
                self.button_group.addButton(btn)
                self._register_tool_terms(entry)
                self._icon_targets.append((btn, entry.icon))
                buttons.append(btn)
            self._section_buttons[section] = buttons
            self._section_grids[section] = (grid, holder)
            page_layout.addWidget(holder)
        page_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _build_search_page(self):
        page = QWidget()
        self._search_layout = QVBoxLayout(page)
        self._search_layout.setContentsMargins(0, 0, 0, 0)
        self._search_layout.setSpacing(1)
        self._search_title = QLabel("")
        self._search_title.setObjectName("metaLabel")
        self._search_layout.addWidget(self._search_title)
        self._search_list = QVBoxLayout()
        self._search_list.setSpacing(1)
        self._search_layout.addLayout(self._search_list)
        self._search_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _build_active_card(self):
        card = QFrame()
        card.setObjectName("activeCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 8)
        card_layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._card_icon = QLabel()
        self._card_icon.setFixedSize(18, 18)
        header.addWidget(self._card_icon)
        self._card_name = QLabel("")
        self._card_name.setObjectName("cardName")
        # Long tool names clip instead of widening the dock.
        self._card_name.setMinimumWidth(1)
        self._card_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self._card_name, 1)
        self._card_alias = QLabel("")
        self._card_alias.setObjectName("cardAlias")
        header.addWidget(self._card_alias)
        self._card_help = QToolButton()
        self._card_help.setText("?")
        self._card_help.setObjectName("cardAction")
        self._card_help.setAccessibleName("Help for the active tool")
        self._card_help.clicked.connect(self.open_help_for_last_tool)
        header.addWidget(self._card_help)
        self._card_cancel = QToolButton()
        self._card_cancel.setText("Cancel")
        self._card_cancel.setObjectName("cardAction")
        self._card_cancel.setToolTip("Cancel the active tool [Esc]")
        self._card_cancel.setAccessibleName("Cancel the active tool")
        self._card_cancel.clicked.connect(self.cancel_requested.emit)
        header.addWidget(self._card_cancel)
        card_layout.addLayout(header)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("cardHint")
        self.hint_label.setWordWrap(True)
        card_layout.addWidget(self.hint_label)

        self._options_host = QWidget()
        self._options_form = QFormLayout(self._options_host)
        self._options_form.setContentsMargins(0, 2, 0, 0)
        self._options_form.setHorizontalSpacing(8)
        self._options_form.setVerticalSpacing(4)
        self._options_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        # In a narrow dock a long label moves above its field.
        self._options_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        card_layout.addWidget(self._options_host)

        self._card_header_widgets = (
            self._card_icon, self._card_name, self._card_alias,
            self._card_help, self._card_cancel,
        )
        self._active_card = card
        self.clear_tool_options()
        return card

    def _install_command_completer(self):
        """Attach an autocomplete popup to the command line, listing every
        AutoCAD alias plus each canonical tool key (built after buttons exist)."""
        extra_commands = {"ortho", "polar", "osnap", "dyn"}
        words = sorted(set(self._COMMAND_ALIASES.keys()) | set(self.buttons.keys()) | extra_commands)
        completer = QCompleter(words, self.search_input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_input.setCompleter(completer)

    # ── Theme ───────────────────────────────────────────────────────────

    def _apply_theme(self):
        self._dark = _is_dark(self)
        self._theme = dict(_DARK if self._dark else _LIGHT)
        t = self._theme
        self.widget().setStyleSheet(f"""
            QLabel#promptLine {{
                color: {t['muted']}; font-family: 'Consolas','Courier New',monospace;
            }}
            QLineEdit#commandLine {{
                border: 1px solid {t['border']}; border-radius: 4px; padding: 4px 6px;
                font-family: 'Consolas','Courier New',monospace;
            }}
            QLineEdit#commandLine:focus {{ border: 1px solid {t['accent']}; }}
            QLabel#metaLabel {{ color: {t['muted']}; }}
            QToolButton#quickButton {{ border: 1px solid transparent; border-radius: 4px; }}
            QToolButton#quickButton:hover {{ background: {t['accent_soft']}; border-color: {t['accent_mid']}; }}
            QToolButton#quickButton[pinned="true"] {{ border-bottom: 2px solid {t['pin']}; }}
            QTabBar#toolTabs::tab {{
                padding: 5px 2px; border: 0; border-bottom: 2px solid transparent;
                color: {t['muted']}; font-weight: bold;
            }}
            QTabBar#toolTabs::tab:selected {{ color: {t['accent']}; border-bottom: 2px solid {t['accent']}; }}
            QTabBar#toolTabs::tab:hover {{ color: {t['accent']}; }}
            QToolButton#moreButton {{ border: 0; padding: 0 8px; font-size: 14pt; color: {t['muted']}; }}
            QToolButton#moreButton:hover {{ color: {t['accent']}; }}
            QToolButton#moreButton::menu-indicator {{ image: none; }}
            QToolButton#sectionHeader {{
                border: 0; color: {t['muted']}; font-weight: bold; text-align: left; padding: 4px 2px 2px 2px;
            }}
            QToolButton#sectionHeader:hover {{ color: {t['accent']}; }}
            QPushButton[toolRow="true"] {{
                text-align: left; border: 1px solid transparent; border-radius: 4px;
                padding: 2px 6px; background: transparent;
            }}
            QPushButton[toolRow="true"]:hover {{ background: {t['accent_soft']}; border-color: {t['accent_mid']}; }}
            QPushButton[toolRow="true"]:focus {{ border: 1px solid {t['accent']}; }}
            QPushButton[toolRow="true"]:checked {{ background: {t['accent_mid']}; border: 1px solid {t['accent']}; }}
            QFrame#activeCard {{ border: 1px solid {t['border']}; border-radius: 6px; }}
            QLabel#cardName {{ font-weight: bold; letter-spacing: 1px; }}
            QLabel#cardAlias {{ color: {t['accent']}; font-weight: bold; }}
            QLabel#cardHint {{ color: {t['muted']}; }}
            QToolButton#cardAction {{ border: 1px solid {t['border']}; border-radius: 4px; padding: 1px 7px; }}
            QToolButton#cardAction:hover {{ border-color: {t['accent']}; color: {t['accent']}; }}
            QToolButton#layerBar {{
                border: 1px solid {t['border']}; border-radius: 4px; padding: 3px 6px; text-align: left;
            }}
            QToolButton#layerBar:hover {{ border-color: {t['accent']}; }}
            QToolButton#draftChip {{
                border: 1px solid {t['border']}; border-radius: 4px; padding: 2px 1px;
                color: {t['muted']}; font-weight: bold; font-size: 8pt;
                font-family: 'Consolas','Courier New',monospace;
            }}
            QToolButton#draftChip:checked {{
                background: {t['accent_soft']}; color: {t['accent']}; border-color: {t['accent_mid']};
            }}
        """)
        for widget, icon_file in self._icon_targets:
            with suppress(RuntimeError):
                widget.setIcon(self._themed_icon(icon_file))
        for btn in self.buttons.values():
            btn.alias_color = QColor(t["accent"])
            btn.update()
        self._refresh_quick_buttons()
        if self._card_key:
            self._set_card_icon(self._card_key)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and _is_dark(self) != self._dark:
            self._apply_theme()

    # ── Width modes ─────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_width_mode()

    def _apply_width_mode(self, force=False):
        width = self.width()
        if width < _LABELS_MIN:
            mode = "icons"
        elif width < _TWO_COLUMNS_MIN:
            mode = "one"
        else:
            mode = "two"
        if mode == self._width_mode and not force:
            if mode == "icons":
                self._relayout_grids(mode)  # icon count per row follows width
            return
        self._width_mode = mode
        self._quick_label.setVisible(mode == "two")
        self._relayout_grids(mode)

    def _relayout_grids(self, mode):
        compact = mode == "icons"
        icon_columns = max(1, (self.width() - 24) // 37)
        for tab_id, _title, sections in TABS:
            multi = len(sections) > 1
            for section in sections:
                grid, _holder = self._section_grids[section]
                buttons = self._section_buttons[section]
                if compact:
                    columns = icon_columns
                elif multi and mode == "two":
                    columns = 2
                else:
                    columns = 1
                for btn in buttons:
                    grid.removeWidget(btn)
                for index, btn in enumerate(buttons):
                    btn.set_compact(compact)
                    grid.addWidget(btn, index // columns, index % columns)
                for col in range(max(columns, 2)):
                    grid.setColumnStretch(col, 1 if col < columns and not compact else 0)
                grid.invalidate()
                grid.activate()
        for index in range(self.pages.count()):
            page = self.pages.widget(index).widget()
            if page is not None and page.layout() is not None:
                page.layout().invalidate()
                page.layout().activate()

    # ── Tool buttons, terms, quick strip ────────────────────────────────

    def _register_tool_terms(self, entry):
        terms = [entry.key.lower(), entry.alias.lower(), entry.section.lower()]
        terms.extend(part.lower() for part in entry.label.replace("-", " ").split())
        self._tool_search_terms[entry.key] = " ".join(terms)

    def _on_button_clicked(self, key):
        self.tool_activated.emit(key)

    def _emit_quick(self, button):
        key = button.property("tool_key")
        if key:
            self.tool_activated.emit(key)

    def _quick_keys(self):
        keys = list(self._favorites)
        keys.extend(k for k in self._recent_tools if k not in keys)
        return keys[:_QUICK_SLOTS]

    def _refresh_quick_buttons(self):
        keys = self._quick_keys()
        for index, btn in enumerate(self._quick_buttons):
            if index < len(keys):
                entry = tool_entry(keys[index])
                pinned = keys[index] in self._favorites
                btn.setIcon(self._themed_icon(entry.icon) if entry else QIcon())
                btn.setProperty("tool_key", keys[index])
                btn.setProperty("pinned", pinned)
                name = entry.label if entry else keys[index]
                btn.setToolTip(f"{name} ({'pinned' if pinned else 'recent'}). Right-click to {'unpin' if pinned else 'pin'}.")
                btn.setAccessibleName(name)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.show()
            else:
                btn.setProperty("tool_key", None)
                btn.hide()
        self._quick_empty.setVisible(not keys)

    def _show_tool_menu(self, key, widget, pos):
        entry = tool_entry(key) if key else None
        if entry is None:
            return
        menu = QMenu(widget)
        pinned = key in self._favorites
        pin_action = menu.addAction("Unpin from Quick" if pinned else "Pin to Quick")
        help_action = menu.addAction(f"Help: {entry.label}")
        chosen = menu.exec(widget.mapToGlobal(pos))
        if chosen is pin_action:
            self.toggle_pin(key)
        elif chosen is help_action:
            self.tool_help_requested.emit(key)

    def toggle_pin(self, key):
        if key in self._favorites:
            self._favorites.remove(key)
            self.set_status(f"Unpinned: {tool_entry(key).label if tool_entry(key) else key}")
        else:
            self._favorites.insert(0, key)
            self._favorites = self._favorites[:_QUICK_SLOTS]
            self.set_status(f"Pinned: {tool_entry(key).label if tool_entry(key) else key}")
        self._refresh_quick_buttons()
        self._save_state()

    # ── Tabs, sections, search ──────────────────────────────────────────

    def _on_tab_changed(self, index):
        if 0 <= index < len(self._tab_ids) and not self._search_active():
            self.pages.setCurrentIndex(index)
        QSettings(*_SETTINGS).setValue("dock/tab", self._tab_ids[index] if 0 <= index < len(self._tab_ids) else "cad")

    def show_tab(self, tab_id):
        if tab_id in self._tab_ids:
            self.tab_bar.setCurrentIndex(self._tab_ids.index(tab_id))
            if not self._search_active():
                self.pages.setCurrentIndex(self._tab_ids.index(tab_id))

    def current_tab(self):
        index = self.tab_bar.currentIndex()
        return self._tab_ids[index] if 0 <= index < len(self._tab_ids) else None

    def _set_section_open(self, section, is_open):
        header = self._section_headers.get(section)
        if header is not None:
            header.setArrowType(Qt.ArrowType.DownArrow if is_open else Qt.ArrowType.RightArrow)
        _grid, holder = self._section_grids[section]
        holder.setVisible(is_open)
        QSettings(*_SETTINGS).setValue(f"dock/collapsed/{section}", not is_open)

    def _search_active(self):
        return self.pages.currentWidget() is self._search_page

    @staticmethod
    def _looks_like_value(text):
        return bool(text) and text[0] in "@+-.0123456789"

    def _apply_tool_filter(self, text):
        query = (text or "").strip()
        if not query or self._looks_like_value(query) or query.lower() in ("ortho", "polar", "osnap", "dyn"):
            self._clear_search_results()
            index = self.tab_bar.currentIndex()
            self.pages.setCurrentIndex(index if index >= 0 else 0)
            return
        matches = match_tools(query)
        self._clear_search_results()
        if matches:
            self._search_title.setText(f"Matches in all tabs ({len(matches)}). Enter runs the first.")
        else:
            self._search_title.setText(
                f"No tool matches “{query}”. With a command active, Enter sends it as a value."
            )
        for entry in matches:
            btn = ToolRowButton(entry.key, f"{entry.label}  · {entry.section}", entry.alias,
                                self._tooltip_for(entry))
            btn.setCheckable(False)
            btn.setIcon(self._themed_icon(entry.icon))
            btn.alias_color = QColor(self._theme["accent"])
            btn.clicked.connect(lambda _checked=False, k=entry.key: self._run_search_result(k))
            self._search_list.addWidget(btn)
            self._search_buttons.append(btn)
        self.pages.setCurrentWidget(self._search_page)

    def _clear_search_results(self):
        for btn in self._search_buttons:
            self._search_list.removeWidget(btn)
            btn.deleteLater()
        self._search_buttons = []

    def _run_search_result(self, key):
        self.search_input.clear()
        self.tool_activated.emit(key)

    # ── Active-command card ─────────────────────────────────────────────

    def _set_card_icon(self, key):
        entry = tool_entry(key)
        icon = self._themed_icon(entry.icon, 18) if entry else QIcon()
        self._card_icon.setPixmap(icon.pixmap(QSize(18, 18)) if not icon.isNull() else QPixmap())

    def show_tool_options(self, key, tool):
        """Show the active tool's prompt and its inline settings on the card."""
        entry = tool_entry(key)
        self._card_tool = tool
        self._card_key = key
        for widget in self._card_header_widgets:
            widget.show()
        self._set_card_icon(key)
        self._card_name.setText((entry.label if entry else key.replace("_", " ").title()).upper())
        self._card_alias.setText(entry.alias if entry else "")
        self.hint_label.setText(entry.hint if entry else "Follow the prompts on the map.")
        self._build_option_rows(tool, key)

    def clear_tool_options(self):
        self._card_tool = None
        self._card_key = None
        for widget in self._card_header_widgets:
            widget.hide()
        self._clear_option_rows()
        repeat = tool_entry(self._last_activated_key) if self._last_activated_key else None
        idle = "No active command. Pick a tool or type its alias."
        if repeat:
            idle += f" Enter on an empty line repeats {repeat.label}."
        self.hint_label.setText(idle)

    def _clear_option_rows(self):
        while self._options_form.rowCount():
            self._options_form.removeRow(0)
        self._option_rows = []
        self._options_host.hide()

    def _build_option_rows(self, tool, key):
        self._clear_option_rows()
        specs = getattr(tool, "INLINE_OPTIONS", ()) or ()
        if not specs:
            return
        values = option_values(tool, specs)
        for spec in specs:
            widget = self._make_option_widget(spec, values.get(spec.attr, spec.default))
            if widget is None:
                continue
            label = QLabel(spec.label)
            label.setBuddy(widget)
            widget.setAccessibleName(f"{tool_entry(key).label if tool_entry(key) else key}: {spec.label}")
            self._options_form.addRow(label, widget)
            self._option_rows.append((spec, label, widget))
        self._options_host.show()
        self._refresh_option_visibility()

    def _make_option_widget(self, spec, value):
        return make_option_widget(spec, value, self._on_option_changed)

    def _on_option_changed(self, spec, value):
        tool = self._card_tool
        if tool is None:
            return
        set_option(tool, spec, value)
        with suppress(Exception):
            save_options(tool, self._card_key, (spec,), QSettings(*_SETTINGS))
        self._refresh_option_visibility()

    def _refresh_option_visibility(self):
        if self._card_tool is None:
            return
        values = option_values(self._card_tool, [row[0] for row in self._option_rows])
        for spec, label, widget in self._option_rows:
            visible = spec.is_visible(values)
            label.setVisible(visible)
            widget.setVisible(visible)

    # ── Drafting chips ──────────────────────────────────────────────────

    def _on_chip_clicked(self, signal):
        signal.emit()
        # The plugin updates DRAFTING_STATE; re-sync in case nothing listens.
        self._on_drafting_changed(DRAFTING_STATE)

    def _on_drafting_changed(self, state):
        values = {
            "osnap": state.osnap, "ortho": state.ortho,
            "polar": state.polar, "dyn": state.dynamic_input,
        }
        for key, chip in getattr(self, "_chips", {}).items():
            chip.setChecked(bool(values[key]))

    # ── Public API used by main_plugin ──────────────────────────────────

    def unload(self):
        self._save_state()
        DRAFTING_STATE.remove_listener(self._on_drafting_changed)
        if hasattr(self, 'coord_widget') and self.coord_widget:
            with suppress(Exception):
                self.coord_widget.unload()

    def set_status(self, message):
        self.status_label.setText(message)

    @staticmethod
    def _format_usage(count):
        """Compact usage-counter text (kept for diagnostics)."""
        return f"Act {int(count)}"

    def register_tool_activation(self, key):
        if key not in self.buttons:
            return

        self.set_active_tool(key)
        if key in self._recent_tools:
            self._recent_tools.remove(key)
        self._recent_tools.insert(0, key)
        self._recent_tools = self._recent_tools[:_QUICK_SLOTS]
        self._last_activated_key = key
        self._refresh_quick_buttons()
        self.refresh_layer_state()
        self._activation_count += 1
        self._tool_usage_counts[key] = int(self._tool_usage_counts.get(key, 0)) + 1
        if not self._search_active():
            self.show_tab(tab_of(key))

    def set_active_tool(self, key):
        """Synchronize the checked tool without recording an activation."""
        btn = self.buttons.get(key)
        self.button_group.setExclusive(False)
        for button in self.buttons.values():
            button.setChecked(False)
        if btn is not None:
            btn.setChecked(True)
        self.button_group.setExclusive(True)

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
        matches = match_tools(token)
        if matches:
            return matches[0].key
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
        lower = raw.lower()
        if lower in ("ortho", "f8"):
            self.search_input.clear()
            self.ortho_toggle_requested.emit()
            return
        if lower in ("polar", "f10"):
            self.search_input.clear()
            self.polar_toggle_requested.emit()
            return
        if lower in ("osnap", "f3"):
            self.search_input.clear()
            self.osnap_toggle_requested.emit()
            return
        if lower in ("dyn", "dynmode", "f12"):
            self.search_input.clear()
            self.dynamic_input_toggle_requested.emit()
            return

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
        self.clear_tool_options()

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
        self._refresh_quick_buttons()
        self.set_status("Recent tools cleared")
        self._save_state()

    def pin_last_tool(self):
        if not self._last_activated_key:
            self.set_status("No tool to pin yet")
            return
        key = self._last_activated_key
        if key in self._favorites:
            self._favorites.remove(key)
        self._favorites.insert(0, key)
        self._favorites = self._favorites[:_QUICK_SLOTS]
        self._refresh_quick_buttons()
        self.set_status(f"Pinned: {key}")
        self._save_state()
        self.pin_last_requested.emit()

    def refresh_layer_state(self):
        layer = self.iface.activeLayer()
        if layer is None:
            self.edit_btn.setText("○  No layer selected")
            self.edit_btn.setEnabled(False)
            self.edit_btn.setToolTip("Select a vector layer to edit")
            self.edit_btn.setAccessibleName("Edit unavailable")
            self.edit_btn.setAccessibleDescription(self.edit_btn.toolTip())
            return

        name = getattr(layer, "name", lambda: "unknown")()
        is_vector = hasattr(layer, "geometryType") and hasattr(layer, "isEditable")
        if not is_vector:
            self.edit_btn.setText(f"○  {name} (not a vector layer)")
            self.edit_btn.setEnabled(False)
            self.edit_btn.setToolTip("The active layer is not a vector layer")
            self.edit_btn.setAccessibleName("Edit unavailable")
            self.edit_btn.setAccessibleDescription(self.edit_btn.toolTip())
            return

        editable = getattr(layer, "isEditable", lambda: False)()
        if editable:
            text = f"●  {name}   editing"
            tip = "Click to stop editing [Ctrl+Alt+E]"
            accessible = "Edit OFF"
        else:
            text = f"○  {name}   read-only"
            tip = "Click to start editing [Ctrl+Alt+E]"
            accessible = "Edit ON"
        metrics = QFontMetrics(self.edit_btn.font())
        self.edit_btn.setText(metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max(120, self.width() - 30)))
        self.edit_btn.setEnabled(True)
        self.edit_btn.setToolTip(f"{name}: {'editing' if editable else 'read-only'}. {tip}")
        self.edit_btn.setAccessibleName(accessible)
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
            self.set_status("Preflight: layer is read-only; click the layer bar to edit")
            return
        self.set_status("Preflight: OK (vector and editable)")

    def _save_state(self):
        s = QSettings(*_SETTINGS)
        s.setValue("dock/recent_tools", self._recent_tools)
        s.setValue("dock/favorites", self._favorites)
        # Command text and usage counters describe the current session.  Remove
        # legacy persisted values so an unfinished command cannot hide tools on
        # the next launch and the session counter always starts at zero.
        s.remove("dock/search_text")
        s.remove("dock/activation_count")
        s.remove("dock/tool_usage_counts")

    def _load_state(self):
        s = QSettings(*_SETTINGS)
        recent = s.value("dock/recent_tools", [], type=list)
        favs = s.value("dock/favorites", [], type=list)

        self.search_input.clear()
        self._recent_tools = [k for k in (recent or []) if k in self.buttons][:_QUICK_SLOTS]
        self._favorites = [k for k in (favs or []) if k in self.buttons][:_QUICK_SLOTS]
        self._activation_count = 0
        self._tool_usage_counts = {}
        self._refresh_quick_buttons()

        tab = s.value("dock/tab", "cad")
        self.show_tab(tab if tab in self._tab_ids else "cad")
        for section, header in self._section_headers.items():
            collapsed = str(s.value(f"dock/collapsed/{section}", False)).lower() in ("true", "1")
            header.setChecked(not collapsed)
            self._set_section_open(section, not collapsed)

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
            "dock_tab": self.current_tab(),
            "drafting": DRAFTING_STATE.snapshot(),
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
        self._refresh_quick_buttons()
        self.set_status("Workspace reset complete")
        self._save_state()

    def open_help_for_last_tool(self):
        key = self._card_key or self._last_activated_key
        if not key:
            self.set_status("No active tool; opening the command reference")
            self.docs_requested.emit()
            return
        self.tool_help_requested.emit(key)
