# -*- coding: utf-8 -*-
"""PlanX CAD Toolset: QGIS plugin entry point and workbench shell."""

import os
from contextlib import suppress

from qgis.PyQt.QtCore import Qt, QTimer, QSettings, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QKeySequence
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QShortcut
from qgis.core import QgsProject, QgsVectorLayer, QgsWkbTypes


class PlanXCADPlugin:
    """Manage the PlanX CAD Toolset interface, tools, and lifecycle."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_dir = os.path.join(self.plugin_dir, "icons")

        self.actions = []
        self.menu = None
        self.toolbar = None
        self._dock = None
        self._current_tool = None
        self._current_tool_key = None
        self._watched_layer = None
        self._unloading = False
        self._quick_start_timer = None

        # Tool instances are loaded lazily.
        self._tools = {}

        # Tool history: most-recently activated key for "repeat last"
        self._last_tool_key = None
        # QShortcuts owned by the plugin (cleaned up in unload)
        self._shortcuts = []
        self._canvas_tool_signal_connected = False
        self._layer_signal_connected = False

    # ═══════════════════════════════════════════════════════════════════════
    # QGIS Plugin Interface
    # ═══════════════════════════════════════════════════════════════════════

    def initGui(self):
        """Add the menu, toolbar, dock, and shortcuts to QGIS."""
        # ── Menu ─────────────────────────────────────────────────────────
        self.menu = QMenu("&planX CAD Toolset")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # ── Toolbar ──────────────────────────────────────────────────────
        self.toolbar = QToolBar("planX CAD Toolbar")
        self.toolbar.setObjectName("PlanXCADToolbar")
        self.iface.addToolBar(self.toolbar)

        # ── Main panel toggle ────────────────────────────────────────────
        main_icon = os.path.join(self.icon_dir, "icon.png")
        self.panel_action = self._add_action(
            main_icon,
            "PlanX CAD Panel",
            self._toggle_dock,
            checkable=True,
            status_tip="Open or close the PlanX CAD panel"
        )

        # ── Menu separator ───────────────────────────────────────────────
        self.menu.addSeparator()

        # ── Help and diagnostics ─────────────────────────────────────────
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "About",
            self._show_about,
            add_to_toolbar=False,
            status_tip="About PlanX CAD Toolset"
        )
        self._add_action(
            main_icon,
            "Plugin Page and Rating",
            self._open_plugin_page,
            add_to_toolbar=False,
            status_tip="Open the official QGIS plugin page",
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Shortcut Guide",
            self._show_shortcut_guide,
            add_to_toolbar=False,
            status_tip="Open the keyboard shortcut and workflow guide"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Command Reference",
            self._show_command_reference,
            add_to_toolbar=False,
            status_tip="Open detailed command documentation"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Smoke Test Checklist",
            self._show_smoke_test,
            add_to_toolbar=False,
            status_tip="Open the QGIS smoke-test checklist"
        )
        self._add_action(
            ":/images/themes/default/mIconExpression.svg",
            "Command Palette",
            self._show_command_palette,
            add_to_toolbar=False,
            status_tip="Find and activate commands quickly"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Quick Start",
            self._show_quick_start,
            add_to_toolbar=False,
            status_tip="Open the onboarding guide"
        )
        self._add_action(
            ":/images/themes/default/mActionRefresh.svg",
            "Session Checklist",
            self._show_session_checklist,
            add_to_toolbar=False,
            status_tip="Open the drafting-session checklist"
        )
        self._add_action(
            ":/images/themes/default/mActionPropertiesWidget.svg",
            "Diagnostics",
            self._show_diagnostics,
            add_to_toolbar=False,
            status_tip="Open the runtime diagnostics report"
        )
        self._add_action(
            ":/images/themes/default/mActionOptions.svg",
            "Health Check",
            self._show_health_check,
            add_to_toolbar=False,
            status_tip="Run runtime readiness checks"
        )
        self._add_action(
            ":/images/themes/default/mIconFieldInteger.svg",
            "Shortcut Audit",
            self._show_shortcut_audit,
            add_to_toolbar=False,
            status_tip="Check shortcut conflicts and duplicates"
        )
        self._add_action(
            ":/images/themes/default/mIconNewText.svg",
            "Issue Template",
            self._show_issue_template,
            add_to_toolbar=False,
            status_tip="Open a copy-ready issue report template"
        )
        self._add_action(
            ":/images/themes/default/mActionRefresh.svg",
            "Release Readiness",
            self._show_release_readiness,
            add_to_toolbar=False,
            status_tip="Open release-readiness checks"
        )

        # ── Keyboard shortcuts ────────────────────────────────────────────
        self._setup_shortcuts()
        try:
            self.iface.mapCanvas().mapToolSet.connect(self._on_map_tool_set)
            self._canvas_tool_signal_connected = True
        except Exception:
            self._canvas_tool_signal_connected = False
        self._maybe_show_quick_start_once()

    def unload(self):
        """Remove plugin UI and release runtime resources."""
        self._unloading = True
        if self._quick_start_timer is not None:
            self._quick_start_timer.stop()
            self._quick_start_timer.deleteLater()
            self._quick_start_timer = None
        if self._canvas_tool_signal_connected:
            with suppress(Exception):
                self.iface.mapCanvas().mapToolSet.disconnect(self._on_map_tool_set)
            self._canvas_tool_signal_connected = False

        # Deactivate the current map tool.
        if self._current_tool:
            self.iface.mapCanvas().unsetMapTool(self._current_tool)
            self._current_tool = None
            self._current_tool_key = None

        # Dock widget
        if self._dock:
            if hasattr(self._dock, 'unload'):
                self._dock.unload()
            if self._layer_signal_connected:
                with suppress(Exception):
                    self.iface.currentLayerChanged.disconnect(self._on_current_layer_changed)
                self._layer_signal_connected = False
            self._bind_active_layer(None)
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

        # Tools
        for tool in self._tools.values():
            if tool:
                del tool
        self._tools.clear()

        # Keyboard shortcuts
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        # Actions
        for action in self.actions:
            if self.toolbar:
                self.toolbar.removeAction(action)
            if self.menu:
                self.menu.removeAction(action)
            action.setParent(None)
            action.deleteLater()
        self.actions.clear()

        # Toolbar
        if self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.setParent(None)
            self.toolbar.deleteLater()
            self.toolbar = None

        # Menu
        if self.menu:
            self.iface.mainWindow().menuBar().removeAction(self.menu.menuAction())
            self.menu.setParent(None)
            self.menu.deleteLater()
            self.menu = None

        self.panel_action = None

    # ═══════════════════════════════════════════════════════════════════════
    # Dock Widget
    # ═══════════════════════════════════════════════════════════════════════

    def _toggle_dock(self):
        """Open, close, or create the CAD dock."""
        if self._dock is None:
            dock = None
            try:
                from .dialogs.cad_dock import CADDockWidget

                dock = CADDockWidget(
                    self.iface, self.icon_dir, self.iface.mainWindow()
                )
                dock.setObjectName("PlanXCADDock")
                dock.visibilityChanged.connect(self._on_dock_visibility)
                dock.tool_activated.connect(self._activate_tool)
                dock.set_precision_input_handler(self._handle_precision_input)
                dock.set_command_enter_handler(self._handle_command_enter)
                dock.cancel_requested.connect(self._cancel_active_tool)
                dock.edit_toggle_requested.connect(self._toggle_active_layer_editing)
                dock.quick_start_requested.connect(self._show_quick_start)
                dock.docs_requested.connect(self._show_command_reference)
                dock.shortcuts_requested.connect(self._show_shortcut_guide)
                dock.diagnostics_requested.connect(self._show_diagnostics)
                dock.workspace_reset_requested.connect(self._reset_workspace_state)
                dock.tool_help_requested.connect(self._show_tool_help)
                dock.usage_stats_requested.connect(self._show_usage_stats)
                dock.health_check_requested.connect(self._show_health_check)
                dock.shortcut_audit_requested.connect(self._show_shortcut_audit)
                try:
                    self.iface.currentLayerChanged.connect(self._on_current_layer_changed)
                    self._layer_signal_connected = True
                except Exception:
                    self._layer_signal_connected = False

                self.iface.addDockWidget(
                    Qt.DockWidgetArea.LeftDockWidgetArea, dock
                )
                self._dock = dock
                self._bind_active_layer(self.iface.activeLayer())
                self._dock.show()
                self._dock.raise_()
                return

            except Exception as e:
                if self._layer_signal_connected:
                    with suppress(Exception):
                        self.iface.currentLayerChanged.disconnect(
                            self._on_current_layer_changed
                        )
                    self._layer_signal_connected = False
                if dock is not None:
                    with suppress(Exception):
                        dock.unload()
                    dock.deleteLater()
                self._dock = None
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "PlanX CAD Error",
                    f"Failed to create the panel:\n{str(e)}"
                )
                if self.panel_action:
                    self.panel_action.setChecked(False)
                return

        # Toggle
        if self._dock.isVisible():
            self._dock.hide()
        else:
            self._dock.show()
            self._dock.raise_()

    def _on_dock_visibility(self, visible):
        if self.panel_action:
            self.panel_action.setChecked(visible)

    def _on_map_tool_set(self, new_tool, *_args):
        """Keep the dock selection synchronized with QGIS' active map tool."""
        if self._current_tool is None or new_tool is self._current_tool:
            return
        self._current_tool = None
        self._current_tool_key = None
        if self._dock:
            self._dock.uncheck_all()
            self._dock.set_status(
                "CAD tool paused; a QGIS map tool is active"
            )

    # ═══════════════════════════════════════════════════════════════════════
    # Tool management
    # ═══════════════════════════════════════════════════════════════════════

    # Dialog-based tools require a fresh instance for every activation.
    _DIALOG_TOOLS = {"buffer", "fillet", "polygon", "road", "junction", "measure_area", "ada_kirma", "array", "divide", "multi_offset", "join", "hatch"}
    # Drawing tools write to the active layer. Feature-editing tools may pick
    # from any editable vector layer in the project. Output tools (Buffer,
    # Hatch, Dimension, Construction and Road) create their own layers and
    # must not be blocked by an unrelated read-only active layer.
    _ACTIVE_TARGET_TOOLS = {
        "line", "polyline", "rectangle", "polygon", "circle", "arc",
    }
    _ACTIVE_TARGET_GEOMETRY = {
        "line": QgsWkbTypes.GeometryType.LineGeometry,
        "polyline": QgsWkbTypes.GeometryType.LineGeometry,
        "arc": QgsWkbTypes.GeometryType.LineGeometry,
        "rectangle": QgsWkbTypes.GeometryType.PolygonGeometry,
        "polygon": QgsWkbTypes.GeometryType.PolygonGeometry,
        "circle": QgsWkbTypes.GeometryType.PolygonGeometry,
    }
    _EDITABLE_PICK_TOOLS = {
        "offset", "trim", "extend", "fillet", "vertex_edit",
        "move", "copy", "rotate", "scale", "mirror", "array",
        "divide", "multi_offset", "join",
    }
    _READ_ONLY_PICK_TOOLS = {"buffer", "hatch", "measure_select_line", "measure_select_area"}

    # Backward-compatible names used by diagnostics/tests.
    _TOOLS_REQUIRING_LAYER = set(_ACTIVE_TARGET_TOOLS)
    _TOOLS_REQUIRING_EDITABLE = set(_ACTIVE_TARGET_TOOLS) | set(_EDITABLE_PICK_TOOLS)

    # ═══════════════════════════════════════════════════════════════════════
    # Keyboard shortcuts and tool history
    # ═══════════════════════════════════════════════════════════════════════

    # Tool key -> shortcut. Ctrl+Shift combinations avoid common QGIS bindings.
    _SHORTCUTS = (
        ("line",                  "Ctrl+Shift+L"),
        ("polyline",              "Ctrl+Shift+P"),
        ("rectangle",             "Ctrl+Shift+R"),
        ("polygon",               "Ctrl+Shift+G"),
        ("circle",                "Ctrl+Shift+C"),
        ("arc",                   "Ctrl+Shift+A"),
        ("offset",                "Ctrl+Shift+O"),
        ("trim",                  "Ctrl+Shift+T"),
        ("extend",                "Ctrl+Shift+E"),
        ("fillet",                "Ctrl+Shift+F"),
        ("buffer",                "Ctrl+Shift+B"),
        ("move",                  "Ctrl+Shift+M"),
        ("array",                 "Ctrl+Shift+Y"),
        ("vertex_edit",           "Ctrl+Shift+V"),
        ("hatch",                 "Ctrl+Shift+H"),
        ("construction_inf",      "Ctrl+Shift+K"),
        ("construction_ray",      "Ctrl+Alt+K"),
        ("construction_seg",      "Ctrl+Alt+L"),
        ("dimension",             "Ctrl+Shift+D"),
        ("measure",               "Ctrl+Shift+I"),
        ("divide",                "Ctrl+Shift+U"),
        ("multi_offset",          "Ctrl+Shift+X"),
        ("join",                  "Ctrl+Shift+J"),
    )
    _ALL_TOOL_KEYS = (
        "line", "polyline", "rectangle", "polygon", "circle", "arc",
        "offset", "trim", "extend", "fillet", "buffer", "array",
        "vertex_edit", "divide", "multi_offset", "join", "hatch",
        "construction_inf", "construction_ray", "construction_seg",
        "move", "copy", "rotate", "scale", "mirror",
        "measure", "measure_area", "dimension", "measure_select_line",
        "measure_select_area", "road", "junction", "ada_kirma",
    )

    @classmethod
    def _tool_palette_entries(cls):
        shortcut_by_key = dict(cls._SHORTCUTS)
        return tuple(
            (key, shortcut_by_key.get(key, "—")) for key in cls._ALL_TOOL_KEYS
        )

    def _setup_shortcuts(self):
        """Bind application-wide shortcuts to the QGIS main window."""
        parent = self.iface.mainWindow()
        for key, seq in self._SHORTCUTS:
            sc = QShortcut(QKeySequence(seq), parent)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(lambda k=key: self._activate_tool(k))
            self._shortcuts.append(sc)
        # Repeat last tool
        repeat = QShortcut(QKeySequence("Ctrl+Shift+Space"), parent)
        repeat.setContext(Qt.ShortcutContext.ApplicationShortcut)
        repeat.activated.connect(self._repeat_last_tool)
        self._shortcuts.append(repeat)
        # Focus dock search
        focus_search = QShortcut(QKeySequence("Ctrl+Shift+S"), parent)
        focus_search.setContext(Qt.ShortcutContext.ApplicationShortcut)
        focus_search.activated.connect(self._focus_dock_search)
        self._shortcuts.append(focus_search)
        # Shortcut guide
        shortcut_help = QShortcut(QKeySequence("Ctrl+Shift+/"), parent)
        shortcut_help.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut_help.activated.connect(self._show_shortcut_guide)
        self._shortcuts.append(shortcut_help)
        docs_help = QShortcut(QKeySequence("Ctrl+Alt+H"), parent)
        docs_help.setContext(Qt.ShortcutContext.ApplicationShortcut)
        docs_help.activated.connect(self._show_command_reference)
        self._shortcuts.append(docs_help)
        smoke_test = QShortcut(QKeySequence("Ctrl+Alt+M"), parent)
        smoke_test.setContext(Qt.ShortcutContext.ApplicationShortcut)
        smoke_test.activated.connect(self._show_smoke_test)
        self._shortcuts.append(smoke_test)
        palette = QShortcut(QKeySequence("Ctrl+Alt+P"), parent)
        palette.setContext(Qt.ShortcutContext.ApplicationShortcut)
        palette.activated.connect(self._show_command_palette)
        self._shortcuts.append(palette)
        cancel_tool = QShortcut(QKeySequence("Ctrl+Alt+C"), parent)
        cancel_tool.setContext(Qt.ShortcutContext.ApplicationShortcut)
        cancel_tool.activated.connect(self._cancel_active_tool)
        self._shortcuts.append(cancel_tool)
        edit_toggle = QShortcut(QKeySequence("Ctrl+Alt+E"), parent)
        edit_toggle.setContext(Qt.ShortcutContext.ApplicationShortcut)
        edit_toggle.activated.connect(self._toggle_active_layer_editing)
        self._shortcuts.append(edit_toggle)
        preflight = QShortcut(QKeySequence("Ctrl+Alt+F"), parent)
        preflight.setContext(Qt.ShortcutContext.ApplicationShortcut)
        preflight.activated.connect(self._run_dock_preflight)
        self._shortcuts.append(preflight)
        quick_start = QShortcut(QKeySequence("Ctrl+Alt+Q"), parent)
        quick_start.setContext(Qt.ShortcutContext.ApplicationShortcut)
        quick_start.activated.connect(self._show_quick_start)
        self._shortcuts.append(quick_start)
        checklist = QShortcut(QKeySequence("Ctrl+Alt+G"), parent)
        checklist.setContext(Qt.ShortcutContext.ApplicationShortcut)
        checklist.activated.connect(self._show_session_checklist)
        self._shortcuts.append(checklist)
        pin_last = QShortcut(QKeySequence("Ctrl+Alt+Z"), parent)
        pin_last.setContext(Qt.ShortcutContext.ApplicationShortcut)
        pin_last.activated.connect(self._pin_last_tool)
        self._shortcuts.append(pin_last)
        diagnostics = QShortcut(QKeySequence("Ctrl+Alt+D"), parent)
        diagnostics.setContext(Qt.ShortcutContext.ApplicationShortcut)
        diagnostics.activated.connect(self._show_diagnostics)
        self._shortcuts.append(diagnostics)
        reset_workspace = QShortcut(QKeySequence("Ctrl+Alt+R"), parent)
        reset_workspace.setContext(Qt.ShortcutContext.ApplicationShortcut)
        reset_workspace.activated.connect(self._reset_workspace_state)
        self._shortcuts.append(reset_workspace)
        usage_stats = QShortcut(QKeySequence("Ctrl+Alt+T"), parent)
        usage_stats.setContext(Qt.ShortcutContext.ApplicationShortcut)
        usage_stats.activated.connect(self._show_usage_stats)
        self._shortcuts.append(usage_stats)
        health = QShortcut(QKeySequence("Ctrl+Alt+W"), parent)
        health.setContext(Qt.ShortcutContext.ApplicationShortcut)
        health.activated.connect(self._show_health_check)
        self._shortcuts.append(health)
        shortcut_audit = QShortcut(QKeySequence("Ctrl+Alt+Y"), parent)
        shortcut_audit.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut_audit.activated.connect(self._show_shortcut_audit)
        self._shortcuts.append(shortcut_audit)
        issue_template = QShortcut(QKeySequence("Ctrl+Alt+N"), parent)
        issue_template.setContext(Qt.ShortcutContext.ApplicationShortcut)
        issue_template.activated.connect(self._show_issue_template)
        self._shortcuts.append(issue_template)
        release_readiness = QShortcut(QKeySequence("Ctrl+Alt+V"), parent)
        release_readiness.setContext(Qt.ShortcutContext.ApplicationShortcut)
        release_readiness.activated.connect(self._show_release_readiness)
        self._shortcuts.append(release_readiness)

    def _repeat_last_tool(self):
        if self._last_tool_key:
            self._activate_tool(self._last_tool_key)
        else:
            self._set_status("⚠️ No previous tool to repeat")

    def _focus_dock_search(self):
        if self._dock is None:
            self._toggle_dock()
        if self._dock and hasattr(self._dock, "focus_search"):
            self._dock.focus_search()

    def _begin_precision_entry(self, seed):
        """Move direct canvas typing into the CAD command line."""
        if self._dock is None:
            self._toggle_dock()
        elif not self._dock.isVisible():
            self._dock.show()
            self._dock.raise_()
        if self._dock and hasattr(self._dock, "search_input"):
            self._dock.search_input.setText(seed)
            self._dock.search_input.setFocus()
            self._dock.search_input.setCursorPosition(len(seed))

    def _cancel_active_tool(self):
        canvas = self.iface.mapCanvas()
        if self._current_tool:
            canvas.unsetMapTool(self._current_tool)
            self._current_tool = None
            self._current_tool_key = None
        if self._dock:
            self._dock.uncheck_all()
            self._dock.set_status("Active tool cancelled")
            if hasattr(self._dock, "refresh_layer_state"):
                self._dock.refresh_layer_state()

    def _toggle_active_layer_editing(self):
        layer = self.iface.activeLayer()
        if layer is None:
            self._set_status("No active layer")
            return
        if not isinstance(layer, QgsVectorLayer):
            self._set_status("The active layer is not a vector layer")
            return

        try:
            if layer.isEditable():
                # Delegate the edit-off transition to QGIS so the standard
                # Save / Discard / Cancel prompt protects pending user edits.
                toggle_action = getattr(self.iface, "actionToggleEditing", lambda: None)()
                if toggle_action is None:
                    msg = "Use QGIS Toggle Editing to save or discard changes"
                else:
                    toggle_action.trigger()
                    msg = "Editing remains ON" if layer.isEditable() else "Editing OFF"
            else:
                started = bool(layer.startEditing())
                msg = (
                    "Editing ON"
                    if started
                    else "Could not start editing; the layer may be read-only"
                )
            self._set_status(msg)
            if self._dock and hasattr(self._dock, "refresh_layer_state"):
                self._dock.refresh_layer_state()
        except Exception as e:
            self._set_status(f"Editing toggle failed: {e}")

    def _on_current_layer_changed(self, _layer):
        self._bind_active_layer(_layer)
        if self._dock and hasattr(self._dock, "refresh_layer_state"):
            self._dock.refresh_layer_state()

    def _bind_active_layer(self, layer):
        """Refresh dock state when QGIS toggles editing on the same layer."""
        if self._watched_layer is not None:
            for signal_name in ("editingStarted", "editingStopped"):
                with suppress(Exception):
                    getattr(self._watched_layer, signal_name).disconnect(
                        self._on_layer_edit_state_changed
                    )
        self._watched_layer = layer if isinstance(layer, QgsVectorLayer) else None
        if self._watched_layer is not None:
            for signal_name in ("editingStarted", "editingStopped"):
                with suppress(Exception):
                    getattr(self._watched_layer, signal_name).connect(
                        self._on_layer_edit_state_changed
                    )

    def _on_layer_edit_state_changed(self):
        if self._dock and hasattr(self._dock, "refresh_layer_state"):
            self._dock.refresh_layer_state()

    def _run_dock_preflight(self):
        if self._dock is None:
            self._toggle_dock()
        if self._dock and hasattr(self._dock, "run_preflight"):
            self._dock.run_preflight()

    def _pin_last_tool(self):
        if self._dock is None:
            self._toggle_dock()
        if self._dock and hasattr(self._dock, "pin_last_tool"):
            self._dock.pin_last_tool()

    def _reset_workspace_state(self):
        self._cancel_active_tool()
        self._last_tool_key = None
        if self._dock and hasattr(self._dock, "clear_workspace_state"):
            self._dock.clear_workspace_state()

    def _show_diagnostics(self):
        try:
            from .dialogs.diagnostics_dialog import DiagnosticsDialog
            report = self._build_diagnostics_report()
            dlg = DiagnosticsDialog(report, self.iface.mainWindow())
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Diagnostics",
                f"Diagnostics report could not be opened:\n{e}"
            )

    def _show_usage_stats(self):
        if not self._dock:
            self._toggle_dock()
        if not self._dock:
            return
        try:
            from .dialogs.usage_stats_dialog import UsageStatsDialog
            snap = self._dock.diagnostics_snapshot()
            dlg = UsageStatsDialog(
                usage_counts=snap.get("tool_usage_counts", {}),
                total_activations=snap.get("activation_count", 0),
                parent=self.iface.mainWindow()
            )
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Usage Stats",
                f"Usage statistics could not be opened:\n{e}"
            )

    def _show_tool_help(self, tool_key=None):
        anchor = self._doc_anchor_for_tool(tool_key or self._last_tool_key)
        self._show_command_reference(anchor=anchor)

    def _doc_anchor_for_tool(self, tool_key):
        drawing = {"line", "polyline", "rectangle", "polygon", "circle", "arc"}
        editing = {"offset", "trim", "extend", "fillet", "buffer", "vertex_edit", "hatch", "construction_inf", "construction_ray", "construction_seg", "divide", "multi_offset", "join"}
        transform = {"move", "copy", "rotate", "scale", "mirror", "array"}
        measure = {"dimension", "measure", "measure_area", "measure_select_line", "measure_select_area"}
        urban = {"road", "junction", "ada_kirma"}
        if tool_key in drawing:
            return "drawing"
        if tool_key in editing:
            return "editing"
        if tool_key in transform:
            return "transform"
        if tool_key in measure:
            return "measurement"
        if tool_key in urban:
            return "urban"
        return "workflow"

    def _show_health_check(self):
        try:
            from .dialogs.health_check_dialog import HealthCheckDialog
            dlg = HealthCheckDialog(self._build_health_checks(), self.iface.mainWindow())
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Health Check",
                f"Health check could not be opened:\n{e}"
            )

    def _show_shortcut_audit(self):
        rows = self._build_shortcut_audit_rows()
        text = ["Shortcut Audit", "==============", ""]
        has_issue = False
        for row in rows:
            line = f"[{row['status']}] {row['shortcut']} -> {row['commands']}"
            text.append(line)
            if row["status"] != "OK":
                has_issue = True
        text.append("")
        text.append("Result: ISSUE found" if has_issue else "Result: OK")
        try:
            from .dialogs.diagnostics_dialog import DiagnosticsDialog
            dlg = DiagnosticsDialog("\n".join(text), self.iface.mainWindow())
            dlg.setWindowTitle("PlanX CAD - Shortcut Audit")
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Shortcut Audit",
                f"Shortcut audit could not be opened:\n{e}"
            )

    def _build_health_checks(self):
        checks = []
        layer = self.iface.activeLayer()
        checks.append({
            "check": "Active layer",
            "status": "OK" if layer else "WARN",
            "value": layer.name() if layer and hasattr(layer, "name") else "None",
            "hint": "Select target vector layer before editing tools."
        })
        editable = bool(layer.isEditable()) if layer and hasattr(layer, "isEditable") else False
        checks.append({
            "check": "Layer editable",
            "status": "OK" if editable else "WARN",
            "value": editable,
            "hint": "Use Edit ON/OFF if tool requires write operations."
        })
        checks.append({
            "check": "Tool registry",
            "status": "OK" if len(self._SHORTCUTS) >= 20 else "WARN",
            "value": f"{len(self._SHORTCUTS)} mapped tools",
            "hint": "Shortcut coverage should include core CAD commands."
        })
        snap_enabled = False
        try:
            canvas = self.iface.mapCanvas()
            snap_utils = canvas.snappingUtils() if canvas else None
            snap_cfg = snap_utils.config() if snap_utils else None
            snap_enabled = bool(snap_cfg.enabled()) if snap_cfg else False
        except Exception:
            snap_enabled = False
        checks.append({
            "check": "Snapping",
            "status": "OK" if snap_enabled else "WARN",
            "value": snap_enabled,
            "hint": "Enable snapping for topology-safe drawing."
        })
        checks.append({
            "check": "Dock state",
            "status": "OK" if self._dock else "WARN",
            "value": "Loaded" if self._dock else "Not loaded",
            "hint": "Open PlanX CAD dock for full workflow controls."
        })
        return checks

    def _build_shortcut_audit_rows(self):
        shortcut_map = {}
        for key, seq in self._SHORTCUTS:
            s = str(seq).lower()
            shortcut_map.setdefault(s, []).append(key)
        system_pairs = [
            ("repeat_last", "Ctrl+Shift+Space"),
            ("focus_search", "Ctrl+Shift+S"),
            ("open_shortcuts", "Ctrl+Shift+/"),
            ("open_docs", "Ctrl+Alt+H"),
            ("open_smoke_test", "Ctrl+Alt+M"),
            ("command_palette", "Ctrl+Alt+P"),
            ("cancel_active_tool", "Ctrl+Alt+C"),
            ("toggle_layer_editing", "Ctrl+Alt+E"),
            ("run_preflight", "Ctrl+Alt+F"),
            ("quick_start", "Ctrl+Alt+Q"),
            ("session_checklist", "Ctrl+Alt+G"),
            ("pin_last_tool", "Ctrl+Alt+Z"),
            ("open_diagnostics", "Ctrl+Alt+D"),
            ("reset_workspace_state", "Ctrl+Alt+R"),
            ("open_usage_stats", "Ctrl+Alt+T"),
            ("open_health_check", "Ctrl+Alt+W"),
            ("open_shortcut_audit", "Ctrl+Alt+Y"),
            ("open_issue_template", "Ctrl+Alt+N"),
            ("open_release_readiness", "Ctrl+Alt+V"),
        ]
        for name, seq in system_pairs:
            s = str(seq).lower()
            shortcut_map.setdefault(s, []).append(name)

        rows = []
        for seq in sorted(shortcut_map.keys()):
            commands = shortcut_map[seq]
            status = "OK" if len(commands) == 1 else "CONFLICT"
            rows.append({
                "shortcut": seq,
                "commands": ", ".join(commands),
                "status": status,
            })
        return rows

    def _build_diagnostics_report(self):
        layer = self.iface.activeLayer()
        layer_name = layer.name() if layer and hasattr(layer, "name") else "None"
        layer_editable = bool(layer.isEditable()) if layer and hasattr(layer, "isEditable") else False
        layer_type = layer.__class__.__name__ if layer else "None"

        dock_data = {}
        if self._dock and hasattr(self._dock, "diagnostics_snapshot"):
            dock_data = self._dock.diagnostics_snapshot()

        lines = [
            "PlanX CAD Diagnostics",
            "=====================",
            f"Plugin directory: {self.plugin_dir}",
            f"Current tool key: {self._last_tool_key or 'None'}",
            f"Loaded tool instances: {sorted(list(self._tools.keys()))}",
            f"Active layer name: {layer_name}",
            f"Active layer editable: {layer_editable}",
            f"Active layer class: {layer_type}",
            "",
            "Dock state:",
            f"  search_text: {dock_data.get('search_text', '')}",
            f"  recent_tools: {dock_data.get('recent_tools', [])}",
            f"  favorites: {dock_data.get('favorites', [])}",
            f"  activation_count: {dock_data.get('activation_count', 0)}",
            f"  tool_usage_counts: {dock_data.get('tool_usage_counts', {})}",
        ]
        return "\n".join(lines)

    def _show_issue_template(self):
        try:
            from .dialogs.diagnostics_dialog import DiagnosticsDialog
            report = self._build_issue_template_text()
            dlg = DiagnosticsDialog(report, self.iface.mainWindow())
            dlg.setWindowTitle("PlanX CAD - Issue Template")
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Issue Template",
                f"Issue template could not be opened:\n{e}"
            )

    def _build_issue_template_text(self):
        diagnostics = self._build_diagnostics_report()
        return (
            "PlanX CAD Issue Template\n"
            "========================\n\n"
            "1) Summary:\n"
            "-\n\n"
            "2) Expected behavior:\n"
            "-\n\n"
            "3) Actual behavior:\n"
            "-\n\n"
            "4) Reproduction steps:\n"
            "1.\n2.\n3.\n\n"
            "5) Data context:\n"
            "- CRS:\n- Layer type:\n- Editable state:\n\n"
            "6) Diagnostics:\n\n"
            f"{diagnostics}\n"
        )

    def _show_release_readiness(self):
        try:
            from .dialogs.release_readiness_dialog import ReleaseReadinessDialog
            rows = self._build_release_readiness_rows()
            dlg = ReleaseReadinessDialog(rows, self.iface.mainWindow())
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Release Readiness",
                f"Release readiness report could not be opened:\n{e}"
            )

    def _build_release_readiness_rows(self):
        rows = []
        health_rows = self._build_health_checks()
        health_warn = sum(1 for r in health_rows if r.get("status") != "OK")
        rows.append({
            "check": "Runtime health checks",
            "status": "OK" if health_warn == 0 else "WARN",
            "value": f"{len(health_rows) - health_warn}/{len(health_rows)} OK",
            "action": "Run Health and fix warnings",
        })

        shortcut_rows = self._build_shortcut_audit_rows()
        conflicts = [r for r in shortcut_rows if r.get("status") != "OK"]
        rows.append({
            "check": "Shortcut conflicts",
            "status": "OK" if not conflicts else "WARN",
            "value": f"{len(conflicts)} conflicts",
            "action": "Run Key Audit and resolve duplicates",
        })

        docs = ["command_reference.html", "shortcuts.html", "smoke_test_checklist.html"]
        for name in docs:
            path = os.path.join(self.plugin_dir, "docs", name)
            exists = os.path.exists(path)
            rows.append({
                "check": f"Docs file: {name}",
                "status": "OK" if exists else "WARN",
                "value": "present" if exists else "missing",
                "action": "Restore documentation file",
            })

        meta_path = os.path.join(self.plugin_dir, "metadata.txt")
        version = "unknown"
        with suppress(Exception):
            with open(meta_path, "r", encoding="utf-8") as f:
                import re
                content = f.read()
                m = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if m:
                    version = m.group(1).strip()
        rows.append({
            "check": "Metadata version",
            "status": "OK" if version not in ("", "unknown") else "WARN",
            "value": version,
            "action": "Set release target version before packaging",
        })
        return rows

    def _activate_tool(self, tool_key):
        """Activate the requested CAD map tool."""
        # "Repeat last" button in dock emits the sentinel key.
        if tool_key == "__repeat__":
            self._repeat_last_tool()
            return
        if not self._validate_tool_activation_context(tool_key):
            self._restore_dock_active_state()
            return

        canvas = self.iface.mapCanvas()
        previous_tool = self._current_tool
        previous_key = self._current_tool_key

        # Dialog-based tools require a fresh instance every time.
        if tool_key in self._DIALOG_TOOLS:
            tool = self._create_tool(tool_key)
        else:
            # Create reusable map tools lazily.
            if tool_key not in self._tools:
                self._tools[tool_key] = self._create_tool(tool_key)
            tool = self._tools.get(tool_key)

        if tool is None:
            self._set_status(
                f"⚠️ Failed to load tool '{tool_key}'"
            )
            self._restore_dock_active_state()
            return

        try:
            # Repeating the same instance must run its activation lifecycle
            # again; switching to a different tool is handled by QGIS.
            if tool is previous_tool:
                canvas.unsetMapTool(tool)
            self._current_tool = tool
            self._current_tool_key = tool_key
            canvas.setMapTool(tool)
            if getattr(tool, "_activation_cancelled", False):
                canvas.unsetMapTool(tool)
                self._current_tool = None
                self._current_tool_key = None
                self._restore_dock_active_state()
                self._set_status("Tool setup cancelled")
                return
        except Exception as e:
            self._current_tool = previous_tool
            self._current_tool_key = previous_key
            if previous_tool is not None:
                try:
                    canvas.setMapTool(previous_tool)
                except Exception:
                    self._current_tool = None
                    self._current_tool_key = None
            self._set_status(f"Tool activation failed: {e}")
            self._restore_dock_active_state()
            return

        # Tool history changes only after successful construction/activation.
        self._last_tool_key = tool_key
        if self._dock and hasattr(self._dock, "register_tool_activation"):
            self._dock.register_tool_activation(tool_key)

    def _restore_dock_active_state(self):
        if not self._dock:
            return
        if self._current_tool_key and hasattr(self._dock, "set_active_tool"):
            self._dock.set_active_tool(self._current_tool_key)
        else:
            self._dock.uncheck_all()

    def _set_status(self, message):
        if self._dock:
            self._dock.set_status(message)
            return
        with suppress(Exception):
            self.iface.mainWindow().statusBar().showMessage(message, 6000)

    def _relay_tool_message(self, message):
        self._set_status(message)

    def _handle_precision_input(self, text):
        """Route numeric command-line input only to the active map tool."""
        tool = self._current_tool
        handler = getattr(tool, "handle_precision_input", None)
        if tool is None or not callable(handler):
            return False
        try:
            return bool(handler(text))
        except Exception as error:
            self._set_status(
                f"Precision input failed: {error}"
            )
            return True

    def _handle_command_enter(self):
        """Let the active map tool consume an empty command-line Enter."""
        tool = self._current_tool
        handler = getattr(tool, "handle_command_enter", None)
        if tool is None or not callable(handler):
            return False
        try:
            return bool(handler())
        except Exception as error:
            self._set_status(f"Unable to finish the active command: {error}")
            return True

    def _on_tool_finished(self):
        # Do not overwrite the tool's useful success/cancel message with a
        # generic "Ready" immediately after completion.
        if self._dock and hasattr(self._dock, "refresh_layer_state"):
            self._dock.refresh_layer_state()

    def _validate_tool_activation_context(self, tool_key):
        layer = self.iface.activeLayer()

        if tool_key in self._ACTIVE_TARGET_TOOLS:
            if not isinstance(layer, QgsVectorLayer):
                self._set_status("Select a target vector layer first")
                return False

            expected = self._ACTIVE_TARGET_GEOMETRY.get(tool_key)
            if expected is not None and layer.geometryType() != expected:
                target_name = (
                    "line"
                    if expected == QgsWkbTypes.GeometryType.LineGeometry
                    else "polygon"
                )
                self._set_status(
                    f"{tool_key.replace('_', ' ').title()} needs a {target_name} layer"
                )
                return False

            if not layer.isEditable():
                if not layer.startEditing():
                    self._set_status(
                        "The target layer is read-only"
                    )
                    return False
                self._set_status(
                    "Editing started automatically"
                )

        elif tool_key in self._EDITABLE_PICK_TOOLS:
            editable_layers = [
                lyr for lyr in QgsProject.instance().mapLayers().values()
                if isinstance(lyr, QgsVectorLayer) and lyr.isEditable()
            ]
            if not editable_layers and isinstance(layer, QgsVectorLayer):
                if layer.startEditing():
                    editable_layers.append(layer)
                    self._set_status(
                        "Editing started automatically"
                    )
            if not editable_layers:
                self._set_status(
                    "Start editing a vector layer first"
                )
                return False

        elif tool_key in self._READ_ONLY_PICK_TOOLS:
            has_vector = isinstance(layer, QgsVectorLayer) or any(
                isinstance(lyr, QgsVectorLayer)
                for lyr in QgsProject.instance().mapLayers().values()
            )
            if not has_vector:
                self._set_status(
                    "Add a vector source layer first"
                )
                return False

        return True

    def _create_tool(self, key):
        """Create a CAD map-tool instance."""
        canvas = self.iface.mapCanvas()

        try:
            # ── Drawing Tools ────────────────────────────────────────────
            if key == "line":
                from .sketcher.sketcher_line import sketcher_line
                t = sketcher_line(canvas, self.iface)
            elif key == "polyline":
                from .sketcher.sketcher_polyline import sketcher_polyline
                t = sketcher_polyline(canvas, self.iface)
            elif key == "rectangle":
                from .sketcher.sketcher_rectangle import sketcher_rectangle
                t = sketcher_rectangle(canvas, self.iface)
            elif key == "polygon":
                from .sketcher.sketcher_polygon import sketcher_polygon
                t = sketcher_polygon(canvas, self.iface)
            elif key == "circle":
                from .sketcher.sketcher_circle import sketcher_circle
                t = sketcher_circle(canvas, self.iface)
            elif key == "arc":
                from .sketcher.sketcher_arc import sketcher_arc
                t = sketcher_arc(canvas, self.iface)

            # ── Editing Tools ────────────────────────────────────────────
            elif key == "offset":
                from .tools.tool_offset import tool_offset
                t = tool_offset(canvas, self.iface)
            elif key == "trim":
                from .tools.tool_trim import tool_trim
                t = tool_trim(canvas, self.iface)
            elif key == "extend":
                from .tools.tool_extend import tool_extend
                t = tool_extend(canvas, self.iface)
            elif key == "fillet":
                from .tools.tool_fillet import tool_fillet
                t = tool_fillet(canvas, self.iface)
            elif key == "buffer":
                from .tools.tool_buffer import tool_buffer
                t = tool_buffer(canvas, self.iface)

            # ── Transform Tools ──────────────────────────────────────────
            elif key == "move":
                from .tools.tool_move import tool_move
                t = tool_move(canvas, self.iface)
            elif key == "copy":
                from .tools.tool_copy import tool_copy
                t = tool_copy(canvas, self.iface)
            elif key == "rotate":
                from .tools.tool_rotate import tool_rotate
                t = tool_rotate(canvas, self.iface)
            elif key == "scale":
                from .tools.tool_scale import tool_scale
                t = tool_scale(canvas, self.iface)
            elif key == "mirror":
                from .tools.tool_mirror import tool_mirror
                t = tool_mirror(canvas, self.iface)

            # ── Array, construction, and dimension tools ────────────────
            elif key == "array":
                from .tools.tool_array import tool_array
                t = tool_array(canvas, self.iface)
            elif key == "vertex_edit":
                from .tools.tool_vertex_edit import tool_vertex_edit
                t = tool_vertex_edit(canvas, self.iface)
            elif key == "hatch":
                from .tools.tool_hatch import tool_hatch
                t = tool_hatch(canvas, self.iface)
            elif key == "construction_inf":
                from .tools.tool_construction_line import tool_construction_line
                t = tool_construction_line(canvas, self.iface, mode=tool_construction_line.MODE_INFINITE)
            elif key == "construction_ray":
                from .tools.tool_construction_line import tool_construction_line
                t = tool_construction_line(canvas, self.iface, mode=tool_construction_line.MODE_RAY)
            elif key == "construction_seg":
                from .tools.tool_construction_line import tool_construction_line
                t = tool_construction_line(canvas, self.iface, mode=tool_construction_line.MODE_SEGMENT)
            elif key == "dimension":
                from .tools.tool_dimension import tool_dimension
                t = tool_dimension(canvas, self.iface)
            elif key == "divide":
                from .tools.tool_divide import tool_divide
                t = tool_divide(canvas, self.iface)
            elif key == "multi_offset":
                from .tools.tool_multi_offset import tool_multi_offset
                t = tool_multi_offset(canvas, self.iface)
            elif key == "join":
                from .tools.tool_join import tool_join
                t = tool_join(canvas, self.iface)

            # ── Measurement ──────────────────────────────────────────────
            elif key == "measure":
                from .tools.tool_measure import tool_measure
                t = tool_measure(canvas, self.iface, mode=0)
            elif key == "measure_area":
                from .tools.tool_measure import tool_measure
                t = tool_measure(canvas, self.iface, mode=1)
            elif key == "measure_select_line":
                from .tools.tool_measure_select import tool_measure_select
                t = tool_measure_select(canvas, self.iface, mode=0)
            elif key == "measure_select_area":
                from .tools.tool_measure_select import tool_measure_select
                t = tool_measure_select(canvas, self.iface, mode=1)

            # ── Urban Planning ───────────────────────────────────────────
            elif key == "road":
                from .urban.road_sketcher import RoadSketcher
                t = RoadSketcher(canvas, self.iface)
            elif key == "junction":
                from .urban.junction_sketcher import JunctionSketcher
                t = JunctionSketcher(canvas, self.iface)
            elif key == "ada_kirma":
                from .urban.ada_kirma_sketcher import AdaKirmaSketcher
                t = AdaKirmaSketcher(canvas, self.iface)

            else:
                return None

            # Relay through plugin-owned slots so tools created by shortcuts
            # before the dock opens still report status after it is opened.
            if hasattr(t, 'sketcher_message'):
                t.sketcher_message.connect(self._relay_tool_message)
            if hasattr(t, 'tool_message'):
                t.tool_message.connect(self._relay_tool_message)

            if hasattr(t, 'sketcher_finished'):
                t.sketcher_finished.connect(self._on_tool_finished)
            if hasattr(t, 'tool_finished'):
                t.tool_finished.connect(self._on_tool_finished)
            if hasattr(t, 'precision_key_started'):
                t.precision_key_started.connect(self._begin_precision_entry)

            return t

        except Exception as e:
            print(f"[PlanX CAD] Failed to load tool '{key}': {e}")
            import traceback
            traceback.print_exc()
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _add_action(self, icon_path, text, callback, add_to_toolbar=True,
                    add_to_menu=True, checkable=False, status_tip=None):
        """Add an action to the toolbar and/or menu."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, self.iface.mainWindow())
        action.triggered.connect(callback)
        action.setCheckable(checkable)

        if status_tip:
            action.setStatusTip(status_tip)

        if add_to_toolbar and self.toolbar:
            self.toolbar.addAction(action)

        if add_to_menu and self.menu:
            self.menu.addAction(action)

        self.actions.append(action)
        return action

    def _show_about(self):
        """Show plugin version and capability information."""
        version = "1.0.0"
        with suppress(Exception):
            meta_path = os.path.join(self.plugin_dir, "metadata.txt")
            with open(meta_path, "r", encoding="utf-8") as f:
                import re
                content = f.read()
                match = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if match:
                    version = match.group(1).strip()

        QMessageBox.about(
            self.iface.mainWindow(),
            "About PlanX CAD Toolset",
            f"""
