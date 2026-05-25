# -*- coding: utf-8 -*-
"""planX CAD â€” Construction (reference) lines.

Pick two points to define a construction line. Modes:
  - Infinite: the line stretches across the current canvas extent (auto
    re-extended every time the map is repainted).
  - Ray: from the first point through the second, extending forward only.
  - Segment: bounded by the two clicks (regular line on the construction
    layer, but with the construction-line style).

Construction lines live on the auto-created `planx_construction` layer with
a dashed cyan style so they are visually distinct from real geometry.

Right-click clears the active mode and prepares for a new pair of points.
"""
from __future__ import annotations

import math

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineSymbol,
    QgsPointXY,
    QgsSingleSymbolRenderer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband,
    cleanup_sketcher_rubberband,
    COLOR_ACCENT,
)
from ..core.sketcher_layer_utils import get_or_create_layer


_INF_EXTEND_FACTOR = 10.0  # multiples of canvas extent for "infinite" lines


def _extend_through(p1: QgsPointXY, p2: QgsPointXY, length: float) -> tuple[QgsPointXY, QgsPointXY]:
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return p1, p2
    ux, uy = dx / norm, dy / norm
    a = QgsPointXY(p1.x() - ux * length, p1.y() - uy * length)
    b = QgsPointXY(p2.x() + ux * length, p2.y() + uy * length)
    return a, b


def _ray_through(p1: QgsPointXY, p2: QgsPointXY, length: float) -> QgsPointXY:
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return p2
    ux, uy = dx / norm, dy / norm
    return QgsPointXY(p2.x() + ux * length, p2.y() + uy * length)


class tool_construction_line(QgsMapTool):
    """Map tool: 2 clicks â†’ committed construction line on planx_construction."""

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)

    MODE_INFINITE = "infinite"
    MODE_RAY = "ray"
    MODE_SEGMENT = "segment"

    def __init__(self, canvas, iface, mode: str = MODE_INFINITE):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.mode = mode
        self.first_point: QgsPointXY | None = None
        self.preview_rb = None
        self._count = 0

    def tool_name(self):
        return f"Construction ({self.mode})"

    def activate(self):
        super().activate()
        self.first_point = None
        self.preview_rb = create_preview_rubberband(self.canvas, QgsWkbTypes.LineGeometry)
        if self.preview_rb is not None:
            self.preview_rb.setColor(COLOR_ACCENT)
            self.preview_rb.setWidth(1)
            self.preview_rb.setLineStyle(Qt.PenStyle.DashLine)
        self.tool_message.emit(
            f"â”„ Construction ({self.mode}) â€” click the first reference point | "
            f"right-click resets | Esc cancels"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        self.first_point = None
        super().deactivate()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.first_point = None
            if self.preview_rb is not None:
                self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            self.tool_message.emit("â”„ Construction â€” cancelled")

    def canvasPressEvent(self, event):
        point = self._snap(event)
        if event.button() == Qt.MouseButton.RightButton:
            self.first_point = None
            if self.preview_rb is not None:
                self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            self.tool_message.emit(f"â”„ Construction â€” reset ({self._count} so far)")
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.first_point is None:
            self.first_point = point
            self.tool_message.emit(f"â”„ Construction ({self.mode}) â€” click the second reference point")
        else:
            self._commit(self.first_point, point)
            self.first_point = None

    def canvasMoveEvent(self, event):
        if self.first_point is None or self.preview_rb is None:
            return
        p2 = self._snap(event)
        a, b = self._segment_for_preview(self.first_point, p2)
        self.preview_rb.reset(QgsWkbTypes.LineGeometry)
        self.preview_rb.addPoint(a)
        self.preview_rb.addPoint(b)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _snap(self, event) -> QgsPointXY:
        snapper = self.canvas.snappingUtils()
        if snapper is not None:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                return match.point()
        return self.toMapCoordinates(event.pos())

    def _canvas_diagonal(self) -> float:
        rect = self.canvas.extent()
        return math.hypot(rect.width(), rect.height()) * _INF_EXTEND_FACTOR

    def _segment_for_preview(self, p1, p2) -> tuple[QgsPointXY, QgsPointXY]:
        if self.mode == self.MODE_INFINITE:
            return _extend_through(p1, p2, self._canvas_diagonal())
        if self.mode == self.MODE_RAY:
            return p1, _ray_through(p1, p2, self._canvas_diagonal())
        return p1, p2  # segment

    def _commit(self, p1, p2):
        a, b = self._segment_for_preview(p1, p2)
        line = QgsGeometry.fromPolylineXY([a, b])
        layer = get_or_create_layer(
            "planx_construction",
            geom_type="LineString",
            fields=[("mode", "string"), ("from_x", "double"), ("from_y", "double"),
                    ("to_x", "double"), ("to_y", "double")],
        )
        if layer is None:
            self.tool_message.emit("âš ï¸ Construction â€” layer creation failed")
            return

        was_editing = layer.isEditable()
        if not was_editing:
            layer.startEditing()
        feat = QgsFeature(layer.fields())
        feat.setGeometry(line)
        feat.setAttribute(layer.fields().indexOf("mode"), self.mode)
        feat.setAttribute(layer.fields().indexOf("from_x"), p1.x())
        feat.setAttribute(layer.fields().indexOf("from_y"), p1.y())
        feat.setAttribute(layer.fields().indexOf("to_x"), p2.x())
        feat.setAttribute(layer.fields().indexOf("to_y"), p2.y())
        layer.addFeature(feat)
        if not was_editing:
            layer.commitChanges()

        # Apply the dashed cyan style once per layer lifetime.
        if layer.customProperty("planx_construction_style_applied") != "yes":
            sym = QgsLineSymbol.createSimple({
                "line_color": "0,188,212,200",
                "line_width": "0.4",
                "line_style": "dash",
                "capstyle": "round",
            })
            layer.setRenderer(QgsSingleSymbolRenderer(sym))
            layer.setCustomProperty("planx_construction_style_applied", "yes")
        layer.triggerRepaint()
        self._count += 1
        self.tool_message.emit(
            f"âœ… Construction #{self._count} â€” {self.mode}; continue or right-click to reset"
        )
