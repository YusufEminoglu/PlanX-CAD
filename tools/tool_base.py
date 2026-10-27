# -*- coding: utf-8 -*-
"""
planX CAD — Tool Base Class
Base class for editing and transform tools.
Provides feature picking, previews, precision input, and undo-safe edits.
"""

from contextlib import suppress

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QCursor, QPixmap, QPainter, QPen, QBrush
from qgis.core import (
    QgsWkbTypes, QgsPointXY, QgsGeometry, QgsFeature,
    QgsProject, QgsVectorLayer, QgsRectangle, QgsCoordinateTransform,
    QgsFeatureRequest
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT
)
from ..core.precision_input import (
    PrecisionInputError,
    looks_like_precision_input,
    parse_precision_input,
    resolve_precision_point,
)
from ..core.drafting_workbench import DraftingWorkbench


class tool_base(QgsMapTool):
    """Base class for editing and transform tools.

    Subclasses should override:
        - tool_name(): str
        - on_entity_selected(layer, feature, point): selection handler
        - on_click(point, button): additional click handler
        - on_move(point): optional pointer-move handler
    """

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)
    precision_key_started = pyqtSignal(str)

    # Feature-picking tolerance in pixels.
    PICK_TOLERANCE = 10

    # Settings shown on the dock's active-command card (core.tool_options).
    # While the card shows them, ``use_inline_options()`` is True and the tool
    # skips its modal dialog. Without the dock the dialog still opens.
    INLINE_OPTIONS = ()
    inline_options_enabled = False

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.selected_layer = None
        self.selected_feature = None
        self.selected_point = None
        self.preview_rb = None
        self._step = 0  # Current interaction step
        self.require_editable = True  # Search editable layers by default.
        self._last_cursor_canvas_point = None

        # Visual feedback: snap marker and feature highlight.
        self.drafting = DraftingWorkbench(self.canvas, self.iface)
        self.drafting.tool_status_message.connect(self.tool_message.emit)
        self.snap_marker = self.drafting.osnap_markers._marker

        self.highlight_rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self.highlight_rb.setWidth(4)
        self.highlight_rb.setColor(QColor(13, 148, 136, 160))

        self._set_cursor()

    def _set_cursor(self):
        """Create the EasyFillet-style green aperture cursor."""
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor('#3ad6a1'))
        brush = QColor('#f0c2d3')
        brush.setAlphaF(0.3)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawEllipse(6, 6, size-12, size-12)
        painter.end()
        self.setCursor(QCursor(pixmap))

    # ── Override edilecek ─────────────────────────────────────────────────

    def tool_name(self):
        return "Tool"

    def on_entity_selected(self, layer, feature, point):
        """Handle a selected feature."""
        pass

    def on_click(self, point, button):
        """Handle an additional canvas click."""
        pass

    def on_move(self, point):
        """Handle pointer movement."""
        pass

    def use_inline_options(self):
        """True when the dock card supplies this tool's settings."""
        return bool(self.INLINE_OPTIONS) and bool(self.inline_options_enabled)

    # ── Lifecycle ───────────────────────────────────────────────────

    def activate(self):
        super().activate()
        self._step = 0
        self._last_cursor_canvas_point = None
        self.preview_rb = create_preview_rubberband(self.canvas)
        self.drafting._setup_tracking_band()
        self.snap_marker = self.drafting.osnap_markers._marker

        if getattr(self, 'highlight_rb', None) is None:
            self.highlight_rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
            self.highlight_rb.setWidth(4)
            self.highlight_rb.setColor(QColor(13, 148, 136, 160))
            
        self._set_cursor()

        self.tool_message.emit(
            f"🔧 {self.tool_name()} — Select a feature"
        )

    def deactivate(self):
        self._cleanup()
        self.drafting.cleanup()
        if self.highlight_rb:
            self.canvas.scene().removeItem(self.highlight_rb)
            self.highlight_rb = None
        super().deactivate()

    def _cleanup(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        if self.highlight_rb:
            self.highlight_rb.reset()
        self.drafting.hide()
        self.preview_rb = None
        self.selected_layer = None
        self.selected_feature = None
        self.selected_point = None
        self._step = 0
        self._last_cursor_canvas_point = None

    def to_layer_coordinates(self, point, layer=None):
        """Transform a QgsPointXY from Canvas CRS to Layer CRS."""
        if layer is None:
            layer = self.selected_layer
        if layer is None:
            return point
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()
        if canvas_crs.isValid() and layer_crs.isValid() and canvas_crs != layer_crs:
            transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
            return transform.transform(point)
        return point

    def to_canvas_coordinates(self, point, layer=None):
        """Transform a QgsPointXY from Layer CRS to Canvas CRS."""
        if layer is None:
            layer = self.selected_layer
        if layer is None:
            return point
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()
        if canvas_crs.isValid() and layer_crs.isValid() and canvas_crs != layer_crs:
            transform = QgsCoordinateTransform(layer_crs, canvas_crs, QgsProject.instance())
            return transform.transform(point)
        return point

    def geometry_to_layer_crs(self, geometry, source_layer, target_layer):
        """Return a detached geometry transformed between two layer CRSs.

        Two-stage tools may pick their operands from different layers. QGIS
        stores each feature in its layer CRS, so direct geometry operations on
        those operands are invalid until both share a coordinate space.
        """
        if geometry is None or source_layer is None or target_layer is None:
            return None
        result = QgsGeometry(geometry)
        source_crs = source_layer.crs()
        target_crs = target_layer.crs()
        if source_crs != target_crs:
            if not source_crs.isValid() or not target_crs.isValid():
                return None
            try:
                transform = QgsCoordinateTransform(
                    source_crs, target_crs, QgsProject.instance()
                )
                result.transform(transform)
            except Exception:
                return None
        return result

    # ── Event handlers ─────────────────────────────────────────────────

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())

        # Apply native snapping.
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        if self._step == 0 and event.button() == Qt.MouseButton.LeftButton:
            # Pick a feature.
            result = self._pick_feature(event.pos())
            if result:
                layer, feature = result
                self.selected_layer = layer
                self.selected_feature = feature
                self.selected_point = self.to_layer_coordinates(point, layer)
                self._step = 1

                # Highlight the selected feature.
                geom = feature.geometry()
                self.highlight_rb.reset(geom.type())
                self.highlight_rb.setToGeometry(geom, layer)

                self.on_entity_selected(layer, feature, self.selected_point)
            else:
                self.tool_message.emit(
                    f"⚠️ {self.tool_name()} — No feature found; try again"
                )
        else:
            layer_point = self.to_layer_coordinates(point)
            self.on_click(layer_point, event.button())

    def _get_current_anchor(self) -> QgsPointXY | None:
        """Return the active anchor point (in canvas coordinates) for the current step."""
        pt = None
        if getattr(self, "base_point", None) is not None:
            pt = self.base_point
        elif getattr(self, "center", None) is not None:
            pt = self.center
        elif getattr(self, "line_start", None) is not None:
            pt = self.line_start
        elif getattr(self, "src1", None) is not None:
            pt = self.src1
        elif getattr(self, "selected_point", None) is not None and self._step > 0:
            pt = self.selected_point

        if pt is not None:
            return self.to_canvas_coordinates(pt, self.selected_layer)
        return None

    def canvasMoveEvent(self, event):
        anchor = self._get_current_anchor()
        point, snap_res, track_res = self.drafting.process_move(event.pos(), anchor_point=anchor)
        self._last_cursor_canvas_point = QgsPointXY(point)
        layer_point = self.to_layer_coordinates(point)
        self.on_move(layer_point)

    def resolve_precision_target(self, text, base_point, layer=None):
        """Resolve precision input from a layer base point back to that layer."""
        if not looks_like_precision_input(text):
            return None
        layer = layer or self.selected_layer
        if layer is None:
            raise PrecisionInputError("Select a source feature first")
        parsed = parse_precision_input(text)
        base_canvas = self.to_canvas_coordinates(base_point, layer)
        target_canvas = resolve_precision_point(
            parsed,
            base_canvas,
            self._last_cursor_canvas_point,
            self.canvas.mapSettings().destinationCrs(),
        )
        return self.to_layer_coordinates(target_canvas, layer)

    def keyPressEvent(self, event):
        text = event.text()
        if text and text[0] in "@+-.0123456789":
            self.precision_key_started.emit(text)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._reset()
        elif event.key() == Qt.Key.Key_F3:
            enabled = not self.drafting.is_osnap_enabled()
            self.drafting.set_osnap_enabled(enabled)
            self.tool_message.emit(f"OSNAP: {'ON' if enabled else 'OFF'}")
            event.accept()
        elif event.key() == Qt.Key.Key_F8:
            mode = self.drafting.toggle_ortho()
            self.tool_message.emit(f"Tracking: {mode.value.upper()}")
            event.accept()
        elif event.key() == Qt.Key.Key_F10:
            mode = self.drafting.toggle_polar()
            self.tool_message.emit(f"Tracking: {mode.value.upper()}")
            event.accept()
        elif event.key() == Qt.Key.Key_F12:
            enabled = not self.drafting.is_dynamic_input_enabled()
            self.drafting.set_dynamic_input_enabled(enabled)
            self.tool_message.emit(f"Dynamic Input: {'ON' if enabled else 'OFF'}")
            event.accept()

    # ── Helpers ─────────────────────────────────────────────────────────

    def _snap_point(self, pos):
        return self.drafting.snap_point(pos, anchor_point=self._get_current_anchor())

    def _pick_feature(self, pos, exclude=None):
        """Find the closest feature at the clicked point.

        ``exclude`` is a ``(layer, feature)`` pair used by two-step tools such
        as Fillet, Trim, and Extend to prevent selecting the first feature
        again during the second pick.
        """
        point = self.toMapCoordinates(pos)

        # Calculate the map-unit pick tolerance.
        map_tol = self.canvas.mapUnitsPerPixel() * self.PICK_TOLERANCE
        search_rect = QgsRectangle(
            point.x() - map_tol, point.y() - map_tol,
            point.x() + map_tol, point.y() + map_tol
        )

        # Search the active layer first.
        layer = self.iface.activeLayer()
        if layer and isinstance(layer, QgsVectorLayer):
            if not self.require_editable or layer.isEditable():
                result = self._search_layer(layer, search_rect, point, exclude)
                if result:
                    return result

        # Search the remaining vector layers.
        active_id = layer.id() if isinstance(layer, QgsVectorLayer) else None
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer):
                if active_id is not None and lyr.id() == active_id:
                    continue
                if self.require_editable and not lyr.isEditable():
                    continue
                result = self._search_layer(lyr, search_rect, point, exclude)
                if result:
                    return result

        return None

    def _search_layer(self, layer, search_rect, point, exclude=None):
        """Search one layer for the closest eligible feature."""
        query_rect = search_rect
        query_point = point

        # In QGIS 4 the canvas and layer CRS can differ. Transform the search
        # window into the layer CRS so picking and previews remain reliable.
        try:
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            layer_crs = layer.crs()
            if canvas_crs.isValid() and layer_crs.isValid() and canvas_crs != layer_crs:
                transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
                query_rect = transform.transformBoundingBox(search_rect)
                query_point = transform.transform(point)
        except Exception:
            query_rect = search_rect
            query_point = point

        request = QgsFeatureRequest().setFilterRect(query_rect)
        features = layer.getFeatures(request)
        best_dist = float('inf')
        best_feat = None

        exclude_id = None
        if exclude is not None and exclude[0] is not None and exclude[1] is not None:
            if exclude[0] is layer or exclude[0].id() == layer.id():
                exclude_id = exclude[1].id()

        click_geom = QgsGeometry.fromPointXY(query_point)
        for feat in features:
            if exclude_id is not None and feat.id() == exclude_id:
                continue
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            dist = geom.distance(click_geom)
            if dist < best_dist:
                best_dist = dist
                best_feat = feat

        # getFeatures(rect) only checks bounding-box overlap. A long or
        # diagonal feature can have a box that covers the click while its
        # geometry remains far away, so enforce the aperture on true distance.
        pick_tol = max(query_rect.width(), query_rect.height()) / 2.0
        if best_feat is not None and best_dist <= pick_tol:
            return (layer, best_feat)
        return None

    def _reset(self):
        """Reset the tool for another feature selection."""
        self._cleanup()
        self.preview_rb = create_preview_rubberband(self.canvas)
        self.tool_message.emit(f"🔧 {self.tool_name()} — Select a feature")

    def _apply_edit(self, layer, feature, new_geometry):
        """Update a feature geometry in one undoable edit command."""
        if (layer is None or feature is None or new_geometry is None or
                new_geometry.isEmpty() or
                new_geometry.type() != layer.geometryType()):
            self.tool_message.emit(
                f"⚠️ {self.tool_name()} — Geometry is incompatible with the layer"
            )
            return False

        if not layer.isEditable() and not layer.startEditing():
            self.tool_message.emit(
                f"⚠️ {self.tool_name()} — Layer could not enter edit mode"
            )
            return False

        layer.beginEditCommand(self.tool_name())
        if not layer.changeGeometry(feature.id(), QgsGeometry(new_geometry)):
            layer.destroyEditCommand()
            self.tool_message.emit(
                f"⚠️ {self.tool_name()} — Geometry could not be updated"
            )
            return False
        layer.endEditCommand()
        layer.triggerRepaint()
        self.tool_message.emit(f"✅ {self.tool_name()} — Edit applied")
        return True

    def _add_feature(self, layer, geometry, source_feature=None):
        """Add one new feature to a layer."""
        added = self._add_features(layer, [geometry], source_feature)
        return added[0] if added else None

    def _add_features(self, layer, geometries, source_feature=None):
        """Batch-add geometries as one undoable edit command.

        Array, Divide and Multi-Offset previously created one edit command per
        feature through repeated calls, which was slow and filled the undo
        stack. This path validates once and uses QgsVectorLayer.addFeatures.
        """
        if layer is None or not isinstance(layer, QgsVectorLayer):
            return []
        valid_geometries = [
            geometry for geometry in geometries
            if (geometry is not None and not geometry.isEmpty() and
                geometry.type() == layer.geometryType())
        ]
        if not valid_geometries:
            return []
        if not layer.isEditable() and not layer.startEditing():
            self.tool_message.emit(
                f"⚠️ {self.tool_name()} — Layer could not enter edit mode"
            )
            return []

        features = []
        for geometry in valid_geometries:
            feat = QgsFeature(layer.fields())
            feat.setGeometry(QgsGeometry(geometry))

            if source_feature:
                for i, _field in enumerate(layer.fields()):
                    with suppress(Exception):
                        feat.setAttribute(i, source_feature.attribute(i))
            features.append(feat)

        layer.beginEditCommand(self.tool_name())
        if not layer.addFeatures(features):
            layer.destroyEditCommand()
            self.tool_message.emit(
                f"⚠️ {self.tool_name()} — New features could not be added"
            )
            return []
        layer.endEditCommand()
        layer.triggerRepaint()
        return features
