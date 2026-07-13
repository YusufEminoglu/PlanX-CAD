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

from qgis.PyQt.QtCore import QObject, QSettings, pyqtSignal
from qgis.PyQt.QtWidgets import QAction, QMainWindow, QToolBar
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapCanvas, QgsMapTool

from ..main_plugin import PlanXCADPlugin
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
