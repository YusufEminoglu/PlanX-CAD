"""QGIS-runtime checks for AutoCAD-style precision input."""

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
)
from qgis.gui import QgsMapCanvas  # noqa: E402

from planX_CAD_arac_Seti.core.precision_input import (  # noqa: E402
    PrecisionInputError,
    parse_precision_input,
    resolve_precision_point,
)
from planX_CAD_arac_Seti.sketcher.sketcher_circle import sketcher_circle  # noqa: E402
from planX_CAD_arac_Seti.sketcher.sketcher_arc import sketcher_arc  # noqa: E402
from planX_CAD_arac_Seti.sketcher.sketcher_line import sketcher_line  # noqa: E402
from planX_CAD_arac_Seti.sketcher.sketcher_polyline import sketcher_polyline  # noqa: E402
from planX_CAD_arac_Seti.sketcher.sketcher_rectangle import sketcher_rectangle  # noqa: E402
from planX_CAD_arac_Seti.tools.tool_copy import tool_copy  # noqa: E402
from planX_CAD_arac_Seti.tools.tool_move import tool_move  # noqa: E402
from planX_CAD_arac_Seti.tools.tool_rotate import tool_rotate  # noqa: E402
from planX_CAD_arac_Seti.tools.tool_scale import tool_scale  # noqa: E402


class _MessageBar:
    def pushSuccess(self, *_args):
        pass

    def pushWarning(self, *_args):
        pass


class _Iface:
    def __init__(self, canvas):
        self._canvas = canvas
        self._active_layer = None
        self._message_bar = _MessageBar()

    def mapCanvas(self):
        return self._canvas

    def activeLayer(self):
        return self._active_layer

    def set_active_layer(self, layer):
        self._active_layer = layer

    def mainWindow(self):
        return None

    def messageBar(self):
        return self._message_bar


