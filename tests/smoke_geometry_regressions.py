"""Focused QGIS-runtime regression checks for CAD geometry/edit helpers.

Run from the plugins parent directory with a QGIS Python launcher:

    python-qgis.bat -m planX_CAD_arac_Seti.tests.smoke_geometry_regressions
"""

import importlib
import pkgutil
import sys
import tempfile
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)


PLUGIN_PARENT = Path(__file__).resolve().parents[2]
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))


def _ok(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}{(' — ' + detail) if detail else ''}")
    return condition


def test_extend_reaches_distant_boundary():
    from planX_CAD_arac_Seti.core.sketcher_utils import extend_geometry_to_boundary

    target = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)])
    boundary = QgsGeometry.fromPolylineXY(
        [QgsPointXY(100, -5), QgsPointXY(100, 5)]
    )
    result = extend_geometry_to_boundary(target, boundary)
    endpoint = result.asPolyline()[-1] if result else None
    return _ok(
        "extend reaches boundary beyond old 10x limit",
        endpoint is not None and abs(endpoint.x() - 100.0) < 1e-8,
        result.asWkt() if result else "None",
    )


def test_extend_never_chooses_boundary_behind_endpoint():
    from planX_CAD_arac_Seti.core.sketcher_utils import extend_geometry_to_boundary

    target = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)])
    boundaries = QgsGeometry.fromMultiPolylineXY([
        [QgsPointXY(-2, -5), QgsPointXY(-2, 5)],
        [QgsPointXY(10, -5), QgsPointXY(10, 5)],
    ])
    result = extend_geometry_to_boundary(target, boundaries)
    endpoint = result.asPolyline()[-1] if result else None
    return _ok(
        "extend ignores intersections behind endpoint",
        endpoint is not None and abs(endpoint.x() - 10.0) < 1e-8,
        result.asWkt() if result else "None",
    )


def test_offset_uses_cross_version_join_enum():
    from planX_CAD_arac_Seti.core.sketcher_utils import offset_geometry

    source = QgsGeometry.fromPolylineXY(
        [QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10)]
    )
    result = offset_geometry(source, 2.0, "left")
    return _ok(
        "offset join style works in this QGIS runtime",
        result is not None and not result.isEmpty(),
        result.asWkt() if result else "None",
    )


def test_affine_transforms_preserve_curves_and_zm():
    from planX_CAD_arac_Seti.core.sketcher_utils import (
        mirror_geometry,
        scale_geometry,
    )

    wkts = (
        "CompoundCurve ZM ("
        "CircularString ZM (0 0 1 10, 5 5 2 20, 10 0 3 30),"
        "(10 0 3 30, 15 0 4 40))",
        "CurvePolygon ZM ("
        "CircularString ZM (0 0 1 10, 5 5 2 20, 10 0 3 30, "
        "5 -5 4 40, 0 0 1 10))",
    )
    failures = []
    center = QgsPointXY(2.0, -3.0)

    for wkt in wkts:
        source = QgsGeometry.fromWkt(wkt)
        source_vertices = list(source.vertices())
        expected_zm = [(point.z(), point.m()) for point in source_vertices]
        transformed = (
            (
                "scale",
                scale_geometry(source, center, 2.0),
                lambda point: (
                    center.x() + (point.x() - center.x()) * 2.0,
                    center.y() + (point.y() - center.y()) * 2.0,
                ),
            ),
            (
                "mirror",
                mirror_geometry(
                    source, QgsPointXY(0, 0), QgsPointXY(0, 10)
                ),
                lambda point: (-point.x(), point.y()),
            ),
        )
        for name, result, expected_xy in transformed:
            if result is None:
                failures.append(f"{name} returned None for {source.wkbType()}")
                continue
            result_vertices = list(result.vertices())
            actual_zm = [(point.z(), point.m()) for point in result_vertices]
            actual_xy = [(point.x(), point.y()) for point in result_vertices]
            wanted_xy = [expected_xy(point) for point in source_vertices]
            xy_matches = len(actual_xy) == len(wanted_xy) and all(
                abs(actual[0] - wanted[0]) < 1e-9
                and abs(actual[1] - wanted[1]) < 1e-9
                for actual, wanted in zip(actual_xy, wanted_xy)
            )
            if not (
                result.wkbType() == source.wkbType()
                and result.constGet().hasCurvedSegments()
                and actual_zm == expected_zm
                and xy_matches
            ):
                failures.append(
                    f"{name} changed type/curve/ZM/XY for {source.wkbType()}"
                )

    invalid_axis = mirror_geometry(
        QgsGeometry.fromWkt(wkts[0]), QgsPointXY(1, 1), QgsPointXY(1, 1)
    )
    if invalid_axis is not None:
        failures.append("zero-length mirror axis was accepted")

    return _ok(
        "scale/mirror preserve curved WKB and Z/M",
        not failures,
        "; ".join(failures),
    )


