"""Headless QGIS runtime smoke checks for plugin lifecycle and workbench state.

Run from the plugins parent directory so the package import is realistic::

    python-qgis-ltr.bat -m planX_CAD_arac_Seti.tests.smoke_runtime
    python-qgis.bat -m planX_CAD_arac_Seti.tests.smoke_runtime
"""
from __future__ import annotations

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
        checks.append(("dock exposes every tool", len(plugin._dock.buttons) == 33))

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
