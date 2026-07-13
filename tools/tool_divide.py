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

        # Treat every multipart component independently. The previous code
        # silently kept only part 0, so dividing a multipart feature deleted
        # all of its remaining parts.
        line_parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
        line_parts = [part for part in line_parts if len(part) >= 2]
        if not line_parts:
            self.tool_message.emit("⚠️ Divide — Insufficient vertex count / Yetersiz vertex sayısı")
            self._reset()
            return

        if not any(self._part_metrics(part)[1] > 1e-6 for part in line_parts):
            self.tool_message.emit("⚠️ Divide — Line length is zero / Çizgi uzunluğu sıfır")
            self._reset()
            return

        if method == DivideDialog.METHOD_SPLIT:
            self._split_line(layer, feature, line_parts, segments_count)
        else:
            self._create_division_points(line_parts, segments_count)

        self._reset()

    @staticmethod
    def _part_metrics(line_pts):
        cum_dists = [0.0]
        for idx in range(1, len(line_pts)):
            p1 = line_pts[idx - 1]
            p2 = line_pts[idx]
            cum_dists.append(
                cum_dists[-1] + math.hypot(
                    p2.x() - p1.x(), p2.y() - p1.y()
                )
            )
        return cum_dists, cum_dists[-1]

    def _split_line(self, layer, feature, line_parts, N):
        segments_geoms = []

        for line_pts in line_parts:
            cum_dists, total_len = self._part_metrics(line_pts)
            if total_len <= 1e-6:
                continue
            part_geom = QgsGeometry.fromPolylineXY(line_pts)
            seg_len = total_len / N
            for j in range(N):
                d_start = j * seg_len
                d_end = (j + 1) * seg_len
                pt_start_geom = part_geom.interpolate(d_start)
                pt_end_geom = part_geom.interpolate(d_end)
                if pt_start_geom.isEmpty() or pt_end_geom.isEmpty():
                    continue
                p_start = QgsPointXY(pt_start_geom.asPoint())
                p_end = QgsPointXY(pt_end_geom.asPoint())
                seg_pts = [p_start]
                for idx, d_val in enumerate(cum_dists):
                    if d_start + 1e-9 < d_val < d_end - 1e-9:
                        seg_pts.append(line_pts[idx])
                seg_pts.append(p_end)
                segment_geom = QgsGeometry.fromPolylineXY(seg_pts)
                if QgsWkbTypes.isMultiType(layer.wkbType()):
                    segment_geom.convertToMultiType()
                segments_geoms.append(segment_geom)

        if not segments_geoms:
            self.tool_message.emit("⚠️ Divide — Division failed / Bölme işlemi başarısız")
            return

        new_features = []
        for geometry in segments_geoms[1:]:
            new_feature = QgsFeature(layer.fields())
            new_feature.setGeometry(geometry)
            for index in range(layer.fields().count()):
                new_feature.setAttribute(index, feature.attribute(index))
            new_features.append(new_feature)

        layer.beginEditCommand("PlanX CAD: divide")
        success = layer.changeGeometry(feature.id(), segments_geoms[0])
        if success and new_features:
            success = layer.addFeatures(new_features)
        if not success:
            layer.destroyEditCommand()
            self.tool_message.emit(
                "⚠️ Divide — Write failed; all changes were rolled back / "
                "Yazma hatası; tüm değişiklikler geri alındı"
            )
            return
        layer.endEditCommand()

        layer.triggerRepaint()
        self.tool_message.emit(
            f"✅ Divide — Line divided into {len(segments_geoms)} segments / "
            f"Çizgi {len(segments_geoms)} eşit parçaya bölündü"
        )

    def _create_division_points(self, line_parts, N):
        points = []
        for line_pts in line_parts:
            _cum_dists, total_len = self._part_metrics(line_pts)
            if total_len <= 1e-6:
                continue
            part_geom = QgsGeometry.fromPolylineXY(line_pts)
            seg_len = total_len / N
            for i in range(1, N):
                pt_geom = part_geom.interpolate(i * seg_len)
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
                crs=self.selected_layer.crs(),
                fields=[("source_fid", "longlong")]
            )

        if target_layer is None:
            self.tool_message.emit("⚠️ Divide — Could not create target layer / Hedef nokta katmanı oluşturulamadı")
            return

        was_editing = target_layer.isEditable()
        if not was_editing and not target_layer.startEditing():
            self.tool_message.emit(
                "⚠️ Divide — Point layer is not editable / Nokta katmanı düzenlenemiyor"
            )
            return

        source_fid = self.selected_feature.id() if self.selected_feature else -1
        idx_fid = target_layer.fields().indexOf("source_fid")
        
        features = []
        for pt in points:
            target_geom = self.geometry_to_layer_crs(
                pt, self.selected_layer, target_layer
            )
            if target_geom is None:
                continue
            if QgsWkbTypes.isMultiType(target_layer.wkbType()):
                target_geom.convertToMultiType()
            feat = QgsFeature(target_layer.fields())
            feat.setGeometry(target_geom)
            if idx_fid >= 0:
                feat.setAttribute(idx_fid, source_fid)
            features.append(feat)
            
        target_layer.beginEditCommand("PlanX CAD: division points")
        if not features or not target_layer.addFeatures(features):
            target_layer.destroyEditCommand()
            if not was_editing:
                target_layer.rollBack()
            self.tool_message.emit(
                "⚠️ Divide — Points could not be added / Noktalar eklenemedi"
            )
            return
        target_layer.endEditCommand()

        if not was_editing:
            if not target_layer.commitChanges():
                target_layer.rollBack()
                self.tool_message.emit(
                    "⚠️ Divide — Point layer could not be saved / Nokta katmanı kaydedilemedi"
                )
                return
        else:
            target_layer.triggerRepaint()

        self.tool_message.emit(
            f"✅ Divide — {len(features)} division points added to '{target_layer.name()}' / "
            f"{len(features)} adet bölüm noktası '{target_layer.name()}' katmanına eklendi"
        )
