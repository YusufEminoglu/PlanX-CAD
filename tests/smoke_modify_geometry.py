"""QGIS-runtime checks for the 1.27 modify helpers.

Covers chamfer, break, lengthen, align, stretch, and explode. Run from the
plugins parent directory with a QGIS Python launcher:

    python-qgis-ltr.bat -m planX_CAD_arac_Seti.tests.smoke_modify_geometry
    python-qgis.bat     -m planX_CAD_arac_Seti.tests.smoke_modify_geometry
"""

import math
import sys
import tempfile
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
)


PLUGIN_PARENT = Path(__file__).resolve().parents[2]
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))


def _ok(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}{(' — ' + detail) if detail else ''}")
    return condition


def _line(*coords):
    return QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in coords])


def _close(a, b, tolerance=1e-6):
    return abs(a - b) <= tolerance


def _point_close(point, x, y, tolerance=1e-6):
    return _close(point.x(), x, tolerance) and _close(point.y(), y, tolerance)


# ── chamfer ───────────────────────────────────────────────────────────────────

def test_chamfer_right_angle():
    from planX_CAD_arac_Seti.core.sketcher_utils import create_chamfer_and_trims

    result = create_chamfer_and_trims(
        _line((0, 0), (10, 0)), _line((10, 0), (10, 10)), 2.0, 2.0
    )
    if not result:
        return _ok("chamfer on 90 degree corner", False, "returned None")
    length = result['line'].length()
    return _ok(
        "chamfer on 90 degree corner",
        _close(length, 2.0 * math.sqrt(2.0)) and
        _point_close(result['tp1'], 8.0, 0.0) and
        _point_close(result['tp2'], 10.0, 2.0) and
        _point_close(result['inter_pt'], 10.0, 0.0),
        f"len={length:.4f} tp1={result['tp1'].toString(3)} "
        f"tp2={result['tp2'].toString(3)}",
    )


def test_chamfer_unequal_distances():
    from planX_CAD_arac_Seti.core.sketcher_utils import create_chamfer_and_trims

    result = create_chamfer_and_trims(
        _line((0, 0), (10, 0)), _line((10, 0), (10, 10)), 3.0, 1.0
    )
    if not result:
        return _ok("chamfer with unequal distances", False, "returned None")
    return _ok(
        "chamfer with unequal distances",
        _point_close(result['tp1'], 7.0, 0.0) and
        _point_close(result['tp2'], 10.0, 1.0),
        f"tp1={result['tp1'].toString(3)} tp2={result['tp2'].toString(3)}",
    )


def test_chamfer_rejects_parallel_and_overlong():
    from planX_CAD_arac_Seti.core.sketcher_utils import create_chamfer_and_trims

    parallel = create_chamfer_and_trims(
        _line((0, 0), (10, 0)), _line((0, 5), (10, 5)), 2.0
    )
    overlong = create_chamfer_and_trims(
        _line((0, 0), (10, 0)), _line((10, 0), (10, 10)), 40.0
    )
    return _ok(
        "chamfer rejects parallel lines and overlong cutback",
        parallel is None and overlong is None,
        f"parallel={parallel} overlong={overlong}",
    )


# ── break ─────────────────────────────────────────────────────────────────────

def test_break_at_single_point():
    from planX_CAD_arac_Seti.core.sketcher_utils import break_line_at_points

    parts = break_line_at_points(_line((0, 0), (10, 0)), QgsPointXY(4, 0))
    lengths = sorted(part.length() for part in parts)
    return _ok(
        "break at point splits into two parts",
        len(parts) == 2 and _close(lengths[0], 4.0) and _close(lengths[1], 6.0),
        f"parts={len(parts)} lengths={[round(v, 4) for v in lengths]}",
    )


