# -*- coding: utf-8 -*-
"""PlanX CAD Stretch tool: move the vertices caught by a crossing window."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsPointXY,
    QgsProject, QgsRectangle, QgsVectorLayer, QgsWkbTypes,
)
from qgis.gui import QgsRubberBand

from .tool_base import tool_base
from ..core.precision_input import (
    PrecisionInputError,
    looks_like_precision_input,
    parse_precision_input,
    resolve_precision_point,
)
from ..core.sketcher_utils import stretch_geometry


class tool_stretch(tool_base):
    """Stretch every vertex inside a crossing window.

    1. Click the first window corner | 2. Click the opposite corner |
    3. Click the base point | 4. Click the target point
    """

    _STEP_CORNER_1 = 0
    _STEP_CORNER_2 = 1
    _STEP_BASE = 2
    _STEP_TARGET = 3

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.corner_1 = None
        self.window_rect = None
        self.base_point = None
        self.targets = []
        self.window_rb = None

    def tool_name(self):
        return "Stretch"

    def activate(self):
        super().activate()
        self._clear_stretch_state()
        self._ensure_window_rubberband()
        self.tool_message.emit(
            "⇔ Stretch — Click the first corner of the crossing window"
        )

    def deactivate(self):
        self._remove_window_rubberband()
        super().deactivate()

    def _ensure_window_rubberband(self):
        if self.window_rb is None:
            self.window_rb = QgsRubberBand(
                self.canvas, QgsWkbTypes.GeometryType.PolygonGeometry
            )
            self.window_rb.setColor(QColor(13, 148, 136, 60))
            self.window_rb.setStrokeColor(QColor(13, 148, 136, 220))
            self.window_rb.setWidth(2)
            self.window_rb.setLineStyle(Qt.PenStyle.DashLine)

    def _remove_window_rubberband(self):
        if self.window_rb is not None:
            self.canvas.scene().removeItem(self.window_rb)
            self.window_rb = None

    # ── Interaction ───────────────────────────────────────────────────────

    def canvasPressEvent(self, event):
        """Stretch drives its own flow: it never picks a single feature."""
        point = self.toMapCoordinates(event.pos())
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        if event.button() != Qt.MouseButton.LeftButton:
            self._reset_stretch()
            return

        if self._step == self._STEP_CORNER_1:
            self.corner_1 = QgsPointXY(point)
            self._step = self._STEP_CORNER_2
            self.tool_message.emit("⇔ Stretch — Click the opposite corner")
        elif self._step == self._STEP_CORNER_2:
            self._close_window(QgsPointXY(point))
        elif self._step == self._STEP_BASE:
            self.base_point = QgsPointXY(point)
            self._step = self._STEP_TARGET
            self.tool_message.emit("⇔ Stretch — Click the target point")
        elif self._step == self._STEP_TARGET:
            self._apply_stretch(QgsPointXY(point))

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped
            if self.snap_marker:
                self.snap_marker.setCenter(point)
                self.snap_marker.show()
        elif self.snap_marker:
            self.snap_marker.hide()
        self._last_cursor_canvas_point = QgsPointXY(point)

        if self._step == self._STEP_CORNER_2 and self.corner_1 is not None:
            self._draw_window(QgsRectangle(self.corner_1, QgsPointXY(point)))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._reset_stretch()
            return
        super().keyPressEvent(event)

    def handle_precision_input(self, text):
        if not looks_like_precision_input(text):
            return False
        if self._step != self._STEP_TARGET or self.base_point is None:
            self.tool_message.emit(
                "⚠️ Stretch — Define the window and base point first"
            )
            return True
        # Stretch works in canvas coordinates throughout, so it resolves
        # precision input against the canvas CRS rather than a layer CRS.
        try:
            target = resolve_precision_point(
                parse_precision_input(text),
                self.base_point,
                self._last_cursor_canvas_point,
                self.canvas.mapSettings().destinationCrs(),
            )
        except PrecisionInputError as error:
            self.tool_message.emit(f"⚠️ Stretch — {error}")
            return True
        self._apply_stretch(QgsPointXY(target))
        return True

    # ── Window handling ───────────────────────────────────────────────────

    def _draw_window(self, rect):
        self._ensure_window_rubberband()
        self.window_rb.setToGeometry(QgsGeometry.fromRect(rect), None)

    def _close_window(self, corner_2):
        rect = QgsRectangle(self.corner_1, corner_2)
        if rect.width() <= 0 and rect.height() <= 0:
            self.tool_message.emit("⚠️ Stretch — The window has no area")
            self._reset_stretch()
            return

        self.window_rect = rect
        self._draw_window(rect)
        self.targets = self._collect_targets(rect)
        if not self.targets:
            self.tool_message.emit(
                "⚠️ Stretch — No editable feature crosses the window"
            )
            self._reset_stretch()
            return

        self._step = self._STEP_BASE
        self.tool_message.emit(
            f"⇔ Stretch — {len(self.targets)} feature(s) caught; "
            "click the base point"
        )

    def _collect_targets(self, canvas_rect):
        """Return (layer, feature, layer_rect) for every crossed feature."""
        targets = []
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer) or not layer.isEditable():
                continue
            layer_rect = self._to_layer_rect(canvas_rect, canvas_crs, layer)
            if layer_rect is None:
                continue
            window = QgsGeometry.fromRect(layer_rect)
            request = QgsFeatureRequest().setFilterRect(layer_rect)
            for feature in layer.getFeatures(request):
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                if geometry.intersects(window):
                    targets.append((layer, feature, layer_rect))
        return targets

    def _to_layer_rect(self, rect, canvas_crs, layer):
        layer_crs = layer.crs()
        if not canvas_crs.isValid() or not layer_crs.isValid():
            return QgsRectangle(rect)
        if canvas_crs == layer_crs:
            return QgsRectangle(rect)
        try:
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            return transform.transformBoundingBox(rect)
        except Exception:
            return None

    # ── Apply ─────────────────────────────────────────────────────────────

    def _apply_stretch(self, target_point):
        if self.base_point is None or not self.targets:
            self._reset_stretch()
            return

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        edited_layers = []
        moved = 0
        failed = False

        by_layer = {}
        for layer, feature, layer_rect in self.targets:
            by_layer.setdefault(layer.id(), (layer, layer_rect, []))[2].append(feature)

        for layer, layer_rect, features in by_layer.values():
            base = self._to_layer_point(self.base_point, canvas_crs, layer)
            target = self._to_layer_point(target_point, canvas_crs, layer)
            if base is None or target is None:
                continue
            dx = target.x() - base.x()
            dy = target.y() - base.y()

            updates = []
            for feature in features:
                stretched = stretch_geometry(
                    feature.geometry(), layer_rect, dx, dy
                )
                if stretched is not None and not stretched.isEmpty():
                    updates.append((feature.id(), stretched))
            if not updates:
                continue

            layer.beginEditCommand(self.tool_name())
            edited_layers.append(layer)
            for feature_id, geometry in updates:
                if not layer.changeGeometry(feature_id, geometry):
                    failed = True
                    break
                moved += 1
            if failed:
                break
            layer.endEditCommand()
            layer.triggerRepaint()

        if failed:
            for layer in edited_layers:
                layer.destroyEditCommand()
            self.tool_message.emit(
                "⚠️ Stretch — Layer write failed; changes were rolled back"
            )
        elif moved:
            self.tool_message.emit(f"✅ Stretch — {moved} feature(s) stretched")
        else:
            self.tool_message.emit(
                "⚠️ Stretch — No vertex fell inside the window"
            )
        self._reset_stretch()

    def _to_layer_point(self, point, canvas_crs, layer):
        layer_crs = layer.crs()
        if not canvas_crs.isValid() or not layer_crs.isValid():
            return QgsPointXY(point)
        if canvas_crs == layer_crs:
            return QgsPointXY(point)
        try:
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            return QgsPointXY(transform.transform(point))
        except Exception:
            return None

    # ── State ─────────────────────────────────────────────────────────────

    def _clear_stretch_state(self):
        self.corner_1 = None
        self.window_rect = None
        self.base_point = None
        self.targets = []
        self._step = self._STEP_CORNER_1

    def _reset_stretch(self):
        self._clear_stretch_state()
        if self.window_rb is not None:
            self.window_rb.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
        self._reset()
        self._step = self._STEP_CORNER_1
        self.tool_message.emit(
            "⇔ Stretch — Click the first corner of the crossing window"
        )
