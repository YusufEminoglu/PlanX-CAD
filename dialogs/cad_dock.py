# -*- coding: utf-8 -*-
"""
planX CAD — Ana Dockable Panel
Türkçe arayüzlü, kategorize edilmiş araç butonları.
QButtonGroup ile tüm kategoriler arası tek seçim garanti.
"""

import os

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtGui import QIcon, QFont, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QGridLayout,
    QFrame, QSizePolicy, QToolButton, QButtonGroup
)


class CadToolButton(QToolButton):
    """Özelleştirilmiş CAD araç butonu."""

    def __init__(self, icon_path, tooltip, parent=None):
        super().__init__(parent)
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        self.setToolTip(tooltip)
        self.setIconSize(QSize(28, 28))
        self.setFixedSize(44, 44)
        self.setCheckable(True)
        self.setStyleSheet("""
            QToolButton {
                border: 1px solid transparent;
                border-radius: 6px;
                background: transparent;
                padding: 4px;
            }
            QToolButton:hover {
                background: #e8eaf6;
                border: 1px solid #c5cae9;
            }
            QToolButton:checked {
                background: #c5cae9;
                border: 1px solid #7986cb;
            }
            QToolButton:pressed {
                background: #9fa8da;
            }
        """)


class CollapsibleGroupBox(QGroupBox):
    """Katlanabilir grup kutusu."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._on_toggle)
        self._content_widget = None

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #1a237e;
                border: 1px solid #c5cae9;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 2px 8px;
                background: #e8eaf6;
                border-radius: 4px;
            }
            QGroupBox::indicator {
                width: 13px;
                height: 13px;
            }
        """)

    def set_content_widget(self, widget):
        self._content_widget = widget

    def _on_toggle(self, checked):
        if self._content_widget:
            self._content_widget.setVisible(checked)


