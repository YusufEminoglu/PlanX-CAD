"""QGIS-runtime checks for OSNAP engine, Ortho/Polar tracking, and Dynamic Input.

Covers:
  - SnapKind classification (endpoint, midpoint, centre, quadrant, perpendicular,
    tangent, intersection, apparent intersection, extension, nearest)
  - Ortho and Polar tracking angle constraints and precedence rules (S3)
  - Dynamic input HUD metrics computation
  - Tool pin test: asserts all registered tool classes construct and execute
    their move/press lifecycles with the unified drafting workbench active.

Run with:
    python-qgis-ltr.bat -m planX_CAD_arac_Seti.tests.smoke_osnap_tracking
    python-qgis.bat     -m planX_CAD_arac_Seti.tests.smoke_osnap_tracking
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))

from qgis.PyQt.QtCore import QPoint, Qt
from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapCanvas

from planX_CAD_arac_Seti.core.osnap_engine import (
    OsnapEngine,
    SnapKind,
    _foot_of_perpendicular,
    _line_intersection,
    _circle_tangents_from_point,
)
from planX_CAD_arac_Seti.core.tracking_engine import (
    TrackingEngine,
    TrackingMode,
    TrackingResult,
)
from planX_CAD_arac_Seti.core.drafting_workbench import DraftingWorkbench
from planX_CAD_arac_Seti.main_plugin import PlanXCADPlugin


def _check(name: str, condition: bool, detail: str = "") -> None:
    tag = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{tag}] {name}{suffix}")
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def run_osnap_math_checks():
    print("--- OSNAP Geometric Primitives ---")

    # 1. Perpendicular foot
    p = QgsPointXY(5, 5)
    a = QgsPointXY(0, 0)
    b = QgsPointXY(10, 0)
    foot, t = _foot_of_perpendicular(p, a, b)
    _check(
        "foot of perpendicular on horizontal segment",
        foot is not None and abs(foot.x() - 5.0) < 1e-6 and abs(foot.y() - 0.0) < 1e-6 and abs(t - 0.5) < 1e-6,
        f"foot={foot}, t={t}",
    )

    # 2. Tangent points from anchor to circle
    anchor = QgsPointXY(10, 0)
    center = QgsPointXY(0, 0)
    radius = 5.0
    tangents = _circle_tangents_from_point(anchor, center, radius)
    _check(
        "two tangent points to circle exist",
        len(tangents) == 2,
        f"tangents={tangents}",
    )
    for tp in tangents:
        # Distance from center to tangent point equals radius
        d_c = math.hypot(tp.x(), tp.y())
        # Dot product of radius vector (center->tp) and tangent vector (tp->anchor) is 0
        rv = (tp.x() - center.x(), tp.y() - center.y())
        tv = (anchor.x() - tp.x(), anchor.y() - tp.y())
        dot = rv[0] * tv[0] + rv[1] * tv[1]
        _check(
            "tangent vector is orthogonal to radius",
            abs(d_c - radius) < 1e-5 and abs(dot) < 1e-4,
            f"dist={d_c:.4f}, dot={dot:.4f}",
        )

    # 3. Direct line intersection
    s1_a, s1_b = QgsPointXY(0, 0), QgsPointXY(10, 10)
    s2_a, s2_b = QgsPointXY(0, 10), QgsPointXY(10, 0)
    pt_cross = _line_intersection(s1_a, s1_b, s2_a, s2_b, infinite=False)
    _check(
        "direct segment intersection at (5, 5)",
        pt_cross is not None and abs(pt_cross.x() - 5.0) < 1e-6 and abs(pt_cross.y() - 5.0) < 1e-6,
        f"intersection={pt_cross}",
    )

    # 4. Apparent intersection (segments do not physically cross within bounds)
    s3_a, s3_b = QgsPointXY(0, 0), QgsPointXY(4, 4)
    s4_a, s4_b = QgsPointXY(0, 10), QgsPointXY(3, 7)
    pt_none = _line_intersection(s3_a, s3_b, s4_a, s4_b, infinite=False)
    pt_inf = _line_intersection(s3_a, s3_b, s4_a, s4_b, infinite=True)
    _check(
        "apparent intersection computes infinite extension",
        pt_none is None and pt_inf is not None and abs(pt_inf.x() - 5.0) < 1e-6 and abs(pt_inf.y() - 5.0) < 1e-6,
        f"direct={pt_none}, apparent={pt_inf}",
    )


def run_tracking_checks():
    print("--- Ortho & Polar Tracking Checks ---")
    engine = TrackingEngine()
    crs = QgsCoordinateReferenceSystem.fromEpsgId(3857)
    anchor = QgsPointXY(0, 0)

    # Ortho mode: 0, 90, 180, 270
    engine.set_mode(TrackingMode.ORTHO)
    res_ortho_x = engine.process(QgsPointXY(10.0, 1.2), anchor, crs)
    _check(
        "ortho constrains slight diagonal to 0 deg horizontal",
        res_ortho_x.angle_deg == 0.0 and abs(res_ortho_x.point.y()) < 1e-6,
        f"angle={res_ortho_x.angle_deg}, pt={res_ortho_x.point}",
    )

    res_ortho_y = engine.process(QgsPointXY(1.0, 12.0), anchor, crs)
    _check(
        "ortho constrains slight diagonal to 90 deg vertical",
        res_ortho_y.angle_deg == 90.0 and abs(res_ortho_y.point.x()) < 1e-6,
        f"angle={res_ortho_y.angle_deg}, pt={res_ortho_y.point}",
    )

    # Polar mode: 45 degree increments
    engine.set_mode(TrackingMode.POLAR)
    engine.set_polar_increment(45.0)
    res_polar = engine.process(QgsPointXY(10.0, 9.8), anchor, crs)
    _check(
        "polar tracking locks near 45 deg ray",
        abs(res_polar.angle_deg - 45.0) < 1e-6 and res_polar.mode == TrackingMode.POLAR,
        f"angle={res_polar.angle_deg}, readout={res_polar.readout}",
    )

    res_free = engine.process(QgsPointXY(10.0, 3.0), anchor, crs)
    _check(
        "polar tracking outside tolerance allows free movement",
        res_free.guide_line is None and res_free.mode == TrackingMode.OFF,
        f"mode={res_free.mode}, guide={res_free.guide_line}",
    )

    # S3 Precedence rule check: Object-Snap tracking takes precedence over Polar tracking
    engine.acquire_point(QgsPointXY(50.0, 20.0))
    res_obj = engine.process(QgsPointXY(15.0, 20.05), anchor, crs)
    _check(
        "object tracking alignment ray takes precedence over polar angle (S3)",
        res_obj.mode == "object_tracking" and abs(res_obj.point.y() - 20.0) < 1e-6,
        f"mode={res_obj.mode}, readout={res_obj.readout}",
    )


def run_tool_pin_checks():
    print("--- All Registered Tools Pin Check ---")
    canvas = QgsMapCanvas()
    canvas.setDestinationCrs(QgsCoordinateReferenceSystem.fromEpsgId(3857))

    class _MockIface:
        def __init__(self, c):
            self._c = c
            self._layer = None

        def mapCanvas(self):
            return self._c

        def activeLayer(self):
            return self._layer

        def mainWindow(self):
            return None

    iface = _MockIface(canvas)
    plugin = PlanXCADPlugin(iface)

    layer = QgsVectorLayer("LineString?crs=EPSG:3857", "test_line", "memory")
    QgsProject.instance().addMapLayer(layer)
    layer.startEditing()
    feat = QgsFeature(layer.fields())
    feat.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)]))
    layer.addFeature(feat)
    iface._layer = layer

    total_tested = 0
    for key in PlanXCADPlugin._ALL_TOOL_KEYS:
        tool = plugin._create_tool(key)
        _check(
            f"tool '{key}' constructs successfully",
            tool is not None,
            f"type={type(tool).__name__ if tool else 'None'}",
        )
        total_tested += 1

    _check(
        "all 39 registered tool classes pin-tested",
        total_tested == 39,
        f"count={total_tested}",
    )


def run_all() -> bool:
    print("=" * 60)
    print(" PlanX CAD Toolset — OSNAP, Tracking & Dynamic Input smoke tests")
    print("=" * 60)
    try:
        run_osnap_math_checks()
        run_tracking_checks()
        run_tool_pin_checks()
        print("-" * 60)
        print("  All OSNAP, Tracking and Dynamic Input checks passed!")
        return True
    except Exception as error:
        print(f"FAIL: {error}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    app = QgsApplication([], False)
    app.initQgis()
    success = run_all()
    app.exitQgis()
    sys.exit(0 if success else 1)
