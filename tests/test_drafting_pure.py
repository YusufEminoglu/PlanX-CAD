# -*- coding: utf-8 -*-
"""Pure Python unit tests for CAD drafting math, OSNAP primitives and tracking.

Runs without native QGIS runtime dependencies.
"""

from __future__ import annotations

import math
import sys
import types
import pytest

from planX_CAD_arac_Seti.core.precision_input import (
    parse_precision_input,
    looks_like_precision_input,
    PrecisionInput,
    PrecisionInputError,
)
from planX_CAD_arac_Seti.core.osnap_engine import (
    SnapKind,
    _foot_of_perpendicular,
    _line_intersection,
    _circle_tangents_from_point,
)
from planX_CAD_arac_Seti.core.tracking_engine import (
    TrackingMode,
    TrackingEngine,
    TrackingResult,
)
from qgis.core import QgsPointXY


# ---------------------------------------------------------------------------
# Precision Input Parsing Tests
# ---------------------------------------------------------------------------

def test_precision_input_cartesian_absolute():
    p = parse_precision_input("100.5, 200.75")
    assert p.kind == "absolute"
    assert p.first == pytest.approx(100.5)
    assert p.second == pytest.approx(200.75)


def test_precision_input_cartesian_relative():
    p = parse_precision_input("@ -50.25, +12.0")
    assert p.kind == "relative_cartesian"
    assert p.first == pytest.approx(-50.25)
    assert p.second == pytest.approx(12.0)


def test_precision_input_polar_relative():
    p = parse_precision_input("@25.0 < 45.0")
    assert p.kind == "relative_polar"
    assert p.first == pytest.approx(25.0)
    assert p.second == pytest.approx(45.0)


def test_precision_input_scalar():
    p = parse_precision_input("150.0")
    assert p.kind == "direct_distance"
    assert p.first == pytest.approx(150.0)
    assert p.second is None


def test_precision_input_invalid():
    assert not looks_like_precision_input("abc")
    with pytest.raises(PrecisionInputError):
        parse_precision_input("invalid 12,34")


# ---------------------------------------------------------------------------
# OSNAP Geometric Primitives Tests
# ---------------------------------------------------------------------------

def test_snap_kind_enum():
    kinds = {k.name for k in SnapKind}
    expected = {
        "ENDPOINT", "MIDPOINT", "CENTRE", "QUADRANT", "VERTEX",
        "INTERSECTION", "APPARENT_INTERSECTION", "PERPENDICULAR",
        "TANGENT", "NEAREST", "EXTENSION"
    }
    assert expected.issubset(kinds)


def test_foot_of_perpendicular_horizontal():
    p1 = QgsPointXY(0.0, 0.0)
    p2 = QgsPointXY(10.0, 0.0)
    pt = QgsPointXY(5.0, 5.0)
    foot, t = _foot_of_perpendicular(pt, p1, p2)
    assert foot is not None
    assert foot.x() == pytest.approx(5.0)
    assert foot.y() == pytest.approx(0.0)
    assert t == pytest.approx(0.5)


def test_foot_of_perpendicular_diagonal():
    p1 = QgsPointXY(0.0, 0.0)
    p2 = QgsPointXY(10.0, 10.0)
    pt = QgsPointXY(0.0, 10.0)
    foot, t = _foot_of_perpendicular(pt, p1, p2)
    assert foot is not None
    assert foot.x() == pytest.approx(5.0)
    assert foot.y() == pytest.approx(5.0)
    assert t == pytest.approx(0.5)


def test_line_intersection_direct():
    a1 = QgsPointXY(0.0, 5.0)
    a2 = QgsPointXY(10.0, 5.0)
    b1 = QgsPointXY(5.0, 0.0)
    b2 = QgsPointXY(5.0, 10.0)
    inter = _line_intersection(a1, a2, b1, b2, infinite=False)
    assert inter is not None
    assert inter.x() == pytest.approx(5.0)
    assert inter.y() == pytest.approx(5.0)


def test_line_intersection_parallel():
    a1 = QgsPointXY(0.0, 0.0)
    a2 = QgsPointXY(10.0, 0.0)
    b1 = QgsPointXY(0.0, 5.0)
    b2 = QgsPointXY(10.0, 5.0)
    assert _line_intersection(a1, a2, b1, b2, infinite=True) is None


