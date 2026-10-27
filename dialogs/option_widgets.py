# -*- coding: utf-8 -*-
"""Widgets for inline tool settings (core.tool_options).

``make_option_widget`` is shared by the dock's active-command card and by
``ToolOptionsDialog``, the fallback a tool opens when the dock is hidden.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QLabel, QLineEdit, QSizePolicy, QSpinBox, QVBoxLayout,
)

try:
    from qgis.gui import QgsColorButton
except ImportError:  # pragma: no cover - defensive
    QgsColorButton = None

from ..core.tool_options import BOOL, CHOICE, COLOR, FLOAT, INT, TEXT, option_values, set_option


def make_option_widget(spec, value, on_change):
    """Return an editor for ``spec`` showing ``value``.

    ``on_change(spec, new_value)`` is called with the stored (coerced) type of
    value whenever the user changes it. Returns None for an unsupported kind.
    """
    if spec.kind == FLOAT:
        widget = QDoubleSpinBox()
        widget.setDecimals(spec.decimals)
        widget.setRange(spec.minimum if spec.minimum is not None else -1e9,
                        spec.maximum if spec.maximum is not None else 1e9)
        widget.setSuffix(spec.suffix)
        widget.setValue(float(spec.coerce(value)))
        widget.setKeyboardTracking(False)
        widget.valueChanged.connect(lambda v, s=spec: on_change(s, v))
    elif spec.kind == INT:
        widget = QSpinBox()
        widget.setRange(int(spec.minimum if spec.minimum is not None else -10**9),
                        int(spec.maximum if spec.maximum is not None else 10**9))
        widget.setSuffix(spec.suffix)
        widget.setValue(int(spec.coerce(value)))
        widget.setKeyboardTracking(False)
        widget.valueChanged.connect(lambda v, s=spec: on_change(s, v))
    elif spec.kind == CHOICE:
        widget = QComboBox()
        for stored, label in spec.choices:
            widget.addItem(label, stored)
        current = spec.coerce(value)
        for index, (stored, _label) in enumerate(spec.choices):
            if stored == current:
                widget.setCurrentIndex(index)
        widget.currentIndexChanged.connect(
            lambda i, s=spec: on_change(s, s.choices[i][0] if 0 <= i < len(s.choices) else s.default)
        )
    elif spec.kind == BOOL:
        widget = QCheckBox()
        widget.setChecked(bool(spec.coerce(value)))
        widget.toggled.connect(lambda on, s=spec: on_change(s, on))
    elif spec.kind == TEXT:
        widget = QLineEdit(str(spec.coerce(value)))
        widget.editingFinished.connect(lambda s=spec, w=widget: on_change(s, w.text()))
    elif spec.kind == COLOR and QgsColorButton is not None:
        widget = QgsColorButton()
        widget.setColor(QColor(spec.coerce(value)))
        widget.colorChanged.connect(lambda c, s=spec: on_change(s, c.name()))
    else:
        return None
    if spec.tooltip:
        widget.setToolTip(spec.tooltip)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class ToolOptionsDialog(QDialog):
    """Modal settings form built from a tool's INLINE_OPTIONS.

    Values are applied to the tool only when the user clicks OK.
    """

    def __init__(self, tool, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(320)
        self._tool = tool
        self._specs = tuple(getattr(tool, "INLINE_OPTIONS", ()) or ())
        self._values = option_values(tool, self._specs)
        self._rows = []

        layout = QVBoxLayout(self)
        heading = QLabel(title)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        heading.setFont(font)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)

        form = QFormLayout()
        for spec in self._specs:
            widget = make_option_widget(spec, self._values.get(spec.attr, spec.default), self._changed)
            if widget is None:
                continue
            label = QLabel(spec.label)
            label.setBuddy(widget)
            form.addRow(label, widget)
            self._rows.append((spec, label, widget))
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_visibility()

    def _changed(self, spec, value):
        self._values[spec.attr] = spec.coerce(value)
        self._refresh_visibility()

    def _refresh_visibility(self):
        for spec, label, widget in self._rows:
            visible = spec.is_visible(self._values)
            label.setVisible(visible)
            widget.setVisible(visible)

    def apply(self):
        """Copy the edited values onto the tool."""
        for spec in self._specs:
            if spec.attr in self._values:
                set_option(self._tool, spec, self._values[spec.attr])
