"""Headless QGIS runtime smoke checks for plugin lifecycle and workbench state.

Run from the plugins parent directory so the package import is realistic::

    python-qgis-ltr.bat -m planX_CAD_arac_Seti.tests.smoke_runtime
    python-qgis.bat -m planX_CAD_arac_Seti.tests.smoke_runtime
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.PyQt.QtCore import QObject, QSettings, Qt, pyqtSignal
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QAction, QMainWindow, QToolBar
from qgis.core import (
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.gui import QgsMapCanvas, QgsMapTool

from ..main_plugin import PlanXCADPlugin
from ..tools.tool_multi_offset import tool_multi_offset
from ..urban.junction_dialog import JunctionDialog


class _MessageBar:
    def pushSuccess(self, *_args, **_kwargs):
        return None

    def pushWarning(self, *_args, **_kwargs):
        return None


class _Iface(QObject):
    currentLayerChanged = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._window = QMainWindow()
        self._canvas = QgsMapCanvas(self._window)
        self._window.setCentralWidget(self._canvas)
        self._active_layer = None
        self._message_bar = _MessageBar()
        self._toggle_action = QAction("Toggle editing", self._window)

    def mainWindow(self):
        return self._window

    def mapCanvas(self):
        return self._canvas

    def activeLayer(self):
        return self._active_layer

    def set_active_layer(self, layer):
        self._active_layer = layer
        self.currentLayerChanged.emit(layer)

    def addToolBar(self, toolbar):
        self._window.addToolBar(toolbar)

    def addDockWidget(self, area, dock):
        self._window.addDockWidget(area, dock)

    def removeDockWidget(self, dock):
        self._window.removeDockWidget(dock)

    def actionToggleEditing(self):
        return self._toggle_action

    def messageBar(self):
        return self._message_bar


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _seed_layer(project, uri, name, geometries):
    """Create an editable memory layer preloaded with geometries."""
    layer = QgsVectorLayer(uri, name, "memory")
    project.addMapLayer(layer)
    layer.startEditing()
    for geometry in geometries:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        layer.addFeature(feature)
    return layer


def _modify_write_checks(iface, project):
    """Drive the 1.27 modify tools against real layers, bypassing dialogs.

    The tool classes own the layer writes (edit commands, part creation,
    managed output layers), so the geometry helpers passing is not enough.
    """
    from ..core.sketcher_utils import explode_geometry
    from ..tools.tool_align import tool_align
    from ..tools.tool_break import tool_break
    from ..tools.tool_chamfer import tool_chamfer
    from ..tools.tool_explode import tool_explode
    from ..tools.tool_stretch import tool_stretch

    canvas = iface.mapCanvas()
    checks = []
    line_uri = "LineString?crs=EPSG:3857"

    # Break splits the picked feature and adds the remainder.
    break_layer = _seed_layer(project, line_uri, "break_target", [
        QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)]),
    ])
    breaker = tool_break(canvas, iface)
    breaker.selected_layer = break_layer
    breaker.selected_feature = next(break_layer.getFeatures())
    breaker._step = 3
    breaker._apply_break(QgsPointXY(4, 0), None)
    lengths = sorted(round(f.geometry().length(), 6)
                     for f in break_layer.getFeatures())
    checks.append((
        "break tool writes both parts to the layer",
        break_layer.featureCount() == 2 and lengths == [4.0, 6.0],
    ))

    # Break with a gap keeps two parts and drops the span between the picks.
    gap_layer = _seed_layer(project, line_uri, "break_gap_target", [
        QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)]),
    ])
    gap_tool = tool_break(canvas, iface)
    gap_tool.selected_layer = gap_layer
    gap_tool.selected_feature = next(gap_layer.getFeatures())
    gap_tool._step = 3
    gap_tool._apply_break(QgsPointXY(3, 0), QgsPointXY(7, 0))
    gap_lengths = sorted(round(f.geometry().length(), 6)
                         for f in gap_layer.getFeatures())
    checks.append((
        "break tool with a gap removes the middle span",
        gap_layer.featureCount() == 2 and gap_lengths == [3.0, 3.0],
    ))

    # Chamfer trims both lines and adds the cut segment.
    chamfer_layer = _seed_layer(project, line_uri, "chamfer_target", [
        QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(10, 0)]),
        QgsGeometry.fromPolylineXY([QgsPointXY(10, 0), QgsPointXY(10, 10)]),
    ])
    features = list(chamfer_layer.getFeatures())
    chamfer = tool_chamfer(canvas, iface)
    chamfer.first_distance = 2.0
    chamfer.second_distance = 2.0
    chamfer.first_layer = chamfer_layer
    chamfer.first_feature = features[0]
    chamfer._do_chamfer(chamfer_layer, features[1])
    chamfer_lengths = sorted(round(f.geometry().length(), 3)
                             for f in chamfer_layer.getFeatures())
    checks.append((
        "chamfer tool trims both lines and adds the cut",
        chamfer_layer.featureCount() == 3
        and abs(chamfer_lengths[0] - 2.0 * math.sqrt(2.0)) < 0.05
        and all(abs(value - 8.0) < 0.05 for value in chamfer_lengths[1:]),
    ))

    # Stretch moves only the vertices caught by the window.
    stretch_layer = _seed_layer(project, line_uri, "stretch_target", [
        QgsGeometry.fromPolylineXY([
            QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10),
        ]),
    ])
    window = QgsRectangle(9.0, -1.0, 11.0, 1.0)
    stretcher = tool_stretch(canvas, iface)
    stretcher.base_point = QgsPointXY(0, 0)
    stretcher.window_rect = window
    stretcher.targets = [
        (stretch_layer, next(stretch_layer.getFeatures()), window)
    ]
    stretcher._step = tool_stretch._STEP_TARGET
    stretcher._apply_stretch(QgsPointXY(0, 5))
    stretched = next(stretch_layer.getFeatures()).geometry().asPolyline()
    checks.append((
        "stretch tool moves only the enclosed vertex",
        len(stretched) == 3
        and abs(stretched[0].y()) < 1e-6
        and abs(stretched[1].y() - 5.0) < 1e-6
        and abs(stretched[2].y() - 10.0) < 1e-6,
    ))

    # Align rotates the picked feature onto the destination pair.
    align_layer = _seed_layer(project, line_uri, "align_target", [
        QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(1, 0)]),
    ])
    aligner = tool_align(canvas, iface)
    aligner.selected_layer = align_layer
    aligner.selected_feature = next(align_layer.getFeatures())
    aligner.src1 = QgsPointXY(0, 0)
    aligner.dst1 = QgsPointXY(10, 10)
    aligner.src2 = QgsPointXY(1, 0)
    aligner._step = tool_align._STEP_TARGET_2
    aligner._apply_align(QgsPointXY(10, 11))
    aligned = next(align_layer.getFeatures()).geometry().asPolyline()
    checks.append((
        "align tool rewrites the feature onto the destination pair",
        len(aligned) == 2
        and abs(aligned[0].x() - 10.0) < 1e-6 and abs(aligned[0].y() - 10.0) < 1e-6
        and abs(aligned[1].x() - 10.0) < 1e-6 and abs(aligned[1].y() - 11.0) < 1e-6,
    ))

    # Explode sends polygon segments to the managed line layer.
    polygon_layer = _seed_layer(
        project, "Polygon?crs=EPSG:3857", "explode_target",
        [QgsGeometry.fromPolygonXY([[
            QgsPointXY(0, 0), QgsPointXY(10, 0), QgsPointXY(10, 10),
            QgsPointXY(0, 10), QgsPointXY(0, 0),
        ]])],
    )
    exploder = tool_explode(canvas, iface)
    exploder.remove_source = False
    source = next(polygon_layer.getFeatures())
    pieces = explode_geometry(source.geometry(), "segments")
    written = exploder._write_pieces(polygon_layer, source, pieces, "segments")
    managed = project.mapLayersByName("planx_explode")
    checks.append((
        "explode writes polygon segments to the managed layer",
        written and len(managed) == 1 and managed[0].featureCount() == 4
        and polygon_layer.featureCount() == 1,
    ))

    for layer in (break_layer, gap_layer, chamfer_layer, stretch_layer,
                  align_layer, polygon_layer):
        layer.rollBack()
    return checks


def run_all() -> bool:
    app = QgsApplication.instance()
    owns_app = app is None
    profile_dir = None
    if owns_app:
        profile_dir = tempfile.TemporaryDirectory(prefix="planx-cad-test-")
        app = QgsApplication([], False, profile_dir.name, "external")
        app.initQgis()

    project = QgsProject.instance()
    project.clear()
    settings = QSettings("PlanX", "PlanXCAD")
    settings_snapshot = {key: settings.value(key) for key in settings.allKeys()}
    settings.setValue("onboarding/quick_start_seen", True)

    iface = _Iface()
    plugin = PlanXCADPlugin(iface)
    checks = []
    try:
        plugin.initGui()
        plugin._toggle_dock()
        app.processEvents()
        checks.append(("dock exposes every tool", len(plugin._dock.buttons) == 39))
        checks.append((
            "dock has a button for every registered tool key",
            set(plugin._ALL_TOOL_KEYS) == set(plugin._dock.buttons),
        ))

        junction_dialog = JunctionDialog(iface.mainWindow())
        default_params = junction_dialog.get_params()
        junction_dialog.cmb_corner_mode.setCurrentIndex(1)
        fillet_params = junction_dialog.get_params()
        checks.append((
            "junction mode controls the active numeric parameter",
            default_params["corner_mode"] == "chamfer"
            and fillet_params["corner_mode"] == "fillet"
            and not junction_dialog.spn_chamfer_dist.isEnabled()
            and junction_dialog.spn_fillet_radius.isEnabled(),
        ))
        junction_dialog.close()

        line = QgsVectorLayer("LineString?crs=EPSG:3857", "target", "memory")
        project.addMapLayer(line)
        iface.mapCanvas().setDestinationCrs(line.crs())
        iface.set_active_layer(line)
        checks.append(("drawing auto-starts editing", plugin._validate_tool_activation_context("line") and line.isEditable()))

        plugin._activate_tool("line")
        plugin._dock.search_input.setText("100,200")
        plugin._dock._run_command()
        plugin._dock.search_input.setText("@10,0")
        plugin._dock._run_command()
        checks.append((
            "dock routes precision input to active drawing tool",
            line.featureCount() == 1,
        ))
        plugin._current_tool.precision_key_started.emit("@")
        app.processEvents()
        checks.append((
            "direct canvas typing seeds the command line",
            plugin._dock.search_input.text() == "@",
        ))
        plugin._dock.search_input.clear()

        plugin._activate_tool("polyline")
        plugin._dock.search_input.setText("200,200")
        plugin._dock._run_command()
        plugin._dock.search_input.setText("@10,0")
        plugin._dock._run_command()
        in_progress_tool = plugin._current_tool
        feature_count = line.featureCount()
        plugin._dock._run_command()
        checks.append((
            "empty Enter finishes an in-progress sketch",
            line.featureCount() == feature_count + 1
            and plugin._current_tool is in_progress_tool
            and not in_progress_tool.vertices,
        ))

        plugin._dock.search_input.setText("300,300")
        plugin._dock._run_command()
        feature_count = line.featureCount()
        plugin._dock._run_command()
        checks.append((
            "empty Enter preserves an insufficient sketch",
            line.featureCount() == feature_count
            and plugin._current_tool is in_progress_tool
            and len(in_progress_tool.vertices) == 1,
        ))

        class _EnterEvent:
            def __init__(self):
                self.accepted = False

            @staticmethod
            def text():
                return ""

            @staticmethod
            def key():
                return Qt.Key.Key_Return

            def accept(self):
                self.accepted = True

        enter_event = _EnterEvent()
        in_progress_tool.keyPressEvent(enter_event)
        checks.append((
            "canvas Enter preserves an insufficient sketch",
            enter_event.accepted
            and line.featureCount() == feature_count
            and len(in_progress_tool.vertices) == 1,
        ))

        plugin._dock.search_input.setText("@10,0")
        plugin._dock._run_command()
        feature_count = line.featureCount()
        enter_event = _EnterEvent()
        in_progress_tool.keyPressEvent(enter_event)
        checks.append((
            "canvas Enter finishes a valid sketch",
            enter_event.accepted
            and line.featureCount() == feature_count + 1
            and not in_progress_tool.vertices,
        ))

        plugin._dock.search_input.setText("320,300")
        plugin._dock._run_command()

        plugin._dock.search_input.setText("pending input")
        plugin._dock.search_input.setFocus()
        QTest.keyClick(plugin._dock.search_input, Qt.Key.Key_Escape)
        app.processEvents()
        checks.append((
            "command-line Escape clears input and cancels the active tool",
            not plugin._dock.search_input.text()
            and plugin._current_tool is None
            and plugin._current_tool_key is None,
        ))

        plugin._dock._run_command()
        checks.append((
            "idle empty Enter still repeats the last tool",
            plugin._current_tool is not None
            and plugin._current_tool_key == "polyline",
        ))

        mixed_crs_layer = QgsVectorLayer(
            "LineString?crs=EPSG:4326", "mixed_crs_offset", "memory"
        )
        mixed_crs_feature = QgsFeature(mixed_crs_layer.fields())
        mixed_crs_feature.setGeometry(QgsGeometry.fromPolylineXY([
            QgsPointXY(27.1400, 38.4200),
            QgsPointXY(27.1420, 38.4200),
        ]))

        class _PreviewSpy:
            def __init__(self):
                self.layer = None

            def reset(self, *_args):
                return None

            def setToGeometry(self, _geometry, layer=None):
                self.layer = layer

        offset_tool = tool_multi_offset(iface.mapCanvas(), iface)
        offset_tool.selected_layer = mixed_crs_layer
        offset_tool.selected_feature = mixed_crs_feature
        offset_tool.parsed_distances = [5.0]
        offset_tool._step = 2
        preview_spy = _PreviewSpy()
        offset_tool.preview_rb = preview_spy
        offset_tool.on_move(QgsPointXY(27.1410, 38.4210))
        checks.append((
            "multi-offset preview carries its layer CRS",
            preview_spy.layer is mixed_crs_layer,
        ))
        offset_tool.preview_rb = None
        offset_tool.deactivate()

        polygon = QgsVectorLayer("Polygon?crs=EPSG:3857", "wrong_target", "memory")
        project.addMapLayer(polygon)
        iface.set_active_layer(polygon)
        checks.append(("wrong target geometry is rejected", not plugin._validate_tool_activation_context("line")))

        iface.set_active_layer(None)
        checks.append(("own-layer tool needs no active layer", plugin._validate_tool_activation_context("dimension")))

        class _CancelledTool(QgsMapTool):
            def activate(self):
                super().activate()
                self._activation_cancelled = True

        cancelled_tool = _CancelledTool(iface.mapCanvas())
        original_factory = plugin._create_tool
        plugin._create_tool = lambda _key: cancelled_tool
        previous_last = plugin._last_tool_key
        plugin._activate_tool("road")
        plugin._create_tool = original_factory
        checks.append((
            "cancelled setup leaves no inert CAD tool",
            plugin._current_tool is None and plugin._last_tool_key == previous_last,
        ))

        iface.set_active_layer(line)
        plugin._toggle_active_layer_editing()
        checks.append(("edit toggle never commits directly", line.isEditable()))

        modify_keys = ("chamfer", "break", "lengthen", "align", "stretch",
                       "explode")
        modify_tools = {key: plugin._create_tool(key) for key in modify_keys}
        checks.append((
            "modify gap-filler tools construct",
            all(tool is not None for tool in modify_tools.values()),
        ))
        checks.append((
            "modify gap-filler tools report their name",
            [modify_tools[key].tool_name() for key in modify_keys] ==
            ["Chamfer", "Break", "Lengthen", "Align", "Stretch", "Explode"],
        ))

        # Break and Stretch open no dialog, so they can be activated headless.
        iface.set_active_layer(line)
        plugin._activate_tool("break")
        break_tool = plugin._current_tool
        plugin._activate_tool("stretch")
        stretch_tool = plugin._current_tool
        checks.append((
            "dialog-free modify tools activate",
            break_tool is not None and stretch_tool is not None
            and plugin._current_tool_key == "stretch",
        ))
        checks.extend(_modify_write_checks(iface, project))

        iface.set_active_layer(None)
        plugin._activate_tool("construction_seg")
        active_tool = plugin._current_tool
        checks.append(("construction tool activates", active_tool is not None))
        iface.mapCanvas().setMapTool(QgsMapTool(iface.mapCanvas()))
        checks.append(("external QGIS tool clears CAD state", plugin._current_tool is None and plugin._current_tool_key is None))

        plugin.unload()
        app.sendPostedEvents()
        app.processEvents()
        toolbars = iface.mainWindow().findChildren(QToolBar)
        checks.append(("unload removes toolbar", not any(tb.objectName() == "PlanXCADToolbar" for tb in toolbars)))
        checks.append(("unload removes menu", not any(action.text().startswith("&planX CAD") for action in iface.mainWindow().menuBar().actions())))
    finally:
        if plugin.menu is not None or plugin.toolbar is not None:
            plugin.unload()
        project.clear()
        iface.mainWindow().close()
        settings.clear()
        for key, value in settings_snapshot.items():
            settings.setValue(key, value)
        if owns_app:
            app.exitQgis()
            profile_dir.cleanup()

    print("=" * 60)
    print(" PlanX CAD Toolset - QGIS runtime smoke tests")
    print("=" * 60)
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed_count = sum(passed for _, passed in checks)
    print("-" * 60)
    print(f"  {passed_count}/{len(checks)} passed")
    return passed_count == len(checks)


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
