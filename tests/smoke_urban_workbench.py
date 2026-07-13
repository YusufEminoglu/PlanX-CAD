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


class _MessageBar:
    def pushSuccess(self, *_args):
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


def test_geographic_road_generation_and_edit_lifecycle(iface):
    project = QgsProject.instance()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    project.setCrs(geographic)
    iface.mapCanvas().setDestinationCrs(geographic)

    params = {
        "yol_tipi": "Test road",
        "tek_yon": False,
        "serit_sayisi": 2,
        "serit_genisligi": 3.5,
        "refuj_genislik": 2.0,
        "sol_kaldirim": 2.0,
        "sag_kaldirim": 2.0,
        "toplam_genislik": 20.0,
    }
    center = QgsGeometry.fromPolylineXY([
        QgsPointXY(27.1400, 38.4200),
        QgsPointXY(27.1410, 38.4200),
    ])
    generator = RoadGenerator(iface)
    count = generator.generate(center, params)
    layer = project.mapLayersByName("planx_yol_platformu")[0]

    _check("road component count", count == 9, f"count={count}")
    _check(
        "road output keeps MultiLineString layer type",
        all(feature.geometry().isMultipart() for feature in layer.getFeatures()),
    )

    sidewalks = [
        feature for feature in layer.getFeatures()
        if feature["bilesen"] == "kaldirim"
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


def test_junction_does_not_touch_unrelated_layers(canvas, iface, road_layer):
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
        "chamfer_dist": 5.0,
        "fillet_radius": 3.0,
        "ada_tipi": "yok",
        "ada_radius": 3.0,
        "teardrop_uzunluk": 6.0,
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
        test_junction_does_not_touch_unrelated_layers(canvas, iface, road_layer)
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