<h2>PlanX CAD Toolset</h2>
<p>Version: {version}</p>

<h3>Features</h3>
<ul>
<li><b>6 Drawing Tools:</b> Line, Polyline, Rectangle, Polygon, Circle, Arc</li>
<li><b>14 Editing and Construction Tools:</b> Offset, Trim, Extend, Fillet, Buffer, Array, Vertex Edit, Divide, Multi-Offset, Join, Hatch, XLine, Ray, Segment</li>
<li><b>5 Transform Tools:</b> Move, Copy, Rotate, Scale, Mirror</li>
<li><b>5 Measurement Tools:</b> Distance, Area, Dimension, Select Line, Select Area</li>
<li><b>3 Urban Planning Tools:</b> Road, Junction, Block Chamfer</li>
</ul>

<p>Designed for precise CAD and urban-planning workflows inside QGIS.</p>
<p><i>Integrates with native QGIS snapping and editing.</i></p>
"""
        )

    @staticmethod
    def _open_plugin_page():
        QDesktopServices.openUrl(
            QUrl("https://plugins.qgis.org/plugins/planX_CAD_arac_Seti/")
        )

    def _show_shortcut_guide(self):
        try:
            from .dialogs.shortcut_help_dialog import ShortcutHelpDialog
            dlg = ShortcutHelpDialog(
                self._tool_palette_entries(), self.iface.mainWindow()
            )
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Shortcut Guide",
                f"Shortcut guide could not be opened:\n{e}"
            )

    def _show_command_reference(self, anchor=None):
        try:
            from .dialogs.docs_dialog import DocsDialog
            dlg = DocsDialog(self.plugin_dir, self.iface.mainWindow(), initial_tab=0, command_anchor=anchor)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Command Reference",
                f"Command reference could not be opened:\n{e}"
            )

    def _show_smoke_test(self):
        try:
            from .dialogs.docs_dialog import DocsDialog
            dlg = DocsDialog(self.plugin_dir, self.iface.mainWindow(), initial_tab=2, command_anchor=None)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Smoke Test Checklist",
                f"Smoke test checklist could not be opened:\n{e}"
            )

    def _show_command_palette(self):
        try:
            from .dialogs.command_palette_dialog import CommandPaletteDialog
            usage_counts = {}
            if self._dock and hasattr(self._dock, "diagnostics_snapshot"):
                usage_counts = self._dock.diagnostics_snapshot().get("tool_usage_counts", {})
            dlg = CommandPaletteDialog(
                self._tool_palette_entries(),
                usage_counts=usage_counts,
                parent=self.iface.mainWindow(),
            )
            dlg.tool_selected.connect(self._activate_tool)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Command Palette",
                f"Command palette could not be opened:\n{e}"
            )

    def _show_session_checklist(self):
        try:
            from .dialogs.session_checklist_dialog import SessionChecklistDialog
            dlg = SessionChecklistDialog(
                run_preflight_cb=self._run_dock_preflight,
                run_health_cb=self._show_health_check,
                run_audit_cb=self._show_shortcut_audit,
                parent=self.iface.mainWindow()
            )
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Session Checklist",
                f"Session checklist could not be opened:\n{e}"
            )

    def _show_quick_start(self):
        try:
            from .dialogs.quick_start_dialog import QuickStartDialog
            dlg = QuickStartDialog(self.iface.mainWindow())
            dlg.exec()
            QSettings("PlanX", "PlanXCAD").setValue(
                "onboarding/quick_start_seen", True
            )
            return True
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Quick Start",
                f"Quick Start could not be opened:\n{e}"
            )
            return False

    def _show_scheduled_quick_start(self):
        timer = self._quick_start_timer
        self._quick_start_timer = None
        if timer is not None:
            timer.deleteLater()
        if not self._unloading:
            self._show_quick_start()

    def _maybe_show_quick_start_once(self):
        with suppress(Exception):
            s = QSettings("PlanX", "PlanXCAD")
            seen = s.value("onboarding/quick_start_seen", False, type=bool)
            if seen:
                return
            self._quick_start_timer = QTimer(self.iface.mainWindow())
            self._quick_start_timer.setSingleShot(True)
            self._quick_start_timer.timeout.connect(
                self._show_scheduled_quick_start
            )
            self._quick_start_timer.start(400)