def test_line_intersection_apparent():
    a1 = QgsPointXY(0.0, 0.0)
    a2 = QgsPointXY(2.0, 0.0)
    b1 = QgsPointXY(5.0, 5.0)
    b2 = QgsPointXY(5.0, 3.0)
    # Direct segments do not intersect
    assert _line_intersection(a1, a2, b1, b2, infinite=False) is None
    # Apparent infinite intersection meets at (5, 0)
    inter = _line_intersection(a1, a2, b1, b2, infinite=True)
    assert inter is not None
    assert inter.x() == pytest.approx(5.0)
    assert inter.y() == pytest.approx(0.0)


def test_circle_tangents_external_point():
    center = QgsPointXY(0.0, 0.0)
    radius = 5.0
    pt = QgsPointXY(10.0, 0.0)
    tangents = _circle_tangents_from_point(pt, center, radius)
    assert len(tangents) == 2
    for t in tangents:
        # Distance to center is radius
        d = math.hypot(t.x() - center.x(), t.y() - center.y())
        assert d == pytest.approx(radius)
        # Dot product of radius vector and tangent vector is 0
        vx = t.x() - center.x()
        vy = t.y() - center.y()
        tx = pt.x() - t.x()
        ty = pt.y() - t.y()
        dot = vx * tx + vy * ty
        assert abs(dot) < 1e-6


def test_circle_tangents_internal_point():
    center = QgsPointXY(0.0, 0.0)
    radius = 5.0
    pt = QgsPointXY(2.0, 2.0)
    tangents = _circle_tangents_from_point(pt, center, radius)
    assert len(tangents) == 0


# ---------------------------------------------------------------------------
# Tracking Engine Tests
# ---------------------------------------------------------------------------

def test_ortho_tracking():
    engine = TrackingEngine()
    engine.mode = TrackingMode.ORTHO
    anchor = QgsPointXY(0.0, 0.0)
    cursor = QgsPointXY(10.0, 0.5)

    res = engine.process(cursor, anchor_point=anchor, canvas_crs=None, map_units_per_pixel=1.0)
    assert res.angle_deg == pytest.approx(0.0)
    assert res.point.y() == pytest.approx(0.0)
    assert res.point.x() == pytest.approx(10.0, abs=0.1)


def test_polar_tracking_near_ray():
    engine = TrackingEngine()
    engine.mode = TrackingMode.POLAR
    engine.polar_increment = 45.0
    anchor = QgsPointXY(0.0, 0.0)
    # 44 degrees, radius 10 -> close to 45 deg ray
    rad = math.radians(44.0)
    cursor = QgsPointXY(10.0 * math.cos(rad), 10.0 * math.sin(rad))

    res = engine.process(cursor, anchor_point=anchor, canvas_crs=None, map_units_per_pixel=0.1)
    assert res.angle_deg == pytest.approx(45.0)
    assert "polar:" in res.readout


def test_polar_tracking_outside_tolerance():
    engine = TrackingEngine()
    engine.mode = TrackingMode.POLAR
    engine.polar_increment = 90.0
    anchor = QgsPointXY(0.0, 0.0)
    # 45 degrees is 45 deg away from 0/90 rays
    rad = math.radians(45.0)
    cursor = QgsPointXY(10.0 * math.cos(rad), 10.0 * math.sin(rad))

    res = engine.process(cursor, anchor_point=anchor, canvas_crs=None, map_units_per_pixel=0.1)
    assert res.mode == TrackingMode.OFF
    assert res.guide_line is None


def test_object_tracking_precedence_s3():
    engine = TrackingEngine()
    engine.mode = TrackingMode.POLAR
    engine.polar_increment = 45.0
    anchor = QgsPointXY(0.0, 0.0)
    engine.acquire_point(QgsPointXY(10.0, 20.0))

    # Cursor is near horizontal alignment with acquired point (Y ~ 20)
    cursor = QgsPointXY(5.0, 20.2)
    res = engine.process(cursor, anchor_point=anchor, canvas_crs=None, map_units_per_pixel=1.0)

    # Precedence S3: object tracking ray takes precedence over polar
    assert res.mode == "object_tracking"
    assert "tracking:" in res.readout
    assert res.point.y() == pytest.approx(20.0)
