# -*- coding: utf-8 -*-
"""Shared base for the street and parcel design tools.

These tools read source features from any vector layer and write their
results to plugin-managed polygon layers (``planx_envelope``,
``planx_parking`` ...). Settings come from the dock's active-command card or,
with the dock hidden, from a form generated from ``INLINE_OPTIONS``.
"""
from __future__ import annotations

from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes

from .tool_base import tool_base
from ..core.crs_utils import local_metric_crs, transform_geometry, transform_point
from ..core.sketcher_layer_utils import get_or_create_layer
from ..dialogs.option_widgets import ToolOptionsDialog


class urban_output_tool(tool_base):
    """Pick-based tool that writes polygons to a managed output layer."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        # Sources only need to be readable; output goes to managed layers.
        self.require_editable = False
        self._activation_cancelled = False

    # ── Settings ────────────────────────────────────────────────────────
    def _ask_options(self) -> bool:
        """Use the dock card's values, or ask once with a generated form."""
        if self.use_inline_options() or not self.INLINE_OPTIONS:
            return True
        dialog = ToolOptionsDialog(self, self.tool_name(), self.iface.mainWindow())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        dialog.apply()
        return True

    def _start(self, prompt) -> bool:
        """Shared activation: collect settings, then show the first prompt."""
        self._activation_cancelled = False
        if not self._ask_options():
            self._activation_cancelled = True
            self.tool_message.emit(f"{self.tool_name()} — Cancelled")
            return False
        self.tool_message.emit(f"{self.tool_name()} — {prompt}")
        return True

    # ── CRS helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _metric_crs_for(point, crs):
        if crs is None or not crs.isValid():
            return None
        return local_metric_crs(QgsPointXY(point), crs)

    @staticmethod
    def _to_metric(geometry, crs, metric_crs):
        return transform_geometry(geometry, crs, metric_crs)

    @staticmethod
    def _point_to_metric(point, crs, metric_crs):
        return transform_point(point, crs, metric_crs)

    @staticmethod
    def _from_metric(geometry, metric_crs, crs):
        return transform_geometry(geometry, metric_crs, crs)

    # ── Output ──────────────────────────────────────────────────────────
    def _write(self, layer_name, crs, fields, items):
        """Add ``items`` = [(geometry in ``crs``, {field: value})] to the
        managed layer in one undoable edit command. Returns the layer or None.
        """
        items = [(g, a) for g, a in items if g is not None and not g.isEmpty()]
        if not items:
            return None
        layer = get_or_create_layer(layer_name, geom_type="Polygon", crs=crs, fields=fields)
        if layer is None:
            return None
        was_editing = layer.isEditable()
        if not was_editing and not layer.startEditing():
            return None
        features = []
        for geometry, attributes in items:
            geometry = QgsGeometry(geometry)
            if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
                geometry.convertToMultiType()
            feature = QgsFeature(layer.fields())
            feature.setGeometry(geometry)
            for name, value in attributes.items():
                index = layer.fields().indexOf(name)
                if index >= 0:
                    feature.setAttribute(index, value)
            features.append(feature)
        layer.beginEditCommand(f"PlanX CAD: {self.tool_name()}")
        if not layer.addFeatures(features):
            layer.destroyEditCommand()
            if not was_editing:
                layer.rollBack()
            return None
        layer.endEditCommand()
        # Commit only an edit session this tool opened.
        if not was_editing and not layer.commitChanges():
            layer.rollBack()
            return None
        layer.triggerRepaint()
        return layer
