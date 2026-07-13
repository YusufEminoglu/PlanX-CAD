"""Standalone QGIS-runtime tests for the pure junction corner solver.

Run with either supported OSGeo4W launcher:

    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat tests\\smoke_junction_geometry.py
    C:\\OSGeo4W\\bin\\python-qgis.bat tests\\smoke_junction_geometry.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_PARENT))

from qgis.core import QgsApplication, QgsPointXY  # noqa: E402

from planX_CAD_arac_Seti.urban.junction_geometry import (  # noqa: E402
    CurbHalfEdge,
    cluster_approaches,
    sector_facing_pairs,
    solve_chamfer,
    solve_fillet,
    solve_sector_corners,
    support_line_intersection,
)


TOLERANCE = 1e-7


def _check(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}{' — ' + detail if detail else ''}")
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def _edge(road, source, point, outward, part=0):
    return CurbHalfEdge(
        road_id=road,
        component="sidewalk",
        source_id=source,
        source_part=part,
        cut_point=QgsPointXY(*point),
        outward=outward,
        source_ref={"road": road, "source": source},
    )


def _x_edges():
    return [
        _edge("H", "H_E_L", (10, 2), (1, 0)),
        _edge("H", "H_E_R", (10, -2), (1, 0)),
        _edge("H", "H_W_L", (-10, -2), (-1, 0)),
        _edge("H", "H_W_R", (-10, 2), (-1, 0)),
        _edge("V", "V_N_L", (-2, 10), (0, 1)),
        _edge("V", "V_N_R", (2, 10), (0, 1)),
        _edge("V", "V_S_L", (2, -10), (0, -1)),
        _edge("V", "V_S_R", (-2, -10), (0, -1)),
    ]


def _distance(first, second):
    return math.hypot(first.x() - second.x(), first.y() - second.y())


def _dot(first, second):
    return first[0] * second[0] + first[1] * second[1]


def test_x_approaches_and_sector_pairing():
    center = QgsPointXY(0, 0)
    approaches = cluster_approaches(_x_edges())
    _check("X creates four approaches", len(approaches) == 4, str(len(approaches)))
    horizontal = [approach for approach in approaches if approach.road_id == "H"]
    _check("through-road antipodes stay separate", len(horizontal) == 2)
    angle_gap = abs(horizontal[1].angle - horizontal[0].angle)
    _check("horizontal approaches are antipodal", abs(angle_gap - math.pi) < TOLERANCE)

    pairs = sector_facing_pairs(approaches, center)
    _check("X has four sector-facing curb pairs", len(pairs) == 4)
    intersections = [
        support_line_intersection(first, second) for first, second in pairs
    ]
    expected = {(2, 2), (-2, 2), (-2, -2), (2, -2)}
    actual = {
        (round(point.x(), 6), round(point.y(), 6))
        for point in intersections if point is not None
    }
    _check("X uses true curb support intersections", actual == expected, str(actual))


def test_chamfer_distance_is_exact():
    center = QgsPointXY(0, 0)
    solutions_2 = solve_sector_corners(_x_edges(), center, "chamfer", 2.0)
    solutions_8 = solve_sector_corners(_x_edges(), center, "chamfer", 8.0)
    _check("X creates four 2m chamfers", len(solutions_2) == 4)
    _check("X creates four 8m chamfers", len(solutions_8) == 4)
    for label, solutions, expected in (
        ("2m", solutions_2, 2.0), ("8m", solutions_8, 8.0)
    ):
        exact = all(
            abs(_distance(solution.support_intersection, solution.cut_first) - expected)
            < TOLERANCE
            and abs(_distance(solution.support_intersection, solution.cut_second) - expected)
            < TOLERANCE
            for solution in solutions
        )
        _check(f"{label} chamfer cutbacks are exact", exact)
        endpoints_match = all(
            _distance(solution.connection.asPolyline()[0], solution.cut_first) < TOLERANCE
            and _distance(solution.connection.asPolyline()[-1], solution.cut_second)
            < TOLERANCE
            for solution in solutions
        )
        _check(f"{label} connection endpoints equal cut points", endpoints_match)


def test_fillet_radius_and_tangency():
    center = QgsPointXY(0, 0)
    solutions = solve_sector_corners(_x_edges(), center, "fillet", 3.0, segments=24)
    _check("X creates four fillets", len(solutions) == 4)
    for solution in solutions:
        _check("fillet has arc center", solution.arc_center is not None)
        points = solution.connection.asPolyline()
        radii_are_exact = all(
            abs(_distance(point, solution.arc_center) - 3.0) < 1e-6
            for point in points
        )
        _check("fillet vertices stay on requested radius", radii_are_exact)
        radial_first = (
            solution.cut_first.x() - solution.arc_center.x(),
            solution.cut_first.y() - solution.arc_center.y(),
        )
        radial_second = (
            solution.cut_second.x() - solution.arc_center.x(),
            solution.cut_second.y() - solution.arc_center.y(),
        )
        _check(
            "first fillet endpoint is tangent",
            abs(_dot(radial_first, solution.first.outward)) < TOLERANCE,
        )
        _check(
            "second fillet endpoint is tangent",
            abs(_dot(radial_second, solution.second.outward)) < TOLERANCE,
        )
        _check(
            "fillet geometry endpoints equal trim points",
            _distance(points[0], solution.cut_first) < TOLERANCE
            and _distance(points[-1], solution.cut_second) < TOLERANCE,
        )


def test_t_and_skew_layouts():
    center = QgsPointXY(0, 0)
    t_edges = [
        edge for edge in _x_edges()
        if not str(edge.source_id).startswith("V_S")
    ]
    approaches = cluster_approaches(t_edges)
    _check("T creates three approaches", len(approaches) == 3)
    # The two 90-degree corners solve; the straight-through 180-degree sector
    # is safely skipped because its support lines are parallel.
    t_solutions = solve_sector_corners(t_edges, center, "chamfer", 4.0)
    _check("T creates two valid corners", len(t_solutions) == 2, str(len(t_solutions)))

    directions = (0.0, 120.0, 240.0)
    skew_edges = []
    for road_index, degrees in enumerate(directions):
        angle = math.radians(degrees)
        outward = (math.cos(angle), math.sin(angle))
        left = (-outward[1], outward[0])
        for side, sign in (("L", 1.0), ("R", -1.0)):
            point = (
                outward[0] * 10.0 + left[0] * 2.0 * sign,
                outward[1] * 10.0 + left[1] * 2.0 * sign,
            )
            skew_edges.append(_edge(
                f"S{road_index}", f"S{road_index}_{side}", point, outward
            ))
    skew_solutions = solve_sector_corners(skew_edges, center, "fillet", 2.0)
    _check("skew three-arm junction creates three corners", len(skew_solutions) == 3)
    _check(
        "skew fillet solutions are finite",
        all(
            math.isfinite(solution.support_intersection.x())
            and math.isfinite(solution.support_intersection.y())
            for solution in skew_solutions
        ),
    )


def test_near_parallel_safety():
    first = _edge("A", "A1", (0, 0), (1, 0))
    second = _edge("B", "B1", (0, 1), (1, 1e-10))
    _check(
        "near-parallel support lines have no intersection",
        support_line_intersection(first, second) is None,
    )
    _check("near-parallel chamfer is skipped", solve_chamfer(first, second, 5) is None)
    _check("near-parallel fillet is skipped", solve_fillet(first, second, 5) is None)

    shallow_angle = math.radians(1.0)
    remote_edges = [
        _edge("A", "A_L", (10, 2), (1, 0)),
        _edge("A", "A_R", (10, -2), (1, 0)),
        _edge(
            "B", "B_L", (10, 4),
            (math.cos(shallow_angle), math.sin(shallow_angle)),
        ),
        _edge(
            "B", "B_R", (10, 0),
            (math.cos(shallow_angle), math.sin(shallow_angle)),
        ),
    ]
    _check(
        "remote shallow-angle corner is skipped",
        not solve_sector_corners(
            remote_edges, QgsPointXY(0, 0), "chamfer", 5.0
        ),
    )

    _check(
        "excessive acute fillet tangent is skipped",
        not solve_sector_corners(
            remote_edges, QgsPointXY(0, 0), "fillet", 3.0
        ),
    )


def test_incomplete_approach_is_rejected():
    edges = _x_edges()
    edges = [edge for edge in edges if edge.source_id != "V_N_R"]
    approaches = cluster_approaches(edges)
    _check(
        "one-curb branch is not a solvable approach",
        len(approaches) == 3,
        f"approaches={len(approaches)}",
    )
    solutions = solve_sector_corners(
        edges, QgsPointXY(0, 0), "chamfer", 3.0
    )
    used = [
        id(edge)
        for solution in solutions
        for edge in (solution.first, solution.second)
    ]
    _check("no curb is reused by multiple corners", len(used) == len(set(used)))


def run_all():
    profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-junction-test-")
    app = QgsApplication([], False, profile_dir.name, "external")
    app.initQgis()
    try:
        test_x_approaches_and_sector_pairing()
        test_chamfer_distance_is_exact()
        test_fillet_radius_and_tangency()
        test_t_and_skew_layouts()
        test_near_parallel_safety()
        test_incomplete_approach_is_rejected()
        print("  All pure junction geometry checks passed")
        return True
    finally:
        app.exitQgis()
        profile_dir.cleanup()


if __name__ == "__main__":
    try:
        run_all()
    except Exception as error:
        print(f"  [FAIL] {type(error).__name__}: {error}")
        raise