def _check(name, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    print(f"  [{tag}] {name}{' — ' + detail if detail else ''}")
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def _line_points(geometry):
    if geometry.isMultipart():
        return [QgsPointXY(point) for point in geometry.asMultiPolyline()[0]]
    return [QgsPointXY(point) for point in geometry.asPolyline()]


def test_parser_and_geographic_resolution():
    absolute = parse_precision_input(" 27.14 , 38.42 ")
    relative = parse_precision_input("@10,-5")
    polar = parse_precision_input("@100<90°")
    scalar = parse_precision_input("25")
    _check("absolute coordinate parses", absolute.kind == "absolute")
    _check("relative Cartesian parses", relative.kind == "relative_cartesian")
    _check("relative polar parses", polar.kind == "relative_polar")
    _check("direct distance parses", scalar.kind == "direct_distance")

    malformed = False
    try:
        parse_precision_input("@10<")
    except PrecisionInputError:
        malformed = True
    _check("malformed numeric input is rejected", malformed)

    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    base = QgsPointXY(27.14, 38.42)
    target = resolve_precision_point(polar, base, None, geographic)
    distance = QgsDistanceArea()
    distance.setSourceCrs(geographic, QgsProject.instance().transformContext())
    distance.setEllipsoid("WGS84")
    measured = distance.measureLine(base, target)
    _check(
        "relative polar distance is metres in EPSG:4326",
        99.5 < measured < 100.5,
        f"distance={measured:.3f}m",
    )

    for label, latitude in (("north", 85.0), ("south", -85.0)):
        polar_base = QgsPointXY(20.0, latitude)
        polar_target = resolve_precision_point(
            polar, polar_base, None, geographic
        )
        polar_measured = distance.measureLine(polar_base, polar_target)
        _check(
            f"relative distance remains metres near the {label} pole",
            99.99 < polar_measured < 100.01,
            f"distance={polar_measured:.3f}m",
        )


def test_drawing_tools(canvas, iface):
    project = QgsProject.instance()
    projected = QgsCoordinateReferenceSystem.fromEpsgId(32635)
    project.setCrs(projected)
    canvas.setDestinationCrs(projected)

    line_layer = QgsVectorLayer("LineString?crs=EPSG:32635", "precision_lines", "memory")
    project.addMapLayer(line_layer)
    iface.set_active_layer(line_layer)

    line_tool = sketcher_line(canvas, iface)
    line_tool.activate()
    _check("line accepts absolute point", line_tool.handle_precision_input("500000,4250000"))
    _check("line accepts relative point", line_tool.handle_precision_input("@10,0"))
    first_line = next(line_layer.getFeatures()).geometry()
    points = _line_points(first_line)
    _check(
        "line precision endpoints are exact",
        points[0].distance(QgsPointXY(500000, 4250000)) < 1e-7
        and points[-1].distance(QgsPointXY(500010, 4250000)) < 1e-7,
    )
    line_tool.deactivate()

    polyline_tool = sketcher_polyline(canvas, iface)
    polyline_tool.activate()
    polyline_tool.handle_precision_input("500100,4250000")
    polyline_tool.handle_precision_input("@10<0")
    polyline_tool.handle_precision_input("@10<90")
    polyline_tool._finish()
    polylines = list(line_layer.getFeatures())
    poly_points = _line_points(polylines[-1].geometry())
    _check(
        "polyline chains relative polar vertices",
        len(poly_points) == 3
        and poly_points[-1].distance(QgsPointXY(500110, 4250010)) < 1e-6,
    )
    polyline_tool.deactivate()

    invalid_tool = sketcher_line(canvas, iface)
    invalid_tool.activate()
    invalid_tool.handle_precision_input("500200,4250000")
    before = list(invalid_tool.vertices)
    _check("invalid precision text is consumed", invalid_tool.handle_precision_input("@bad"))
    _check("invalid input leaves sketch state unchanged", invalid_tool.vertices == before)
    invalid_tool.deactivate()

    distance_tool = sketcher_line(canvas, iface)
    distance_tool.activate()
    distance_tool.handle_precision_input("500200,4250000")
    distance_tool._last_cursor_point = QgsPointXY(500200, 4250010)
    _check(
        "line accepts distance along cursor bearing",
        distance_tool.handle_precision_input("5"),
    )
    distance_line = list(line_layer.getFeatures())[-1].geometry()
    distance_points = _line_points(distance_line)
    _check(
        "direct distance follows cursor bearing in metres",
        distance_points[-1].distance(QgsPointXY(500200, 4250005)) < 1e-7,
    )
    distance_tool.deactivate()


def test_geographic_shapes(canvas, iface):
    project = QgsProject.instance()
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    project.setCrs(geographic)
    canvas.setDestinationCrs(geographic)
    polygon_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "precision_polygons", "memory")
    project.addMapLayer(polygon_layer)
    iface.set_active_layer(polygon_layer)

    circle_tool = sketcher_circle(canvas, iface)
    circle_tool.activate()
    circle_tool.handle_precision_input("27.14,38.42")
    circle_tool.handle_precision_input("@5<0")
    circle = next(polygon_layer.getFeatures()).geometry()
    distance = QgsDistanceArea()
    distance.setSourceCrs(geographic, project.transformContext())
    distance.setEllipsoid("WGS84")
    area = distance.measureArea(circle)
    _check(
        "numeric circle radius remains five metres in EPSG:4326",
        77.5 < area < 79.5,
        f"area={area:.3f}m2",
    )
    circle_tool.deactivate()

    rectangle_tool = sketcher_rectangle(canvas, iface)
    rectangle_tool.activate()
    rectangle_tool.handle_precision_input("27.141,38.42")
    rectangle_tool.handle_precision_input("@10,10")
    polygons = list(polygon_layer.getFeatures())
    rectangle_area = distance.measureArea(polygons[-1].geometry())
    _check(
        "numeric geographic rectangle is metre-safe",
        99.0 < rectangle_area < 101.0,
        f"area={rectangle_area:.3f}m2",
    )
    rectangle_tool.deactivate()

    arc_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "precision_arcs", "memory")
    project.addMapLayer(arc_layer)
    iface.set_active_layer(arc_layer)
    arc_tool = sketcher_arc(canvas, iface)
    arc_tool.activate()
    arc_tool.handle_precision_input("27.142,38.42")
    arc_tool.handle_precision_input("@10,10")
    arc_tool.handle_precision_input("@10,-10")
    arc = next(arc_layer.getFeatures()).geometry()
    arc_length = distance.measureLength(arc)
    _check(
        "numeric geographic arc is constructed in a metric work CRS",
        31.0 < arc_length < 32.0,
        f"length={arc_length:.3f}m",
    )
    arc_tool.deactivate()


