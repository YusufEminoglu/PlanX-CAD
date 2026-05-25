# -*- coding: utf-8 -*-
"""Shortcut guide dialog for PlanX CAD."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QHBoxLayout, QComboBox
)


class ShortcutHelpDialog(QDialog):
    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PlanX CAD - Shortcut Guide / Kisayol Rehberi")
        self.setMinimumWidth(700)
        self.setMinimumHeight(560)
        self._shortcuts = shortcuts
        self._rows = []
        self._build_ui()
        self._populate_rows()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Keyboard-first workflow: Ctrl+Shift+S focuses search, Ctrl+Shift+Space repeats last tool.\n"
            "Klavye odakli akista Ctrl+Shift+S aramayi odaklar, Ctrl+Shift+Space son araci tekrarlar."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #334155; padding: 4px;")
        layout.addWidget(intro)

        filter_row = QHBoxLayout()
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search command or shortcut / Komut veya kisayol ara")
        self.search_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.search_input)

        self.category_combo = QComboBox(self)
        self.category_combo.addItems(["All / Tum", "Drawing", "Editing", "Transform", "Measure", "Urban", "System"])
        self.category_combo.currentTextChanged.connect(self._apply_filter)
        filter_row.addWidget(self.category_combo)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Command", "Komut", "Shortcut", "Category"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        close_btn = QPushButton("Close / Kapat")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _populate_rows(self):
        tr_map = {
            "line": "Cizgi", "polyline": "Coklu Cizgi", "rectangle": "Dikdortgen", "polygon": "Cokgen",
            "circle": "Daire", "arc": "Yay", "offset": "Oteleme", "trim": "Budama", "extend": "Uzatma",
            "fillet": "Kose Yuvarlama", "buffer": "Tampon", "move": "Tasi", "array": "Coklu Kopya",
            "vertex_edit": "Kose Duzenleme", "hatch": "Tarama", "construction_inf": "Sonsuz Referans",
            "construction_ray": "Isin Referans", "construction_seg": "Segment Referans", "dimension": "Olculendirme",
            "measure": "Mesafe Olc", "divide": "Esit Parcaya Bol", "multi_offset": "Coklu Oteleme", "join": "Birlestir"
        }

        categories = {
            "line": "Drawing", "polyline": "Drawing", "rectangle": "Drawing", "polygon": "Drawing", "circle": "Drawing", "arc": "Drawing",
            "offset": "Editing", "trim": "Editing", "extend": "Editing", "fillet": "Editing", "buffer": "Editing", "vertex_edit": "Editing",
            "hatch": "Editing", "construction_inf": "Editing", "construction_ray": "Editing", "construction_seg": "Editing",
            "divide": "Editing", "multi_offset": "Editing", "join": "Editing",
            "move": "Transform", "array": "Transform",
            "dimension": "Measure", "measure": "Measure",
        }

        self._rows = []
        for tool_key, seq in self._shortcuts:
            self._rows.append({
                "en": tool_key,
                "tr": tr_map.get(tool_key, tool_key),
                "shortcut": seq,
                "category": categories.get(tool_key, "System"),
            })

        self._rows.extend([
            {"en": "repeat_last", "tr": "son_araci_tekrar", "shortcut": "Ctrl+Shift+Space", "category": "System"},
            {"en": "focus_search", "tr": "arama_odagi", "shortcut": "Ctrl+Shift+S", "category": "System"},
            {"en": "open_shortcuts", "tr": "kisayol_rehberi", "shortcut": "Ctrl+Shift+/", "category": "System"},
            {"en": "open_docs", "tr": "komut_kilavuzu", "shortcut": "Ctrl+Alt+H", "category": "System"},
            {"en": "open_smoke_test", "tr": "duman_test_listesi", "shortcut": "Ctrl+Alt+M", "category": "System"},
            {"en": "command_palette", "tr": "komut_paleti", "shortcut": "Ctrl+Alt+P", "category": "System"},
            {"en": "cancel_active_tool", "tr": "aktif_araci_iptal", "shortcut": "Ctrl+Alt+C", "category": "System"},
            {"en": "toggle_layer_editing", "tr": "katman_duzenleme_ac_kapat", "shortcut": "Ctrl+Alt+E", "category": "System"},
            {"en": "run_preflight", "tr": "preflight_kontrolu", "shortcut": "Ctrl+Alt+F", "category": "System"},
            {"en": "quick_start", "tr": "hizli_baslangic", "shortcut": "Ctrl+Alt+Q", "category": "System"},
            {"en": "session_checklist", "tr": "oturum_kontrol_listesi", "shortcut": "Ctrl+Alt+G", "category": "System"},
            {"en": "pin_last_tool", "tr": "son_araci_sabitle", "shortcut": "Ctrl+Alt+Z", "category": "System"},
            {"en": "open_diagnostics", "tr": "tani_raporu", "shortcut": "Ctrl+Alt+D", "category": "System"},
            {"en": "reset_workspace_state", "tr": "calisma_alani_sifirla", "shortcut": "Ctrl+Alt+R", "category": "System"},
            {"en": "open_usage_stats", "tr": "kullanim_istatistikleri", "shortcut": "Ctrl+Alt+T", "category": "System"},
            {"en": "open_health_check", "tr": "sistem_kontrolu", "shortcut": "Ctrl+Alt+W", "category": "System"},
            {"en": "open_shortcut_audit", "tr": "kisayol_denetimi", "shortcut": "Ctrl+Alt+Y", "category": "System"},
            {"en": "open_issue_template", "tr": "hata_rapor_sablonu", "shortcut": "Ctrl+Alt+N", "category": "System"},
            {"en": "open_release_readiness", "tr": "surum_hazirlik", "shortcut": "Ctrl+Alt+V", "category": "System"},
        ])

        self._render_rows(self._rows)

    def _render_rows(self, rows):
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(row["en"]))
            self.table.setItem(r, 1, QTableWidgetItem(row["tr"]))
            self.table.setItem(r, 2, QTableWidgetItem(row["shortcut"]))
            self.table.setItem(r, 3, QTableWidgetItem(row["category"]))
        self.table.resizeColumnsToContents()

    def _apply_filter(self):
        query = (self.search_input.text() or "").strip().lower()
        cat = self.category_combo.currentText()
        cat = cat.split(" /")[0]

        filtered = []
        for row in self._rows:
            if cat != "All" and row["category"] != cat:
                continue
            blob = f"{row['en']} {row['tr']} {row['shortcut']} {row['category']}".lower()
            if query and query not in blob:
                continue
            filtered.append(row)

        self._render_rows(filtered)
