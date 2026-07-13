# -*- coding: utf-8 -*-
"""Live coordinate read-out for the CAD dock.

Subscribes to the canvas' `xyCoordinates` signal and updates a compact label
showing the cursor's map-coordinate position, plus the current map units (CRS)
and the scale denominator. Survives canvas / CRS changes.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class LiveCoordWidget(QWidget):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self._signal_connections = []
        self._build_ui()
        self._connect_canvas_signal("xyCoordinates", self._on_xy)
        self._connect_canvas_signal("scaleChanged", self._on_scale)
        self._connect_canvas_signal("destinationCrsChanged", self._on_crs_changed)
        self._on_scale(self.canvas.scale())

    def _connect_canvas_signal(self, name, slot) -> None:
        """Connect an optional canvas signal and remember it for safe cleanup."""
        signal = getattr(self.canvas, name, None)
        if signal is None:
            return
        try:
            signal.connect(slot)
            self._signal_connections.append((signal, slot))
        except Exception:
            # Signal availability differs across supported QGIS versions.
            pass

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        box = QFrame(self)
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box.setStyleSheet(
            "QFrame { background: #f4f7fb; border: 1px solid #d8e0ea;"
            " border-radius: 4px; padding: 2px 4px; }"
            "QLabel { color: #0f766e; font-family: 'Consolas','Courier New', monospace; }"
        )
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)

        self.lbl_xy = QLabel("X: —   Y: —")
        xy_font = QFont()
        xy_font.setPointSize(9)
        xy_font.setBold(True)
        self.lbl_xy.setFont(xy_font)
        self.lbl_xy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.lbl_xy)

        self.lbl_meta = QLabel("CRS: —    1: —")
        meta_font = QFont()
        meta_font.setPointSizeF(7.5)
        self.lbl_meta.setFont(meta_font)
        self.lbl_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_meta.setStyleSheet("color: #546e7a;")
        box_layout.addWidget(self.lbl_meta)

        outer.addWidget(box)

    def _on_xy(self, point) -> None:
        try:
            self.lbl_xy.setText(f"X: {point.x():,.3f}   Y: {point.y():,.3f}")
        except Exception:
            pass

    def _on_scale(self, scale: float) -> None:
        try:
            crs = self.canvas.mapSettings().destinationCrs()
            crs_id = crs.authid() or "—"
            self.lbl_meta.setText(f"CRS: {crs_id}    1: {scale:,.0f}")
        except Exception:
            pass

    def _on_crs_changed(self, *_args) -> None:
        self._on_scale(self.canvas.scale())

    def unload(self) -> None:
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except Exception:
                pass
        self._signal_connections.clear()
