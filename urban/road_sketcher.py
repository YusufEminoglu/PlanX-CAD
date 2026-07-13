# -*- coding: utf-8 -*-
"""Interactive road-centerline sketcher and platform generator."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import QgsWkbTypes, QgsGeometry
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT
)
from .road_dialog import RoadDialog
from .road_generator import RoadGenerator


class RoadSketcher(QgsMapTool):
    """Sketch a road centerline and generate its platform components.

    1. Collect platform parameters.
    2. Sketch a centerline polyline on the map.
    3. Generate platform components when the sketch is finished.
    """

    sketcher_finished = pyqtSignal()
    sketcher_message = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.vertices = []
        self.rb = None
        self.preview_rb = None
        self.params = None
        self.generator = RoadGenerator(iface)
        self._activation_cancelled = False

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        self.vertices = []

        # Collect road-platform parameters before opening the sketch.
        dlg = RoadDialog(self.iface.mainWindow())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.params = dlg.get_params()
            self.rb = create_sketcher_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
            )
            self.preview_rb = create_preview_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry
            )
            self.sketcher_message.emit(
                f"🛣️ Draw Road ({self.params['road_type']}, "
                f"total: {self.params['total_width']:.1f} m) — "
                "Sketch the centerline | Right-click: Finish"
            )
        else:
            self._activation_cancelled = True
            self.sketcher_message.emit("🛣️ Draw Road — Cancelled")
            self.sketcher_finished.emit()

    def deactivate(self):
        self._cleanup()
        super().deactivate()

    def _cleanup(self):
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []

    def canvasPressEvent(self, event):
        if self.params is None:
            return

        point = self.toMapCoordinates(event.pos())

        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        if event.button() == Qt.MouseButton.LeftButton:
            self.vertices.append(point)
            if self.rb:
                self.rb.addPoint(point)
            self.sketcher_message.emit(
                f"🛣️ Draw Road — {len(self.vertices)} points | "
                "Right-click: Finish | Esc: Cancel"
            )

        elif event.button() == Qt.MouseButton.RightButton:
            if len(self.vertices) >= 2:
                self._finish()

    def canvasMoveEvent(self, event):
        if len(self.vertices) > 0 and self.preview_rb:
            point = self.toMapCoordinates(event.pos())
            snapper = self.canvas.snappingUtils()
            if snapper:
                match = snapper.snapToMap(event.pos())
                if match.isValid():
                    point = match.point()

            self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cleanup()
            self.rb = create_sketcher_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
            )
            self.preview_rb = create_preview_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry
            )
            self.sketcher_message.emit("🛣️ Draw Road — Cancelled")
        elif event.key() == Qt.Key.Key_Backspace:
            if len(self.vertices) > 0:
                self.vertices.pop()
                if self.rb:
                    self.rb.reset(QgsWkbTypes.LineGeometry)
                    for v in self.vertices:
                        self.rb.addPoint(v)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.vertices) >= 2:
                self._finish()

    def _finish(self):
        """Build the centerline and generate the road platform."""
        if len(self.vertices) < 2 or self.params is None:
            return

        center_geom = QgsGeometry.fromPolylineXY(self.vertices)
        count = self.generator.generate(center_geom, self.params)

        if count > 0:
            self.sketcher_message.emit(
                f"✅ Draw Road — {count} components generated "
                "(added to planx_road_platform)"
            )
            self.iface.messageBar().pushSuccess(
                "planX CAD",
                f"Road platform created: {count} components"
            )
        else:
            self.sketcher_message.emit(
                "⚠️ Draw Road — Platform could not be generated"
            )

        self._cleanup()
        self.rb = create_sketcher_rubberband(
            self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
        )
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.LineGeometry
        )
        self.sketcher_finished.emit()
