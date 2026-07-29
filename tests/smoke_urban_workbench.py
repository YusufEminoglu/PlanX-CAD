"""Focused QGIS-runtime smoke tests for the urban workbench.

Run with an OSGeo/QGIS Python launcher, for example:

    C:\\OSGeo4W\\bin\\python-qgis-ltr.bat tests\\smoke_urban_workbench.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_PARENT))

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapCanvas  # noqa: E402

from planX_CAD_arac_Seti.urban.ada_kirma_sketcher import (  # noqa: E402
    AdaKirmaSketcher,
)
from planX_CAD_arac_Seti.urban.junction_sketcher import (  # noqa: E402
    JunctionSketcher,
)
from planX_CAD_arac_Seti.urban.road_generator import RoadGenerator  # noqa: E402
from planX_CAD_arac_Seti.core.sketcher_layer_utils import (  # noqa: E402
    get_road_platform_layer,
    road_attribute,
)
from planX_CAD_arac_Seti.urban.crs_utils import (  # noqa: E402
    local_metric_crs,
    transform_geometry,
)


class _MessageBar:
    def pushSuccess(self, *_args):
        pass

    def pushWarning(self, *_args):
        pass


class _Iface:
    def __init__(self, canvas):
        self._canvas = canvas
        self._message_bar = _MessageBar()

    def mapCanvas(self):
        return self._canvas

    def messageBar(self):
        return self._message_bar

    def mainWindow(self):
        return None


def _check(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}{' — ' + detail if detail else ''}")
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def _first_point(geometry):
    if geometry.isMultipart():
        return QgsPointXY(geometry.asMultiPolyline()[0][0])
    return QgsPointXY(geometry.asPolyline()[0])


def _line_endpoints(geometry):
    lines = geometry.asMultiPolyline() if geometry.isMultipart() else [
        geometry.asPolyline()
    ]
    return [
        QgsPointXY(point)
        for line in lines if line
        for point in (line[0], line[-1])
    ]


def _road_params():
    return {
        "road_type": "Test road",
        "one_way": False,
        "lane_count": 2,
        "lane_width": 3.5,
        "median_width": 2.0,
        "left_sidewalk": 2.0,
        "right_sidewalk": 2.0,
        "total_width": 20.0,
    }


def _generate_cross(iface):
    generator = RoadGenerator(iface)
    horizontal = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1400, 38.4200),
        QgsPointXY(27.1410, 38.4200),
    ])
    vertical = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1405, 38.4195),
        QgsPointXY(27.1405, 38.4205),
    ])
    _check("cross horizontal generated", generator.generate(
        horizontal, _road_params()
    ) == 9)
    _check("cross vertical generated", generator.generate(
        vertical, _road_params()
    ) == 9)
    return QgsProject.instance().mapLayersByName("planx_road_platform")[0]


def _assert_connections_are_gap_free(layer, component, expected_count):
    center = QgsPointXY(27.1405, 38.4200)
    metric_crs = local_metric_crs(center, layer.crs())
    curb_endpoints = []
    connections = []
    for feature in layer.getFeatures():
        geometry = transform_geometry(feature.geometry(), layer.crs(), metric_crs)
        if road_attribute(layer, feature, "component") == "sidewalk":
            curb_endpoints.extend(_line_endpoints(geometry))
        elif road_attribute(layer, feature, "component") == component:
            connections.append(geometry)

    _check(
        f"{component} connection count",
        len(connections) == expected_count,
        f"count={len(connections)}",
    )
    gaps = []
    for connection in connections:
        for endpoint in _line_endpoints(connection):
            gaps.append(min(endpoint.distance(curb) for curb in curb_endpoints))
    _check(
        f"{component} endpoints match trimmed curbs",
        gaps and max(gaps) < 0.02,
        f"max_gap={max(gaps) if gaps else float('inf'):.6f}m",
    )
    return connections


def test_geographic_road_generation_and_edit_lifecycle(iface):
    project = QgsProject.instance()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    project.setCrs(geographic)
    iface.mapCanvas().setDestinationCrs(geographic)

    params = _road_params()
    center = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1400, 38.4200),
        QgsPointXY(27.1410, 38.4200),
    ])
    generator = RoadGenerator(iface)
    count = generator.generate(center, params)
    layer = project.mapLayersByName("planx_road_platform")[0]

    _check("road component count", count == 9, f"count={count}")
    _check(
        "road output keeps MultiLineString layer type",
        all(feature.geometry().isMultipart() for feature in layer.getFeatures()),
    )

    sidewalks = [
        feature for feature in layer.getFeatures()
        if road_attribute(layer, feature, "component") == "sidewalk"
    ]
    distance_area = QgsDistanceArea()
    distance_area.setSourceCrs(geographic, project.transformContext())
    distance_area.setEllipsoid("WGS84")
    separation = distance_area.measureLine(
        _first_point(sidewalks[0].geometry()),
        _first_point(sidewalks[1].geometry()),
    )
    _check(
        "metre widths are correct in geographic CRS",
        19.0 < separation < 21.0,
        f"sidewalk separation={separation:.3f}m",
    )

    before = layer.featureCount()
    layer.startEditing()
    second_count = generator.generate(center, params)
    _check("generator preserves open edit session", layer.isEditable())
    _check("second road generated", second_count == 9, f"count={second_count}")
    layer.rollBack()
    _check(
        "rollback still belongs to caller",
        layer.featureCount() == before,
        f"before={before}, after={layer.featureCount()}",
    )
    return layer


def test_precise_multipart_trim(canvas, iface):
    sketcher = AdaKirmaSketcher(canvas, iface)
    u_line = QgsGeometry.fromPolylineXY([
        QgsPointXY(0, 0), QgsPointXY(10, 0),
        QgsPointXY(10, 10), QgsPointXY(0, 10),
    ])
    trimmed, cut = sketcher._trim_line_from_point(
        u_line, QgsPointXY(0, 0), 25.0
    )
    _check("bent line cut point", cut.distance(QgsPointXY(5, 10)) < 1e-9)
    _check(
        "bent line uses along-line distance",
        abs(trimmed.length() - 5.0) < 1e-9,
        f"length={trimmed.length():.6f}",
    )

    multi = QgsGeometry.fromMultiPolylineXY([
        [QgsPointXY(0, 0), QgsPointXY(10, 0)],
        [QgsPointXY(100, 0), QgsPointXY(110, 0)],
    ])
    trimmed_multi, _ = sketcher._trim_line_from_point(
        multi, QgsPointXY(0, 0), 2.0
    )
    parts = trimmed_multi.asMultiPolyline()
    _check("multipart trim preserves both parts", len(parts) == 2)
    _check(
        "multipart trim leaves unrelated part untouched",
        QgsPointXY(parts[1][0]).distance(QgsPointXY(100, 0)) < 1e-9
        and QgsPointXY(parts[1][-1]).distance(QgsPointXY(110, 0)) < 1e-9,
    )


def test_teardrop_geometry(canvas, iface):
    sketcher = JunctionSketcher(canvas, iface)
    center = QgsPointXY(0, 0)
    short = sketcher._create_teardrop(center, 3.0, 6.0, (1.0, 0.0))
    long = sketcher._create_teardrop(center, 3.0, 12.0, (1.0, 0.0))
    _check("teardrop is valid", short.isGeosValid() and long.isGeosValid())
    _check(
        "teardrop length changes usable island area",
        long.area() > short.area() + 15.0,
        f"short={short.area():.3f}, long={long.area():.3f}",
    )
    _check(
        "teardrop nose follows selected approach",
        abs(long.boundingBox().xMaximum() - 12.0) < 1e-9,
    )


def test_junction_does_not_touch_unrelated_layers(canvas, iface, road_layer):
    original_roads = {
        feature.id(): feature.geometry().asWkb()
        for feature in road_layer.getFeatures()
    }
    single_road_sketcher = JunctionSketcher(canvas, iface)
    single_road_sketcher.params = {
        "radius": 12.0,
        "corner_mode": "chamfer",
        "chamfer_dist": 5.0,
        "fillet_radius": 3.0,
        "island_type": "none",
        "island_radius": 3.0,
        "teardrop_length": 6.0,
    }
    single_road_sketcher._create_junction(QgsPointXY(27.1405, 38.4200))
    after_single_road = {
        feature.id(): feature.geometry().asWkb()
        for feature in road_layer.getFeatures()
    }
    _check(
        "single-road junction attempt is a destructive no-op",
        after_single_road == original_roads and not road_layer.isEditable(),
    )

    vertical = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1405, 38.4195),
        QgsPointXY(27.1405, 38.4205),
    ])
    _check(
        "crossing road generated for chamfer integration",
        RoadGenerator(iface).generate(vertical, _road_params()) == 9,
    )
    unrelated = QgsVectorLayer(
        "LineString?crs=EPSG:4326", "unrelated_user_lines", "memory"
    )
    feature = QgsFeature(unrelated.fields())
    original = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1404, 38.4195),
        QgsPointXY(27.1404, 38.4205),
    ])
    feature.setGeometry(original)
    unrelated.dataProvider().addFeature(feature)
    QgsProject.instance().addMapLayer(unrelated)

    sketcher = JunctionSketcher(canvas, iface)
    sketcher.params = {
        "radius": 12.0,
        "corner_mode": "chamfer",
        "chamfer_dist": 5.0,
        "fillet_radius": 3.0,
        "island_type": "round",
        "island_radius": 3.0,
        "teardrop_length": 6.0,
    }
    sketcher._create_junction(QgsPointXY(27.1405, 38.4200))

    after = next(unrelated.getFeatures()).geometry()
    exact_equal = (
        after.isExactlyEqual(original)
        if hasattr(after, "isExactlyEqual")
        else after.equals(original)
    )
    _check("junction leaves unrelated line layers unchanged", exact_equal)
    _check("junction does not open unrelated layer editing", not unrelated.isEditable())
    _check("junction closes plugin-started road edit", not road_layer.isEditable())
    connections = _assert_connections_are_gap_free(
        road_layer, "junction_chamfer", 4
    )
    lengths = [connection.length() for connection in connections]
    _check(
        "5m chamfer geometry is deterministic",
        all(7.0 < length < 7.2 for length in lengths),
        f"lengths={lengths}",
    )
    metric_crs = local_metric_crs(
        QgsPointXY(27.1405, 38.4200), road_layer.crs()
    )
    refuge_caps = [
        transform_geometry(feature.geometry(), road_layer.crs(), metric_crs)
        for feature in road_layer.getFeatures()
        if road_attribute(road_layer, feature, "component") == "median_connection"
    ]
    _check(
        "round junction closes every directional refuge arm",
        len(refuge_caps) == 4,
        f"count={len(refuge_caps)}",
    )
    _check(
        "refuge caps stay local",
        all(1.9 < geometry.length() < 2.1 for geometry in refuge_caps),
        f"lengths={[geometry.length() for geometry in refuge_caps]}",
    )
    island_layer = QgsProject.instance().mapLayersByName(
        "planx_junction_islands"
    )[0]
    _check("round junction creates one island", island_layer.featureCount() == 1)


def test_fillet_junction_integration(canvas, iface):
    project = QgsProject.instance()
    project.clear()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)
    road_layer = _generate_cross(iface)

    sketcher = JunctionSketcher(canvas, iface)
    sketcher.params = {
        "radius": 12.0,
        "corner_mode": "fillet",
        "chamfer_dist": 5.0,
        "fillet_radius": 3.0,
        "island_type": "none",
        "island_radius": 3.0,
        "teardrop_length": 6.0,
    }
    sketcher._create_junction(QgsPointXY(27.1405, 38.4200))

    connections = _assert_connections_are_gap_free(
        road_layer, "junction_fillet", 4
    )
    lengths = [connection.length() for connection in connections]
    _check(
        "3m fillet arcs have quarter-circle length",
        all(4.65 < length < 4.80 for length in lengths),
        f"lengths={lengths}",
    )
    _check(
        "fillet mode does not emit chamfer components",
        not any(
            road_attribute(road_layer, feature, "component") ==
            "junction_chamfer"
            for feature in road_layer.getFeatures()
        ),
    )
    _check("fillet junction closes plugin-started edit", not road_layer.isEditable())


def _road_snapshot(layer):
    return {
        feature.id(): (feature.geometry().asWkb(), tuple(feature.attributes()))
        for feature in layer.getFeatures()
    }


def _junction_params(island="none"):
    return {
        "radius": 12.0,
        "corner_mode": "chamfer",
        "chamfer_dist": 5.0,
        "fillet_radius": 3.0,
        "island_type": island,
        "island_radius": 3.0,
        "teardrop_length": 6.0,
    }


def test_junction_failure_rollback(canvas, iface):
    project = QgsProject.instance()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)

    project.clear()
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)
    road_layer = _generate_cross(iface)
    before = _road_snapshot(road_layer)
    sketcher = JunctionSketcher(canvas, iface)
    sketcher.params = _junction_params()
    original_trim = sketcher._annular_trim_parts
    call_count = {"value": 0}

    def fail_after_first_write(*args):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("injected geometry failure")
        return original_trim(*args)

    sketcher._annular_trim_parts = fail_after_first_write
    sketcher._create_junction(QgsPointXY(27.1405, 38.4200))
    _check(
        "exception rolls back partial road command",
        _road_snapshot(road_layer) == before and not road_layer.isEditable(),
    )

    project.clear()
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)
    road_layer = _generate_cross(iface)
    before = _road_snapshot(road_layer)
    road_layer.startEditing()
    sketcher = JunctionSketcher(canvas, iface)
    sketcher.params = _junction_params("round")
    sketcher._create_junction(QgsPointXY(27.1405, 38.4200))
    island_layer = project.mapLayersByName("planx_junction_islands")[0]
    _check(
        "island junction refuses mixed user edit ownership",
        _road_snapshot(road_layer) == before
        and road_layer.isEditable()
        and island_layer.featureCount() == 0,
    )
    road_layer.rollBack()

    project.clear()
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)
    road_layer = _generate_cross(iface)
    before = _road_snapshot(road_layer)
    setup_sketcher = JunctionSketcher(canvas, iface)
    island_layer = setup_sketcher._get_junction_island_layer()
    existing_island = QgsFeature(island_layer.fields())
    existing_island.setGeometry(
        QgsGeometry.fromPointXY(QgsPointXY(27.1405, 38.4200)).buffer(
            0.00001, 8
        )
    )
    existing_island.setAttribute("junction_id", 3)
    existing_island.setAttribute("island_type", "existing")
    existing_island.setAttribute("island_radius", 1.0)
    island_layer.dataProvider().addFeature(existing_island)
    original_commit = road_layer.commitChanges
    road_layer.commitChanges = lambda: False
    try:
        sketcher = JunctionSketcher(canvas, iface)
        sketcher.params = _junction_params("round")
        sketcher._create_junction(QgsPointXY(27.1405, 38.4200))
    finally:
        road_layer.commitChanges = original_commit
    island_layer = project.mapLayersByName("planx_junction_islands")[0]
    remaining_islands = list(island_layer.getFeatures())
    _check(
        "road commit failure compensates committed island",
        _road_snapshot(road_layer) == before
        and not road_layer.isEditable()
        and len(remaining_islands) == 1
        and remaining_islands[0]["island_type"] == "existing",
    )


def test_legacy_schema_compatibility(canvas, iface):
    """Pre-1.26 project layers remain writable without duplicate outputs."""
    project = QgsProject.instance()
    project.clear()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)

    legacy_road = QgsVectorLayer(
        "MultiLineString?crs=EPSG:4326"
        "&field=yol_id:integer&field=yol_tipi:string&field=bilesen:string"
        "&field=taraf:string&field=serit_no:integer"
        "&field=serit_sayisi:integer&field=serit_genisligi:double"
        "&field=refuj_genislik:double&field=kaldirim_genislik:double"
        "&field=toplam_genislik:double&field=gorunur:integer",
        "planx_yol_platformu", "memory"
    )
    project.addMapLayer(legacy_road)

    # Saved projects commonly change their project CRS while managed output
    # layers retain their original, valid layer CRS.
    project.setCrs(QgsCoordinateReferenceSystem.fromEpsgId(3857))

    resolved = get_road_platform_layer()
    _check(
        "legacy road layer is reused after a project-CRS change",
        resolved.id() == legacy_road.id(),
    )
    center = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1400, 38.4200),
        QgsPointXY(27.1410, 38.4200),
    ])
    count = RoadGenerator(iface).generate(center, _road_params())
    _check("legacy road schema remains writable", count == 9)
    _check(
        "legacy road values remain compatible",
        any(
            feature["bilesen"] == "kaldirim"
            and road_attribute(legacy_road, feature, "component") == "sidewalk"
            for feature in legacy_road.getFeatures()
        ),
    )
    _check(
        "English road layer is not duplicated over legacy data",
        not project.mapLayersByName("planx_road_platform"),
    )

    legacy_islands = QgsVectorLayer(
        "Polygon?crs=EPSG:4326&field=kavsak_id:integer"
        "&field=ada_tipi:string&field=ada_radius:double",
        "kavsak_ada", "memory"
    )
    project.addMapLayer(legacy_islands)
    resolved_islands = JunctionSketcher(
        canvas, iface
    )._get_junction_island_layer()
    _check(
        "legacy junction-island layer is reused after a project-CRS change",
        resolved_islands.id() == legacy_islands.id(),
    )
    _check(
        "English island layer is not duplicated over legacy data",
        not project.mapLayersByName("planx_junction_islands"),
    )


def run_all():
    profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-test-")
    app = QgsApplication([], False, profile_dir.name, "external")
    app.initQgis()
    project = QgsProject.instance()
    project.clear()
    canvas = QgsMapCanvas()
    iface = _Iface(canvas)
    try:
        road_layer = test_geographic_road_generation_and_edit_lifecycle(iface)
        test_precise_multipart_trim(canvas, iface)
        test_teardrop_geometry(canvas, iface)
        test_junction_does_not_touch_unrelated_layers(canvas, iface, road_layer)
        test_fillet_junction_integration(canvas, iface)
        test_junction_failure_rollback(canvas, iface)
        test_legacy_schema_compatibility(canvas, iface)
        print("  All urban workbench runtime checks passed")
        return True
    finally:
        project.clear()
        app.exitQgis()
        profile_dir.cleanup()


if __name__ == "__main__":
    try:
        run_all()
    except Exception as error:
        print(f"  [FAIL] {type(error).__name__}: {error}")
        raise
