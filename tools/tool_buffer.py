# -*- coding: utf-8 -*-
"""planX CAD — Buffer Aracı
Dialog ile join style seçimi + otomatik katman oluşturma.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry, Qgis
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QComboBox, QPushButton, QHBoxLayout, QLabel, QGroupBox
)
from qgis.PyQt.QtGui import QFont
from .tool_base import tool_base
from ..core.sketcher_layer_utils import get_or_create_layer


class BufferDialog(QDialog):
    """Buffer parametre dialog'u."""

    def __init__(self, parent=None, default_distance=5.0):
        super().__init__(parent)
        self.setWindowTitle("◎ Buffer Parametreleri")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._setup_ui(default_distance)

    def _setup_ui(self, default_distance):
        layout = QVBoxLayout(self)

        title = QLabel("◎ Buffer (Tampon) Parametreleri")
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self.spn_distance = QDoubleSpinBox()
        self.spn_distance.setRange(0.01, 100000.0)
        self.spn_distance.setValue(default_distance)
        self.spn_distance.setSuffix(" m")
        self.spn_distance.setSingleStep(0.5)
        self.spn_distance.setDecimals(2)
        form.addRow("Tampon mesafesi:", self.spn_distance)

        self.cmb_join = QComboBox()
        self.cmb_join.addItems([
            "Yuvarlak (Round)",
            "Düz (Flat / Bevel)",
            "Köşeli (Miter)"
        ])
        form.addRow("Köşe stili:", self.cmb_join)

        self.spn_segments = QDoubleSpinBox()
        self.spn_segments.setRange(4, 128)
        self.spn_segments.setValue(16)
        self.spn_segments.setDecimals(0)
        form.addRow("Segment sayısı:", self.spn_segments)

        layout.addLayout(form)

        # Butonlar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("✅ Uygula")
        btn_ok.setMinimumHeight(36)
        btn_ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 8px 20px; }"
            "QPushButton:hover { background: #283593; }"
        )
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        btn_cancel = QPushButton("İptal")
        btn_cancel.setMinimumHeight(36)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def get_params(self):
        join_map = {0: 1, 1: 2, 2: 3}  # Round=1, Bevel=2, Miter=3
        return {
            "distance": self.spn_distance.value(),
            "join_style": join_map.get(self.cmb_join.currentIndex(), 1),
            "segments": int(self.spn_segments.value()),
        }


class tool_buffer(tool_base):
    """Tampon bölge oluşturma — otomatik katman ile."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.distance = 5.0
        self.join_style = 1
        self.segments = 16

    def tool_name(self):
        return "Buffer"

    def activate(self):
        super().activate()
        dlg = BufferDialog(self.iface.mainWindow(), self.distance)
        if dlg.exec_() == QDialog.Accepted:
            params = dlg.get_params()
            self.distance = params["distance"]
            self.join_style = params["join_style"]
            self.segments = params["segments"]

            join_names = {1: "Yuvarlak", 2: "Düz", 3: "Köşeli"}
            self.tool_message.emit(
                f"◎ Buffer ({self.distance}m, {join_names.get(self.join_style, '?')}) "
                f"— Tamponlanacak objeyi seçin"
            )
        else:
            self.tool_message.emit("◎ Buffer — İptal edildi")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()

        # QGIS buffer: join_style (1=Round, 2=Bevel, 3=Miter)
        join_enum = Qgis.JoinStyle.Round
        if self.join_style == 2:
            join_enum = Qgis.JoinStyle.Bevel
        elif self.join_style == 3:
            join_enum = Qgis.JoinStyle.Miter

        buffered = geom.buffer(
            self.distance,
            self.segments,
            Qgis.EndCapStyle.Round,
            join_enum,
            2.0  # miter limit
        )

        if buffered and not buffered.isEmpty():
            # Otomatik katman: planx_buffer
            buffer_layer = get_or_create_layer(
                "planx_buffer",
                geom_type="Polygon",
                fields=[
                    ("kaynak_katman", "string"),
                    ("buffer_mesafe", "double"),
                    ("join_stili", "string"),
                ]
            )

            if buffer_layer:
                join_names = {1: "round", 2: "bevel", 3: "miter"}
                self._add_feature(buffer_layer, buffered)

                # Öznitelikleri güncelle
                buffer_layer.startEditing()
                last_feat = list(buffer_layer.getFeatures())
                if last_feat:
                    fid = last_feat[-1].id()
                    buffer_layer.changeAttributeValue(
                        fid,
                        buffer_layer.fields().indexOf("kaynak_katman"),
                        layer.name()
                    )
                    buffer_layer.changeAttributeValue(
                        fid,
                        buffer_layer.fields().indexOf("buffer_mesafe"),
                        self.distance
                    )
                    buffer_layer.changeAttributeValue(
                        fid,
                        buffer_layer.fields().indexOf("join_stili"),
                        join_names.get(self.join_style, "round")
                    )
                buffer_layer.commitChanges()

                self.tool_message.emit(
                    f"✅ Buffer ({self.distance}m) — planx_buffer katmanına eklendi"
                )
            else:
                self.tool_message.emit("⚠️ Buffer — Katman oluşturulamadı")
        else:
            self.tool_message.emit("⚠️ Buffer — Tampon oluşturulamadı")

        self._reset()
