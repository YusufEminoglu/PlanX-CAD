# -*- coding: utf-8 -*-
"""
planX CAD Araç Seti — Ana Plugin Sınıfı
18 CAD aracı, dockable panel UI, toolbar ve menü yönetimi.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox


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

    # ═══════════════════════════════════════════════════════════════════════
    # QGIS Plugin Interface
    # ═══════════════════════════════════════════════════════════════════════

    def initGui(self):
        """QGIS GUI'ye menü, toolbar ve dock widget ekle."""
        # ── Menü ─────────────────────────────────────────────────────────
        self.menu = QMenu("&planX CAD Araç Seti")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # ── Toolbar ──────────────────────────────────────────────────────
        self.toolbar = QToolBar("planX CAD Toolbar")
        self.toolbar.setObjectName("PlanXCADToolbar")
        self.iface.addToolBar(self.toolbar)

        # ── Ana Panel Toggle ─────────────────────────────────────────────
        main_icon = os.path.join(self.icon_dir, "icon_main.svg")
        self.panel_action = self._add_action(
            main_icon,
            "planX CAD Paneli",
            self._toggle_dock,
            checkable=True,
            status_tip="planX CAD Araç Panelini aç/kapat"
        )

        # ── Menü Separator ───────────────────────────────────────────────
        self.menu.addSeparator()

        # ── Hakkında ─────────────────────────────────────────────────────
        self._add_action(
            ":/images/themes/default/mActionHelpContents.svg",
            "Hakkında",
            self._show_about,
            add_to_toolbar=False,
            status_tip="planX CAD Araç Seti hakkında"
        )

    def unload(self):
        """Plugin kaldırıldığında temizlik yap."""
        # Aktif aracı deaktive et
        if self._current_tool:
            self.iface.mapCanvas().unsetMapTool(self._current_tool)
            self._current_tool = None

        # Dock widget
        if self._dock:
            self.iface.removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

        # Araçlar
        for tool in self._tools.values():
            if tool:
                del tool
        self._tools.clear()

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

                self.iface.addDockWidget(
                    Qt.LeftDockWidgetArea, self._dock
                )
                self._dock.show()
                self._dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Hata",
                    f"Panel oluşturulamadı:\n{str(e)}"
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
    _DIALOG_TOOLS = {"buffer", "fillet", "polygon", "road", "junction", "measure_area", "ada_kirma"}

    def _activate_tool(self, tool_key):
        """Araç tuşuna basıldığında ilgili map tool'u aktifleştirir."""
        canvas = self.iface.mapCanvas()

        # Önceki aracı deaktive et
        if self._current_tool:
            canvas.unsetMapTool(self._current_tool)
            self._current_tool = None

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
                self._dock.set_status(f"⚠️ '{tool_key}' aracı yüklenemedi")
            return

        self._current_tool = tool
        canvas.setMapTool(tool)

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
                    lambda: self._dock.set_status("Hazır")
                )
            if hasattr(t, 'tool_finished') and self._dock:
                t.tool_finished.connect(
                    lambda: self._dock.set_status("Hazır")
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
            "planX CAD Araç Seti Hakkında",
            f"""
<h2>planX CAD Araç Seti</h2>
<p>Versiyon: {version}</p>

<h3>Özellikler:</h3>
<ul>
<li><b>6 Çizim Aracı:</b> Çizgi, Polyline, Dikdörtgen, Çokgen, Daire, Ark</li>
<li><b>5 Düzenleme Aracı:</b> Offset, Trim, Extend, Fillet, Buffer</li>
<li><b>5 Dönüşüm Aracı:</b> Taşı, Kopyala, Döndür (Ctrl:90°), Ölçekle, Aynala</li>
<li><b>2 Ölçüm Aracı:</b> Mesafe ölçümü + Alan ölçümü</li>
<li><b>3 Şehir Planlama Aracı:</b> Yol Çiz + Kavşak Oluştur + Ada Kırma</li>
</ul>

<p>Şehir planlama süreçleri için tasarlanmıştır.</p>
<p><i>QGIS native snap desteği ile çalışır.</i></p>
"""
        )