def test_rotate_and_mirror_are_metric_safe_in_geographic_crs():
    from planX_CAD_arac_Seti.core.crs_utils import (
        local_metric_crs,
        transform_geometry,
        transform_point,
    )
    from planX_CAD_arac_Seti.core.sketcher_utils import (
        mirror_geometry,
        rotate_geometry,
    )

    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    center = QgsPointXY(20.0, 60.0)
    metric = local_metric_crs(center, geographic)
    metric_center = transform_point(center, geographic, metric)
    cx, cy = metric_center.x(), metric_center.y()
    source_metric = QgsGeometry.fromPolylineXY([
        QgsPointXY(cx + 100.0, cy),
        QgsPointXY(cx, cy),
        QgsPointXY(cx, cy + 100.0),
    ])
    source = transform_geometry(source_metric, metric, geographic)
    axis_end = transform_point(
        QgsPointXY(cx, cy + 100.0), metric, geographic
    )

    rotated = rotate_geometry(source, center, 90.0, geographic)
    mirrored = mirror_geometry(source, center, axis_end, geographic)
    distance = QgsDistanceArea()
    distance.setSourceCrs(geographic, QgsProject.instance().transformContext())
    distance.setEllipsoid("WGS84")

    def segment_lengths(geometry):
        points = geometry.asPolyline()
        return [
            distance.measureLine(points[index], points[index + 1])
            for index in range(len(points) - 1)
        ]

    rotated_lengths = segment_lengths(rotated) if rotated else []
    mirrored_lengths = segment_lengths(mirrored) if mirrored else []
    lengths = rotated_lengths + mirrored_lengths

    curved = QgsGeometry.fromWkt(
        "CompoundCurve ZM (CircularString ZM ("
        "20 60 1 10, 20.001 60.001 2 20, 20.002 60 3 30))"
    )
    expected_zm = [(point.z(), point.m()) for point in curved.vertices()]
    curved_results = (
        rotate_geometry(curved, center, 90.0, geographic),
        mirror_geometry(curved, center, axis_end, geographic),
    )
    curves_preserved = all(
        result is not None
        and result.wkbType() == curved.wkbType()
        and result.constGet().hasCurvedSegments()
        and [(point.z(), point.m()) for point in result.vertices()] == expected_zm
        for result in curved_results
    )
    return _ok(
        "rotate/mirror preserve metric lengths and curved Z/M in geographic CRS",
        len(lengths) == 4
        and all(99.8 < value < 100.2 for value in lengths)
        and curves_preserved,
        f"lengths={[round(value, 3) for value in lengths]}",
    )


def test_same_name_incompatible_layer_is_not_reused():
    from planX_CAD_arac_Seti.core.sketcher_layer_utils import get_or_create_layer

    project = QgsProject.instance()
    name = "planx_regression_layer_collision"
    wrong = QgsVectorLayer("Point?crs=EPSG:3857", name, "memory")
    project.addMapLayer(wrong)
    try:
        result = get_or_create_layer(
            name,
            geom_type="LineString",
            crs=wrong.crs(),
            fields=[("kind", "string")],
        )
        return _ok(
            "same-name incompatible layer is not reused",
            result is not None and result.id() != wrong.id() and
            result.geometryType() != wrong.geometryType(),
        )
    finally:
        for layer in list(project.mapLayersByName(name)):
            project.removeMapLayer(layer.id())


