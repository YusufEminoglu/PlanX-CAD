"""Smoke tests for sketcher_utils geometry helpers.

NOT a unit test framework — these are checks you run **inside QGIS Python
console** to verify the 1.2.0 fixes work as intended on real QGIS objects.

Usage (QGIS Python Console):
    >>> exec(open(r"C:\\Users\\YE\\PyCharmMiscProject\\qgis_plugins\\planX_CAD_arac_Seti\\tests\\smoke_geometry.py").read())

Each test prints PASS / FAIL with a short reason. Run after installing the
plugin and refreshing.
"""
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes


def _ok(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}{(' — ' + detail) if detail else ''}")
    return cond


def test_create_fillet_shortest_arc():
    """Shortest arc selection — two 90° lines, fillet should be ≤ 90° not 270°."""
    from planX_CAD_arac_Seti.core.sketcher_utils import create_fillet_and_trims

    g1 = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)])
    g2 = QgsGeometry.fromPolylineXY([QgsPointXY(10, 0), QgsPointXY(10, 10)])
    result = create_fillet_and_trims(g1, g2, 2.0)
    if not result:
        return _ok("fillet shortest arc", False, "function returned None")

    arc = result["arc"]
    arc_pts = arc.asPolyline()
    # For 90° corner with R=2: short arc length ≈ π·R/2 ≈ 3.14
    arc_len = arc.length()
    return _ok(
        "fillet shortest arc (90° corner)",
        2.5 < arc_len < 4.0,
        f"arc_len={arc_len:.2f} (expected ≈ 3.14)",
    )


def test_scale_multipart_polygon():
    """Multipart polygon scale — should remain multipart with same part count."""
    from planX_CAD_arac_Seti.core.sketcher_utils import scale_geometry

    p1 = [QgsPointXY(0, 0), QgsPointXY(4, 0), QgsPointXY(4, 4), QgsPointXY(0, 4), QgsPointXY(0, 0)]
    p2 = [QgsPointXY(10, 10), QgsPointXY(14, 10), QgsPointXY(14, 14), QgsPointXY(10, 14), QgsPointXY(10, 10)]
    mp = QgsGeometry.fromMultiPolygonXY([[p1], [p2]])
    center = QgsPointXY(0, 0)

    scaled = scale_geometry(mp, center, 2.0)
    if scaled is None:
        return _ok("scale multipart polygon", False, "returned None")

    is_multi = scaled.isMultipart()
    part_count = len(scaled.asMultiPolygon()) if is_multi else 1
    return _ok(
        "scale multipart polygon preserves parts",
        is_multi and part_count == 2,
        f"isMultipart={is_multi}, parts={part_count}",
    )


def test_mirror_polygon_with_hole():
    """Polygon with hole — mirror should keep ring count."""
    from planX_CAD_arac_Seti.core.sketcher_utils import mirror_geometry

    outer = [QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10), QgsPointXY(0, 10), QgsPointXY(0, 0)]
    hole = [QgsPointXY(3, 3), QgsPointXY(7, 3), QgsPointXY(7, 7), QgsPointXY(3, 7), QgsPointXY(3, 3)]
    poly = QgsGeometry.fromPolygonXY([outer, hole])

    mirrored = mirror_geometry(poly, QgsPointXY(20, 0), QgsPointXY(20, 10))
    if mirrored is None:
        return _ok("mirror polygon with hole", False, "returned None")

    rings = mirrored.asPolygon()
    return _ok(
        "mirror polygon preserves hole",
        len(rings) == 2,
        f"rings={len(rings)} (expected 2)",
    )


def test_extend_multipart_line():
    """Extend on a multi-line geom should not crash and produce a valid line."""
    from planX_CAD_arac_Seti.core.sketcher_utils import extend_geometry_to_boundary

    multi = QgsGeometry.fromMultiPolylineXY([
        [QgsPointXY(0, 0), QgsPointXY(5, 0)],
        [QgsPointXY(20, 20), QgsPointXY(25, 20)],
    ])
    boundary = QgsGeometry.fromPolylineXY([QgsPointXY(10, -5), QgsPointXY(10, 5)])

    result = extend_geometry_to_boundary(multi, boundary)
    # Should pick the first part, extend it to x=10, return single line.
    return _ok(
        "extend on multipart input",
        result is not None and not result.isEmpty(),
        f"got: {result.asWkt() if result else None}",
    )


def run_all():
    print("=" * 60)
    print(" planX_CAD_arac_Seti — smoke tests (geometry helpers)")
    print("=" * 60)
    results = [
        test_create_fillet_shortest_arc(),
        test_scale_multipart_polygon(),
        test_mirror_polygon_with_hole(),
        test_extend_multipart_line(),
    ]
    passed = sum(1 for r in results if r)
    print("-" * 60)
    print(f"  {passed}/{len(results)} passed")
    return passed == len(results)


if __name__ == "__main__":
    run_all()
else:
    run_all()
