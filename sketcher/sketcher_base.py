# -*- coding: utf-8 -*-
"""
planX CAD — Sketcher Base Class
Base class for all QgsMapTool-based drawing tools.
Provides rubber-band management, native snapping, precision input, and cancellation.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap
from qgis.core import QgsWkbTypes, QgsPointXY, QgsGeometry, QgsSnappingUtils
from qgis.gui import QgsMapTool, QgsRubberBand

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_PRIMARY, COLOR_ACCENT
)
from ..core.sketcher_layer_utils import add_geometry_to_current_layer
from ..core.precision_input import (
    PrecisionInputError,
    looks_like_precision_input,
    parse_precision_input,
    resolve_precision_point,
)


class sketcher_base(QgsMapTool):
    """Base class inherited by every sketching tool.

    Subclasses should override:
        - tool_name(): str — displayed tool name
        - geom_type(): QgsWkbTypes — output geometry type
        - on_click(point, button): click handler
        - on_move(point): optional pointer-move handler
        - build_geometry(): QgsGeometry — completed geometry
    """

    sketcher_finished = pyqtSignal()
    sketcher_message = pyqtSignal(str)
    precision_key_started = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.vertices = []
        self.rb = None
        self.preview_rb = None
        self._is_active = False
        self._last_cursor_point = None

    # ── Override edilecek metodlar ────────────────────────────────────────

    def tool_name(self):
        """Return the displayed tool name."""
        return "Sketcher"

    def geom_type(self):
        """Return the output QgsWkbTypes geometry type."""
        return QgsWkbTypes.LineGeometry

    def on_click(self, point, button):
        """Handle a canvas click; subclasses override this method."""
        pass

    def on_move(self, point):
        """Handle pointer movement; subclasses may override this method."""
        pass

    def build_geometry(self):
        """Build the completed geometry; subclasses override this method."""
        return None

    # ── Lifecycle ───────────────────────────────────────────────────

    def activate(self):
        """Activate the tool and initialize its feedback items."""
        super().activate()
        self._is_active = True
        self.vertices = []
        self._last_cursor_point = None
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(
            f"✏️ {self.tool_name()} — Click or enter a precise point: "
            "x,y | @dx,dy | @distance<angle"
        )

    def deactivate(self):
        """Deactivate the tool and remove its feedback items."""
        self._is_active = False
        self._cleanup()
        super().deactivate()

    def _cleanup(self):
        """Remove all sketch rubber bands and reset transient state."""
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []
        self._last_cursor_point = None

    # ── Event handlers ─────────────────────────────────────────────────

    def canvasPressEvent(self, event):
        """Handle a map-canvas press event."""
        point = self.toMapCoordinates(event.pos())

        # Apply native snapping.
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        self.on_click(point, event.button())

    def canvasMoveEvent(self, event):
        """Handle map-canvas pointer movement."""
        if not self._is_active:
            return

        point = self.toMapCoordinates(event.pos())

        # Apply native snapping.
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        self._last_cursor_point = QgsPointXY(point)
        self.on_move(point)

    def keyPressEvent(self, event):
        """Handle keyboard input while the tool owns the canvas."""
        text = event.text()
        if text and text[0] in "@+-.0123456789":
            self.precision_key_started.emit(text)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key.Key_Z:
            self._undo_last_vertex()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.handle_command_enter()
            event.accept()

    # ── Helpers ────────────────────────────────────────────────

    def _snap_point(self, pos):
        """Return the nearest point reported by native QGIS snapping."""
        snapper = self.canvas.snappingUtils()
        if snapper is None:
            return None
        match = snapper.snapToMap(pos)
        if match.isValid():
            return match.point()
        return None

    def add_vertex(self, point):
        """Add a new sketch vertex."""
        self.vertices.append(point)
        if self.rb:
            self.rb.addPoint(point)
        self.sketcher_message.emit(
            f"✏️ {self.tool_name()} — {len(self.vertices)} point(s) | "
            "Enter: Finish | Esc: Cancel | Backspace: Undo"
        )

    def handle_precision_input(self, text):
        """Consume numeric command-line input as the next sketch vertex."""
        if not self._is_active or not looks_like_precision_input(text):
            return False
        try:
            parsed = parse_precision_input(text)
            base_point = self.vertices[-1] if self.vertices else None
            point = resolve_precision_point(
                parsed,
                base_point,
                self._last_cursor_point,
                self.canvas.mapSettings().destinationCrs(),
            )
        except PrecisionInputError as error:
            self.sketcher_message.emit(
                f"⚠️ Precision input — {error}"
            )
            return True

        self.on_click(point, Qt.MouseButton.LeftButton)
        return True

    def handle_command_enter(self):
        """Finish a valid in-progress sketch without restarting the tool."""
        if not self._is_active or not self.vertices:
            return False

        geometry = self.build_geometry()
        if geometry is None or geometry.isEmpty():
            self.sketcher_message.emit(
                "More points are required. Continue drawing or press Esc to cancel."
            )
            return True

        self._finish()
        return True

    def _undo_last_vertex(self):
        """Remove the most recently added vertex."""
        if len(self.vertices) > 0:
            self.vertices.pop()
            self._rebuild_sketcher_rubberband()
            self.sketcher_message.emit(
                f"✏️ {self.tool_name()} — Last point removed. "
                f"{len(self.vertices)} point(s) remain"
            )

    def _rebuild_sketcher_rubberband(self):
        """Rebuild the sketch rubber band from the current vertices."""
        if self.rb:
            self.rb.reset(self.geom_type())
            for v in self.vertices:
                self.rb.addPoint(v)

    def _finish(self):
        """Finish the sketch and add its geometry to the target layer."""
        geom = self.build_geometry()
        if geom and not geom.isEmpty():
            success = add_geometry_to_current_layer(self.iface, geom)
            if success:
                self.sketcher_message.emit(
                    f"✅ {self.tool_name()} — Geometry added"
                )
                self.iface.mapCanvas().refresh()
            else:
                self.sketcher_message.emit(
                    "⚠️ No active editable target layer was found"
                )
        else:
            self.sketcher_message.emit(
                "⚠️ Could not create valid geometry"
            )

        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_finished.emit()

    def _cancel(self):
        """Cancel the current sketch."""
        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(f"❌ {self.tool_name()} — Cancelled")
        self.sketcher_finished.emit()

    def update_preview(self, current_point):
        """Update the live preview rubber band."""
        if self.preview_rb and len(self.vertices) > 0:
            self.preview_rb.reset(self.geom_type())
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(current_point)