def test_break_with_gap_removes_span():
    from planX_CAD_arac_Seti.core.sketcher_utils import break_line_at_points

    parts = break_line_at_points(
        _line((0, 0), (10, 0)), QgsPointXY(3, 0), QgsPointXY(7, 0)
    )
    lengths = sorted(part.length() for part in parts)
    return _ok(
        "break with gap removes the middle span",
        len(parts) == 2 and _close(lengths[0], 3.0) and _close(lengths[1], 3.0),
        f"parts={len(parts)} lengths={[round(v, 4) for v in lengths]}",
    )


def test_break_keeps_intermediate_vertices():
    from planX_CAD_arac_Seti.core.sketcher_utils import break_line_at_points

    polyline = _line((0, 0), (10, 0), (10, 10))
    parts = break_line_at_points(polyline, QgsPointXY(10, 4))
    if len(parts) != 2:
        return _ok("break keeps polyline corner vertices", False,
                   f"parts={len(parts)}")
    first = parts[0].asPolyline()
    return _ok(
        "break keeps polyline corner vertices",
        len(first) == 3 and _point_close(first[-1], 10.0, 4.0) and
        _close(parts[0].length(), 14.0) and _close(parts[1].length(), 6.0),
        f"first={[p.toString(2) for p in first]}",
    )


def test_break_rejects_endpoint():
    from planX_CAD_arac_Seti.core.sketcher_utils import break_line_at_points

    parts = break_line_at_points(_line((0, 0), (10, 0)), QgsPointXY(0, 0))
    return _ok("break at an endpoint is rejected", parts == [], f"parts={parts}")


# ── lengthen ──────────────────────────────────────────────────────────────────

def test_lengthen_delta_percent_total():
    from planX_CAD_arac_Seti.core.sketcher_utils import lengthen_line

    source = _line((0, 0), (10, 0))
    delta = lengthen_line(source, "delta", 5.0)
    percent = lengthen_line(source, "percent", 50.0)
    total = lengthen_line(source, "total", 4.0)
    return _ok(
        "lengthen delta / percent / total",
        delta is not None and _close(delta.length(), 15.0) and
        _point_close(delta.asPolyline()[-1], 15.0, 0.0) and
        percent is not None and _close(percent.length(), 5.0) and
        total is not None and _close(total.length(), 4.0),
        f"delta={delta.length():.3f} percent={percent.length():.3f} "
        f"total={total.length():.3f}",
    )


def test_lengthen_from_start_end():
    from planX_CAD_arac_Seti.core.sketcher_utils import lengthen_line

    result = lengthen_line(_line((0, 0), (10, 0)), "delta", 5.0, from_end=False)
    if result is None:
        return _ok("lengthen from the start vertex", False, "returned None")
    points = result.asPolyline()
    return _ok(
        "lengthen from the start vertex",
        _point_close(points[0], -5.0, 0.0) and
        _point_close(points[-1], 10.0, 0.0),
        f"start={points[0].toString(3)}",
    )


def test_lengthen_follows_last_segment_direction():
    from planX_CAD_arac_Seti.core.sketcher_utils import lengthen_line

    result = lengthen_line(_line((0, 0), (10, 0), (10, 10)), "delta", 5.0)
    if result is None:
        return _ok("lengthen follows the terminal segment", False, "None")
    end = result.asPolyline()[-1]
    return _ok(
        "lengthen follows the terminal segment",
        _point_close(end, 10.0, 15.0) and _close(result.length(), 25.0),
        f"end={end.toString(3)} len={result.length():.3f}",
    )


def test_lengthen_rejects_invalid():
    from planX_CAD_arac_Seti.core.sketcher_utils import lengthen_line

    source = _line((0, 0), (10, 0))
    return _ok(
        "lengthen rejects a non-positive result and unknown mode",
        lengthen_line(source, "delta", -20.0) is None and
        lengthen_line(source, "elastic", 5.0) is None,
    )


# ── align ─────────────────────────────────────────────────────────────────────

