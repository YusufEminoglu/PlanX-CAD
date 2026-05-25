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
        self._build_ui()
        try:
            self.canvas.xyCoordinates.connect(self._on_xy)
            self.canvas.scaleChanged.connect(self._on_scale)
        except Exception:
            # Signal API differs across QGIS minor versions â€” fail safe.
            pass
        self._on_scale(self.canvas.scale())

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        box = QFrame(self)
        box.setFrameShape(QFrame.StyledPanel)
        box.setStyleSheet(
            "QFrame { background: #f4f7fb; border: 1px solid #d8e0ea;"
            " border-radius: 4px; padding: 2px 4px; }"
            "QLabel { color: #0f766e; font-family: 'Consolas','Courier New', monospace; }"
        )
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setSpacing(0)

        self.lbl_xy = QLabel("X: â€”   Y: â€”")
        xy_font = QFont()
        xy_font.setPointSize(9)
        xy_font.setBold(True)
        self.lbl_xy.setFont(xy_font)
        self.lbl_xy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box_layout.addWidget(self.lbl_xy)

        self.lbl_meta = QLabel("CRS: â€”    1: â€”")
        meta_font = QFont()
        meta_font.setPointSize(7.5)
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
            crs_id = crs.authid() or "â€”"
            self.lbl_meta.setText(f"CRS: {crs_id}    1: {scale:,.0f}")
        except Exception:
            pass

    def unload(self) -> None:
        try:
            self.canvas.xyCoordinates.disconnect(self._on_xy)
            self.canvas.scaleChanged.disconnect(self._on_scale)
        except Exception:
            pass
