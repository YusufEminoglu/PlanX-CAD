# -*- coding: utf-8 -*-
"""PlanX CAD Break tool: split a line at a point or remove a span."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.precision_input import PrecisionInputError, looks_like_precision_input
from ..core.sketcher_utils import break_line_at_points


class tool_break(tool_base):
    """Break a line feature into two parts, optionally leaving a gap.

    1. Select a line | 2. Click the first break point |
    3. Click a second point for a gap, or press Enter / right-click to break
       at the first point only.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.first_point = None

    def tool_name(self):
        return "Break"

    def activate(self):
        super().activate()
        self.first_point = None
        self.tool_message.emit("✂️ Break — Select a line to break")

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Break — Geometry is empty")
            self._reset_break()
            return
        if geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
            self.tool_message.emit("⚠️ Break — Only line features can be broken")
            self._reset_break()
            return
        self.first_point = None
        self._step = 2
        self.tool_message.emit("✂️ Break — Click the first break point")

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            self.first_point = QgsPointXY(point)
            self._step = 3
            self.tool_message.emit(
                "✂️ Break — Click the second point for a gap, or press Enter "
                "to break at this point"
            )
            return
        if self._step == 3:
            if button == Qt.MouseButton.LeftButton:
                self._apply_break(self.first_point, QgsPointXY(point))
            else:
                # A right-click is the AutoCAD "break at point" confirmation.
                self._apply_break(self.first_point, None)

    def handle_command_enter(self):
        """Break at the first point when the operator presses Enter."""
        if self._step != 3 or self.first_point is None:
            return False
        self._apply_break(self.first_point, None)
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
        if self._step not in (2, 3):
            self.tool_message.emit("⚠️ Break — Select a line first")
            return True
        base = self.first_point if self._step == 3 else self.selected_point
        try:
            target = self.resolve_precision_target(
                text, base, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Break — {error}")
            return True
        self.on_click(target, Qt.MouseButton.LeftButton)
        return True

    def _apply_break(self, first_point, second_point):
        layer = self.selected_layer
        feature = self.selected_feature
        if layer is None or feature is None:
            self._reset_break()
            return

        parts = break_line_at_points(feature.geometry(), first_point, second_point)
        if not parts:
            self.tool_message.emit(
                "⚠️ Break — The break point must lie between the line endpoints"
            )
            self._reset_break()
            return

        if len(parts) == 1:
            # A gap that reaches an endpoint only shortens the line.
            self._apply_edit(layer, feature, self._coerce(parts[0], layer))
            self.tool_message.emit("✅ Break — Line shortened")
            self._reset_break()
            return

        if not layer.isEditable() and not layer.startEditing():
            self.tool_message.emit("⚠️ Break — Layer could not enter edit mode")
            self._reset_break()
            return

        layer.beginEditCommand(self.tool_name())
        head = self._coerce(parts[0], layer)
        if not layer.changeGeometry(feature.id(), head):
            layer.destroyEditCommand()
            self.tool_message.emit("⚠️ Break — Geometry could not be updated")
            self._reset_break()
            return
        layer.endEditCommand()

        added = self._add_features(layer, [self._coerce(part, layer)
                                           for part in parts[1:]], feature)
        if not added:
            self.tool_message.emit(
                "⚠️ Break — The second part could not be added"
            )
            self._reset_break()
            return

        layer.triggerRepaint()
        self.tool_message.emit(
            "✅ Break — Line split with a gap" if second_point is not None
            else "✅ Break — Line split at the picked point"
        )
        self._reset_break()

    @staticmethod
    def _coerce(geometry, layer):
        result = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not result.isMultipart():
            result.convertToMultiType()
        return result

    def _reset_break(self):
        self.first_point = None
        self._reset()
