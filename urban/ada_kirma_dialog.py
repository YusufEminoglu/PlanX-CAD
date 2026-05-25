# -*- coding: utf-8 -*-
"""
planX CAD â€” Ada KÄ±rma (KÃ¶ÅŸe Chamfer) Dialog'u
Ä°mar adasÄ± kÃ¶ÅŸe kÄ±rma parametreleri.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QDoubleSpinBox, QComboBox,
    QPushButton, QHBoxLayout, QGroupBox, QFrame
)
from qgis.PyQt.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QBrush


class AdaKirmaDialog(QDialog):
    """Ada kÄ±rma parametreleri dialog'u."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ðŸ”¶ Ada KÄ±rma (KÃ¶ÅŸe Chamfer)")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # â”€â”€ BaÅŸlÄ±k â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        title = QLabel("ðŸ”¶ Ada KÄ±rma â€” KÃ¶ÅŸe DÃ¼zleÅŸtirme")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #e65100; padding: 4px;")
        layout.addWidget(title)

        desc = QLabel(
            "YollarÄ±n dÄ±ÅŸ kaldÄ±rÄ±m Ã§izgilerinin kesiÅŸtiÄŸi kÃ¶ÅŸeler\n"
            "kÄ±rÄ±lÄ±r ve arta kalan Ã§izgi parÃ§alarÄ± temizlenir."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #546e7a; font-size: 10px;")
        layout.addWidget(desc)

        # â”€â”€ Åžematik Ã‡izim â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.schema_label = QLabel()
        self.schema_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.schema_label.setMinimumHeight(130)
        self._draw_schema()
        layout.addWidget(self.schema_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # â”€â”€ KÄ±rma Tipi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        tip_group = QGroupBox("KÄ±rma Tipi")
        tip_form = QFormLayout(tip_group)

        self.cmb_tip = QComboBox()
        self.cmb_tip.addItems([
            "EÄŸri (Radius ile yuvarlatma)",
            "DÃ¼z (Chamfer â€” dÃ¼z Ã§izgi ile kÄ±rma)",
        ])
        self.cmb_tip.currentIndexChanged.connect(self._on_tip_changed)
        tip_form.addRow("KÄ±rma tipi:", self.cmb_tip)

        layout.addWidget(tip_group)

        # â”€â”€ Parametre â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        param_group = QGroupBox("Parametreler")
        param_form = QFormLayout(param_group)

        self.spn_mesafe = QDoubleSpinBox()
        self.spn_mesafe.setRange(0.5, 50.0)
        self.spn_mesafe.setValue(5.0)
        self.spn_mesafe.setSuffix(" m")
        self.spn_mesafe.setSingleStep(0.5)
        self.spn_mesafe.setToolTip(
            "KesiÅŸim noktasÄ±ndan bu mesafe kadar geriye kesilir.\n"
            "EÄŸri modda: ark yarÄ±Ã§apÄ± olarak kullanÄ±lÄ±r.\n"
            "DÃ¼z modda: her iki Ã§izgiden bu kadar kesilir."
        )
        self.lbl_mesafe = QLabel("Radius (m):")
        param_form.addRow(self.lbl_mesafe, self.spn_mesafe)

        self.spn_tolerans = QDoubleSpinBox()
        self.spn_tolerans.setRange(0.01, 5.0)
        self.spn_tolerans.setValue(0.5)
        self.spn_tolerans.setSuffix(" m")
        self.spn_tolerans.setSingleStep(0.1)
        self.spn_tolerans.setToolTip(
            "KesiÅŸim noktasÄ± arama toleransÄ±.\n"
            "TÄ±klanan noktanÄ±n bu mesafe etrafÄ±ndaki\n"
            "Ã§izgi kesiÅŸimleri aranÄ±r."
        )
        param_form.addRow("Arama toleransÄ±:", self.spn_tolerans)

        self.spn_artik_temizle = QDoubleSpinBox()
        self.spn_artik_temizle.setRange(0.0, 20.0)
        self.spn_artik_temizle.setValue(1.0)
        self.spn_artik_temizle.setSuffix(" m")
        self.spn_artik_temizle.setSingleStep(0.5)
        self.spn_artik_temizle.setToolTip(
            "KÄ±rma sonrasÄ± arta kalan Ã§ok kÄ±sa Ã§izgi\n"
            "parÃ§alarÄ±nÄ± otomatik silme eÅŸiÄŸi.\n"
            "Bu uzunluktan kÄ±sa parÃ§alar silinir."
        )
        param_form.addRow("ArtÄ±k temizleme:", self.spn_artik_temizle)

        layout.addWidget(param_group)

        # â”€â”€ Butonlar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        btn_layout = QHBoxLayout()

        btn_ok = QPushButton("âœ… KÄ±r")
        btn_ok.setMinimumHeight(40)
        btn_ok.setStyleSheet(
            "QPushButton { background: #e65100; color: white; "
            "font-weight: bold; border-radius: 6px; padding: 10px 24px; "
            "font-size: 12px; }"
            "QPushButton:hover { background: #f57c00; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("Ä°ptal")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _on_tip_changed(self, index):
        if index == 0:
            self.lbl_mesafe.setText("Radius (m):")
        else:
            self.lbl_mesafe.setText("KÄ±rma mesafesi (m):")

    def _draw_schema(self):
        """KÃ¶ÅŸe kÄ±rma ÅŸemasÄ±nÄ± Ã§iz."""
        px = QPixmap(380, 120)
        px.fill(QColor(255, 248, 240))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # â”€â”€ Ã–NCE (sol taraf) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Ä°ki Ã§izgi kesiÅŸiyor â€” kÃ¶ÅŸe keskin
        p.setPen(QPen(QColor(120, 120, 120), 2))
        p.drawLine(20, 100, 90, 30)   # Ã‡izgi 1
        p.drawLine(20, 30, 90, 100)  # Ã‡izgi 2

        # KesiÅŸim noktasÄ±
        p.setPen(QPen(QColor(255, 0, 0), 6))
        p.drawPoint(55, 65)

        # Etiket
        p.setPen(QColor(120, 120, 120))
        font = QFont("Arial", 8, QFont.Bold)
        p.setFont(font)
        p.drawText(30, 115, "Ã–NCE")

        # â”€â”€ OK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p.setPen(QPen(QColor(100, 100, 100), 2))
        p.drawLine(120, 65, 150, 65)
        p.drawLine(145, 60, 150, 65)
        p.drawLine(145, 70, 150, 65)

        # â”€â”€ SONRA: DÃ¼z kÄ±rma (orta) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(170, 100, 200, 55)   # KÄ±rpÄ±lmÄ±ÅŸ Ã§izgi 1
        p.drawLine(170, 30, 200, 75)   # KÄ±rpÄ±lmÄ±ÅŸ Ã§izgi 2

        # Chamfer Ã§izgisi
        p.setPen(QPen(QColor(255, 109, 0), 3))
        p.drawLine(200, 55, 200, 75)

        font2 = QFont("Arial", 7)
        p.setFont(font2)
        p.setPen(QColor(255, 109, 0))
        p.drawText(204, 68, "dÃ¼z")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(170, 115, "DÃœZ")

        # â”€â”€ SONRA: EÄŸri kÄ±rma (saÄŸ) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        p.setPen(QPen(QColor(26, 35, 126), 2))
        p.drawLine(270, 100, 300, 55)
        p.drawLine(270, 30, 300, 75)

        # Ark
        from qgis.PyQt.QtCore import QRectF
        p.setPen(QPen(QColor(76, 175, 80), 3))
        # Basit ark Ã§izimi
        p.drawArc(QRectF(285, 50, 30, 30).toRect(), 60 * 16, 60 * 16)

        p.setPen(QColor(76, 175, 80))
        p.setFont(font2)
        p.drawText(310, 68, "eÄŸri")

        p.setPen(QColor(26, 35, 126))
        p.setFont(font)
        p.drawText(270, 115, "EÄžRÄ°")

        p.end()
        self.schema_label.setPixmap(px)

    def get_params(self):
        """Dialog parametrelerini dÃ¶ndÃ¼r."""
        return {
            "tip": "egri" if self.cmb_tip.currentIndex() == 0 else "duz",
            "mesafe": self.spn_mesafe.value(),
            "tolerans": self.spn_tolerans.value(),
            "artik_esik": self.spn_artik_temizle.value(),
        }