def test_align_translate_only():
    from planX_CAD_arac_Seti.core.sketcher_utils import align_geometry

    result = align_geometry(
        _line((0, 0), (4, 0)), QgsPointXY(0, 0), QgsPointXY(10, 5)
    )
    points = result.asPolyline() if result else []
    return _ok(
        "align with one pair translates",
        len(points) == 2 and _point_close(points[0], 10.0, 5.0) and
        _point_close(points[1], 14.0, 5.0),
        f"points={[p.toString(2) for p in points]}" if points else "None",
    )


def test_align_rotates_without_scaling():
    from planX_CAD_arac_Seti.core.sketcher_utils import align_geometry

    result = align_geometry(
        _line((0, 0), (1, 0), (1, 1)),
        QgsPointXY(0, 0), QgsPointXY(10, 10),
        QgsPointXY(1, 0), QgsPointXY(10, 11),
    )
    points = result.asPolyline() if result else []
    return _ok(
        "align with two pairs rotates 90 degrees, keeps size",
        len(points) == 3 and _point_close(points[0], 10.0, 10.0) and
        _point_close(points[1], 10.0, 11.0) and
        _point_close(points[2], 9.0, 11.0),
        f"points={[p.toString(2) for p in points]}" if points else "None",
    )


def test_align_scales_on_request():
    from planX_CAD_arac_Seti.core.sketcher_utils import align_geometry

    scaled = align_geometry(
        _line((0, 0), (1, 0)),
        QgsPointXY(0, 0), QgsPointXY(0, 0),
        QgsPointXY(1, 0), QgsPointXY(2, 0),
        scale=True,
    )
    unscaled = align_geometry(
        _line((0, 0), (1, 0)),
        QgsPointXY(0, 0), QgsPointXY(0, 0),
        QgsPointXY(1, 0), QgsPointXY(2, 0),
    )
    return _ok(
        "align applies the pair length ratio only when scaling",
        scaled is not None and _close(scaled.length(), 2.0) and
        unscaled is not None and _close(unscaled.length(), 1.0),
        f"scaled={scaled.length():.3f} unscaled={unscaled.length():.3f}",
    )


# ── stretch ───────────────────────────────────────────────────────────────────

def test_stretch_moves_only_enclosed_vertices():
    from planX_CAD_arac_Seti.core.sketcher_utils import stretch_geometry

    window = QgsRectangle(9.0, -1.0, 11.0, 1.0)
    result = stretch_geometry(_line((0, 0), (10, 0), (10, 10)), window, 0.0, 5.0)
    points = result.asPolyline() if result else []
    return _ok(
        "stretch moves only the vertices inside the window",
        len(points) == 3 and _point_close(points[0], 0.0, 0.0) and
        _point_close(points[1], 10.0, 5.0) and
        _point_close(points[2], 10.0, 10.0),
        f"points={[p.toString(2) for p in points]}" if points else "None",
    )


def test_stretch_keeps_polygon_ring_closed():
    from planX_CAD_arac_Seti.core.sketcher_utils import stretch_geometry

    square = QgsGeometry.fromPolygonXY([[
        QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10),
        QgsPointXY(0, 10), QgsPointXY(0, 0),
    ]])
    result = stretch_geometry(square, QgsRectangle(-1, -1, 1, 1), 0.0, -4.0)
    if result is None:
        return _ok("stretch keeps a polygon ring closed", False, "None")
    ring = result.asPolygon()[0]
    return _ok(
        "stretch keeps a polygon ring closed",
        result.isGeosValid() and _point_close(ring[0], ring[-1].x(), ring[-1].y())
        and _point_close(ring[0], 0.0, -4.0),
        f"first={ring[0].toString(2)} last={ring[-1].toString(2)}",
    )


def test_stretch_without_enclosed_vertex():
    from planX_CAD_arac_Seti.core.sketcher_utils import stretch_geometry

    result = stretch_geometry(
        _line((0, 0), (10, 0)), QgsRectangle(50, 50, 60, 60), 1.0, 1.0
    )
    return _ok("stretch with an empty window returns None", result is None)


