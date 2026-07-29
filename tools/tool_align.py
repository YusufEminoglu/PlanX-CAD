# -*- coding: utf-8 -*-
"""PlanX CAD Align tool: move, rotate, and optionally scale by point pairs."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.precision_input import PrecisionInputError, looks_like_precision_input
from ..core.sketcher_feedback import create_preview_rubberband
from ..core.sketcher_utils import align_geometry


class AlignDialog(QDialog):
    """Ask whether the alignment should also scale the feature."""

    def __init__(self, scale=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Align")
        self.setMinimumWidth(340)
        self.setModal(True)
        self._build_ui(scale)

    def _build_ui(self, scale):
        layout = QVBoxLayout(self)

        title = QLabel("Align Options")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.chk_scale = QCheckBox("Scale to match the destination distance")
        self.chk_scale.setChecked(scale)
        self.chk_scale.setAccessibleName("Scale during align")
        self.chk_scale.setAccessibleDescription(
            "Scale the feature by the ratio between the destination and "
            "source point-pair distances."
        )
        layout.addWidget(self.chk_scale)

        hint = QLabel(
            "Pick source point 1, destination point 1, source point 2, then "
            "destination point 2. Press Enter after the first pair to move "
            "without rotating."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        start = QPushButton("Start")
        start.setMinimumHeight(30)
        start.setDefault(True)
        start.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setMinimumHeight(30)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(start)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def params(self):
        return {"scale": self.chk_scale.isChecked()}


class tool_align(tool_base):
    """Align a feature onto a destination using one or two point pairs.

    1. Select a feature | 2. Source point 1 | 3. Destination point 1 |
    4. Source point 2 | 5. Destination point 2 (Enter after step 3 moves only)
    """

    _STEP_SOURCE_1 = 2
    _STEP_TARGET_1 = 3
    _STEP_SOURCE_2 = 4
    _STEP_TARGET_2 = 5

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.scale = False
        self.src1 = None
        self.dst1 = None
        self.src2 = None
        self._activation_cancelled = False

    def tool_name(self):
        return "Align"

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        dialog = AlignDialog(self.scale, self.iface.mainWindow())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._activation_cancelled = True
            self.tool_message.emit("⤢ Align — Cancelled")
            return
        self.scale = dialog.params()["scale"]
        self._clear_points()
        self.tool_message.emit("⤢ Align — Select the feature to align")

    def on_entity_selected(self, layer, feature, point):
        self._clear_points()
        self._step = self._STEP_SOURCE_1
        self.tool_message.emit("⤢ Align — Click source point 1")

    def on_click(self, point, button):
        if button != Qt.MouseButton.LeftButton:
            return
        if self._step == self._STEP_SOURCE_1:
            self.src1 = QgsPointXY(point)
            self._step = self._STEP_TARGET_1
            self.tool_message.emit("⤢ Align — Click destination point 1")
        elif self._step == self._STEP_TARGET_1:
            self.dst1 = QgsPointXY(point)
            self._step = self._STEP_SOURCE_2
            self.tool_message.emit(
                "⤢ Align — Click source point 2, or press Enter to move only"
            )
        elif self._step == self._STEP_SOURCE_2:
            self.src2 = QgsPointXY(point)
            self._step = self._STEP_TARGET_2
            self.tool_message.emit("⤢ Align — Click destination point 2")
        elif self._step == self._STEP_TARGET_2:
            self._apply_align(QgsPointXY(point))

    def on_move(self, point):
        if self._step != self._STEP_TARGET_2 or self.preview_rb is None:
            return
        preview = self._aligned_geometry(QgsPointXY(point))
        if preview is None or preview.isEmpty():
            return
        self.preview_rb.reset(preview.type())
        self.preview_rb.setToGeometry(preview, self.selected_layer)

    def handle_command_enter(self):
        """Enter after the first pair applies a translate-only alignment."""
        if self._step != self._STEP_SOURCE_2 or self.dst1 is None:
            return False
        self._apply_align(None)
        return True

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.handle_command_enter():
                event.accept()
                return
        super().keyPressEvent(event)

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        base = {
            self._STEP_SOURCE_1: self.selected_point,
            self._STEP_TARGET_1: self.src1,
            self._STEP_SOURCE_2: self.dst1,
            self._STEP_TARGET_2: self.src2,
        }.get(self._step)
        if base is None:
            self.tool_message.emit("⚠️ Align — Select a feature first")
            return True
        try:
            target = self.resolve_precision_target(
                text, base, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Align — {error}")
            return True
        self.on_click(target, Qt.MouseButton.LeftButton)
        return True

    def _aligned_geometry(self, dst2):
        if self.selected_feature is None or self.src1 is None or self.dst1 is None:
            return None
        return align_geometry(
            self.selected_feature.geometry(),
            self.src1, self.dst1,
            self.src2 if dst2 is not None else None,
            dst2,
            scale=self.scale,
        )

    def _apply_align(self, dst2):
        layer = self.selected_layer
        feature = self.selected_feature
        result = self._aligned_geometry(dst2)
        if layer is None or feature is None or result is None or result.isEmpty():
            self.tool_message.emit(
                "⚠️ Align — The picked points do not define a valid alignment"
            )
            self._reset_align()
            return

        geometry = QgsGeometry(result)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
            geometry.convertToMultiType()
        if self._apply_edit(layer, feature, geometry):
            self.tool_message.emit(
                "✅ Align — Moved, rotated and scaled" if (dst2 and self.scale)
                else ("✅ Align — Moved and rotated" if dst2 else "✅ Align — Moved")
            )
        self._reset_align()

    def _clear_points(self):
        self.src1 = None
        self.dst1 = None
        self.src2 = None

    def _reset_align(self):
        self._clear_points()
        self._reset()
        if self.preview_rb is None:
            self.preview_rb = create_preview_rubberband(self.canvas)
