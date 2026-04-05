# -*- coding: utf-8 -*-
"""
planX CAD — Yol Platformu Parametre Dialog'u
Yol çizim parametrelerini giren dialog penceresi.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont


class RoadDialog(QDialog):
    """Yol platformu parametreleri dialog'u."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛣️ Yol Platformu Parametreleri")
        self.setMinimumWidth(380)
        self.setModal(True)

        self._params = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Başlık ───────────────────────────────────────────────────────
        title = QLabel("🛣️ Yol Platformu Parametreleri")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # ── Ayırıcı ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # ── Yol Tipi ─────────────────────────────────────────────────────
        type_group = QGroupBox("Yol Tipi")
        type_layout = QFormLayout(type_group)

        self.cmb_yol_tipi = QComboBox()
        self.cmb_yol_tipi.addItems([
            "Araç Yolu",
            "Yaya Yolu",
            "Bisiklet Yolu",
            "Toplayıcı Yol",
            "Arteriyel Yol",
        ])
        type_layout.addRow("Yol Tipi:", self.cmb_yol_tipi)
        
        self.cmb_yon = QComboBox()
        self.cmb_yon.addItems(["Çift Yön (Gidiş-Geliş)", "Tek Yön (One-Way)"])
        type_layout.addRow("Akış Yönü:", self.cmb_yon)
        self.cmb_yon.currentIndexChanged.connect(self._on_yon_changed)

        layout.addWidget(type_group)

        # ── Şerit Parametreleri ──────────────────────────────────────────
        lane_group = QGroupBox("Şerit Parametreleri")
        lane_layout = QFormLayout(lane_group)

        self.spn_serit_sayisi = QSpinBox()
        self.spn_serit_sayisi.setRange(1, 8)
        self.spn_serit_sayisi.setValue(2)
        self.spn_serit_sayisi.setSuffix(" (her yön)")
        lane_layout.addRow("Şerit Sayısı:", self.spn_serit_sayisi)

        self.spn_serit_genislik = QDoubleSpinBox()
        self.spn_serit_genislik.setRange(2.0, 10.0)
        self.spn_serit_genislik.setValue(3.50)
        self.spn_serit_genislik.setSuffix(" m")
        self.spn_serit_genislik.setSingleStep(0.25)
        lane_layout.addRow("Şerit Genişliği:", self.spn_serit_genislik)

        layout.addWidget(lane_group)

        # ── Refüj & Kaldırım ────────────────────────────────────────────
        edge_group = QGroupBox("Refüj & Kaldırım")
        edge_layout = QFormLayout(edge_group)

        self.spn_refuj = QDoubleSpinBox()
        self.spn_refuj.setRange(0.0, 20.0)
        self.spn_refuj.setValue(2.00)
        self.spn_refuj.setSuffix(" m")
        self.spn_refuj.setSingleStep(0.50)
        edge_layout.addRow("Refüj Genişliği:", self.spn_refuj)

        self.spn_sol_kaldirim = QDoubleSpinBox()
        self.spn_sol_kaldirim.setRange(0.0, 10.0)
        self.spn_sol_kaldirim.setValue(2.00)
        self.spn_sol_kaldirim.setSuffix(" m")
        self.spn_sol_kaldirim.setSingleStep(0.50)
        edge_layout.addRow("Sol Kaldırım:", self.spn_sol_kaldirim)

        self.spn_sag_kaldirim = QDoubleSpinBox()
        self.spn_sag_kaldirim.setRange(0.0, 10.0)
        self.spn_sag_kaldirim.setValue(2.00)
        self.spn_sag_kaldirim.setSuffix(" m")
        self.spn_sag_kaldirim.setSingleStep(0.50)
        edge_layout.addRow("Sağ Kaldırım:", self.spn_sag_kaldirim)

        layout.addWidget(edge_group)

        # ── Toplam Genişlik Bilgisi ──────────────────────────────────────
        self.lbl_toplam = QLabel()
        self.lbl_toplam.setAlignment(Qt.AlignCenter)
        self.lbl_toplam.setStyleSheet(
            "font-weight: bold; color: #1a237e; font-size: 12px; "
            "padding: 6px; background: #e8eaf6; border-radius: 4px;"
        )
        layout.addWidget(self.lbl_toplam)
        self._update_total()

        # Değişiklik sinyalleri
        self.spn_serit_sayisi.valueChanged.connect(self._update_total)
        self.spn_serit_genislik.valueChanged.connect(self._update_total)
        self.spn_refuj.valueChanged.connect(self._update_total)
        self.spn_sol_kaldirim.valueChanged.connect(self._update_total)
        self.spn_sag_kaldirim.valueChanged.connect(self._update_total)

        # ── Butonlar ─────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        btn_ciz = QPushButton("✏️ Çiz")
        btn_ciz.setMinimumHeight(36)
        btn_ciz.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 8px 20px; }"
            "QPushButton:hover { background: #283593; }"
        )
        btn_ciz.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ciz)

        btn_iptal = QPushButton("İptal")
        btn_iptal.setMinimumHeight(36)
        btn_iptal.clicked.connect(self.reject)
        btn_layout.addWidget(btn_iptal)

        layout.addLayout(btn_layout)

    def _update_total(self):
        """Toplam genişliği hesapla ve göster."""
        serit = self.spn_serit_sayisi.value()
        genislik = self.spn_serit_genislik.value()
        refuj = self.spn_refuj.value()
        sol_k = self.spn_sol_kaldirim.value()
        sag_k = self.spn_sag_kaldirim.value()

        tek_yon = (self.cmb_yon.currentIndex() == 1)
        yon_carpani = 1 if tek_yon else 2

        # Toplam genişlik
        toplam = (yon_carpani * serit * genislik) + (0 if tek_yon else refuj) + sol_k + sag_k
        self.lbl_toplam.setText(f"Toplam Genişlik: {toplam:.2f} m")

    def _on_yon_changed(self):
        tek_yon = (self.cmb_yon.currentIndex() == 1)
        # Tek yönlü ise refüjü disable yap, şerit textini değiştir
        self.spn_refuj.setEnabled(not tek_yon)
        self.spn_serit_sayisi.setSuffix(" (toplam)" if tek_yon else " (her yön)")
        self._update_total()

    def get_params(self):
        """Dialog parametrelerini döndür."""
        serit = self.spn_serit_sayisi.value()
        genislik = self.spn_serit_genislik.value()
        refuj = self.spn_refuj.value()
        sol_k = self.spn_sol_kaldirim.value()
        sag_k = self.spn_sag_kaldirim.value()
        
        tek_yon = (self.cmb_yon.currentIndex() == 1)
        yon_carpani = 1 if tek_yon else 2
        toplam = (yon_carpani * serit * genislik) + (0 if tek_yon else refuj) + sol_k + sag_k

        return {
            "yol_tipi": self.cmb_yol_tipi.currentText(),
            "tek_yon": tek_yon,
            "serit_sayisi": serit,
            "serit_genisligi": genislik,
            "refuj_genislik": 0.0 if tek_yon else refuj,
            "sol_kaldirim": sol_k,
            "sag_kaldirim": sag_k,
            "toplam_genislik": toplam,
        }
