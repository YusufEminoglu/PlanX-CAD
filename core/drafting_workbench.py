# -*- coding: utf-8 -*-
"""planX CAD — Unified Drafting Precision Controller (DraftingWorkbench).

Coordinates Object Snap (OSNAP), Ortho/Polar Tracking, dashed alignment guide
rubber bands, and the Dynamic Input Heads-Up Display (HUD).

Composed by both tool_base and sketcher_base to eliminate code duplication (S1).
Dual-runtime compatible (QGIS 3 LTR / PyQt5 and QGIS 4 / PyQt6).
Zero external dependencies.
"""
from __future__ import annotations

import contextlib
import math

from qgis.PyQt.QtCore import Qt, QObject, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapCanvas, QgsRubberBand

from .osnap_engine import OsnapEngine, SnapKind, SnapResult
from .osnap_markers import OsnapMarkerManager
from .tracking_engine import TrackingEngine, TrackingMode, TrackingResult
from .crs_utils import local_metric_crs, transform_point
from .drafting_state import DRAFTING_STATE
from ..dialogs.dynamic_input_hud import DynamicInputHud


class DraftingWorkbench(QObject):
    """Unified coordinator for OSNAP, Tracking, and Dynamic Input."""

    tool_status_message = pyqtSignal(str)

    def __init__(self, canvas: QgsMapCanvas, iface=None):
        super().__init__()
        self.canvas = canvas
        self.iface = iface

        self.osnap_engine = OsnapEngine(canvas)
        self.osnap_markers = OsnapMarkerManager(canvas)
        self.tracking_engine = TrackingEngine()
        self.dynamic_hud = DynamicInputHud(canvas)

        self._tracking_band: QgsRubberBand | None = None
        self._setup_tracking_band()
        self._sync_shared_state()

    def _setup_tracking_band(self):
        if self._tracking_band is None and self.canvas is not None:
            self._tracking_band = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
            self._tracking_band.setColor(QColor(13, 148, 136, 180))  # Teal
            self._tracking_band.setWidth(1)
            self._tracking_band.setLineStyle(Qt.PenStyle.DashLine)
            self._tracking_band.hide()

    # ── Configuration & Toggles ───────────────────────────────────────────────

    # The toggles live in the session-wide DRAFTING_STATE so every tool, the
    # F-key shortcuts and the dock chips agree. This workbench mirrors that
    # state into its own engines before each use.

    @property
    def _osnap_enabled(self) -> bool:
        return DRAFTING_STATE.osnap

    def _sync_shared_state(self) -> None:
        mode = TrackingMode(DRAFTING_STATE.tracking)
        if self.tracking_engine.mode != mode:
            self.tracking_engine.set_mode(mode)
            self._reset_guides()
        if self.dynamic_hud.is_enabled() != DRAFTING_STATE.dynamic_input:
            self.dynamic_hud.set_enabled(DRAFTING_STATE.dynamic_input)
        if not DRAFTING_STATE.osnap:
            self.osnap_markers.hide()

    def is_osnap_enabled(self) -> bool:
        return DRAFTING_STATE.osnap

    def set_osnap_enabled(self, enabled: bool) -> None:
        DRAFTING_STATE.set_osnap(enabled)
        self._sync_shared_state()

    def toggle_ortho(self) -> TrackingMode:
        DRAFTING_STATE.toggle_ortho()
        self._sync_shared_state()
        return self.tracking_engine.mode

    def toggle_polar(self) -> TrackingMode:
        DRAFTING_STATE.toggle_polar()
        self._sync_shared_state()
        return self.tracking_engine.mode

    def set_dynamic_input_enabled(self, enabled: bool) -> None:
        DRAFTING_STATE.set_dynamic_input(enabled)
        self._sync_shared_state()

    def is_dynamic_input_enabled(self) -> bool:
        return DRAFTING_STATE.dynamic_input

    # ── Main Processing Flow ──────────────────────────────────────────────────

    def snap_point(self, event_pos, anchor_point: QgsPointXY | None = None) -> QgsPointXY | None:
        """Query direct OSNAP point at event_pos."""
        self._sync_shared_state()
        if not self._osnap_enabled:
            snapper = self.canvas.snappingUtils()
            if snapper:
                m = snapper.snapToMap(event_pos)
                if m.isValid():
                    return m.point()
            return None

        result = self.osnap_engine.snap(event_pos, anchor_point=anchor_point)
        if result is not None:
            self.osnap_markers.update_result(result)
            return result.point

        self.osnap_markers.update_result(None)
        return None

    def process_move(
        self,
        event_pos,
        anchor_point: QgsPointXY | None = None,
    ) -> tuple[QgsPointXY, SnapResult | None, TrackingResult | None]:
        """Compute snapped/tracked coordinate, update markers, guides, and HUD."""
        self._setup_tracking_band()
        self._sync_shared_state()
        raw_point = self.canvas.getCoordinateTransform().toMapCoordinates(event_pos)
        snap_res: SnapResult | None = None
        working_point = raw_point

        # 1. Evaluate OSNAP (if enabled)
        if self._osnap_enabled:
            snap_res = self.osnap_engine.snap(event_pos, anchor_point=anchor_point)
            if snap_res is not None:
                working_point = snap_res.point
                self.osnap_markers.update_result(snap_res)
                # If hovering directly over a point, acquire it for object tracking
                if snap_res.kind in (SnapKind.ENDPOINT, SnapKind.MIDPOINT, SnapKind.CENTRE, SnapKind.INTERSECTION):
                    self.tracking_engine.acquire_point(snap_res.point)
            else:
                self.osnap_markers.update_result(None)
        else:
            self.osnap_markers.update_result(None)

        # 2. Evaluate Tracking Engine (Ortho, Polar, Alignment tracking)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        mupp = self.canvas.mapUnitsPerPixel()
        track_res: TrackingResult = self.tracking_engine.process(
            cursor_point=working_point,
            anchor_point=anchor_point,
            canvas_crs=canvas_crs,
            map_units_per_pixel=mupp,
        )

        final_point = track_res.point if snap_res is None else snap_res.point

        # 3. Update dashed tracking guide rubber band
        if track_res.guide_line is not None and self._tracking_band is not None:
            p1, p2 = track_res.guide_line
            self._tracking_band.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self._tracking_band.addPoint(p1)
            self._tracking_band.addPoint(p2)
            self._tracking_band.show()
        else:
            self._reset_guides()

        # 4. Update Dynamic Input HUD metrics
        if anchor_point is not None:
            metric_crs = local_metric_crs(anchor_point, canvas_crs)
            ma = transform_point(anchor_point, canvas_crs, metric_crs)
            mf = transform_point(final_point, canvas_crs, metric_crs)
            dx = mf.x() - ma.x()
            dy = mf.y() - ma.y()
            dist = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(dy, dx)) % 360.0
            self.dynamic_hud.update_metrics(
                cursor_point=final_point,
                distance_m=dist,
                angle_deg=ang,
                dx_m=dx,
                dy_m=dy,
                extra_label=snap_res.description if snap_res else "",
            )
        else:
            self.dynamic_hud.update_metrics(
                cursor_point=final_point,
                extra_label=snap_res.description if snap_res else "",
            )

        return final_point, snap_res, track_res

    def _reset_guides(self):
        if self._tracking_band is not None:
            self._tracking_band.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self._tracking_band.hide()

    def hide(self):
        self.osnap_markers.hide()
        self._reset_guides()
        self.dynamic_hud.hide_hud()

    def cleanup(self):
        """Release all canvas overlays."""
        self.hide()
        self.osnap_markers.cleanup()
        self.dynamic_hud.cleanup()
        if self._tracking_band and getattr(self._tracking_band, "scene", lambda: None)() is not None:
            with contextlib.suppress(Exception):
                self._tracking_band.scene().removeItem(self._tracking_band)
            self._tracking_band = None
        self.tracking_engine.clear_acquired()
