# -*- coding: utf-8 -*-
"""
planX CAD AraÃ§ Seti â€” Ana Plugin SÄ±nÄ±fÄ±
18 CAD aracÄ±, dockable panel UI, toolbar ve menÃ¼ yÃ¶netimi.
"""

import os

from qgis.PyQt.QtCore import Qt, QTimer, QSettings
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QShortcut


class PlanXCADPlugin:
    """planX CAD AraÃ§ Seti ana plugin sÄ±nÄ±fÄ±."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_dir = os.path.join(self.plugin_dir, "icons")

        self.actions = []
        self.menu = None
        self.toolbar = None
        self._dock = None
        self._current_tool = None

        # AraÃ§ instance'larÄ± (lazy loaded)
        self._tools = {}

        # Tool history: most-recently activated key for "repeat last"
        self._last_tool_key = None
        # QShortcuts owned by the plugin (cleaned up in unload)
        self._shortcuts = []

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # QGIS Plugin Interface
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def initGui(self):
        """QGIS GUI'ye menÃ¼, toolbar ve dock widget ekle."""
        # â”€â”€ MenÃ¼ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.menu = QMenu("&planX CAD Toolset / AraÃ§ Seti")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # â”€â”€ Toolbar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.toolbar = QToolBar("planX CAD Toolbar")
        self.toolbar.setObjectName("PlanXCADToolbar")
        self.iface.addToolBar(self.toolbar)

        # â”€â”€ Ana Panel Toggle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        main_icon = os.path.join(self.icon_dir, "icon_main.svg")
        self.panel_action = self._add_action(
            main_icon,
            "planX CAD Panel / Paneli",
            self._toggle_dock,
            checkable=True,
            status_tip="Open/close planX CAD panel / planX CAD panelini aÃ§/kapat"
        )

        # â”€â”€ MenÃ¼ Separator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.menu.addSeparator()

        # â”€â”€ HakkÄ±nda â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "About / HakkÄ±nda",
            self._show_about,
            add_to_toolbar=False,
            status_tip="About planX CAD Toolset / planX CAD AraÃ§ Seti hakkÄ±nda"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Shortcut Guide / Kisayol Rehberi",
            self._show_shortcut_guide,
            add_to_toolbar=False,
            status_tip="Shortcut and workflow guide / Kisayol ve is akisi rehberi"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Command Reference / Komut Kilavuzu",
            self._show_command_reference,
            add_to_toolbar=False,
            status_tip="Detailed command documentation / Detayli komut dokumani"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Smoke Test Checklist / Duman Test Listesi",
            self._show_smoke_test,
            add_to_toolbar=False,
            status_tip="Open QGIS smoke test checklist / QGIS duman test listesini ac"
        )
        self._add_action(
            ":/images/themes/default/mIconExpression.svg",
            "Command Palette / Komut Paleti",
            self._show_command_palette,
            add_to_toolbar=False,
            status_tip="Fast command activation / Hizli komut aktivasyonu"
        )
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Quick Start / Hizli Baslangic",
            self._show_quick_start,
            add_to_toolbar=False,
            status_tip="Open onboarding guide / Baslangic rehberini ac"
        )
        self._add_action(
            ":/images/themes/default/mActionRefresh.svg",
            "Session Checklist / Oturum Kontrol Listesi",
            self._show_session_checklist,
            add_to_toolbar=False,
            status_tip="Run beta session checklist / Beta oturum kontrol listesini ac"
        )
        self._add_action(
            ":/images/themes/default/mActionPropertiesWidget.svg",
            "Diagnostics / Tani",
            self._show_diagnostics,
            add_to_toolbar=False,
            status_tip="Open runtime diagnostics report / Calisma tani raporunu ac"
        )
        self._add_action(
            ":/images/themes/default/mActionOptions.svg",
            "Health Check / Sistem Kontrolu",
            self._show_health_check,
            add_to_toolbar=False,
            status_tip="Run runtime readiness checks / Calisma hazirlik kontrollerini calistir"
        )
        self._add_action(
            ":/images/themes/default/mIconFieldInteger.svg",
            "Shortcut Audit / Kisayol Denetimi",
            self._show_shortcut_audit,
            add_to_toolbar=False,
            status_tip="Check shortcut conflicts and duplicates / Kisayol cakisma ve tekrarlarini kontrol et"
        )
        self._add_action(
            ":/images/themes/default/mIconNewText.svg",
            "Issue Template / Hata Rapor Sablonu",
            self._show_issue_template,
            add_to_toolbar=False,
            status_tip="Open copy-ready issue report template / Kopyalanabilir hata rapor sablonu ac"
        )
        self._add_action(
            ":/images/themes/default/mActionRefresh.svg",
            "Release Readiness / Surum Hazirlik",
            self._show_release_readiness,
            add_to_toolbar=False,
            status_tip="Open beta release readiness checks / Beta surum hazirlik kontrollerini ac"
        )

        # â”€â”€ Klavye kÄ±sayollarÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._setup_shortcuts()
        self._maybe_show_quick_start_once()

    def unload(self):
        """Plugin kaldÄ±rÄ±ldÄ±ÄŸÄ±nda temizlik yap."""
        # Aktif aracÄ± deaktive et
        if self._current_tool:
            self.iface.mapCanvas().unsetMapTool(self._current_tool)
            self._current_tool = None

        # Dock widget
        if self._dock:
            if hasattr(self._dock, 'unload'):
                self._dock.unload()
            try:
                self.iface.currentLayerChanged.disconnect(self._on_current_layer_changed)
            except Exception:
                pass
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

        # AraÃ§lar
        for tool in self._tools.values():
            if tool:
                del tool
        self._tools.clear()

        # Klavye kÄ±sayollarÄ±
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        # Actions
        for action in self.actions:
            self.iface.removePluginMenu("&planX CAD AraÃ§ Seti", action)

        # Toolbar
        if self.toolbar:
            del self.toolbar

        # Menu
        if self.menu:
            self.menu.deleteLater()

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Dock Widget
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _toggle_dock(self):
        """Dock widget'Ä± aÃ§/kapat."""
        if self._dock is None:
            try:
                from .dialogs.cad_dock import CADDockWidget

                self._dock = CADDockWidget(
                    self.iface, self.icon_dir, self.iface.mainWindow()
                )
                self._dock.setObjectName("PlanXCADDock")
                self._dock.visibilityChanged.connect(self._on_dock_visibility)
                self._dock.tool_activated.connect(self._activate_tool)
                self._dock.cancel_requested.connect(self._cancel_active_tool)
                self._dock.edit_toggle_requested.connect(self._toggle_active_layer_editing)
                self._dock.quick_start_requested.connect(self._show_quick_start)
                self._dock.docs_requested.connect(self._show_command_reference)
                self._dock.shortcuts_requested.connect(self._show_shortcut_guide)
                self._dock.diagnostics_requested.connect(self._show_diagnostics)
                self._dock.workspace_reset_requested.connect(self._reset_workspace_state)
                self._dock.tool_help_requested.connect(self._show_tool_help)
                self._dock.usage_stats_requested.connect(self._show_usage_stats)
                self._dock.health_check_requested.connect(self._show_health_check)
                self._dock.shortcut_audit_requested.connect(self._show_shortcut_audit)
                try:
                    self.iface.currentLayerChanged.connect(self._on_current_layer_changed)
                except Exception:
                    pass

                self.iface.addDockWidget(
                    Qt.LeftDockWidgetArea, self._dock
                )
                self._dock.show()
                self._dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error / Hata",
                    f"Failed to create panel / Panel oluÅŸturulamadÄ±:\n{str(e)}"
                )
                self.panel_action.setChecked(False)
                return

        # Toggle
        if self._dock.isVisible():
            self._dock.hide()
        else:
            self._dock.show()
            self._dock.raise_()

    def _on_dock_visibility(self, visible):
        self.panel_action.setChecked(visible)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # AraÃ§ YÃ¶netimi
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # Dialog aÃ§an araÃ§lar â€” her seferinde yeni instance gerekir
    _DIALOG_TOOLS = {"buffer", "fillet", "polygon", "road", "junction", "measure_area", "ada_kirma", "array", "divide", "multi_offset", "join", "hatch"}
    _TOOLS_REQUIRING_LAYER = {
        "line", "polyline", "rectangle", "polygon", "circle", "arc",
        "offset", "trim", "extend", "fillet", "buffer", "vertex_edit", "hatch",
        "construction_inf", "construction_ray", "construction_seg",
        "move", "copy", "rotate", "scale", "mirror", "array",
        "dimension", "divide", "multi_offset", "join",
        "road", "junction", "ada_kirma",
    }
    _TOOLS_REQUIRING_EDITABLE = set(_TOOLS_REQUIRING_LAYER)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Klavye kÄ±sayollarÄ± + tool history
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # Tool-key -> shortcut spec. Ctrl+Shift+<letter> seÃ§ildi: QGIS'in built-in
    # shortcut'larÄ±yla Ã§akÄ±ÅŸmÄ±yor, kolay hatÄ±rlanÄ±r.
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

    def _setup_shortcuts(self):
        """QShortcut'lar QGIS main window'a baÄŸlanÄ±r (Qt.ShortcutContext.ApplicationShortcut
        context). Plugin yÃ¼klÃ¼ iken her yerden Ã§alÄ±ÅŸÄ±rlar; unload'da temizlenir."""
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
        elif self._dock:
            self._dock.set_status("âš ï¸ No previous tool to repeat / Tekrarlanacak eski bir araÃ§ yok")

    def _focus_dock_search(self):
        if self._dock is None:
            self._toggle_dock()
        if self._dock and hasattr(self._dock, "focus_search"):
            self._dock.focus_search()

    def _cancel_active_tool(self):
        canvas = self.iface.mapCanvas()
        if self._current_tool:
            canvas.unsetMapTool(self._current_tool)
            self._current_tool = None
        if self._dock:
            self._dock.uncheck_all()
            self._dock.set_status("Active tool cancelled / Aktif arac iptal edildi")
            if hasattr(self._dock, "refresh_layer_state"):
                self._dock.refresh_layer_state()

    def _toggle_active_layer_editing(self):
        layer = self.iface.activeLayer()
        if layer is None:
            if self._dock:
                self._dock.set_status("No active layer / Aktif katman yok")
            return
        if not hasattr(layer, "isEditable"):
            if self._dock:
                self._dock.set_status("Layer does not support editing / Katman duzenleme desteklemiyor")
            return

        try:
            if layer.isEditable():
                layer.commitChanges()
                msg = "Editing OFF / Duzenleme KAPALI"
            else:
                layer.startEditing()
                msg = "Editing ON / Duzenleme ACIK"
            if self._dock:
                self._dock.set_status(msg)
                if hasattr(self._dock, "refresh_layer_state"):
                    self._dock.refresh_layer_state()
        except Exception as e:
            if self._dock:
                self._dock.set_status(f"Editing toggle failed / Duzenleme degistirilemedi: {e}")

    def _on_current_layer_changed(self, _layer):
        if self._dock and hasattr(self._dock, "refresh_layer_state"):
            self._dock.refresh_layer_state()

    def _run_dock_preflight(self):
        if self._dock and hasattr(self._dock, "run_preflight"):
            self._dock.run_preflight()

    def _pin_last_tool(self):
        if self._dock and hasattr(self._dock, "pin_last_tool"):
            self._dock.pin_last_tool()

    def _reset_workspace_state(self):
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
        text = ["Shortcut Audit / Kisayol Denetimi", "==============================", ""]
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
            dlg.setWindowTitle("PlanX CAD - Shortcut Audit / Kisayol Denetimi")
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
            ("command_palette", "Ctrl+Alt+P"),
            ("cancel_active_tool", "Ctrl+Alt+C"),
            ("toggle_layer_editing", "Ctrl+Alt+E"),
            ("run_preflight", "Ctrl+Alt+F"),
            ("quick_start", "Ctrl+Alt+Q"),
            ("pin_last_tool", "Ctrl+Alt+Z"),
            ("open_diagnostics", "Ctrl+Alt+D"),
            ("reset_workspace_state", "Ctrl+Alt+R"),
            ("open_usage_stats", "Ctrl+Alt+T"),
            ("open_health_check", "Ctrl+Alt+W"),
            ("open_shortcut_audit", "Ctrl+Alt+Y"),
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
            "PlanX CAD Diagnostics / Tani Raporu",
            "===================================",
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
            dlg.setWindowTitle("PlanX CAD - Issue Template / Hata Rapor Sablonu")
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
            "PlanX CAD Issue Template / Hata Rapor Sablonu\n"
            "============================================\n\n"
            "1) Summary / Ozet:\n"
            "-\n\n"
            "2) Expected behavior / Beklenen davranis:\n"
            "-\n\n"
            "3) Actual behavior / Gercek davranis:\n"
            "-\n\n"
            "4) Reproduction steps / Tekrarlama adimlari:\n"
            "1.\n2.\n3.\n\n"
            "5) Data context / Veri baglami:\n"
            "- CRS:\n- Layer type:\n- Editable state:\n\n"
            "6) Attach diagnostics / Tani metni:\n\n"
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
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                import re
                content = f.read()
                m = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if m:
                    version = m.group(1).strip()
        except Exception:
            pass
        rows.append({
            "check": "Metadata version",
            "status": "OK" if version not in ("", "unknown") else "WARN",
            "value": version,
            "action": "Set release target version before packaging",
        })
        return rows

    def _activate_tool(self, tool_key):
        """AraÃ§ tuÅŸuna basÄ±ldÄ±ÄŸÄ±nda ilgili map tool'u aktifleÅŸtirir."""
        # "Repeat last" button in dock emits the sentinel key.
        if tool_key == "__repeat__":
            self._repeat_last_tool()
            return
        if not self._validate_tool_activation_context(tool_key):
            return

        canvas = self.iface.mapCanvas()

        # Ã–nceki aracÄ± deaktive et
        if self._current_tool:
            canvas.unsetMapTool(self._current_tool)
            self._current_tool = None

        # Tool history â€” used by Ctrl+Shift+Space ("repeat last tool")
        self._last_tool_key = tool_key

        # Dialog tabanlÄ± araÃ§lar â†’ her seferinde yeni instance
        if tool_key in self._DIALOG_TOOLS:
            tool = self._create_tool(tool_key)
        else:
            # Lazy load: araÃ§ henÃ¼z oluÅŸturulmadÄ±ysa oluÅŸtur
            if tool_key not in self._tools:
                self._tools[tool_key] = self._create_tool(tool_key)
            tool = self._tools.get(tool_key)

        if tool is None:
            if self._dock:
                self._dock.set_status(f"âš ï¸ Failed to load tool '{tool_key}' / '{tool_key}' aracÄ± yÃ¼klenemedi")
            return

        self._current_tool = tool
        canvas.setMapTool(tool)
        if self._dock and hasattr(self._dock, "register_tool_activation"):
            self._dock.register_tool_activation(tool_key)

    def _validate_tool_activation_context(self, tool_key):
        layer = self.iface.activeLayer()

        if tool_key in self._TOOLS_REQUIRING_LAYER and layer is None:
            if self._dock:
                self._dock.set_status("Select a target layer first / Once hedef katman secin")
            return False

        if tool_key in self._TOOLS_REQUIRING_LAYER and layer is not None:
            if not hasattr(layer, "geometryType"):
                if self._dock:
                    self._dock.set_status("Active layer is not vector / Aktif katman vektor degil")
                return False

        if tool_key in self._TOOLS_REQUIRING_EDITABLE and layer is not None:
            editable = bool(layer.isEditable()) if hasattr(layer, "isEditable") else False
            if not editable:
                if self._dock:
                    self._dock.set_status(
                        "Layer is read-only: use Edit ON/OFF / Katman salt-okunur: Edit ON/OFF kullanin"
                    )
                return False

        return True

    def _create_tool(self, key):
        """AraÃ§ instance'Ä± oluÅŸturur."""
        canvas = self.iface.mapCanvas()

        try:
            # â”€â”€ Ã‡izim AraÃ§larÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # â”€â”€ DÃ¼zenleme AraÃ§larÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # â”€â”€ DÃ¶nÃ¼ÅŸÃ¼m AraÃ§larÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # â”€â”€ Yeni: Array & Dimension â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # â”€â”€ Ã–lÃ§Ã¼m â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # â”€â”€ Åžehir Planlama â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

            # Mesaj sinyalini dock widget'a baÄŸla
            if hasattr(t, 'sketcher_message') and self._dock:
                t.sketcher_message.connect(self._dock.set_status)
            if hasattr(t, 'tool_message') and self._dock:
                t.tool_message.connect(self._dock.set_status)

            # BitÄ±ÅŸ sinyali
            if hasattr(t, 'sketcher_finished') and self._dock:
                t.sketcher_finished.connect(
                    lambda: self._dock.set_status("Ready / HazÄ±r")
                )
            if hasattr(t, 'tool_finished') and self._dock:
                t.tool_finished.connect(
                    lambda: self._dock.set_status("Ready / HazÄ±r")
                )

            return t

        except Exception as e:
            print(f"[planX-CAD] AraÃ§ yÃ¼klenemedi ({key}): {e}")
            import traceback
            traceback.print_exc()
            return None

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # YardÄ±mcÄ±
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    def _add_action(self, icon_path, text, callback, add_to_toolbar=True,
                    add_to_menu=True, checkable=False, status_tip=None):
        """Toolbar/menÃ¼ye action ekle."""
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
        """HakkÄ±nda dialog'unu gÃ¶ster."""
        version = "1.0.0"
        try:
            meta_path = os.path.join(self.plugin_dir, "metadata.txt")
            with open(meta_path, "r", encoding="utf-8") as f:
                import re
                content = f.read()
                match = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if match:
                    version = match.group(1).strip()
        except Exception:
            pass

        QMessageBox.about(
            self.iface.mainWindow(),
            "About planX CAD Toolset / planX CAD AraÃ§ Seti HakkÄ±nda",
            f"""
<h2>planX CAD Toolset / AraÃ§ Seti</h2>
<p>Version / Versiyon: {version}</p>

<h3>Features / Ã–zellikler:</h3>
<ul>
<li><b>6 Drawing Tools / Ã‡izim AracÄ±:</b> Line, Polyline, Rectangle, Polygon, Circle, Arc</li>
<li><b>7 Editing Tools / DÃ¼zenleme AracÄ±:</b> Offset, Trim, Extend, Fillet, Buffer, Divide, Join</li>
<li><b>5 Transform Tools / DÃ¶nÃ¼ÅŸÃ¼m AracÄ±:</b> Move, Copy, Rotate, Scale, Mirror</li>
<li><b>5 Measurement Tools / Ã–lÃ§Ã¼m AracÄ±:</b> Distance, Area, Dimension, Select Line, Select Area</li>
<li><b>3 Urban Planning Tools / Åžehir Planlama AracÄ±:</b> Road, Junction, Block Chamfer</li>
</ul>

<p>Designed for urban planning workflows / Åžehir planlama sÃ¼reÃ§leri iÃ§in tasarlanmÄ±ÅŸtÄ±r.</p>
<p><i>Integrates with QGIS snapping / QGIS native snap desteÄŸi ile Ã§alÄ±ÅŸÄ±r.</i></p>
"""
        )

    def _show_shortcut_guide(self):
        try:
            from .dialogs.shortcut_help_dialog import ShortcutHelpDialog
            dlg = ShortcutHelpDialog(self._SHORTCUTS, self.iface.mainWindow())
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
            dlg = CommandPaletteDialog(self._SHORTCUTS, usage_counts=usage_counts, parent=self.iface.mainWindow())
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
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Quick Start",
                f"Quick Start could not be opened:\n{e}"
            )

    def _maybe_show_quick_start_once(self):
        try:
            s = QSettings("PlanX", "PlanXCAD")
            seen = s.value("onboarding/quick_start_seen", False, type=bool)
            if seen:
                return
            QTimer.singleShot(400, self._show_quick_start)
            s.setValue("onboarding/quick_start_seen", True)
        except Exception:
            pass