# ── explode ───────────────────────────────────────────────────────────────────

def test_explode_multipart_to_parts():
    from planX_CAD_arac_Seti.core.sketcher_utils import explode_geometry

    multi = QgsGeometry.fromMultiPolylineXY([
        [QgsPointXY(0, 0), QgsPointXY(5, 0)],
        [QgsPointXY(20, 20), QgsPointXY(25, 20)],
    ])
    parts = explode_geometry(multi, "parts")
    return _ok(
        "explode splits a multipart line into single parts",
        len(parts) == 2 and all(not part.isMultipart() for part in parts),
        f"parts={len(parts)}",
    )


def test_explode_polygon_to_segments():
    from planX_CAD_arac_Seti.core.sketcher_utils import explode_geometry

    square = QgsGeometry.fromPolygonXY([[
        QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10),
        QgsPointXY(0, 10), QgsPointXY(0, 0),
    ]])
    segments = explode_geometry(square, "segments")
    total = sum(segment.length() for segment in segments)
    return _ok(
        "explode turns a polygon boundary into segments",
        len(segments) == 4 and _close(total, 40.0),
        f"segments={len(segments)} total={total:.3f}",
    )


def test_explode_polygon_with_hole():
    from planX_CAD_arac_Seti.core.sketcher_utils import explode_geometry

    outer = [QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10),
             QgsPointXY(0, 10), QgsPointXY(0, 0)]
    hole = [QgsPointXY(3, 3), QgsPointXY(6, 3), QgsPointXY(6, 6),
            QgsPointXY(3, 6), QgsPointXY(3, 3)]
    segments = explode_geometry(QgsGeometry.fromPolygonXY([outer, hole]),
                                "segments")
    return _ok(
        "explode includes interior rings",
        len(segments) == 8,
        f"segments={len(segments)}",
    )


def test_explode_polyline_to_segments():
    from planX_CAD_arac_Seti.core.sketcher_utils import explode_geometry

    segments = explode_geometry(_line((0, 0), (10, 0), (10, 10)), "segments")
    return _ok(
        "explode turns a polyline into two segments",
        len(segments) == 2 and all(len(s.asPolyline()) == 2 for s in segments),
        f"segments={len(segments)}",
    )


# ── runner ────────────────────────────────────────────────────────────────────

def run_all():
    print("=" * 60)
    print(" PlanX CAD Toolset - modify helper checks (chamfer/break/lengthen/")
    print(" align/stretch/explode)")
    print("=" * 60)
    results = [
        test_chamfer_right_angle(),
        test_chamfer_unequal_distances(),
        test_chamfer_rejects_parallel_and_overlong(),
        test_break_at_single_point(),
        test_break_with_gap_removes_span(),
        test_break_keeps_intermediate_vertices(),
        test_break_rejects_endpoint(),
        test_lengthen_delta_percent_total(),
        test_lengthen_from_start_end(),
        test_lengthen_follows_last_segment_direction(),
        test_lengthen_rejects_invalid(),
        test_align_translate_only(),
        test_align_rotates_without_scaling(),
        test_align_scales_on_request(),
        test_stretch_moves_only_enclosed_vertices(),
        test_stretch_keeps_polygon_ring_closed(),
        test_stretch_without_enclosed_vertex(),
        test_explode_multipart_to_parts(),
        test_explode_polygon_to_segments(),
        test_explode_polygon_with_hole(),
        test_explode_polyline_to_segments(),
    ]
    passed = sum(1 for result in results if result)
    print("-" * 60)
    print(f"  {passed}/{len(results)} passed")
    return passed == len(results)


def main():
    app = QgsApplication.instance()
    owns_app = app is None
    profile_dir = None
    if owns_app:
        profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-modify-")
        app = QgsApplication([], False, profile_dir.name, "external")
        app.initQgis()
    try:
        return run_all()
    finally:
        if owns_app:
            app.exitQgis()
            profile_dir.cleanup()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
else:
    main()
