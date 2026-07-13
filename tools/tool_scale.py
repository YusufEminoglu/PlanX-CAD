# -*- coding: utf-8 -*-
"""PlanX CAD Scale tool."""

import math

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import scale_geometry, point_distance
from ..core.precision_input import PrecisionInputError, looks_like_precision_input


class tool_scale(tool_base):
    """Scale a feature around its picked center.

    1. Select feature | 2. Scale center |
    3. Reference distance | 4. Target distance
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None
        self.ref_distance = None

    def tool_name(self):
        return "Scale"

    def on_entity_selected(self, layer, feature, point):
        self.center = point
        self._step = 2
        self.tool_message.emit(
            "⤡ Scale — Click to define the reference distance"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.ref_distance = point_distance(self.center, point)
                if self.ref_distance < 0.001:
                    self.tool_message.emit("⚠️ Scale — Reference distance is too small")
                    return
                self._step = 3
                self.tool_message.emit(
                    "⤡ Scale — Click to define the target distance"
                )
            elif self._step == 3:
                target_distance = point_distance(self.center, point)
                factor = target_distance / self.ref_distance
                self._apply_factor(factor)

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            target_distance = point_distance(self.center, point)
            if self.ref_distance > 0.001:
                factor = target_distance / self.ref_distance
                geom = self.selected_feature.geometry()
                preview = scale_geometry(geom, self.center, factor)
                if preview:
                    self.preview_rb.reset(geom.type())
                    self.preview_rb.setToGeometry(preview, self.selected_layer)

    def _apply_factor(self, factor):
        geom = self.selected_feature.geometry()
        scaled = scale_geometry(geom, self.center, factor)
        if scaled:
            applied = self._apply_edit(
                self.selected_layer, self.selected_feature, scaled
            )
            if applied:
                self.tool_message.emit(f"✅ Scale — Factor {factor:.6g}")
        else:
            self.tool_message.emit("⚠️ Scale operation failed")
        self.center = None
        self.ref_distance = None
        self._reset()

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        if self._step not in (2, 3) or self.center is None:
            self.tool_message.emit(
                "⚠️ Scale — Select a feature before entering a precise value"
            )
            return True
        token = (text or "").strip()
        if "," not in token and "@" not in token and "<" not in token:
            try:
                factor = float(token)
                if not math.isfinite(factor) or factor <= 0.0:
                    raise ValueError
            except ValueError:
                self.tool_message.emit(
                    "⚠️ Scale — Enter a factor greater than zero"
                )
                return True
            self._apply_factor(factor)
            return True
        try:
            point = self.resolve_precision_target(
                token, self.center, self.selected_layer
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Scale — {error}")
            return True
        self.on_click(point, Qt.MouseButton.LeftButton)
        return True
