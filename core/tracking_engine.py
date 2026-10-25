# -*- coding: utf-8 -*-
"""planX CAD — Ortho, Polar, and Object-Snap Tracking Engine.

Provides constrained drafting angles, alignment tracking rays, and dashed guide lines:
  - Ortho mode: locks cursor to 0°, 90°, 180°, 270° relative to anchor point.
  - Polar tracking: locks cursor to configured angular increments (15°, 30°, 45°, 90°).
  - Object-Snap tracking: tracks horizontal/vertical alignment rays from acquired OSNAP points.

Dual-runtime compatible (QGIS 3 LTR / PyQt5 and QGIS 4 / PyQt6).
Zero external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

from qgis.core import QgsCoordinateReferenceSystem, QgsPointXY

from .crs_utils import local_metric_crs, transform_point


class TrackingMode(str, Enum):
    OFF = "off"
    ORTHO = "ortho"
    POLAR = "polar"


@dataclass(frozen=True)
class TrackingResult:
    point: QgsPointXY
    guide_line: tuple[QgsPointXY, QgsPointXY] | None
    mode: TrackingMode | str
    angle_deg: float
    distance_m: float
    readout: str


class TrackingEngine:
    """Computes constrained candidate drafting points and guide geometry."""

    DEFAULT_POLAR_INCREMENTS = (15.0, 30.0, 45.0, 90.0)

    def __init__(self):
        self.mode: TrackingMode = TrackingMode.OFF
        self.polar_increment: float = 45.0
        self.polar_tolerance_deg: float = 4.0
        self.acquired_points: list[QgsPointXY] = []
        self._max_acquired: int = 5

    def set_mode(self, mode: TrackingMode | str) -> None:
        if isinstance(mode, str):
            mode = TrackingMode(mode.lower())
        self.mode = mode

    def toggle_ortho(self) -> TrackingMode:
        """Toggle Ortho mode on/off (disabling Polar when Ortho turns on)."""
        if self.mode == TrackingMode.ORTHO:
            self.mode = TrackingMode.OFF
        else:
            self.mode = TrackingMode.ORTHO
        return self.mode

    def toggle_polar(self) -> TrackingMode:
        """Toggle Polar mode on/off (disabling Ortho when Polar turns on)."""
        if self.mode == TrackingMode.POLAR:
            self.mode = TrackingMode.OFF
        else:
            self.mode = TrackingMode.POLAR
        return self.mode

    def set_polar_increment(self, increment: float) -> None:
        if increment > 0:
            self.polar_increment = float(increment)

    def acquire_point(self, pt: QgsPointXY) -> None:
        """Record an OSNAP point for object-alignment tracking."""
        pt_xy = QgsPointXY(pt)
        # Avoid duplicate acquisitions
        for p in self.acquired_points:
            if math.hypot(p.x() - pt_xy.x(), p.y() - pt_xy.y()) < 1e-6:
                return
        self.acquired_points.append(pt_xy)
        if len(self.acquired_points) > self._max_acquired:
            self.acquired_points.pop(0)

    def clear_acquired(self) -> None:
        self.acquired_points.clear()

    def process(
        self,
        cursor_point: QgsPointXY,
        anchor_point: QgsPointXY | None,
        canvas_crs: QgsCoordinateReferenceSystem,
        map_units_per_pixel: float = 1.0,
    ) -> TrackingResult:
        """Resolve cursor point against active tracking mode and acquired alignment rays."""
        # 1. Object-snap tracking check (S3 precedence: highest priority if near alignment ray)
        if self.acquired_points and anchor_point is not None:
            obj_res = self._check_object_tracking(
                cursor_point, anchor_point, canvas_crs, map_units_per_pixel
            )
            if obj_res is not None:
                return obj_res

        # If tracking is OFF or no anchor point exists, return unconstrained
        if self.mode == TrackingMode.OFF or anchor_point is None:
            return self._unconstrained_result(cursor_point, anchor_point, canvas_crs)

        metric_crs = local_metric_crs(anchor_point, canvas_crs)
        metric_anchor = transform_point(anchor_point, canvas_crs, metric_crs)
        metric_cursor = transform_point(cursor_point, canvas_crs, metric_crs)

        dx = metric_cursor.x() - metric_anchor.x()
        dy = metric_cursor.y() - metric_anchor.y()
        distance = math.hypot(dx, dy)

        if distance < 1e-6:
            return self._unconstrained_result(cursor_point, anchor_point, canvas_crs)

        raw_angle = math.degrees(math.atan2(dy, dx)) % 360.0

        # 2. Ortho tracking: 0, 90, 180, 270
        if self.mode == TrackingMode.ORTHO:
            ortho_angles = (0.0, 90.0, 180.0, 270.0)
            target_angle = min(ortho_angles, key=lambda a: min(abs(raw_angle - a), abs(raw_angle - (a + 360))))
            rad = math.radians(target_angle)
            metric_target = QgsPointXY(
                metric_anchor.x() + distance * math.cos(rad),
                metric_anchor.y() + distance * math.sin(rad),
            )
            target_point = transform_point(metric_target, metric_crs, canvas_crs)
            readout = f"ortho: {distance:.2f} m < {target_angle:.1f}°"
            return TrackingResult(
                point=target_point,
                guide_line=(anchor_point, target_point),
                mode=TrackingMode.ORTHO,
                angle_deg=target_angle,
                distance_m=distance,
                readout=readout,
            )

        # 3. Polar tracking: multiples of polar_increment within tolerance window
        if self.mode == TrackingMode.POLAR:
            inc = self.polar_increment
            k = round(raw_angle / inc)
            cand_angle = (k * inc) % 360.0
            diff = min(abs(raw_angle - cand_angle), abs(raw_angle - (cand_angle + 360)), abs(raw_angle - (cand_angle - 360)))

            if diff <= self.polar_tolerance_deg:
                rad = math.radians(cand_angle)
                metric_target = QgsPointXY(
                    metric_anchor.x() + distance * math.cos(rad),
                    metric_anchor.y() + distance * math.sin(rad),
                )
                target_point = transform_point(metric_target, metric_crs, canvas_crs)
                readout = f"polar: {distance:.2f} m < {cand_angle:.1f}°"
                return TrackingResult(
                    point=target_point,
                    guide_line=(anchor_point, target_point),
                    mode=TrackingMode.POLAR,
                    angle_deg=cand_angle,
                    distance_m=distance,
                    readout=readout,
                )

        return self._unconstrained_result(cursor_point, anchor_point, canvas_crs)

    def _check_object_tracking(
        self,
        cursor: QgsPointXY,
        anchor: QgsPointXY,
        canvas_crs: QgsCoordinateReferenceSystem,
        mupp: float,
    ) -> TrackingResult | None:
        """Check if cursor aligns with H/V ray from any acquired OSNAP point."""
        tol = mupp * 12.0

        for acq in reversed(self.acquired_points):
            # Horizontal alignment ray (y = acq.y)
            if abs(cursor.y() - acq.y()) <= tol:
                cand = QgsPointXY(cursor.x(), acq.y())
                metric_crs = local_metric_crs(anchor, canvas_crs)
                ma = transform_point(anchor, canvas_crs, metric_crs)
                mc = transform_point(cand, canvas_crs, metric_crs)
                dx = mc.x() - ma.x()
                dy = mc.y() - ma.y()
                dist = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx)) % 360.0
                return TrackingResult(
                    point=cand,
                    guide_line=(acq, cand),
                    mode="object_tracking",
                    angle_deg=ang,
                    distance_m=dist,
                    readout=f"tracking: Y={acq.y():.2f}",
                )

            # Vertical alignment ray (x = acq.x)
            if abs(cursor.x() - acq.x()) <= tol:
                cand = QgsPointXY(acq.x(), cursor.y())
                metric_crs = local_metric_crs(anchor, canvas_crs)
                ma = transform_point(anchor, canvas_crs, metric_crs)
                mc = transform_point(cand, canvas_crs, metric_crs)
                dx = mc.x() - ma.x()
                dy = mc.y() - ma.y()
                dist = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx)) % 360.0
                return TrackingResult(
                    point=cand,
                    guide_line=(acq, cand),
                    mode="object_tracking",
                    angle_deg=ang,
                    distance_m=dist,
                    readout=f"tracking: X={acq.x():.2f}",
                )

        return None

    def _unconstrained_result(
        self,
        cursor: QgsPointXY,
        anchor: QgsPointXY | None,
        canvas_crs: QgsCoordinateReferenceSystem,
    ) -> TrackingResult:
        if anchor is None:
            return TrackingResult(
                point=cursor,
                guide_line=None,
                mode=TrackingMode.OFF,
                angle_deg=0.0,
                distance_m=0.0,
                readout="",
            )
        metric_crs = local_metric_crs(anchor, canvas_crs)
        ma = transform_point(anchor, canvas_crs, metric_crs)
        mc = transform_point(cursor, canvas_crs, metric_crs)
        dx = mc.x() - ma.x()
        dy = mc.y() - ma.y()
        dist = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dy, dx)) % 360.0
        return TrackingResult(
            point=cursor,
            guide_line=None,
            mode=TrackingMode.OFF,
            angle_deg=ang,
            distance_m=dist,
            readout=f"{dist:.2f} m < {ang:.1f}°",
        )
