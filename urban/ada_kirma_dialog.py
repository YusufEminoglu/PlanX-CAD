# -*- coding: utf-8 -*-
"""
planX CAD — Ada Kırma (Köşe Chamfer) Dialog'u
İmar adası köşe kırma parametreleri.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QHBoxLayout, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush


class AdaKirmaDialog(QDialog):
    """Ada kırma parametreleri dialog'u."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔶 Ada Kırma (Köşe Chamfer)")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ── Başlık ───────────────────────────────────────────────────────
        title = QLabel("🔶 Ada Kırma — Köşe Düzleştirme")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #e65100; padding: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "Yolların dış kaldırım çizgilerinin kesiştiği köşeler\n"
            "kırılır ve arta kalan çizgi parçaları temizlenir."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(desc)

        # ── Şematik Çizim ────────────────────────────────────────────────
        self.schema_label = QLabel()
        self.schema_label.setAlignment(Qt.AlignCenter)
        self.schema_label.setMinimumHeight(130)
        self._draw_schema()
        layout.addWidget(self.schema_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # ── Kırma Tipi ───────────────────────────────────────────────────
        tip_group = QGroupBox("Kırma Tipi")
        tip_form = QFormLayout(tip_group)

        self.cmb_tip = QComboBox()
        self.cmb_tip.addItems([
            "Eğri (Radius ile yuvarlatma)",
            "Düz (Chamfer — düz çizgi ile kırma)",
        ])
        self.cmb_tip.currentIndexChanged.connect(self._on_tip_changed)
        tip_form.addRow("Kırma tipi:", self.cmb_tip)

        layout.addWidget(tip_group)

        # ── Parametre ────────────────────────────────────────────────────
        param_group = QGroupBox("Parametreler")
        param_form = QFormLayout(param_group)

        self.spn_mesafe = QDoubleSpinBox()
        self.spn_mesafe.setRange(0.5, 50.0)
        self.spn_mesafe.setValue(5.0)
        self.spn_mesafe.setSuffix(" m")
        self.spn_mesafe.setSingleStep(0.5)
        self.spn_mesafe.setToolTip(
            "Kesişim noktasından bu mesafe kadar geriye kesilir.\n"
            "Eğri modda: ark yarıçapı olarak kullanılır.\n"
            "Düz modda: her iki çizgiden bu kadar kesilir."
        )
        self.lbl_mesafe = QLabel("Radius (m):")
        param_form.addRow(self.lbl_mesafe, self.spn_mesafe)

        self.spn_tolerans = QDoubleSpinBox()
        self.spn_tolerans.setRange(0.01, 5.0)
        self.spn_tolerans.setValue(0.5)
        self.spn_tolerans.setSuffix(" m")
        self.spn_tolerans.setSingleStep(0.1)
        self.spn_tolerans.setToolTip(
            "Kesişim noktası arama toleransı.\n"
            "Tıklanan noktanın bu mesafe etrafındaki\n"
            "çizgi kesişimleri aranır."
        )
        param_form.addRow("Arama toleransı:", self.spn_tolerans)

        self.spn_artik_temizle = QDoubleSpinBox()
        self.spn_artik_temizle.setRange(0.0, 20.0)
        self.spn_artik_temizle.setValue(1.0)
        self.spn_artik_temizle.setSuffix(" m")
        self.spn_artik_temizle.setSingleStep(0.5)
        self.spn_artik_temizle.setToolTip(
            "Kırma sonrası arta kalan çok kısa çizgi\n"
            "parçalarını otomatik silme eşiği.\n"
            "Bu uzunluktan kısa parçalar silinir."
        )
        param_form.addRow("Artık temizleme:", self.spn_artik_temizle)

        layout.addWidget(param_group)

        # ── Butonlar ─────────────────────────────────────────────────────
        btn_layout = QHBoxLayout()

        btn_ok = QPushButton("✅ Kır")
        btn_ok.setMinimumHeight(40)
        btn_ok.setStyleSheet(
            "QPushButton { background: #e65100; color: white; "
            "font-weight: bold; border-radius: 6px; padding: 10px 24px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #f57c00; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_tip_changed(self, index):
        if index == 0:
            self.lbl_mesafe.setText("Radius (m):")
        else:
            self.lbl_mesafe.setText("Kırma mesafesi (m):")

    def _draw_schema(self):
        """Köşe kırma şemasını çiz."""
        px = QPixmap(380, 120)
        px.fill(QColor(255, 248, 240))
        p = QPainter(px)
        p.setRenderHint(QPainter.Antialiasing)

        # ── ÖNCE (sol taraf) ─────────────────────────────────────
        # İki çizgi kesişiyor — köşe keskin
        p.setPen(QPen(QColor(120, 120, 120), 2))
        p.drawLine(20, 100, 90, 30)   # Çizgi 1
        p.drawLine(20, 30, 90, 100)  # Çizgi 2

        # Kesişim noktası
        p.setPen(QPen(QColor(255, 0, 0), 6))
        p.drawPoint(55, 65)

        # Etiket
        p.setPen(QColor(120, 120, 120))
        font = QFont("Arial", 8, QFont.Bold)
        p.setFont(font)
        p.drawText(30, 115, "ÖNCE")

        # ── OK ───────────────────────────────────────────────────
        p.setPen(QPen(QColor(100, 100, 100), 2))
        p.drawLine(120, 65, 150, 65)
        p.drawLine(145, 60, 150, 65)
        p.drawLine(145, 70, 150, 65)

        # ── SONRA: Düz kırma (orta) ─────────────────────────────
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(170, 100, 200, 55)   # Kırpılmış çizgi 1
        p.drawLine(170, 30, 200, 75)   # Kırpılmış çizgi 2

        # Chamfer çizgisi
        p.setPen(QPen(QColor(255, 109, 0), 3))
        p.drawLine(200, 55, 200, 75)

        font2 = QFont("Arial", 7)
        p.setFont(font2)
        p.setPen(QColor(255, 109, 0))
        p.drawText(204, 68, "düz")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(170, 115, "DÜZ")

        # ── SONRA: Eğri kırma (sağ) ─────────────────────────────
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(270, 100, 300, 55)
        p.drawLine(270, 30, 300, 75)

        # Ark
        from qgis.PyQt.QtCore import QRectF
        p.setPen(QPen(QColor(76, 175, 80), 3))
        # Basit ark çizimi
        p.drawArc(QRectF(285, 50, 30, 30).toRect(), 60 * 16, 60 * 16)

        p.setPen(QColor(76, 175, 80))
        p.setFont(font2)
        p.drawText(310, 68, "eğri")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(270, 115, "EĞRİ")

        p.end()
        self.schema_label.setPixmap(px)

    def get_params(self):
        """Dialog parametrelerini döndür."""
        return {
            "tip": "egri" if self.cmb_tip.currentIndex() == 0 else "duz",
            "mesafe": self.spn_mesafe.value(),
            "tolerans": self.spn_tolerans.value(),
            "artik_esik": self.spn_artik_temizle.value(),
        }
