# -*- coding: utf-8 -*-
"""PlanX CAD Explode tool: split a feature into parts or single segments."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout,
)
from qgis.core import QgsGeometry, QgsWkbTypes

from .tool_base import tool_base
from ..core.sketcher_layer_utils import add_feature_to_layer, get_or_create_layer
from ..core.sketcher_utils import explode_geometry


EXPLODE_LAYER_NAME = "planx_explode"


class ExplodeDialog(QDialog):
    """Collect the explode mode and whether the source is removed."""

    MODES = (("Multipart to single parts", "parts"),
             ("Boundary to single segments", "segments"))

    def __init__(self, remove_source=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Explode")
        self.setMinimumWidth(340)
        self.setModal(True)
        self._build_ui(remove_source)

    def _build_ui(self, remove_source):
        layout = QVBoxLayout(self)

        title = QLabel("Explode Options")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(10)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        self.cmb_mode = QComboBox()
        for label, _key in self.MODES:
            self.cmb_mode.addItem(label)
        self.cmb_mode.setAccessibleName("Explode mode")
        self.cmb_mode.setAccessibleDescription(
            "Parts splits a multipart feature into single parts. Segments "
            "turns a line or a polygon boundary into two-point segments."
        )
        form.addRow("Mode:", self.cmb_mode)
        layout.addLayout(form)

        self.chk_remove = QCheckBox("Remove the source feature")
        self.chk_remove.setChecked(remove_source)
        self.chk_remove.setAccessibleName("Remove source feature")
        layout.addWidget(self.chk_remove)

        hint = QLabel(
            "Segments from a polygon are written to a managed "
            f"{EXPLODE_LAYER_NAME} line layer, because a polygon layer cannot "
            "hold them."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        apply_button = QPushButton("Apply")
        apply_button.setMinimumHeight(30)
        apply_button.setDefault(True)
        apply_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(30)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def params(self):
        return {
            "mode": self.MODES[self.cmb_mode.currentIndex()][1],
            "remove_source": self.chk_remove.isChecked(),
        }


class tool_explode(tool_base):
    """Split a picked feature into single parts or single segments."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.remove_source = True

    def tool_name(self):
        return "Explode"

    def activate(self):
        super().activate()
        self.tool_message.emit("💥 Explode — Select the feature to explode")

    def on_entity_selected(self, layer, feature, point):
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            self.tool_message.emit("⚠️ Explode — Geometry is empty")
            self._reset()
            return

        dialog = ExplodeDialog(self.remove_source, self.iface.mainWindow())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.tool_message.emit("⚠️ Explode — Cancelled")
            self._reset()
            return
        params = dialog.params()
        self.remove_source = params["remove_source"]

        pieces = explode_geometry(geometry, params["mode"])
        if not pieces:
            self.tool_message.emit(
                "⚠️ Explode — This feature cannot be split further"
            )
            self._reset()
            return
        if params["mode"] == "parts" and len(pieces) < 2:
            self.tool_message.emit(
                "⚠️ Explode — The feature is already a single part"
            )
            self._reset()
            return

        if self._write_pieces(layer, feature, pieces, params["mode"]):
            self.tool_message.emit(
                f"✅ Explode — {len(pieces)} feature(s) created"
            )
        self._reset()

    def _write_pieces(self, layer, feature, pieces, mode):
        """Write the exploded pieces to the source or a managed layer."""
        piece_type = pieces[0].type()
        same_layer = piece_type == layer.geometryType()

        if same_layer:
            coerced = [self._coerce(piece, layer) for piece in pieces]
            if not self._add_features(layer, coerced, feature):
                self.tool_message.emit(
                    "⚠️ Explode — The exploded features could not be added"
                )
                return False
        else:
            target = get_or_create_layer(
                EXPLODE_LAYER_NAME, geom_type="LineString", crs=layer.crs()
            )
            if target is None:
                self.tool_message.emit(
                    f"⚠️ Explode — The {EXPLODE_LAYER_NAME} layer "
                    "could not be created"
                )
                return False
            written = 0
            for piece in pieces:
                if add_feature_to_layer(target, piece) is not None:
                    written += 1
            if not written:
                self.tool_message.emit(
                    f"⚠️ Explode — Nothing could be written to "
                    f"{EXPLODE_LAYER_NAME}"
                )
                return False
            target.triggerRepaint()

        if self.remove_source:
            if not layer.isEditable() and not layer.startEditing():
                self.tool_message.emit(
                    "⚠️ Explode — Pieces added, but the source layer is "
                    "read-only so the original was kept"
                )
                return True
            layer.beginEditCommand("PlanX CAD: explode source removal")
            if layer.deleteFeature(feature.id()):
                layer.endEditCommand()
            else:
                layer.destroyEditCommand()
                self.tool_message.emit(
                    "⚠️ Explode — Pieces added, but the original could not "
                    "be removed"
                )
            layer.triggerRepaint()
        return True

    @staticmethod
    def _coerce(geometry, layer):
        result = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not result.isMultipart():
            result.convertToMultiType()
        return result

    def on_click(self, point, button):
        """Explode completes on selection; further clicks restart the tool."""
        if button == Qt.MouseButton.LeftButton:
            self._reset()
