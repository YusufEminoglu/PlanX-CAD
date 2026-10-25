# -*- coding: utf-8 -*-
"""planX CAD — Dynamic Input Heads-Up Display (HUD) Canvas Item.

Renders an AutoCAD-style floating cursor HUD directly on the QgsMapCanvas scene:
  - Live length and angle readout
  - Live Δx and Δy coordinate deltas
  - Clean translucent dark pill styling
  - Zero flickering, native QgsMapCanvasItem implementation for 100% Qt5/Qt6 parity.
"""
from __future__ import annotations

import contextlib
import math

from qgis.PyQt.QtCore import QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPen
from qgis.core import QgsPointXY
from qgis.gui import QgsMapCanvas, QgsMapCanvasItem


class DynamicInputHud(QgsMapCanvasItem):
    """Map-canvas overlay displaying live drafting metrics next to the cursor."""

    def __init__(self, canvas: QgsMapCanvas):
        super().__init__(canvas)
        self.canvas = canvas
        self._enabled: bool = True
        self._visible: bool = False
        self._text_line1: str = ""
        self._text_line2: str = ""
        self._cursor_point: QgsPointXY | None = None
        self._screen_pos = QPointF(0, 0)
        self._box_rect = QRectF(0, 0, 0, 0)
        self._padding = 6.0
        self._offset_x = 18.0
        self._offset_y = 18.0

        self.font = QFont("Segoe UI", 9)
        self.font.setBold(True)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        if not self._enabled:
            self.hide_hud()

    def update_metrics(
        self,
        cursor_point: QgsPointXY,
        distance_m: float | None = None,
        angle_deg: float | None = None,
        dx_m: float | None = None,
        dy_m: float | None = None,
        extra_label: str = "",
    ) -> None:
        """Update live drafting values and trigger canvas redraw."""
        if not self._enabled:
            return

        self._cursor_point = QgsPointXY(cursor_point)

        if distance_m is not None and angle_deg is not None and distance_m > 0:
            self._text_line1 = f"Len: {distance_m:.2f} m   Ang: {angle_deg:.1f}°"
            if dx_m is not None and dy_m is not None:
                self._text_line2 = f"Δx: {dx_m:.2f} m   Δy: {dy_m:.2f} m"
            else:
                self._text_line2 = extra_label
        elif extra_label:
            self._text_line1 = extra_label
            self._text_line2 = f"X: {cursor_point.x():.2f}  Y: {cursor_point.y():.2f}"
        else:
            self._text_line1 = f"X: {cursor_point.x():.2f}  Y: {cursor_point.y():.2f}"
            self._text_line2 = ""

        self._visible = True
        self.setPos(self.toCanvasCoordinates(cursor_point))
        self.update()

    def hide_hud(self) -> None:
        self._visible = False
        self._text_line1 = ""
        self._text_line2 = ""
        self.update()

    def boundingRect(self) -> QRectF:
        if not self._visible or not self._text_line1:
            return QRectF()

        fm = QFontMetrics(self.font)
        w1 = fm.horizontalAdvance(self._text_line1) if hasattr(fm, "horizontalAdvance") else fm.width(self._text_line1)
        w2 = (
            fm.horizontalAdvance(self._text_line2)
            if hasattr(fm, "horizontalAdvance")
            else fm.width(self._text_line2)
        ) if self._text_line2 else 0
        text_w = max(w1, w2)
        line_h = fm.height()
        total_h = line_h * 2 + 2 if self._text_line2 else line_h

        box_w = text_w + self._padding * 2 + 8
        box_h = total_h + self._padding * 2

        self._box_rect = QRectF(self._offset_x, self._offset_y, box_w, box_h)
        # Margin around box for pen width
        return self._box_rect.adjusted(-2, -2, 2, 2)

    def paint(self, painter: QPainter, *_args) -> None:
        if not self._visible or not self._text_line1 or not self._enabled:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self.font)

        rect = self._box_rect
        if rect.isEmpty():
            self.boundingRect()
            rect = self._box_rect

        # Translucent dark Slate pill background
        bg_brush = QBrush(QColor(15, 23, 42, 218))
        border_pen = QPen(QColor(13, 148, 136, 200), 1.2)  # PlanX Teal accent border
        painter.setBrush(bg_brush)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 5.0, 5.0)

        # Draw primary text line
        text_pen1 = QPen(QColor(248, 250, 252))  # Slate 50
        painter.setPen(text_pen1)
        fm = QFontMetrics(self.font)
        line_h = fm.height()
        y1 = rect.top() + self._padding + fm.ascent()
        painter.drawText(QPointF(rect.left() + self._padding + 4, y1), self._text_line1)

        # Draw secondary text line (if present)
        if self._text_line2:
            text_pen2 = QPen(QColor(148, 163, 184))  # Slate 400
            painter.setPen(text_pen2)
            y2 = y1 + line_h + 2
            painter.drawText(QPointF(rect.left() + self._padding + 4, y2), self._text_line2)

        painter.restore()

    def cleanup(self) -> None:
        self.hide_hud()
        if self.scene() is not None:
            with contextlib.suppress(Exception):
                self.scene().removeItem(self)
