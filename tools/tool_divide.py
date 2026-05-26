# -*- coding: utf-8 -*-
"""planX CAD — Divide (Eşit Parçaya Bölme) tool.

Divides a selected line feature into N equal segments.
Can either split the line itself or generate point markers along the divisions.
Bilingual: English (Primary) and Turkish (Secondary).
"""
from __future__ import annotations

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QFormLayout
)
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsWkbTypes, QgsFeature, QgsProject
)
from .tool_base import tool_base
from ..core.sketcher_layer_utils import get_or_create_layer


class DivideDialog(QDialog):
    """Dialog asking the user for division parameters."""

    METHOD_SPLIT = 0
    METHOD_POINTS = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("÷ Divide / Böl")
        self.setMinimumWidth(320)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("÷ Division Parameters / Bölme Parametreleri")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        
        self.spn_segments = QSpinBox()
        self.spn_segments.setRange(2, 10000)
        self.spn_segments.setValue(3)
        form.addRow("Segments / Parça Sayısı:", self.spn_segments)

        self.cmb_method = QComboBox()
        self.cmb_method.addItems([
            "Split Line / Çizgiyi Parçalara Böl",
            "Create Points / Bölüm Noktaları Oluştur"
        ])
        form.addRow("Method / Yöntem:", self.cmb_method)
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
            "segments": self.spn_segments.value(),
            "method": self.cmb_method.currentIndex()
        }


class tool_divide(tool_base):
    """Line/Polyline division tool with bilingual UI."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.require_editable = True

    def tool_name(self):
        return "Divide / Eşit Parçaya Böl"

    def activate(self):
        super().activate()
        self.tool_message.emit("÷ Divide — Select line to divide / Bölme — Bölünecek çizgiyi seçin")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Divide — Empty geometry / Boş geometri")
            self._reset()
            return

        if geom.type() != QgsWkbTypes.LineGeometry:
            self.tool_message.emit("⚠️ Divide — Only lines can be divided / Sadece çizgi objeleri bölünebilir")
            self._reset()
            return

        # Open dialog
        dlg = DivideDialog(self.iface.mainWindow())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.tool_message.emit("⚠️ Divide — Cancelled / İptal edildi")
            self._reset()
            return

        params = dlg.params()
        segments_count = params["segments"]
        method = params["method"]

        # Calculate line details
        if geom.isMultipart():
            parts = geom.asMultiPolyline()
            if not parts or not parts[0]:
                self.tool_message.emit("⚠️ Divide — Line part not found / Çizgi parçası bulunamadı")
                self._reset()
                return
            line_pts = parts[0]
        else:
            line_pts = geom.asPolyline()

        if len(line_pts) < 2:
            self.tool_message.emit("⚠️ Divide — Insufficient vertex count / Yetersiz vertex sayısı")
            self._reset()
            return

        # Cumulative distances
        cum_dists = [0.0]
        for idx in range(1, len(line_pts)):
            p1 = line_pts[idx - 1]
            p2 = line_pts[idx]
            d = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
            cum_dists.append(cum_dists[-1] + d)

        total_len = cum_dists[-1]
        if total_len <= 1e-6:
            self.tool_message.emit("⚠️ Divide — Line length is zero / Çizgi uzunluğu sıfır")
            self._reset()
            return

        if method == DivideDialog.METHOD_SPLIT:
            self._split_line(layer, feature, geom, line_pts, cum_dists, total_len, segments_count)
        else:
            self._create_division_points(geom, total_len, segments_count)

        self._reset()

    def _split_line(self, layer, feature, geom, line_pts, cum_dists, total_len, N):
        seg_len = total_len / N
        segments_geoms = []

        for j in range(N):
            d_start = j * seg_len
            d_end = (j + 1) * seg_len

            # Interpolated points
            pt_start_geom = geom.interpolate(d_start)
            pt_end_geom = geom.interpolate(d_end)
            if pt_start_geom.isEmpty() or pt_end_geom.isEmpty():
                continue
            p_start = QgsPointXY(pt_start_geom.asPoint())
            p_end = QgsPointXY(pt_end_geom.asPoint())

            # Find intermediate points
            seg_pts = [p_start]
            for idx, d_val in enumerate(cum_dists):
                if d_start + 1e-9 < d_val < d_end - 1e-9:
                    seg_pts.append(line_pts[idx])
            seg_pts.append(p_end)

            segments_geoms.append(QgsGeometry.fromPolylineXY(seg_pts))

        if not segments_geoms:
            self.tool_message.emit("⚠️ Divide — Division failed / Bölme işlemi başarısız")
            return

        # Start edit block
        if not layer.isEditable():
            layer.startEditing()

        # Update first segment in place
        self._apply_edit(layer, feature, segments_geoms[0])

        # Add other segments as new features inheriting attributes
        for s_geom in segments_geoms[1:]:
            self._add_feature(layer, s_geom, feature)

        layer.triggerRepaint()
        self.tool_message.emit(f"✅ Divide — Line divided into {N} segments / Çizgi {N} eşit parçaya bölündü")

    def _create_division_points(self, geom, total_len, N):
        seg_len = total_len / N
        points = []
        for i in range(1, N):
            d_val = i * seg_len
            pt_geom = geom.interpolate(d_val)
            if not pt_geom.isEmpty():
                points.append(pt_geom)

        if not points:
            self.tool_message.emit("⚠️ Divide — Points not calculated / Noktalar hesaplanamadı")
            return

        # Determine target point layer
        active_layer = self.iface.activeLayer()
        target_layer = None
        if active_layer and active_layer.isEditable() and active_layer.geometryType() == QgsWkbTypes.PointGeometry:
            target_layer = active_layer
        else:
            # Get or create memory layer planx_divisions
            target_layer = get_or_create_layer(
                "planx_divisions",
                geom_type="Point",
                fields=[("source_fid", "longlong")]
            )

        if target_layer is None:
            self.tool_message.emit("⚠️ Divide — Could not create target layer / Hedef nokta katmanı oluşturulamadı")
            return

        was_editing = target_layer.isEditable()
        if not was_editing:
            target_layer.startEditing()

        source_fid = self.selected_feature.id() if self.selected_feature else -1
        idx_fid = target_layer.fields().indexOf("source_fid")
        
        features = []
        for pt in points:
            feat = QgsFeature(target_layer.fields())
            feat.setGeometry(pt)
            if idx_fid >= 0:
                feat.setAttribute(idx_fid, source_fid)
            features.append(feat)
            
        target_layer.addFeatures(features)
        
        if not was_editing:
            target_layer.commitChanges()
        else:
            target_layer.triggerRepaint()

        self.tool_message.emit(
            f"✅ Divide — {N-1} division points added to '{target_layer.name()}' / "
            f"{N-1} adet bölüm noktası '{target_layer.name()}' katmanına eklendi"
        )
