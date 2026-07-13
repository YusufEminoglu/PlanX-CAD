# -*- coding: utf-8 -*-
"""PlanX CAD live distance and area measurement tool."""

from qgis.PyQt.QtCore import Qt, QPointF, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsTextAnnotation,
)
from qgis.gui import QgsMapTool, QgsRubberBand

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT, COLOR_PRIMARY
)
from ..core.sketcher_utils import measure_distance, measure_area


class tool_measure(QgsMapTool):
    """Measure distance or area with live canvas feedback.

    Left click: add point | Right click: finish | Escape: cancel
    """

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)

    MODE_DISTANCE = 0
    MODE_AREA = 1

    def __init__(self, canvas, iface, mode=0):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.vertices = []
        self.rb = None
        self.preview_rb = None
        self.total_distance = 0.0
        self.mode = mode  # 0=distance, 1=area

    def tool_name(self):
        return "Measure Distance" if self.mode == self.MODE_DISTANCE else "Measure Area"

    def activate(self):
        super().activate()
        self.vertices = []
        self.total_distance = 0.0

        geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
        self.rb = create_sketcher_rubberband(self.canvas, geom_type, COLOR_ACCENT, 2)
        self.preview_rb = create_preview_rubberband(self.canvas, geom_type)

        if self.mode == self.MODE_DISTANCE:
            self.tool_message.emit("📏 Measure Distance — Click points | Right-click: Finish")
        else:
            self.tool_message.emit("📐 Measure Area — Click vertices | Right-click: Finish")

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []
        super().deactivate()

    def canvasPressEvent(self, event):
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

            if self.mode == self.MODE_DISTANCE:
                self._show_distance_info()
            else:
                self._show_area_info()

        elif event.button() == Qt.MouseButton.RightButton:
            self._finish_measurement()

    def canvasMoveEvent(self, event):
        """Update the live measurement preview."""
        if not self.vertices:
            return

        point = self.toMapCoordinates(event.pos())
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        # Preview rubberband
        if self.preview_rb:
            geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
            self.preview_rb.reset(geom_type)
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(point)

            if self.mode == self.MODE_AREA and len(self.vertices) >= 2:
                self.preview_rb.addPoint(self.vertices[0])  # Close preview ring.

        # Live distance feedback.
        if self.mode == self.MODE_DISTANCE and len(self.vertices) >= 1:
            live_dist = measure_distance(self.vertices[-1], point)
            total_live = self.total_distance + live_dist
            self.tool_message.emit(
                f"📏 Segment: {live_dist:.2f} m | "
                f"Total: {total_live:.2f} m | "
                f"{len(self.vertices)} point(s)"
            )
        elif self.mode == self.MODE_AREA and len(self.vertices) >= 2:
            temp_pts = self.vertices + [point, self.vertices[0]]
            geom = QgsGeometry.fromPolygonXY([temp_pts])
            area = measure_area(geom)
            self.tool_message.emit(
                f"📐 Area: {self._format_area(area)} | "
                f"{len(self.vertices)} vertices"
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_Backspace:
            self._undo_last()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish_measurement()

    def _show_distance_info(self):
        if len(self.vertices) >= 2:
            seg_dist = measure_distance(self.vertices[-2], self.vertices[-1])
            self.total_distance += seg_dist
            self.tool_message.emit(
                f"📏 Segment: {seg_dist:.2f} m | "
                f"Total: {self.total_distance:.2f} m | "
                f"{len(self.vertices)} point(s)"
            )
        else:
            self.tool_message.emit("📏 Click the second point")

    def _show_area_info(self):
        if len(self.vertices) >= 3:
            geom = QgsGeometry.fromPolygonXY(
                [self.vertices + [self.vertices[0]]]
            )
            area = measure_area(geom)
            self.tool_message.emit(
                f"📐 Area: {self._format_area(area)} | "
                f"{len(self.vertices)} vertices"
            )
        else:
            n = len(self.vertices)
            self.tool_message.emit(
                f"📐 {3 - n} more point(s) required | {n} vertices"
            )

    def _finish_measurement(self):
        if self.mode == self.MODE_DISTANCE:
            if len(self.vertices) >= 2:
                msg = f"📏 Total distance: {self.total_distance:.2f} m"
                self.tool_message.emit(msg)
                self.iface.messageBar().pushInfo("PlanX CAD Measurement", msg)
        else:
            if len(self.vertices) >= 3:
                geom = QgsGeometry.fromPolygonXY(
                    [self.vertices + [self.vertices[0]]]
                )
                area = measure_area(geom)

                # Calculate perimeter as well.
                perimeter = 0.0
                pts = self.vertices + [self.vertices[0]]
                for i in range(len(pts) - 1):
                    perimeter += measure_distance(pts[i], pts[i + 1])

                msg = (
                    f"📐 Area: {self._format_area(area)} | "
                    f"Perimeter: {perimeter:.2f} m"
                )
                self.tool_message.emit(msg)
                self.iface.messageBar().pushInfo("PlanX CAD Measurement", msg)

        # Clear the completed measurement.
        self.vertices = []
        self.total_distance = 0.0
        if self.rb:
            geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
            self.rb.reset(geom_type)
        if self.preview_rb:
            geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
            self.preview_rb.reset(geom_type)

    def _cancel(self):
        self.vertices = []
        self.total_distance = 0.0
        geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
        if self.rb:
            self.rb.reset(geom_type)
        if self.preview_rb:
            self.preview_rb.reset(geom_type)
        self.tool_message.emit(f"{'📏' if self.mode == 0 else '📐'} Measurement cancelled")

    def _undo_last(self):
        if self.vertices:
            removed = self.vertices.pop()
            if len(self.vertices) >= 2:
                self.total_distance -= measure_distance(
                    self.vertices[-1], removed
                )
            else:
                self.total_distance = 0.0

            geom_type = QgsWkbTypes.GeometryType.LineGeometry if self.mode == 0 else QgsWkbTypes.GeometryType.PolygonGeometry
            if self.rb:
                self.rb.reset(geom_type)
                for v in self.vertices:
                    self.rb.addPoint(v)

            self.tool_message.emit(
                f"Last point removed. {len(self.vertices)} point(s) remain"
            )

    def _format_area(self, area):
        """Format an area for display."""
        if area >= 10000:
            return f"{area / 10000:.4f} ha ({area:.2f} m²)"
        return f"{area:.2f} m²"
