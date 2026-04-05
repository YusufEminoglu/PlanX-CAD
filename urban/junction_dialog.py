# -*- coding: utf-8 -*-
"""
planX CAD — Kavşak Parametre Dialog'u
NetCAD tarzı kavşak çözümü parametreleri.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QComboBox,
    QPushButton, QGroupBox, QFrame, QCheckBox
)
from qgis.PyQt.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush


class JunctionDialog(QDialog):
    """Kavşak oluşturma parametreleri dialog'u."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔵 Kavşak Çözümü Parametreleri")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Başlık ───────────────────────────────────────────────────────
        title = QLabel("🔵 Kavşak Çözümü")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #1a237e; padding: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "Yol kesişimlerinde dış kaldırımlar kırma açısı ile,\n"
            "iç kaldırımlar radius ile bağlanır."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(desc)

        # ── Şematik Çizim ────────────────────────────────────────────────
        self.schema_label = QLabel()
        self.schema_label.setAlignment(Qt.AlignCenter)
        self.schema_label.setMinimumHeight(120)
        self._draw_schema()
        layout.addWidget(self.schema_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # ── Kavşak Yarıçapı ──────────────────────────────────────────────
        radius_group = QGroupBox("Kavşak Alanı")
        radius_form = QFormLayout(radius_group)

        self.spn_radius = QDoubleSpinBox()
        self.spn_radius.setRange(3.0, 100.0)
        self.spn_radius.setValue(12.0)
        self.spn_radius.setSuffix(" m")
        self.spn_radius.setSingleStep(1.0)
        self.spn_radius.setToolTip(
            "Kavşak merkezi etrafında etkilenecek alan yarıçapı"
        )
        radius_form.addRow("Etki yarıçapı:", self.spn_radius)

        layout.addWidget(radius_group)

        # ── Dış Kaldırım (Chamfer / Kırma) ───────────────────────────────
        outer_group = QGroupBox("Dış Kaldırım — Kırma (Chamfer)")
        outer_form = QFormLayout(outer_group)

        self.spn_chamfer_dist = QDoubleSpinBox()
        self.spn_chamfer_dist.setRange(0.5, 50.0)
        self.spn_chamfer_dist.setValue(5.0)
        self.spn_chamfer_dist.setSuffix(" m")
        self.spn_chamfer_dist.setSingleStep(0.5)
        self.spn_chamfer_dist.setToolTip(
            "Dış kaldırım köşelerinin düz çizgi ile kırılma mesafesi.\n"
            "Kesişim noktasından bu mesafe kadar geriye kesilir ve\n"
            "düz bir çizgi ile bağlanır (ark değil, düz kırma)."
        )
        outer_form.addRow("Kırma mesafesi:", self.spn_chamfer_dist)

        layout.addWidget(outer_group)

        # ── İç Kaldırım (Fillet / Radius) ────────────────────────────────
        inner_group = QGroupBox("İç Kaldırım — Bağlantı (Fillet)")
        inner_form = QFormLayout(inner_group)

        self.spn_fillet_radius = QDoubleSpinBox()
        self.spn_fillet_radius.setRange(0.5, 50.0)
        self.spn_fillet_radius.setValue(3.0)
        self.spn_fillet_radius.setSuffix(" m")
        self.spn_fillet_radius.setSingleStep(0.5)
        self.spn_fillet_radius.setToolTip(
            "İç kaldırım çizgilerinin kavşakta buluşma noktasında\n"
            "yay (ark) ile bağlanma yarıçapı."
        )
        inner_form.addRow("Bağlantı yarıçapı:", self.spn_fillet_radius)

        layout.addWidget(inner_group)

        # ── Kavşak Adası ─────────────────────────────────────────────────
        island_group = QGroupBox("Kavşak Adası")
        island_form = QFormLayout(island_group)

        self.cmb_ada_tipi = QComboBox()
        self.cmb_ada_tipi.addItems([
            "Yok (Ada oluşturma)",
            "Yuvarlak (Roundabout)",
            "Su Damlası (Teardrop)",
        ])
        self.cmb_ada_tipi.setCurrentIndex(1)
        self.cmb_ada_tipi.currentIndexChanged.connect(self._on_ada_changed)
        island_form.addRow("Ada tipi:", self.cmb_ada_tipi)

        self.spn_ada_radius = QDoubleSpinBox()
        self.spn_ada_radius.setRange(0.5, 30.0)
        self.spn_ada_radius.setValue(3.0)
        self.spn_ada_radius.setSuffix(" m")
        self.spn_ada_radius.setSingleStep(0.5)
        island_form.addRow("Ada yarıçapı:", self.spn_ada_radius)

        self.spn_teardrop_uzunluk = QDoubleSpinBox()
        self.spn_teardrop_uzunluk.setRange(1.0, 50.0)
        self.spn_teardrop_uzunluk.setValue(6.0)
        self.spn_teardrop_uzunluk.setSuffix(" m")
        self.spn_teardrop_uzunluk.setSingleStep(0.5)
        self.spn_teardrop_uzunluk.setEnabled(False)
        island_form.addRow("Su damlası uzunluk:", self.spn_teardrop_uzunluk)

        layout.addWidget(island_group)

        # ── Butonlar ─────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        btn_ok = QPushButton("✅ Kavşak Oluştur")
        btn_ok.setMinimumHeight(40)
        btn_ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 6px; padding: 10px 24px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #283593; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_ada_changed(self, index):
        self.spn_ada_radius.setEnabled(index > 0)
        self.spn_teardrop_uzunluk.setEnabled(index == 2)

    def _draw_schema(self):
        """Kavşak şemasını çiz."""
        px = QPixmap(380, 110)
        px.fill(QColor(245, 245, 255))
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)

        cx, cy = 190, 55

        # Yollar
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(40, cy, 340, cy)   # Yatay yol
        p.drawLine(cx, 5, cx, 105)     # Dikey yol

        # Kaldırım çizgileri
        p.setPen(QPen(QColor(100, 100, 100), 1, Qt.DashLine))
        for offset in [-18, 18]:
            p.drawLine(40, cy + offset, cx - 30, cy + offset)
            p.drawLine(cx + 30, cy + offset, 340, cy + offset)
        for offset in [-18, 18]:
            p.drawLine(cx + offset, 5, cx + offset, cy - 30)
            p.drawLine(cx + offset, cy + 30, cx + offset, 105)

        # Chamfer (dış kırma) — düz çizgi
        p.setPen(QPen(QColor(255, 109, 0), 2))
        p.drawLine(cx - 30, cy - 18, cx - 18, cy - 30)
        p.drawLine(cx + 30, cy - 18, cx + 18, cy - 30)
        p.drawLine(cx - 30, cy + 18, cx - 18, cy + 30)
        p.drawLine(cx + 30, cy + 18, cx + 18, cy + 30)

        # Ada
        p.setPen(QPen(QColor(76, 175, 80), 2))
        p.setBrush(QBrush(QColor(76, 175, 80, 60)))
        p.drawEllipse(cx - 8, cy - 8, 16, 16)

        # Etiketler
        p.setPen(QColor(255, 109, 0))
        font = QFont("Arial", 7)
        p.setFont(font)
        p.drawText(cx - 65, cy - 22, "kırma (düz)")

        p.setPen(QColor(76, 175, 80))
        p.drawText(cx + 12, cy + 4, "ada")

        p.end()
        self.schema_label.setPixmap(px)

    def get_params(self):
        """Dialog parametrelerini döndür."""
        ada_tipi_map = {0: "yok", 1: "yuvarlak", 2: "su_damlasi"}
        return {
            "radius": self.spn_radius.value(),
            "chamfer_dist": self.spn_chamfer_dist.value(),
            "fillet_radius": self.spn_fillet_radius.value(),
            "ada_tipi": ada_tipi_map.get(self.cmb_ada_tipi.currentIndex(), "yok"),
            "ada_radius": self.spn_ada_radius.value(),
            "teardrop_uzunluk": self.spn_teardrop_uzunluk.value(),
        }
