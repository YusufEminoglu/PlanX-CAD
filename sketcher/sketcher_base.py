# -*- coding: utf-8 -*-
"""
planX CAD â€” Sketcher Base Class
TÃ¼m Ã§izim araÃ§larÄ±nÄ±n temel sÄ±nÄ±fÄ±. QgsMapTool tabanlÄ±.
RubberBand yÃ¶netimi, snap desteÄŸi, ESC ile iptal.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap
from qgis.core import QgsWkbTypes, QgsPointXY, QgsGeometry, QgsSnappingUtils
from qgis.gui import QgsMapTool, QgsRubberBand

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_PRIMARY, COLOR_ACCENT
)
from ..core.sketcher_layer_utils import add_geometry_to_current_layer


class sketcher_base(QgsMapTool):
    """TÃ¼m sketcher'larÄ±n miras aldÄ±ÄŸÄ± temel sÄ±nÄ±f.

    Alt sÄ±nÄ±flar ÅŸunlarÄ± override etmelidir:
        - tool_name(): str â€” araÃ§ adÄ±
        - geom_type(): QgsWkbTypes â€” geometri tipi
        - on_click(point, button): tÄ±klama iÅŸlemi
        - on_move(point): fare hareketi (opsiyonel)
        - build_geometry(): QgsGeometry â€” son geometri
    """

    sketcher_finished = pyqtSignal()
    sketcher_message = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.vertices = []
        self.rb = None
        self.preview_rb = None
        self._is_active = False

    # â”€â”€ Override edilecek metodlar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def tool_name(self):
        """AraÃ§ adÄ±."""
        return "Sketcher"

    def geom_type(self):
        """Geometri tipi (QgsWkbTypes)."""
        return QgsWkbTypes.LineGeometry

    def on_click(self, point, button):
        """TÄ±klama iÅŸlemi. Alt sÄ±nÄ±f override eder."""
        pass

    def on_move(self, point):
        """Fare hareketi. Alt sÄ±nÄ±f override eder."""
        pass

    def build_geometry(self):
        """Son geometriyi oluÅŸtur. Alt sÄ±nÄ±f override eder."""
        return None

    # â”€â”€ YaÅŸam DÃ¶ngÃ¼sÃ¼ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def activate(self):
        """AraÃ§ aktifleÅŸtiÄŸinde."""
        super().activate()
        self._is_active = True
        self.vertices = []
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(f"âœï¸ {self.tool_name()} â€” TÄ±klayarak Ã§izime baÅŸlayÄ±n")

    def deactivate(self):
        """AraÃ§ deaktifleÅŸtiÄŸinde."""
        self._is_active = False
        self._cleanup()
        super().deactivate()

    def _cleanup(self):
        """RubberBand'leri temizle."""
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []

    # â”€â”€ Olay Ä°ÅŸleyiciler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def canvasPressEvent(self, event):
        """Harita tuval tÄ±klama olayÄ±."""
        point = self.toMapCoordinates(event.pos())

        # Snap uygula
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        self.on_click(point, event.button())

    def canvasMoveEvent(self, event):
        """Harita tuval fare hareketi."""
        if not self._is_active:
            return

        point = self.toMapCoordinates(event.pos())

        # Snap uygula
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        self.on_move(point)

    def keyPressEvent(self, event):
        """TuÅŸ basma olayÄ±."""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_Backspace or event.key() == Qt.Key_Z:
            self._undo_last_vertex()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._finish()

    # â”€â”€ YardÄ±mcÄ± Metodlar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _snap_point(self, pos):
        """QGIS native snap ile en yakÄ±n noktayÄ± bul."""
        snapper = self.canvas.snappingUtils()
        if snapper is None:
            return None
        match = snapper.snapToMap(pos)
        if match.isValid():
            return match.point()
        return None

    def add_vertex(self, point):
        """Yeni kÃ¶ÅŸe noktasÄ± ekle."""
        self.vertices.append(point)
        if self.rb:
            self.rb.addPoint(point)
        self.sketcher_message.emit(
            f"âœï¸ {self.tool_name()} â€” {len(self.vertices)} nokta | "
            f"Enter: Bitir | Esc: Ä°ptal | Backspace: Geri"
        )

    def _undo_last_vertex(self):
        """Son kÃ¶ÅŸeyi geri al."""
        if len(self.vertices) > 0:
            self.vertices.pop()
            self._rebuild_sketcher_rubberband()
            self.sketcher_message.emit(
                f"âœï¸ {self.tool_name()} â€” Son nokta silindi. "
                f"{len(self.vertices)} nokta kaldÄ±"
            )

    def _rebuild_sketcher_rubberband(self):
        """RubberBand'i kÃ¶ÅŸe listesinden yeniden oluÅŸtur."""
        if self.rb:
            self.rb.reset(self.geom_type())
            for v in self.vertices:
                self.rb.addPoint(v)

    def _finish(self):
        """Ã‡izimi bitir ve katmana ekle."""
        geom = self.build_geometry()
        if geom and not geom.isEmpty():
            success = add_geometry_to_current_layer(self.iface, geom)
            if success:
                self.sketcher_message.emit(
                    f"âœ… {self.tool_name()} â€” Geometri eklendi"
                )
                self.iface.mapCanvas().refresh()
            else:
                self.sketcher_message.emit(
                    "âš ï¸ Aktif dÃ¼zenlenebilir katman bulunamadÄ±!"
                )
        else:
            self.sketcher_message.emit(
                "âš ï¸ GeÃ§erli geometri oluÅŸturulamadÄ±"
            )

        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_finished.emit()

    def _cancel(self):
        """Ã‡izimi iptal et."""
        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(f"âŒ {self.tool_name()} â€” Ä°ptal edildi")
        self.sketcher_finished.emit()

    def update_preview(self, current_point):
        """Ã–nizleme RubberBand'ini gÃ¼ncelle."""
        if self.preview_rb and len(self.vertices) > 0:
            self.preview_rb.reset(self.geom_type())
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(current_point)