def test_divide_preserves_all_multipart_components():
    from planX_CAD_arac_Seti.tools.tool_divide import tool_divide

    class _Messages:
        def emit(self, _message):
            pass

    class _FakeTool:
        tool_message = _Messages()

        @staticmethod
        def _part_metrics(part):
            return tool_divide._part_metrics(part)

    parts = [
        [QgsPointXY(0, 0), QgsPointXY(10, 0)],
        [QgsPointXY(100, 0), QgsPointXY(110, 0)],
    ]
    layer = QgsVectorLayer("MultiLineString?crs=EPSG:3857", "divide_test", "memory")
    layer.startEditing()
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromMultiPolylineXY(parts))
    layer.addFeature(feature)
    fake = _FakeTool()
    tool_divide._split_line(fake, layer, feature, parts, 2)
    output = [result.geometry() for result in layer.getFeatures()]
    return _ok(
        "divide preserves and splits every multipart component",
        len(output) == 4 and
        any(geometry.boundingBox().xMinimum() >= 100 for geometry in output),
        f"segments={len(output)}",
    )


def test_trim_splits_at_every_intersection():
    from planX_CAD_arac_Seti.tools.tool_trim import tool_trim

    line = QgsGeometry.fromPolylineXY(
        [QgsPointXY(0, 0), QgsPointXY(30, 0)]
    )
    parts = tool_trim._split_line_at_points(
        None, line, [QgsPointXY(10, 0), QgsPointXY(20, 0)]
    )
    lengths = sorted(round(part.length(), 8) for part in parts)
    return _ok(
        "trim applies every intersection split",
        len(parts) == 3 and lengths == [10.0, 10.0, 10.0],
        f"parts={len(parts)}, lengths={lengths}",
    )


def test_safe_add_feature_helper():
    from planX_CAD_arac_Seti.core.sketcher_layer_utils import add_feature_to_layer

    layer = QgsVectorLayer("LineString?crs=EPSG:3857&field=kind:string", "add_test", "memory")
    geometry = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 1)])
    feature = add_feature_to_layer(layer, geometry, {"kind": "regression"})
    return _ok(
        "safe add helper commits and reports success",
        feature is not None and layer.featureCount() == 1 and not layer.isEditable(),
    )


def test_batch_add_edit_helper():
    from planX_CAD_arac_Seti.tools.tool_base import tool_base

    class _Messages:
        def emit(self, _message):
            pass

    class _FakeTool:
        tool_message = _Messages()

        @staticmethod
        def tool_name():
            return "batch-test"

    layer = QgsVectorLayer("LineString?crs=EPSG:3857", "batch_test", "memory")
    geometries = [
        QgsGeometry.fromPolylineXY(
            [QgsPointXY(i, 0), QgsPointXY(i + 1, 0)]
        )
        for i in range(100)
    ]
    added = tool_base._add_features(_FakeTool(), layer, geometries)
    return _ok(
        "batch edit helper adds all features in one call",
        len(added) == 100 and layer.featureCount() == 100,
    )


def test_canvas_to_layer_add_does_not_mutate_input():
    from planX_CAD_arac_Seti.core.sketcher_layer_utils import add_geometry_to_current_layer

    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    layer = QgsVectorLayer("LineString?crs=EPSG:3857", "transform_test", "memory")
    geometry = QgsGeometry.fromPolylineXY(
        [QgsPointXY(0, 0), QgsPointXY(1, 0)]
    )

    class _Settings:
        @staticmethod
        def destinationCrs():
            return source_crs

    class _Canvas:
        @staticmethod
        def mapSettings():
            return _Settings()

    class _Iface:
        @staticmethod
        def activeLayer():
            return layer

        @staticmethod
        def mapCanvas():
            return _Canvas()

    success = add_geometry_to_current_layer(_Iface(), geometry)
    stored = next(layer.getFeatures()).geometry() if success else None
    original_end_x = geometry.asPolyline()[-1].x()
    stored_end_x = stored.asPolyline()[-1].x() if stored else 0
    return _ok(
        "canvas-to-layer add transforms a copy, not caller geometry",
        success and abs(original_end_x - 1.0) < 1e-12 and stored_end_x > 100_000,
        f"original_x={original_end_x:.3f}, stored_x={stored_end_x:.3f}",
    )


def test_all_scoped_modules_import():
    failures = []
    for package_name in (
        "planX_CAD_arac_Seti.core",
        "planX_CAD_arac_Seti.sketcher",
        "planX_CAD_arac_Seti.tools",
    ):
        package = importlib.import_module(package_name)
        for module_info in pkgutil.iter_modules(package.__path__):
            full_name = f"{package_name}.{module_info.name}"
            try:
                importlib.import_module(full_name)
            except Exception as exc:
                failures.append(f"{full_name}: {exc}")
    return _ok(
        "all core/sketcher/tools modules import",
        not failures,
        "; ".join(failures),
    )