class CADDockWidget(QDockWidget):
    """planX CAD ana dockable panel."""

    # Araç aktive edildiğinde emit edilir: (araç_adı,)
    tool_activated = pyqtSignal(str)

    def __init__(self, iface, icon_dir, parent=None):
        super().__init__("planX CAD Araç Seti", parent)
        self.iface = iface
        self.icon_dir = icon_dir

        self.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )

        self.buttons = {}
        # Tüm butonlar tek bir QButtonGroup'ta → kategoriler arası exclusive
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self._setup_ui()

    def _icon(self, name):
        """İkon dosyasının yolunu döndür."""
        return os.path.join(self.icon_dir, name)

    def _add_tool_button(self, grid, row, col, key, icon_file, tooltip):
        """Grid'e araç butonu ekle ve button group'a kaydet."""
        btn = CadToolButton(self._icon(icon_file), tooltip)
        btn.clicked.connect(lambda checked, k=key: self._on_button_clicked(k))
        grid.addWidget(btn, row, col)
        self.buttons[key] = btn
        self.button_group.addButton(btn)
        return btn

    def _on_button_clicked(self, key):
        """Buton tıklandığında önce tüm butonları unchecked yap, sonra emit et."""
        self.tool_activated.emit(key)

    def _setup_ui(self):
        main_widget = QWidget()
        self.setWidget(main_widget)

        layout = QVBoxLayout(main_widget)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Başlık ───────────────────────────────────────────────────────
        header = QLabel("🔧 planX CAD Araç Seti")
        header_font = QFont()
        header_font.setPointSize(11)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            "color: #1a237e; padding: 8px; "
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #e8eaf6, stop:1 #c5cae9); "
            "border-radius: 6px;"
        )
        layout.addWidget(header)

        # ── Çizim Araçları ───────────────────────────────────────────────
        draw_group = CollapsibleGroupBox("✏️ Çizim")
        draw_grid = QGridLayout()
        draw_grid.setSpacing(4)

        draw_tools = [
            ("line",      "cad_line.svg",      "Çizgi"),
            ("polyline",  "cad_polyline.svg",  "Polyline"),
            ("rectangle", "cad_rectangle.svg", "Dikdörtgen"),
            ("polygon",   "cad_polygon.svg",   "Çokgen"),
            ("circle",    "cad_circle.svg",    "Daire"),
            ("arc",       "cad_arc.svg",       "Ark"),
        ]
        draw_content = QWidget()
        draw_content.setLayout(draw_grid)
        for i, (key, icon, tip) in enumerate(draw_tools):
            self._add_tool_button(draw_grid, i // 3, i % 3, key, icon, tip)

        draw_group.setLayout(QVBoxLayout())
        draw_group.layout().addWidget(draw_content)
        draw_group.set_content_widget(draw_content)
        layout.addWidget(draw_group)

        # ── Düzenleme Araçları ───────────────────────────────────────────
        edit_group = CollapsibleGroupBox("🔨 Düzenleme")
        edit_grid = QGridLayout()
        edit_grid.setSpacing(4)

        edit_tools = [
            ("offset",  "cad_offset.svg",  "Offset"),
            ("trim",    "cad_trim.svg",    "Trim"),
            ("extend",  "cad_extend.svg",  "Extend"),
            ("fillet",  "cad_fillet.svg",  "Fillet"),
            ("buffer",  "cad_buffer.svg",  "Buffer"),
        ]
        edit_content = QWidget()
        edit_content.setLayout(edit_grid)
        for i, (key, icon, tip) in enumerate(edit_tools):
            self._add_tool_button(edit_grid, i // 3, i % 3, key, icon, tip)

        edit_group.setLayout(QVBoxLayout())
        edit_group.layout().addWidget(edit_content)
        edit_group.set_content_widget(edit_content)
        layout.addWidget(edit_group)

        # ── Dönüşüm Araçları ────────────────────────────────────────────
        transform_group = CollapsibleGroupBox("🔄 Dönüşüm")
        transform_grid = QGridLayout()
        transform_grid.setSpacing(4)

        transform_tools = [
            ("move",    "cad_move.svg",    "Taşı"),
            ("copy",    "cad_copy.svg",    "Kopyala"),
            ("rotate",  "cad_rotate.svg",  "Döndür (Ctrl: 90°)"),
            ("scale",   "cad_scale.svg",   "Ölçekle"),
            ("mirror",  "cad_mirror.svg",  "Aynala"),
        ]
        transform_content = QWidget()
        transform_content.setLayout(transform_grid)
        for i, (key, icon, tip) in enumerate(transform_tools):
            self._add_tool_button(transform_grid, i // 3, i % 3, key, icon, tip)

        transform_group.setLayout(QVBoxLayout())
        transform_group.layout().addWidget(transform_content)
        transform_group.set_content_widget(transform_content)
        layout.addWidget(transform_group)

        # ── Ölçüm Araçları ──────────────────────────────────────────────
        measure_group = CollapsibleGroupBox("📐 Ölçüm")
        measure_grid = QGridLayout()
        measure_grid.setSpacing(4)

        self._add_tool_button(measure_grid, 0, 0, "measure", "cad_measure.svg", "Mesafe Ölç")
        self._add_tool_button(measure_grid, 0, 1, "measure_area", "cad_measure_area.svg", "Alan Ölç")
        self._add_tool_button(measure_grid, 1, 0, "measure_select_line", "cad_measure_select_line.svg", "Seç ve Çizgi Ölç")
        self._add_tool_button(measure_grid, 1, 1, "measure_select_area", "cad_measure_select_area.svg", "Seç ve Alan Ölç")

        measure_content = QWidget()
        measure_content.setLayout(measure_grid)
        measure_group.setLayout(QVBoxLayout())
        measure_group.layout().addWidget(measure_content)
        measure_group.set_content_widget(measure_content)
        layout.addWidget(measure_group)

        # ── Şehir Planlama Araçları ──────────────────────────────────────
        urban_group = CollapsibleGroupBox("🏙️ Şehir Planlama")
        urban_grid = QGridLayout()
        urban_grid.setSpacing(4)

        # Yol Çiz butonu
        road_btn = QPushButton("🛣️ Yol Çiz")
        road_btn.setMinimumHeight(38)
        road_btn.setCheckable(True)
        road_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 11px;
                color: #1a237e; background: #e8eaf6;
                border: 1px solid #c5cae9; border-radius: 6px; padding: 6px;
            }
            QPushButton:hover { background: #c5cae9; }
            QPushButton:checked { background: #7986cb; color: white; }
        """)
        road_btn.clicked.connect(lambda: self._on_button_clicked("road"))
        urban_grid.addWidget(road_btn, 0, 0)
        self.buttons["road"] = road_btn
        self.button_group.addButton(road_btn)

        # Kavşak butonu
        junction_btn = QPushButton("🔵 Kavşak")
        junction_btn.setMinimumHeight(38)
        junction_btn.setCheckable(True)
        junction_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 11px;
                color: #1a237e; background: #e8eaf6;
                border: 1px solid #c5cae9; border-radius: 6px; padding: 6px;
            }
            QPushButton:hover { background: #c5cae9; }
            QPushButton:checked { background: #7986cb; color: white; }
        """)
        junction_btn.clicked.connect(lambda: self._on_button_clicked("junction"))
        urban_grid.addWidget(junction_btn, 0, 1)
        self.buttons["junction"] = junction_btn
        self.button_group.addButton(junction_btn)

        # Ada Kırma butonu
        ada_btn = QPushButton("🔶 Ada Kırma")
        ada_btn.setMinimumHeight(38)
        ada_btn.setCheckable(True)
        ada_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 11px;
                color: #e65100; background: #fff3e0;
                border: 1px solid #ffcc80; border-radius: 6px; padding: 6px;
            }
            QPushButton:hover { background: #ffe0b2; }
            QPushButton:checked { background: #ff9800; color: white; }
        """)
        ada_btn.clicked.connect(lambda: self._on_button_clicked("ada_kirma"))
        urban_grid.addWidget(ada_btn, 1, 0, 1, 2)  # 2. satır, tam genişlik
        self.buttons["ada_kirma"] = ada_btn
        self.button_group.addButton(ada_btn)

        urban_content = QWidget()
        urban_content.setLayout(urban_grid)
        urban_group.setLayout(QVBoxLayout())
        urban_group.layout().addWidget(urban_content)
        urban_group.set_content_widget(urban_content)
        layout.addWidget(urban_group)

        # ── Ayırıcı ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ── Durum Çubuğu ─────────────────────────────────────────────────
        self.status_label = QLabel("Hazır")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            "color: #546e7a; font-size: 10px; padding: 4px; "
            "background: #f5f5f5; border-radius: 4px;"
        )
        layout.addWidget(self.status_label)

        # Boşluk
        layout.addStretch()

    def set_status(self, message):
        """Durum mesajını güncelle."""
        self.status_label.setText(message)

    def uncheck_all(self):
        """Tüm butonları kaldır."""
        checked = self.button_group.checkedButton()
        if checked:
            self.button_group.setExclusive(False)
            checked.setChecked(False)
            self.button_group.setExclusive(True)