def test_move_and_copy(canvas, iface):
    project = QgsProject.instance()
    projected = QgsCoordinateReferenceSystem.fromEpsgId(32635)
    project.setCrs(projected)
    canvas.setDestinationCrs(projected)
    layer = QgsVectorLayer("LineString?crs=EPSG:32635", "precision_transform", "memory")
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(500000, 4250000), QgsPointXY(500005, 4250000)
    ]))
    layer.dataProvider().addFeature(feature)
    project.addMapLayer(layer)
    iface.set_active_layer(layer)

    source = next(layer.getFeatures())
    move_tool = tool_move(canvas, iface)
    move_tool.activate()
    move_tool.selected_layer = layer
    move_tool.selected_feature = source
    move_tool.base_point = QgsPointXY(500000, 4250000)
    move_tool._step = 2
    _check("move consumes relative precision", move_tool.handle_precision_input("@10,0"))
    moved = next(layer.getFeatures()).geometry()
    _check(
        "move applies exact metric displacement",
        _line_points(moved)[0].distance(QgsPointXY(500010, 4250000)) < 1e-7,
    )
    move_tool.deactivate()

    source = next(layer.getFeatures())
    copy_tool = tool_copy(canvas, iface)
    copy_tool.activate()
    copy_tool.selected_layer = layer
    copy_tool.selected_feature = source
    copy_tool.base_point = QgsPointXY(500010, 4250000)
    copy_tool._step = 2
    _check("copy consumes polar precision", copy_tool.handle_precision_input("@10<90"))
    features = list(layer.getFeatures())
    starts = sorted(round(_line_points(item.geometry())[0].y(), 6) for item in features)
    _check("copy applies exact polar displacement", starts == [4250000.0, 4250010.0])
    copy_tool.deactivate()


def test_rotate_and_scale(canvas, iface):
    project = QgsProject.instance()
    projected = QgsCoordinateReferenceSystem.fromEpsgId(32635)
    project.setCrs(projected)
    canvas.setDestinationCrs(projected)
    layer = QgsVectorLayer("LineString?crs=EPSG:32635", "precision_angle_scale", "memory")
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry.fromPolylineXY([
        QgsPointXY(500000, 4250000), QgsPointXY(500010, 4250000)
    ]))
    layer.dataProvider().addFeature(feature)
    project.addMapLayer(layer)
    iface.set_active_layer(layer)

    source = next(layer.getFeatures())
    rotate_tool = tool_rotate(canvas, iface)
    rotate_tool.activate()
    rotate_tool.selected_layer = layer
    rotate_tool.selected_feature = source
    rotate_tool.center = QgsPointXY(500000, 4250000)
    rotate_tool._step = 2
    _check("rotate accepts signed scalar degrees", rotate_tool.handle_precision_input("90"))
    rotated_points = _line_points(next(layer.getFeatures()).geometry())
    _check(
        "scalar rotation preserves radius and reaches perpendicular axis",
        abs(rotated_points[-1].x() - 500000) < 1e-7
        and abs(abs(rotated_points[-1].y() - 4250000) - 10) < 1e-7,
    )
    rotate_tool.deactivate()

    source = next(layer.getFeatures())
    scale_tool = tool_scale(canvas, iface)
    scale_tool.activate()
    scale_tool.selected_layer = layer
    scale_tool.selected_feature = source
    scale_tool.center = QgsPointXY(500000, 4250000)
    scale_tool._step = 2
    before = source.geometry().asWkb()
    _check("invalid zero scale is consumed", scale_tool.handle_precision_input("0"))
    _check("invalid scale leaves geometry unchanged", source.geometry().asWkb() == before)
    _check("scale accepts direct factor", scale_tool.handle_precision_input("2"))
    scaled = next(layer.getFeatures()).geometry()
    _check(
        "direct scale factor doubles geometry radius",
        abs(scaled.length() - 20.0) < 1e-7,
        f"length={scaled.length():.6f}",
    )
    scale_tool.deactivate()


def run_all():
    profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-precision-test-")
    app = QgsApplication([], False, profile_dir.name, "external")
    app.initQgis()
    project = QgsProject.instance()
    project.clear()
    canvas = QgsMapCanvas()
    iface = _Iface(canvas)
    try:
        test_parser_and_geographic_resolution()
        test_drawing_tools(canvas, iface)
        project.clear()
        test_geographic_shapes(canvas, iface)
        project.clear()
        test_move_and_copy(canvas, iface)
        project.clear()
        test_rotate_and_scale(canvas, iface)
        print("  All precision-input runtime checks passed")
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
