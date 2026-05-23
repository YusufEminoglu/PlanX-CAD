# -*- coding: utf-8 -*-
"""
planX CAD — Main Dockable Panel
Bilingual: English (Primary) and Turkish (Secondary).
Highly compact, space-optimized layout with the official PlanX Teal/Slate theme.
"""
from __future__ import annotations

import os

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtGui import QIcon, QFont, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout,
    QFrame, QSizePolicy, QToolButton, QButtonGroup,
    QScrollArea, QLineEdit
)


class CadToolButton(QToolButton):
    """Custom compact CAD tool button styled with PlanX Teal accents."""

    def __init__(self, icon_path, tooltip, parent=None):
        super().__init__(parent)
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        self.setToolTip(tooltip)
        self.setIconSize(QSize(22, 22))
        self.setFixedSize(34, 34)
        self.setCheckable(True)
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
            QToolButton:checked {
                background: #bfe8dc;
                border: 1px solid #0f766e;
            }
            QToolButton:pressed {
                background: #99f6e4;
            }
        """)


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

    # Emitted when a tool is activated: (tool_key,)
    tool_activated = pyqtSignal(str)
    cancel_requested = pyqtSignal()
    docs_requested = pyqtSignal()
    shortcuts_requested = pyqtSignal()

    def __init__(self, iface, icon_dir, parent=None):
        super().__init__("planX CAD Toolset / planX CAD Araç Seti", parent)
        self.iface = iface
        self.icon_dir = icon_dir

        self.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        self.setMinimumWidth(160)

        self.buttons = {}
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._tool_search_terms = {}
        self._recent_tools = []
        self._recent_buttons = []

        self._setup_ui()

    def _icon(self, name):
        """Get icon file absolute path."""
        return os.path.join(self.icon_dir, name)

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
        "line": "Line: click start and end points. / Cizgi: baslangic ve bitis noktasi tiklayin.",
        "polyline": "Polyline: keep clicking vertices, finish with right click. / Coklu Cizgi: koseleri tiklayin, sag tikla bitir.",
        "trim": "Trim: pick cutting boundary, then target segment. / Budama: once sinir, sonra budanacak parca.",
        "extend": "Extend: pick reference edge, then line to extend. / Uzatma: once referans, sonra uzatilacak cizgi.",
        "fillet": "Fillet: select two edges; use small radius for stability. / Fillet: iki kenar secin; kucuk yaricap daha stabil.",
        "construction_inf": "Infinite construction: axis/grid references. / Sonsuz referans: aks ve grid icin.",
        "construction_ray": "Ray construction: one-way projection. / Isin referans: tek yon projeksiyon.",
        "construction_seg": "Segment construction: bounded temporary reference. / Segment referans: sinirli gecici dogru.",
        "measure": "Measure: snap both ends for reliable distance. / Olcum: dogru mesafe icin iki ucu snapleyin.",
        "road": "Road sketch: define centerline cleanly, then platform params. / Yol: once aksi cizin, sonra platform parametreleri.",
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

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        main_widget = QWidget()
        main_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        scroll.setWidget(main_widget)
        self.setWidget(scroll)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 4, 4, 4)

        # ── Header / Başlık ───────────────────────────────────────────────
        header = QLabel("🔧 planX CAD Toolset / Araç Seti")
        header_font = QFont()
        header_font.setPointSize(9)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "color: #12343b; padding: 4px 6px; "
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #eef6f4, stop:1 #dce9ed); "
            "border-radius: 4px;"
        )
        layout.addWidget(header)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find tool / Araç ara (Enter)")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { border: 1px solid #d8e0ea; border-radius: 4px; padding: 4px 6px; "
            "font-size: 10px; background: white; color: #12343b; }"
            "QLineEdit:focus { border: 1px solid #0f766e; }"
        )
        self.search_input.textChanged.connect(self._apply_tool_filter)
        self.search_input.returnPressed.connect(self._activate_first_match)
        layout.addWidget(self.search_input)

        # ── Drawing Tools / Çizim Araçları ─────────────────────────────────
        draw_group = CollapsibleGroupBox("✏️ Drawing / Çizim")
        draw_grid = QGridLayout()
        draw_grid.setSpacing(3)
        draw_grid.setContentsMargins(2, 2, 2, 2)

        draw_tools = [
            ("line",      "cad_line.svg",      "Line / Çizgi"),
            ("polyline",  "cad_polyline.svg",  "Polyline / Çoklu Çizgi"),
            ("rectangle", "cad_rectangle.svg", "Rectangle / Dikdörtgen"),
            ("polygon",   "cad_polygon.svg",   "Polygon / Çokgen"),
            ("circle",    "cad_circle.svg",    "Circle / Daire"),
            ("arc",       "cad_arc.svg",       "Arc / Yay"),
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

        # ── Editing Tools / Düzenleme Araçları ──────────────────────────────
        edit_group = CollapsibleGroupBox("🔨 Editing / Düzenleme")
        edit_grid = QGridLayout()
        edit_grid.setSpacing(3)
        edit_grid.setContentsMargins(2, 2, 2, 2)

        edit_tools = [
            ("offset",       "cad_offset.svg",       "Offset / Öteleme"),
            ("trim",         "cad_trim.svg",         "Trim / Budama"),
            ("extend",       "cad_extend.svg",       "Extend / Uzatma"),
            ("fillet",       "cad_fillet.svg",       "Fillet / Köşe Yuvarlama"),
            ("buffer",       "cad_buffer.svg",       "Buffer / Tampon"),
            ("array",        "cad_array.svg",        "Array / Çoklu Kopyalama"),
            ("vertex_edit",      "cad_vertex_edit.svg",      "Vertex Edit / Köşe Düzenleme"),
            ("divide",           "cad_divide.svg",           "Divide / Eşit Parçaya Böl"),
            ("multi_offset",     "cad_multi_offset.svg",     "Multi-Offset / Çoklu Öteleme"),
            ("join",             "cad_join.svg",             "Join / Çizgileri Birleştir"),
            ("hatch",            "cad_hatch.svg",            "Hatch / Pattern Fill"),
            ("construction_inf", "cad_construction.svg",     "Construction line / Sonsuz referans"),
            ("construction_ray", "cad_construction.svg",     "Construction ray / Isin referans"),
            ("construction_seg", "cad_construction.svg",     "Construction segment / Segment referans"),
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

        # ── Transform Tools / Dönüşüm Araçları ──────────────────────────────
        transform_group = CollapsibleGroupBox("🔄 Transform / Dönüşüm")
        transform_grid = QGridLayout()
        transform_grid.setSpacing(3)
        transform_grid.setContentsMargins(2, 2, 2, 2)

        transform_tools = [
            ("move",    "cad_move.svg",    "Move / Taşı"),
            ("copy",    "cad_copy.svg",    "Copy / Kopyala"),
            ("rotate",  "cad_rotate.svg",  "Rotate / Döndür (Ctrl: 90°)"),
            ("scale",   "cad_scale.svg",   "Scale / Ölçekle"),
            ("mirror",  "cad_mirror.svg",  "Mirror / Aynala"),
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

        # ── Measurement Tools / Ölçüm Araçları ──────────────────────────────
        measure_group = CollapsibleGroupBox("📐 Measurement / Ölçüm")
        measure_grid = QGridLayout()
        measure_grid.setSpacing(3)
        measure_grid.setContentsMargins(2, 2, 2, 2)

        self._add_tool_button(measure_grid, 0, 0, "measure", "cad_measure.svg", "Measure Distance / Mesafe Ölç")
        self._add_tool_button(measure_grid, 0, 1, "measure_area", "cad_measure_area.svg", "Measure Area / Alan Ölç")
        self._add_tool_button(measure_grid, 0, 2, "dimension", "cad_dimension.svg", "Dimension / Kalıcı Etiket")
        self._add_tool_button(measure_grid, 1, 0, "measure_select_line", "cad_measure_select_line.svg", "Select and Measure Line / Seç ve Çizgi Ölç")
        self._add_tool_button(measure_grid, 1, 1, "measure_select_area", "cad_measure_select_area.svg", "Select and Measure Area / Seç ve Alan Ölç")

        measure_content = QWidget()
        measure_content.setLayout(measure_grid)
        
        measure_layout = QVBoxLayout()
        measure_layout.setContentsMargins(4, 4, 4, 4)
        measure_layout.setSpacing(0)
        measure_layout.addWidget(measure_content)
        measure_group.setLayout(measure_layout)
        measure_group.set_content_widget(measure_content)
        layout.addWidget(measure_group)

        # ── Urban Planning Tools / Şehir Planlama Araçları ────────────────────
        urban_group = CollapsibleGroupBox("🏙️ Urban Planning / Şehir Planlama")
        urban_grid = QGridLayout()
        urban_grid.setSpacing(3)
        urban_grid.setContentsMargins(2, 2, 2, 2)

        # Draw Road button
        road_btn = QPushButton("🛣️ Draw Road / Yol Çiz")
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
        road_btn.clicked.connect(lambda: self._on_button_clicked("road"))
        urban_grid.addWidget(road_btn, 0, 0)
        self.buttons["road"] = road_btn
        self.button_group.addButton(road_btn)
        self._register_tool_terms("road", "Draw Road / Yol Ciz")

        # Junction button
        junction_btn = QPushButton("🔵 Junction / Kavşak")
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
        junction_btn.clicked.connect(lambda: self._on_button_clicked("junction"))
        urban_grid.addWidget(junction_btn, 0, 1)
        self.buttons["junction"] = junction_btn
        self.button_group.addButton(junction_btn)
        self._register_tool_terms("junction", "Junction / Kavsak")

        # Block Chamfer button
        ada_btn = QPushButton("🔶 Block Chamfer / Ada Kırma")
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
        ada_btn.clicked.connect(lambda: self._on_button_clicked("ada_kirma"))
        urban_grid.addWidget(ada_btn, 1, 0, 1, 2)
        self.buttons["ada_kirma"] = ada_btn
        self.button_group.addButton(ada_btn)
        self._register_tool_terms("ada_kirma", "Block Chamfer / Ada Kirma")

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
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ── Quick Actions ──────────────────────────────────────────────────
        quick_row = QHBoxLayout()
        repeat_btn = QPushButton("↻ Repeat Last Tool / Son aracı tekrarla")
        repeat_btn.setToolTip("Restart last activated tool [Ctrl+Shift+Space] / Son aktif aracı tekrar başlatır")
        repeat_btn.setMinimumHeight(24)
        repeat_btn.setStyleSheet(
            "QPushButton { background: #eef6f4; color: #0f766e; font-size: 9px;"
            "border: 1px solid #bfe8dc; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #dce9ed; border-color: #0f766e; }"
        )
        repeat_btn.clicked.connect(lambda: self.tool_activated.emit("__repeat__"))
        quick_row.addWidget(repeat_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setToolTip("Cancel active tool / Aktif araci iptal et")
        cancel_btn.setMinimumHeight(24)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #fff1f2; color: #9f1239; font-size: 9px;"
            "border: 1px solid #fecdd3; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #ffe4e6; border-color: #be123c; }"
        )
        cancel_btn.clicked.connect(lambda: self.cancel_requested.emit())
        quick_row.addWidget(cancel_btn)
        docs_btn = QPushButton("Docs")
        docs_btn.setToolTip("Open detailed command reference")
        docs_btn.setMinimumHeight(24)
        docs_btn.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0f766e; font-size: 9px;"
            "border: 1px solid #bfe8dc; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #eef6f4; border-color: #0f766e; }"
        )
        docs_btn.clicked.connect(lambda: self.docs_requested.emit())
        quick_row.addWidget(docs_btn)

        keys_btn = QPushButton("Keys")
        keys_btn.setToolTip("Open shortcut guide")
        keys_btn.setMinimumHeight(24)
        keys_btn.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0f766e; font-size: 9px;"
            "border: 1px solid #bfe8dc; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #eef6f4; border-color: #0f766e; }"
        )
        keys_btn.clicked.connect(lambda: self.shortcuts_requested.emit())
        quick_row.addWidget(keys_btn)
        reset_btn = QPushButton("Reset")
        reset_btn.setToolTip("Reset tool filter / Arac filtresini sifirla")
        reset_btn.setMinimumHeight(24)
        reset_btn.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0f766e; font-size: 9px;"
            "border: 1px solid #bfe8dc; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #eef6f4; border-color: #0f766e; }"
        )
        reset_btn.clicked.connect(self.reset_filter)
        quick_row.addWidget(reset_btn)
        layout.addLayout(quick_row)

        recent_row = QHBoxLayout()
        recent_label = QLabel("Recent / Son:")
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
        clear_recent_btn.setToolTip("Clear recent tools / Son araclari temizle")
        clear_recent_btn.setMinimumHeight(22)
        clear_recent_btn.setStyleSheet(
            "QPushButton { background: #f8fafc; color: #0f766e; font-size: 9px;"
            "border: 1px solid #d8e0ea; border-radius: 4px; padding: 1px 6px; }"
            "QPushButton:hover { background: #eef6f4; border-color: #0f766e; }"
        )
        clear_recent_btn.clicked.connect(self.clear_recent)
        recent_row.addWidget(clear_recent_btn)
        layout.addLayout(recent_row)

        hint_box = QFrame()
        hint_box.setStyleSheet(
            "QFrame { background: #f8fafc; border: 1px solid #d8e0ea; border-radius: 4px; }"
            "QLabel { color: #334155; font-size: 9px; padding: 4px 6px; }"
        )
        hint_layout = QVBoxLayout(hint_box)
        hint_layout.setContentsMargins(0, 0, 0, 0)
        self.hint_label = QLabel("Tip / Ipucu: Activate a tool to see best-practice guidance.")
        self.hint_label.setWordWrap(True)
        hint_layout.addWidget(self.hint_label)
        layout.addWidget(hint_box)

        self.layer_state_label = QLabel("Layer: unknown / Katman: bilinmiyor")
        self.layer_state_label.setWordWrap(True)
        self.layer_state_label.setStyleSheet(
            "color: #475569; font-size: 9px; padding: 2px 4px; "
            "background: #f8fafc; border: 1px solid #d8e0ea; border-radius: 3px;"
        )
        layout.addWidget(self.layer_state_label)

        # ── Live Coordinates Widget ──────────────────────────────────────
        try:
            from .coord_widget import LiveCoordWidget
            self.coord_widget = LiveCoordWidget(self.iface, self)
            layout.addWidget(self.coord_widget)
        except Exception as e:
            print(f"[planX-CAD] LiveCoordWidget load error: {e}")
            self.coord_widget = None

        # ── Status Bar / Durum Çubuğu ──────────────────────────────────────
        self.status_label = QLabel("Ready — shortcuts: Ctrl+Shift+<letter> / Hazır — kısayollar: Ctrl+Shift+<harf>")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #64748b; font-size: 9px; padding: 2px 4px; "
            "background: #f1f5f9; border-radius: 3px;"
        )
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.refresh_layer_state()

    def unload(self):
        if hasattr(self, 'coord_widget') and self.coord_widget:
            try:
                self.coord_widget.unload()
            except Exception:
                pass

    def set_status(self, message):
        self.status_label.setText(message)

    def register_tool_activation(self, key):
        if key not in self.buttons:
            return

        btn = self.buttons.get(key)
        if btn:
            self.button_group.setExclusive(False)
            for b in self.buttons.values():
                b.setChecked(False)
            btn.setChecked(True)
            self.button_group.setExclusive(True)

        if key in self._recent_tools:
            self._recent_tools.remove(key)
        self._recent_tools.insert(0, key)
        self._recent_tools = self._recent_tools[:3]
        self._refresh_recent_buttons()
        self._update_hint(key)
        self.refresh_layer_state()

    def _update_hint(self, key):
        hint = self._TOOL_HINTS.get(
            key,
            "Tip / Ipucu: Use snapping, work on editable layers, and verify topology before export."
        )
        self.hint_label.setText(f"Tip / Ipucu: {hint}")

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

    def _apply_tool_filter(self, text):
        query = (text or "").strip().lower()
        for key, btn in self.buttons.items():
            terms = self._tool_search_terms.get(key, key)
            visible = (not query) or (query in terms)
            btn.setVisible(visible)

    def _activate_first_match(self):
        query = (self.search_input.text() or "").strip().lower()
        if not query:
            return
        for key in self.buttons.keys():
            terms = self._tool_search_terms.get(key, key)
            if query in terms:
                self.tool_activated.emit(key)
                return

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
        self.set_status("Filter reset / Filtre sifirlandi")

    def clear_recent(self):
        self._recent_tools = []
        self._refresh_recent_buttons()
        self.set_status("Recent tools cleared / Son araclar temizlendi")

    def refresh_layer_state(self):
        layer = self.iface.activeLayer()
        if layer is None:
            self.layer_state_label.setText("Layer: none selected / Katman: secili degil")
            return
        name = getattr(layer, "name", lambda: "unknown")()
        editable = getattr(layer, "isEditable", lambda: False)()
        state = "editable" if editable else "read-only"
        state_tr = "duzenlenebilir" if editable else "salt-okunur"
        self.layer_state_label.setText(f"Layer: {name} ({state}) / Katman: {name} ({state_tr})")