def test_buffer_distance_is_meters_in_geographic_crs():
    from planX_CAD_arac_Seti.tools.tool_buffer import tool_buffer

    class _Messages:
        @staticmethod
        def emit(_message):
            pass

    class _FakeBuffer:
        distance = 5.0
        segments = 32
        join_style = 1
        tool_message = _Messages()

        @staticmethod
        def _reset():
            pass

    source = QgsVectorLayer("Point?crs=EPSG:4326", "buffer_source", "memory")
    feature = QgsFeature(source.fields())
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(27.14, 38.42)))
    tool_buffer.on_entity_selected(_FakeBuffer(), source, feature, None)
    output = QgsProject.instance().mapLayersByName("planx_buffer")[-1]
    output_feature = next(output.getFeatures())
    distance = QgsDistanceArea()
    distance.setSourceCrs(output.crs(), QgsProject.instance().transformContext())
    distance.setEllipsoid("WGS84")
    area = distance.measureArea(output_feature.geometry())
    return _ok(
        "buffer uses meters in geographic CRS",
        70.0 < area < 90.0,
        f"area={area:.2f} m2",
    )


def test_fillet_radius_is_meters_in_geographic_crs():
    from planX_CAD_arac_Seti.tools.tool_fillet import tool_fillet
    from planX_CAD_arac_Seti.urban.crs_utils import (
        local_metric_crs, transform_geometry, transform_point,
    )

    geographic = QgsCoordinateReferenceSystem("EPSG:4326")
    center = QgsPointXY(27.14, 38.42)
    metric = local_metric_crs(center, geographic)
    metric_center = transform_point(center, geographic, metric)
    x, y = metric_center.x(), metric_center.y()
    first_metric = QgsGeometry.fromPolylineXY([
        QgsPointXY(x - 20.0, y), QgsPointXY(x, y),
    ])
    second_metric = QgsGeometry.fromPolylineXY([
        QgsPointXY(x, y), QgsPointXY(x, y + 20.0),
    ])
    first = transform_geometry(first_metric, metric, geographic)
    second = transform_geometry(second_metric, metric, geographic)
    layer1 = QgsVectorLayer("LineString?crs=EPSG:4326", "fillet_a", "memory")
    layer2 = QgsVectorLayer("LineString?crs=EPSG:4326", "fillet_b", "memory")

    class _FakeFillet:
        radius = 5.0

    _metric_crs, result = tool_fillet._metric_fillet_result(
        _FakeFillet(), first, layer1, second, layer2
    )
    arc_length = result["arc"].length() if result else 0.0
    return _ok(
        "fillet uses meters in geographic CRS",
        7.5 < arc_length < 8.2,
        f"arc_length={arc_length:.3f} m",
    )


def run_all():
    print("=" * 60)
    print(" PlanX CAD — focused geometry regression checks")
    print("=" * 60)
    results = [
        test_extend_reaches_distant_boundary(),
        test_extend_never_chooses_boundary_behind_endpoint(),
        test_offset_uses_cross_version_join_enum(),
        test_affine_transforms_preserve_curves_and_zm(),
        test_rotate_and_mirror_are_metric_safe_in_geographic_crs(),
        test_same_name_incompatible_layer_is_not_reused(),
        test_divide_preserves_all_multipart_components(),
        test_trim_splits_at_every_intersection(),
        test_safe_add_feature_helper(),
        test_batch_add_edit_helper(),
        test_canvas_to_layer_add_does_not_mutate_input(),
        test_buffer_distance_is_meters_in_geographic_crs(),
        test_fillet_radius_is_meters_in_geographic_crs(),
        test_all_scoped_modules_import(),
    ]
    print("-" * 60)
    print(f"  {sum(bool(result) for result in results)}/{len(results)} passed")
    return all(results)


def _run_with_qgis_application():
    """Give GUI-backed QGIS classes a real application and isolated profile."""
    profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-test-")
    app = QgsApplication([], False, profile_dir.name, "external")
    app.initQgis()
    try:
        return run_all()
    finally:
        QgsProject.instance().clear()
        app.exitQgis()
        profile_dir.cleanup()


if __name__ == "__main__":
    sys.exit(0 if _run_with_qgis_application() else 1)
