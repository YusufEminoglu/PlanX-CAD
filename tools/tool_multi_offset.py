# -*- coding: utf-8 -*-
"""planX CAD — Çoklu Öteleme (Multi-Offset) Aracı

Allows offsetting selected lines/polylines multiple times with custom distances and side settings.
Bilingual: English (Primary) and Turkish (Secondary).
"""
from __future__ import annotations

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QFormLayout
)
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsWkbTypes, QgsFeature, QgsProject
)
from .tool_base import tool_base
from ..core.sketcher_utils import offset_geometry


class MultiOffsetDialog(QDialog):
    """Dialog for entering multiple offset distances and side selection."""

    def __init__(self, parent=None, last_distances="3.0, 6.0", last_side=2):
        super().__init__(parent)
        self.setWindowTitle("Multi-Offset / Çoklu Öteleme")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._last_distances = last_distances
        self._last_side = last_side
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Multi-Offset Parameters / Çoklu Öteleme Parametreleri")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()

        self.txt_distances = QLineEdit()
        self.txt_distances.setText(self._last_distances)
        self.txt_distances.setPlaceholderText("e.g. 3.0, 6.0, 9.0")
        self.txt_distances.setToolTip("Enter comma-separated distances / Virgülle ayrılmış mesafeler girin")
        form.addRow("Distances / Mesafeler (m):", self.txt_distances)

        self.cmb_side = QComboBox()
        self.cmb_side.addItems([
            "Left / Sol",
            "Right / Sağ",
            "Both / Her İki Taraf",
            "Mouse Click / Tıklanan Taraf"
        ])
        self.cmb_side.setCurrentIndex(self._last_side)
        form.addRow("Direction / Yön:", self.cmb_side)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok = QPushButton("✅ Apply / Uygula")
        ok.setMinimumHeight(34)
        ok.setStyleSheet(
            "QPushButton { background: #1a237e; color: white; font-weight: bold;"
            " border-radius: 4px; padding: 6px 16px; }"
            "QPushButton:hover { background: #283593; }"
        )
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel / İptal")
        cancel.setMinimumHeight(34)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def params(self) -> dict:
        return {
            "distances": self.txt_distances.text(),
            "side": self.cmb_side.currentIndex()
        }


class tool_multi_offset(tool_base):
    """Offsets selected line features multiple times simultaneously."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.distances_str = "3.0, 6.0"
        self.side_mode = 2  # default: Both
        self.parsed_distances: list[float] = []

    def tool_name(self):
        return "Multi-Offset / Çoklu Öteleme"

    def activate(self):
        super().activate()
        self.parsed_distances = []
        self.tool_message.emit("🔧 Multi-Offset — Select line to offset / Çoklu Öteleme — Ötelenecek çizgiyi seçin")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Multi-Offset — Empty geometry / Boş geometri")
            self._reset()
            return

        if geom.type() != QgsWkbTypes.LineGeometry:
            self.tool_message.emit("⚠️ Multi-Offset — Only lines can be offset / Sadece çizgiler ötelenebilir")
            self._reset()
            return

        # Open dialog
        dlg = MultiOffsetDialog(self.iface.mainWindow(), self.distances_str, self.side_mode)
        if dlg.exec() != QDialog.Accepted:
            self.tool_message.emit("⚠️ Multi-Offset — Cancelled / İptal edildi")
            self._reset()
            return

        params = dlg.params()
        self.distances_str = params["distances"]
        self.side_mode = params["side"]

        # Parse distances
        raw_vals = [x.strip() for x in self.distances_str.split(",") if x.strip()]
        parsed = []
        for val in raw_vals:
            try:
                parsed.append(abs(float(val)))
            except ValueError:
                pass

        if not parsed:
            self.tool_message.emit("⚠️ Multi-Offset — Invalid distance format / Geçersiz mesafe formatı")
            self._reset()
            return

        self.parsed_distances = parsed

        if self.side_mode == 0:  # Left
            self._apply_offsets(layer, feature, geom, "left")
            self._reset()
        elif self.side_mode == 1:  # Right
            self._apply_offsets(layer, feature, geom, "right")
            self._reset()
        elif self.side_mode == 2:  # Both
            self._apply_offsets(layer, feature, geom, "both")
            self._reset()
        else:  # Clicked Side
            self._step = 2
            self.tool_message.emit(
                "🔧 Multi-Offset — Move mouse to select side and click / Çoklu Öteleme — Mouse ile tarafı seçip tıklayın"
            )

    def _apply_offsets(self, layer, feature, geom, side):
        offset_geoms = []
        if side in ("left", "both"):
            for dist in self.parsed_distances:
                offset_g = offset_geometry(geom, dist, "left")
                if offset_g and not offset_g.isEmpty():
                    offset_geoms.append(offset_g)
        if side in ("right", "both"):
            for dist in self.parsed_distances:
                offset_g = offset_geometry(geom, dist, "right")
                if offset_g and not offset_g.isEmpty():
                    offset_geoms.append(offset_g)

        if not offset_geoms:
            self.tool_message.emit("⚠️ Multi-Offset — Failed to generate offset geometry / Öteleme geometrisi üretilemedi")
            return

        # Start edit block
        if not layer.isEditable():
            layer.startEditing()

        for g in offset_geoms:
            self._add_feature(layer, g, feature)

        layer.triggerRepaint()
        self.tool_message.emit(
            f"✅ Multi-Offset — Added {len(offset_geoms)} parallel lines / "
            f"Çoklu Öteleme — {len(offset_geoms)} adet paralel çizgi eklendi"
        )

    def _get_closer_side(self, geom, point) -> str:
        if not self.parsed_distances:
            return "left"
        test_dist = self.parsed_distances[0]
        left_geom = offset_geometry(geom, test_dist, "left")
        right_geom = offset_geometry(geom, test_dist, "right")

        d_left = left_geom.distance(QgsGeometry.fromPointXY(point)) if left_geom else float('inf')
        d_right = right_geom.distance(QgsGeometry.fromPointXY(point)) if right_geom else float('inf')

        return "left" if d_left < d_right else "right"

    def on_move(self, point):
        if self._step == 2 and self.preview_rb and self.selected_feature:
            geom = self.selected_feature.geometry()
            closer_side = self._get_closer_side(geom, point)

            offset_geoms = []
            for dist in self.parsed_distances:
                offset_g = offset_geometry(geom, dist, closer_side)
                if offset_g and not offset_g.isEmpty():
                    offset_geoms.append(offset_g)

            self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            if offset_geoms:
                combined = QgsGeometry.collectGeometry(offset_geoms)
                self.preview_rb.setToGeometry(combined)

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            geom = self.selected_feature.geometry()
            closer_side = self._get_closer_side(geom, point)
            self._apply_offsets(self.selected_layer, self.selected_feature, geom, closer_side)
            self._reset()
