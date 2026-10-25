# -*- coding: utf-8 -*-
"""planX CAD — OSNAP Glyph Marker and Accessibility Manager.

Renders typed geometric snap glyphs on the QGIS map canvas using native
QgsVertexMarker and QgsRubberBand shapes, matching AutoCAD OSNAP visual
conventions:
  - Endpoint: Box
  - Midpoint: Triangle
  - Centre: Circle
  - Quadrant: Rhombus / Diamond
  - Intersection: X
  - Apparent Intersection: Double Triangle
  - Perpendicular: Inverted Triangle / Orthogonal
  - Tangent: Circle with tangent indicator
  - Nearest: Hourglass / Double Triangle
  - Vertex/Node: Cross
  - Extension: X with ray guide

Accessible to screen-readers via tool messages and status announcements.
"""
from __future__ import annotations

import contextlib

from qgis.PyQt.QtCore import Qt, QObject, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPen
from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsRubberBand, QgsVertexMarker

from .osnap_engine import SnapKind, SnapResult

# High-contrast PlanX CAD snapping color palette
COLOR_OSNAP_DEFAULT = QColor(13, 148, 136)       # Teal 600
COLOR_OSNAP_INTERSECT = QColor(225, 29, 72)      # Rose 600
COLOR_OSNAP_PERP = QColor(37, 99, 235)           # Blue 600
COLOR_OSNAP_ACCENT = QColor(217, 119, 6)         # Amber 600


class OsnapMarkerManager(QObject):
    """Manages canvas markers and accessibility announcements for OSNAP candidates."""

    snap_announced = pyqtSignal(str)

    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self._marker = None
        self._aux_band = None
        self._current_result: SnapResult | None = None
        self._last_announced_kind: SnapKind | None = None
        self._setup_items()

    def _setup_items(self):
        if self._marker is None and self.canvas is not None:
            self._marker = QgsVertexMarker(self.canvas)
            # Scoped access for Qt6 / QGIS 4 compatibility
            icon_box = getattr(
                getattr(QgsVertexMarker, "IconType", QgsVertexMarker),
                "ICON_BOX",
                QgsVertexMarker.ICON_BOX,
            )
            self._marker.setIconType(icon_box)
            self._marker.setColor(COLOR_OSNAP_DEFAULT)
            self._marker.setIconSize(13)
            self._marker.setPenWidth(2)
            self._marker.hide()

        if self._aux_band is None and self.canvas is not None:
            self._aux_band = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
            self._aux_band.setColor(COLOR_OSNAP_DEFAULT)
            self._aux_band.setWidth(1)
            self._aux_band.setLineStyle(Qt.PenStyle.DashLine)
            self._aux_band.hide()

    def update_result(self, result: SnapResult | None) -> None:
        """Update visible marker shape and color according to the snap result."""
        self._setup_items()
        self._current_result = result

        if result is None:
            if self._marker:
                self._marker.hide()
            if self._aux_band:
                self._aux_band.reset(QgsWkbTypes.GeometryType.LineGeometry)
                self._aux_band.hide()
            self._last_announced_kind = None
            return

        pt = result.point
        kind = result.kind
        icon_type, color = self._glyph_for_kind(kind)

        if self._marker:
            self._marker.setIconType(icon_type)
            self._marker.setColor(color)
            self._marker.setCenter(pt)
            self._marker.show()

        # Emit accessible status change
        if kind != self._last_announced_kind:
            self._last_announced_kind = kind
            desc = result.description or kind.value
            self.snap_announced.emit(f"Snap: {desc.title()}")

    def _glyph_for_kind(self, kind: SnapKind) -> tuple[int, QColor]:
        """Map SnapKind to QgsVertexMarker.IconType and theme color."""
        vm = getattr(QgsVertexMarker, "IconType", QgsVertexMarker)

        if kind == SnapKind.ENDPOINT:
            return getattr(vm, "ICON_BOX", QgsVertexMarker.ICON_BOX), COLOR_OSNAP_DEFAULT
        elif kind == SnapKind.MIDPOINT:
            return getattr(vm, "ICON_TRIANGLE", QgsVertexMarker.ICON_TRIANGLE), COLOR_OSNAP_DEFAULT
        elif kind == SnapKind.CENTRE:
            return getattr(vm, "ICON_CIRCLE", QgsVertexMarker.ICON_CIRCLE), COLOR_OSNAP_DEFAULT
        elif kind == SnapKind.QUADRANT:
            return getattr(vm, "ICON_RHOMBUS", QgsVertexMarker.ICON_RHOMBUS), COLOR_OSNAP_ACCENT
        elif kind == SnapKind.INTERSECTION:
            return getattr(vm, "ICON_X", QgsVertexMarker.ICON_X), COLOR_OSNAP_INTERSECT
        elif kind == SnapKind.APPARENT_INTERSECTION:
            return getattr(vm, "ICON_DOUBLE_TRIANGLE", QgsVertexMarker.ICON_DOUBLE_TRIANGLE), COLOR_OSNAP_INTERSECT
        elif kind == SnapKind.PERPENDICULAR:
            return getattr(vm, "ICON_INVERTED_TRIANGLE", QgsVertexMarker.ICON_INVERTED_TRIANGLE), COLOR_OSNAP_PERP
        elif kind == SnapKind.TANGENT:
            return getattr(vm, "ICON_CIRCLE", QgsVertexMarker.ICON_CIRCLE), COLOR_OSNAP_PERP
        elif kind == SnapKind.NEAREST:
            return getattr(vm, "ICON_DOUBLE_TRIANGLE", QgsVertexMarker.ICON_DOUBLE_TRIANGLE), COLOR_OSNAP_DEFAULT
        elif kind == SnapKind.EXTENSION:
            return getattr(vm, "ICON_CROSS", QgsVertexMarker.ICON_CROSS), COLOR_OSNAP_ACCENT
        else:  # VERTEX
            return getattr(vm, "ICON_CROSS", QgsVertexMarker.ICON_CROSS), COLOR_OSNAP_DEFAULT

    def hide(self):
        if self._marker:
            self._marker.hide()
        if self._aux_band:
            self._aux_band.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self._aux_band.hide()
        self._current_result = None
        self._last_announced_kind = None

    def cleanup(self):
        """Remove canvas items completely on tool deactivation."""
        self.hide()
        if self._marker and getattr(self._marker, "scene", lambda: None)() is not None:
            with contextlib.suppress(Exception):
                self._marker.scene().removeItem(self._marker)
            self._marker = None
        if self._aux_band and getattr(self._aux_band, "scene", lambda: None)() is not None:
            with contextlib.suppress(Exception):
                self._aux_band.scene().removeItem(self._aux_band)
            self._aux_band = None
        self._current_result = None
        self._last_announced_kind = None
