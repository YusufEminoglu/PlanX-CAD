# -*- coding: utf-8 -*-
"""
planX CAD Araç Seti — Ana Plugin Sınıfı
18 CAD aracı, dockable panel UI, toolbar ve menü yönetimi.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox, QShortcut


class PlanXCADPlugin:
    """planX CAD Araç Seti ana plugin sınıfı."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.icon_dir = os.path.join(self.plugin_dir, "icons")

        self.actions = []
        self.menu = None
        self.toolbar = None
        self._dock = None
        self._current_tool = None

        # Araç instance'ları (lazy loaded)
        self._tools = {}

        # Tool history: most-recently activated key for "repeat last"
        self._last_tool_key = None
        # QShortcuts owned by the plugin (cleaned up in unload)
        self._shortcuts = []

    # ═══════════════════════════════════════════════════════════════════════
    # QGIS Plugin Interface
    # ═══════════════════════════════════════════════════════════════════════

    def initGui(self):
        """QGIS GUI'ye menü, toolbar ve dock widget ekle."""
        # ── Menü ─────────────────────────────────────────────────────────
        self.menu = QMenu("&planX CAD Toolset / Araç Seti")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # ── Toolbar ──────────────────────────────────────────────────────
        self.toolbar = QToolBar("planX CAD Toolbar")
        self.toolbar.setObjectName("PlanXCADToolbar")
        self.iface.addToolBar(self.toolbar)

        # ── Ana Panel Toggle ─────────────────────────────────────────────
        main_icon = os.path.join(self.icon_dir, "icon_main.svg")
        self.panel_action = self._add_action(
            main_icon,
            "planX CAD Panel / Paneli",
            self._toggle_dock,
            checkable=True,
            status_tip="Open/close planX CAD panel / planX CAD panelini aç/kapat"
        )

        # ── Menü Separator ───────────────────────────────────────────────
        self.menu.addSeparator()

        # ── Hakkında ─────────────────────────────────────────────────────
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "About / Hakkında",
            self._show_about,
            add_to_toolbar=False,
            status_tip="About planX CAD Toolset / planX CAD Araç Seti hakkında"
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

        # ── Klavye kısayolları ─────────────────────────────────────────────
        self._setup_shortcuts()

    def unload(self):
        """Plugin kaldırıldığında temizlik yap."""
        # Aktif aracı deaktive et
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

        # Araçlar
        for tool in self._tools.values():
            if tool:
                del tool
        self._tools.clear()

        # Klavye kısayolları
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        # Actions
        for action in self.actions:
            self.iface.removePluginMenu("&planX CAD Araç Seti", action)

        # Toolbar
        if self.toolbar:
            del self.toolbar

        # Menu
        if self.menu:
            self.menu.deleteLater()

    # ═══════════════════════════════════════════════════════════════════════
    # Dock Widget
    # ═══════════════════════════════════════════════════════════════════════

    def _toggle_dock(self):
        """Dock widget'ı aç/kapat."""
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
                    f"Failed to create panel / Panel oluşturulamadı:\n{str(e)}"
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

    # ═══════════════════════════════════════════════════════════════════════
    # Araç Yönetimi
    # ═══════════════════════════════════════════════════════════════════════

    # Dialog açan araçlar — her seferinde yeni instance gerekir
    _DIALOG_TOOLS = {"buffer", "fillet", "polygon", "road", "junction", "measure_area", "ada_kirma", "array", "divide", "multi_offset", "join", "hatch"}

    # ═══════════════════════════════════════════════════════════════════════
    # Klavye kısayolları + tool history
    # ═══════════════════════════════════════════════════════════════════════

    # Tool-key -> shortcut spec. Ctrl+Shift+<letter> seçildi: QGIS'in built-in
    # shortcut'larıyla çakışmıyor, kolay hatırlanır.
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
        """QShortcut'lar QGIS main window'a bağlanır (Qt.ApplicationShortcut
        context). Plugin yüklü iken her yerden çalışırlar; unload'da temizlenir."""
        parent = self.iface.mainWindow()
        for key, seq in self._SHORTCUTS:
            sc = QShortcut(QKeySequence(seq), parent)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(lambda k=key: self._activate_tool(k))
            self._shortcuts.append(sc)
        # Repeat last tool
        repeat = QShortcut(QKeySequence("Ctrl+Shift+Space"), parent)
        repeat.setContext(Qt.ApplicationShortcut)
        repeat.activated.connect(self._repeat_last_tool)
        self._shortcuts.append(repeat)
        # Focus dock search
        focus_search = QShortcut(QKeySequence("Ctrl+Shift+S"), parent)
        focus_search.setContext(Qt.ApplicationShortcut)
        focus_search.activated.connect(self._focus_dock_search)
        self._shortcuts.append(focus_search)
        # Shortcut guide
        shortcut_help = QShortcut(QKeySequence("Ctrl+Shift+/"), parent)
        shortcut_help.setContext(Qt.ApplicationShortcut)
        shortcut_help.activated.connect(self._show_shortcut_guide)
        self._shortcuts.append(shortcut_help)
        docs_help = QShortcut(QKeySequence("Ctrl+Alt+H"), parent)
        docs_help.setContext(Qt.ApplicationShortcut)
        docs_help.activated.connect(self._show_command_reference)
        self._shortcuts.append(docs_help)
        palette = QShortcut(QKeySequence("Ctrl+Alt+P"), parent)
        palette.setContext(Qt.ApplicationShortcut)
        palette.activated.connect(self._show_command_palette)
        self._shortcuts.append(palette)
        cancel_tool = QShortcut(QKeySequence("Ctrl+Alt+C"), parent)
        cancel_tool.setContext(Qt.ApplicationShortcut)
        cancel_tool.activated.connect(self._cancel_active_tool)
        self._shortcuts.append(cancel_tool)
        edit_toggle = QShortcut(QKeySequence("Ctrl+Alt+E"), parent)
        edit_toggle.setContext(Qt.ApplicationShortcut)
        edit_toggle.activated.connect(self._toggle_active_layer_editing)
        self._shortcuts.append(edit_toggle)
        preflight = QShortcut(QKeySequence("Ctrl+Alt+F"), parent)
        preflight.setContext(Qt.ApplicationShortcut)
        preflight.activated.connect(self._run_dock_preflight)
        self._shortcuts.append(preflight)
        quick_start = QShortcut(QKeySequence("Ctrl+Alt+Q"), parent)
        quick_start.setContext(Qt.ApplicationShortcut)
        quick_start.activated.connect(self._show_quick_start)
        self._shortcuts.append(quick_start)

    def _repeat_last_tool(self):
        if self._last_tool_key:
            self._activate_tool(self._last_tool_key)
        elif self._dock:
            self._dock.set_status("⚠️ No previous tool to repeat / Tekrarlanacak eski bir araç yok")

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

    def _activate_tool(self, tool_key):
        """Araç tuşuna basıldığında ilgili map tool'u aktifleştirir."""
        # "Repeat last" button in dock emits the sentinel key.
        if tool_key == "__repeat__":
            self._repeat_last_tool()
            return

        canvas = self.iface.mapCanvas()

        # Önceki aracı deaktive et
        if self._current_tool:
            canvas.unsetMapTool(self._current_tool)
            self._current_tool = None

        # Tool history — used by Ctrl+Shift+Space ("repeat last tool")
        self._last_tool_key = tool_key

        # Dialog tabanlı araçlar → her seferinde yeni instance
        if tool_key in self._DIALOG_TOOLS:
            tool = self._create_tool(tool_key)
        else:
            # Lazy load: araç henüz oluşturulmadıysa oluştur
            if tool_key not in self._tools:
                self._tools[tool_key] = self._create_tool(tool_key)
            tool = self._tools.get(tool_key)

        if tool is None:
            if self._dock:
                self._dock.set_status(f"⚠️ Failed to load tool '{tool_key}' / '{tool_key}' aracı yüklenemedi")
            return

        self._current_tool = tool
        canvas.setMapTool(tool)
        if self._dock and hasattr(self._dock, "register_tool_activation"):
            self._dock.register_tool_activation(tool_key)

    def _create_tool(self, key):
        """Araç instance'ı oluşturur."""
        canvas = self.iface.mapCanvas()

        try:
            # ── Çizim Araçları ───────────────────────────────────────────
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

            # ── Düzenleme Araçları ───────────────────────────────────────
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

            # ── Dönüşüm Araçları ────────────────────────────────────────
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

            # ── Yeni: Array & Dimension ─────────────────────────────────
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

            # ── Ölçüm ───────────────────────────────────────────────────
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

            # ── Şehir Planlama ──────────────────────────────────────────
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

            # Mesaj sinyalini dock widget'a bağla
            if hasattr(t, 'sketcher_message') and self._dock:
                t.sketcher_message.connect(self._dock.set_status)
            if hasattr(t, 'tool_message') and self._dock:
                t.tool_message.connect(self._dock.set_status)

            # Bitış sinyali
            if hasattr(t, 'sketcher_finished') and self._dock:
                t.sketcher_finished.connect(
                    lambda: self._dock.set_status("Ready / Hazır")
                )
            if hasattr(t, 'tool_finished') and self._dock:
                t.tool_finished.connect(
                    lambda: self._dock.set_status("Ready / Hazır")
                )

            return t

        except Exception as e:
            print(f"[planX-CAD] Araç yüklenemedi ({key}): {e}")
            import traceback
            traceback.print_exc()
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # Yardımcı
    # ═══════════════════════════════════════════════════════════════════════

    def _add_action(self, icon_path, text, callback, add_to_toolbar=True,
                    add_to_menu=True, checkable=False, status_tip=None):
        """Toolbar/menüye action ekle."""
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
        """Hakkında dialog'unu göster."""
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
            "About planX CAD Toolset / planX CAD Araç Seti Hakkında",
            f"""
<h2>planX CAD Toolset / Araç Seti</h2>
<p>Version / Versiyon: {version}</p>

<h3>Features / Özellikler:</h3>
<ul>
<li><b>6 Drawing Tools / Çizim Aracı:</b> Line, Polyline, Rectangle, Polygon, Circle, Arc</li>
<li><b>7 Editing Tools / Düzenleme Aracı:</b> Offset, Trim, Extend, Fillet, Buffer, Divide, Join</li>
<li><b>5 Transform Tools / Dönüşüm Aracı:</b> Move, Copy, Rotate, Scale, Mirror</li>
<li><b>5 Measurement Tools / Ölçüm Aracı:</b> Distance, Area, Dimension, Select Line, Select Area</li>
<li><b>3 Urban Planning Tools / Şehir Planlama Aracı:</b> Road, Junction, Block Chamfer</li>
</ul>

<p>Designed for urban planning workflows / Şehir planlama süreçleri için tasarlanmıştır.</p>
<p><i>Integrates with QGIS snapping / QGIS native snap desteği ile çalışır.</i></p>
"""
        )

    def _show_shortcut_guide(self):
        try:
            from .dialogs.shortcut_help_dialog import ShortcutHelpDialog
            dlg = ShortcutHelpDialog(self._SHORTCUTS, self.iface.mainWindow())
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Shortcut Guide",
                f"Shortcut guide could not be opened:\n{e}"
            )

    def _show_command_reference(self):
        try:
            from .dialogs.docs_dialog import DocsDialog
            dlg = DocsDialog(self.plugin_dir, self.iface.mainWindow())
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Command Reference",
                f"Command reference could not be opened:\n{e}"
            )

    def _show_command_palette(self):
        try:
            from .dialogs.command_palette_dialog import CommandPaletteDialog
            dlg = CommandPaletteDialog(self._SHORTCUTS, self.iface.mainWindow())
            dlg.tool_selected.connect(self._activate_tool)
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Command Palette",
                f"Command palette could not be opened:\n{e}"
            )

    def _show_quick_start(self):
        try:
            from .dialogs.quick_start_dialog import QuickStartDialog
            dlg = QuickStartDialog(self.iface.mainWindow())
            dlg.exec_()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Quick Start",
                f"Quick Start could not be opened:\n{e}"
            )
