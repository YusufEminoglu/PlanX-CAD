"""QGIS-runtime tests for the street and parcel design tools.

Geometry is checked against hand-computed answers, then each tool is driven
against real memory layers to prove what it writes. Run with either launcher:

    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat -m planX_CAD_arac_Seti.tests.smoke_urban_tools
    C:\\OSGeo4W\\bin\\python-qgis.bat -m planX_CAD_arac_Seti.tests.smoke_urban_tools
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_PARENT))

from qgis.PyQt.QtCore import Qt  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsGeometry, QgsPointXY, QgsProject,
)

from planX_CAD_arac_Seti.urban.urban_geometry import (  # noqa: E402
    FRONT, REAR, SIDE,
    approach_directions, buildable_envelope, classify_parcel_edges,
    parking_bays, roundabout_parts, sight_triangle, splitter_island, turning_head,
)

_results = []


def _check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))


def P(x, y):
    return QgsPointXY(x, y)


def _poly(*points):
    pts = [P(*p) for p in points]
    return QgsGeometry.fromPolygonXY([pts + [pts[0]]])


def _line(*points):
    return QgsGeometry.fromPolylineXY([P(*p) for p in points])


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ── geometry ────────────────────────────────────────────────────────────────

def geometry_checks():
    parcel = _poly((0, 0), (20, 0), (20, 40), (0, 40))

    roles = sorted(role for *_ab, role in classify_parcel_edges(parcel, P(10, 0.5)))
    _check("rectangle edges: 1 front, 1 rear, 2 sides",
           roles == sorted([FRONT, REAR, SIDE, SIDE]), str(roles))

    envelope, _edges = buildable_envelope(parcel, P(10, 0.5), 5, 3, 4)
    box = envelope.boundingBox() if envelope else None
    _check("envelope of a 20×40 parcel with 5/3/4 m setbacks is 14×31",
           envelope is not None and _close(envelope.area(), 434.0, 1e-6)
           and _close(box.xMinimum(), 3) and _close(box.yMinimum(), 5)
           and _close(box.xMaximum(), 17) and _close(box.yMaximum(), 36),
           f"area={envelope.area() if envelope else None}")

    corner, corner_edges = buildable_envelope(parcel, P(2, 0.3), 5, 3, 4, corner_parcel=True)
    fronts = sum(1 for *_ab, role in corner_edges if role == FRONT)
    _check("corner parcel takes the neighbouring edge as a second front",
           fronts == 2 and corner is not None and _close(corner.area(), 12 * 31, 1e-6),
           f"fronts={fronts} area={corner.area() if corner else None}")

    l_shape = _poly((0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30))
    l_env, _ = buildable_envelope(l_shape, P(15, 0.2), 2, 2, 2)
    boundary = QgsGeometry.fromPolylineXY([P(*p) for p in
                                           ((0, 0), (30, 0), (30, 10), (10, 10), (10, 30), (0, 30), (0, 0))])
    vertices = [P(v.x(), v.y()) for v in l_env.vertices()] if l_env else []
    min_gap = min(QgsGeometry.fromPointXY(v).distance(boundary) for v in vertices) if vertices else 0
    _check("concave parcel: every envelope vertex keeps the 2 m setback",
           l_env is not None and l_shape.contains(l_env.pointOnSurface())
           and min_gap >= 2.0 - 1e-6 and l_env.area() < l_shape.area(),
           f"min gap={min_gap:.4f}")

    none_left, _ = buildable_envelope(_poly((0, 0), (6, 0), (6, 6), (0, 6)), P(3, 0.1), 3, 3, 3)
    _check("setbacks wider than the parcel leave nothing", none_left is None)

    tri, corner_pt = sight_triangle(_line((0, 0), (50, 0)), P(20, 0),
                                    _line((0, 0), (0, 50)), P(0, 20), 10, 15)
    _check("sight triangle legs 10 m and 15 m from the corner",
           tri is not None and _close(tri.area(), 75.0, 1e-6)
           and corner_pt is not None and _close(corner_pt.x(), 0) and _close(corner_pt.y(), 0),
           f"area={tri.area() if tri else None}")

    short, short_corner = sight_triangle(_line((2, 0), (50, 0)), P(20, 0),
                                         _line((0, 2), (0, 50)), P(0, 20), 10, 15)
    _check("rounded corner: legs start at the virtual curb intersection",
           short is not None and _close(short.area(), 75.0, 1e-6)
           and _close(short_corner.x(), 0) and _close(short_corner.y(), 0))

    crossing, _ = sight_triangle(_line((-50, 0), (50, 0)), P(-20, 0),
                                 _line((0, -50), (0, 50)), P(0, 20), 10, 15)
    centre = crossing.centroid().asPoint() if crossing else None
    _check("crossing lines: the triangle sits in the picked quadrant",
           centre is not None and centre.x() < 0 and centre.y() > 0)

    parallel, _ = sight_triangle(_line((0, 0), (50, 0)), P(10, 0),
                                 _line((0, 5), (50, 5)), P(10, 5), 10, 10)
    _check("parallel lines give no triangle", parallel is None)

    curb = _line((0, 0), (50, 0))
    bays90 = parking_bays(curb, P(25, 10), 90, 2.5, 5.0)
    ys = [v.y() for bay in bays90 for v in bay.vertices()]
    _check("90° parking: 20 stalls of 2.5 × 5 m on the clicked side",
           len(bays90) == 20 and all(_close(b.area(), 12.5, 1e-6) for b in bays90)
           and min(ys) >= -1e-9 and max(ys) <= 5 + 1e-9, f"count={len(bays90)}")

    other_side = parking_bays(curb, P(25, -10), 90, 2.5, 5.0)
    _check("clicking the other side flips the stalls",
           other_side and max(v.y() for b in other_side for v in b.vertices()) <= 1e-9)

    bays60 = parking_bays(curb, P(25, 10), 60, 2.5, 5.0)
    _check("60° parking: 16 stalls fit, none past the curb end",
           len(bays60) == 16 and all(_close(b.area(), 12.5, 1e-6) for b in bays60)
           and max(v.x() for b in bays60 for v in b.vertices()) <= 50 + 1e-9,
           f"count={len(bays60)}")

    parallel_bays = parking_bays(curb, P(25, 10), 0, 2.5, 6.0)
    _check("parallel parking: 8 stalls of 6 × 2.5 m",
           len(parallel_bays) == 8 and all(_close(b.area(), 15.0, 1e-6) for b in parallel_bays))

    bend = parking_bays(_line((0, 0), (10, 0), (10, 10)), P(5, 5), 90, 2.5, 5.0)
    overlaps = sum(1 for i, a in enumerate(bend) for b in bend[i + 1:]
                   if a.intersection(b).area() > 1e-6)
    _check("inside a bend the clashing corner stalls are dropped, none overlap",
           len(bend) == 6 and overlaps == 0, f"count={len(bend)} overlaps={overlaps}")
    outward = parking_bays(_line((0, 0), (10, 0), (10, 10)), P(15, -5), 90, 2.5, 5.0)
    _check("outside a bend every stall fits", len(outward) == 8, f"count={len(outward)}")

    parts = dict(roundabout_parts(P(0, 0), 18, 6, 1.5))
    expected = {
        "central_island": math.pi * 10.5 ** 2,
        "apron": math.pi * (12 ** 2 - 10.5 ** 2),
        "circulatory": math.pi * (18 ** 2 - 12 ** 2),
    }
    _check("roundabout rings match the radii within 0.5%",
           set(parts) == set(expected) and all(
               abs(parts[k].area() - v) / v < 0.005 for k, v in expected.items()),
           {k: round(g.area(), 1) for k, g in parts.items()}.__repr__())
    _check("an island-less roundabout is refused", roundabout_parts(P(0, 0), 8, 6, 1.5) == [])

    legs = approach_directions(P(0, 0), 18, [_line((-40, 0), (40, 0)), _line((0, 0), (0, 40))])
    _check("three approach legs found where lines cross the kerb", len(legs) == 3, str(legs))
    island = splitter_island(P(0, 0), 18, (1.0, 0.0), 12, 3)
    _check("splitter island is a 3 × 12 m triangle beyond the kerb",
           island is not None and _close(island.area(), 18.0, 1e-6)
           and island.boundingBox().xMinimum() >= 18.0)

    bulb, end = turning_head(_line((0, 0), (50, 0)), P(49, 1), 10, 7, 12)
    inside = lambda x, y: bulb.contains(QgsGeometry.fromPointXY(P(x, y)))  # noqa: E731
    _check("turning head: circle at the picked end with tapers back to the road",
           bulb is not None and _close(end.x(), 50) and inside(59.5, 0) and inside(50, 9.5)
           and inside(39, 3.3) and not inside(61, 0) and not inside(30, 0)
           and bulb.area() > math.pi * 100)


# ── tools writing real layers ───────────────────────────────────────────────

def tool_checks():
    from planX_CAD_arac_Seti.tests.smoke_runtime import _Iface, _seed_layer
    from planX_CAD_arac_Seti.tools.tool_envelope import tool_envelope
    from planX_CAD_arac_Seti.tools.tool_parking import tool_parking
    from planX_CAD_arac_Seti.tools.tool_roundabout import tool_roundabout
    from planX_CAD_arac_Seti.tools.tool_sight_triangle import tool_sight_triangle
    from planX_CAD_arac_Seti.tools.tool_turning_head import tool_turning_head
    from planX_CAD_arac_Seti.dialogs.option_widgets import ToolOptionsDialog

    project = QgsProject.instance()
    project.clear()
    iface = _Iface()
    canvas = iface.mapCanvas()
    crs = QgsCoordinateReferenceSystem.fromEpsgId(32635)  # UTM 35N: İzmir
    canvas.setDestinationCrs(crs)
    E, N = 512000.0, 4256000.0

    def managed(name):
        layers = project.mapLayersByName(name)
        return layers[-1] if layers else None

    parcels = _seed_layer(project, "Polygon?crs=EPSG:32635", "parcels", [
        _poly((E, N), (E + 20, N), (E + 20, N + 40), (E, N + 40)),
    ])
    env = tool_envelope(canvas, iface)
    env.front, env.side, env.rear, env.max_coverage = 5.0, 3.0, 4.0, 40.0
    env.on_entity_selected(parcels, next(parcels.getFeatures()), P(E + 10, N + 0.5))
    out = managed("planx_envelope")
    feature = next(out.getFeatures()) if out else None
    _check("envelope tool writes area, buildable share and max footprint",
           feature is not None and _close(feature["envelope_area"], 434.0, 0.01)
           and _close(feature["parcel_area"], 800.0, 0.01)
           and _close(feature["max_footprint"], 320.0, 0.01)
           and _close(feature["buildable_pct"], 434.0 / 800.0 * 100, 0.06),
           str(feature.attributes() if feature else None))

    curbs = _seed_layer(project, "LineString?crs=EPSG:32635", "curbs", [
        _line((E, N), (E + 50, N)),
        _line((E, N), (E, N + 50)),
    ])
    first, second = list(curbs.getFeatures())
    sight = tool_sight_triangle(canvas, iface)
    sight.leg_a, sight.leg_b = 10.0, 15.0
    sight.first_layer, sight.first_feature, sight.first_point = curbs, first, P(E + 20, N)
    sight._create(curbs, second, P(E, N + 20))
    out = managed("planx_sight_triangle")
    feature = next(out.getFeatures()) if out else None
    _check("sight triangle tool writes a 75 m² triangle",
           feature is not None and _close(feature.geometry().area(), 75.0, 0.01))

    park = tool_parking(canvas, iface)
    park.angle, park.bay_width, park.bay_length = 90, 2.5, 5.0
    park.selected_layer = curbs
    park.selected_feature = first
    park.on_entity_selected(curbs, first, P(E + 25, N))
    park.on_click(P(E + 25, N + 10), Qt.MouseButton.LeftButton)
    out = managed("planx_parking")
    numbers = sorted(f["bay_no"] for f in out.getFeatures()) if out else []
    _check("parking tool writes 20 numbered stalls in one edit",
           numbers == list(range(1, 21)), f"count={len(numbers)}")

    roads = _seed_layer(project, "LineString?crs=EPSG:32635", "centrelines", [
        _line((E - 60, N + 200), (E + 60, N + 200)),
        _line((E, N + 200), (E, N + 260)),
    ])
    iface.set_active_layer(roads)
    rb = tool_roundabout(canvas, iface)
    rb.on_click(P(E, N + 200), Qt.MouseButton.LeftButton)
    out = managed("planx_roundabout")
    parts = sorted(f["part"] for f in out.getFeatures()) if out else []
    _check("roundabout tool writes rings plus a splitter island per leg",
           parts == sorted(["apron", "central_island", "circulatory"] + ["splitter_island"] * 3),
           str(parts))

    head = tool_turning_head(canvas, iface)
    head.on_entity_selected(roads, list(roads.getFeatures())[1], P(E, N + 259))
    out = managed("planx_turning_head")
    feature = next(out.getFeatures()) if out else None
    _check("turning head tool writes the bulb at the picked end",
           feature is not None and feature.geometry().contains(
               QgsGeometry.fromPointXY(P(E, N + 268))))

    dialog_tool = tool_parking(canvas, iface)
    dialog = ToolOptionsDialog(dialog_tool, "Parking Layout")
    spec = {s.attr: s for s in dialog_tool.INLINE_OPTIONS}
    dialog._changed(spec["angle"], 45)
    dialog._changed(spec["bay_width"], 2.7)
    unchanged = dialog_tool.angle == 90
    dialog.apply()
    _check("fallback form applies values only on OK",
           unchanged and dialog_tool.angle == 45 and _close(dialog_tool.bay_width, 2.7))
    dialog.deleteLater()

    project.clear()
    iface.mainWindow().close()


def run_all():
    profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-urban-test-")
    app = QgsApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QgsApplication([], False, profile_dir.name, "external")
        app.initQgis()
    try:
        geometry_checks()
        tool_checks()
    finally:
        if owns_app:
            app.exitQgis()
        profile_dir.cleanup()
    print("=" * 60)
    print(" PlanX CAD Toolset - urban design tools")
    print("=" * 60)
    for name, passed, detail in _results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}{'' if passed or not detail else ' — ' + detail}")
    passed_count = sum(passed for _, passed, _ in _results)
    print("-" * 60)
    print(f"  {passed_count}/{len(_results)} passed")
    return passed_count == len(_results)


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
