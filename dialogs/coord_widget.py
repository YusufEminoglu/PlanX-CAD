# -*- coding: utf-8 -*-
"""Live coordinate read-out for the CAD dock.

Subscribes to the canvas' `xyCoordinates` signal and updates a compact label
showing the cursor's map-coordinate position, plus the current map units (CRS)
and the scale denominator. Survives canvas / CRS changes.
"""
from __future__ import annotations

from contextlib import suppress

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QWidget


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
        # Signal availability differs across supported QGIS versions.
        with suppress(Exception):
            signal.connect(slot)
            self._signal_connections.append((signal, slot))

    def _build_ui(self) -> None:
        # One quiet line: cursor position on the left, CRS and scale on the
        # right. Colours come from the dock's stylesheet (coordXY / coordMeta),
        # so the read-out follows light and dark QGIS themes.
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(8)

        self.lbl_xy = QLabel("X: —   Y: —")
        self.lbl_xy.setObjectName("coordXY")
        self.lbl_xy.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.lbl_xy)
        row.addStretch(1)

        self.lbl_meta = QLabel("—   1: —")
        self.lbl_meta.setObjectName("coordMeta")
        row.addWidget(self.lbl_meta)

    def _on_xy(self, point) -> None:
        with suppress(Exception):
            self.lbl_xy.setText(f"X: {point.x():,.3f}   Y: {point.y():,.3f}")

    def _on_scale(self, scale: float) -> None:
        with suppress(Exception):
            crs = self.canvas.mapSettings().destinationCrs()
            crs_id = crs.authid() or "—"
            self.lbl_meta.setText(f"{crs_id}   1:{scale:,.0f}")

    def _on_crs_changed(self, *_args) -> None:
        self._on_scale(self.canvas.scale())

    def unload(self) -> None:
        for signal, slot in self._signal_connections:
            with suppress(Exception):
                signal.disconnect(slot)
        self._signal_connections.clear()
