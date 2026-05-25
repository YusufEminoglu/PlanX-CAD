# -*- coding: utf-8 -*-
"""
planX CAD â€” Yol Ã‡iz (Road Sketcher)
Ä°nteraktif yol orta Ã§izgisi Ã§izimi + platform Ã¼retme.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.core import QgsWkbTypes, QgsGeometry
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT
)
from .road_dialog import RoadDialog
from .road_generator import RoadGenerator


class RoadSketcher(QgsMapTool):
    """Yol orta Ã§izgisi Ã§izip platform Ã¼retir.

    1. Dialog aÃ§Ä±lÄ±r â†’ parametreler girilir
    2. Haritada orta Ã§izgi Ã§izilir (polyline)
    3. Ã‡izim bittiÄŸinde â†’ RoadGenerator ile platform Ã¼retilir
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
        self.params = None
        self.generator = RoadGenerator(iface)

    def activate(self):
        super().activate()
        self.vertices = []

        # Parametre dialog'unu gÃ¶ster
        dlg = RoadDialog(self.iface.mainWindow())
        if dlg.exec() == RoadDialog.Accepted:
            self.params = dlg.get_params()
            self.rb = create_sketcher_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
            )
            self.preview_rb = create_preview_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry
            )
            self.sketcher_message.emit(
                f"ðŸ›£ï¸ Yol Ã‡iz ({self.params['yol_tipi']}, "
                f"Toplam: {self.params['toplam_genislik']:.1f}m) â€” "
                f"Orta Ã§izgiyi Ã§izin | SaÄŸ tÄ±k: Bitir"
            )
        else:
            self.sketcher_message.emit("ðŸ›£ï¸ Yol Ã‡iz â€” Ä°ptal edildi")
            self.sketcher_finished.emit()

    def deactivate(self):
        self._cleanup()
        super().deactivate()

    def _cleanup(self):
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []

    def canvasPressEvent(self, event):
        if self.params is None:
            return

        point = self.toMapCoordinates(event.pos())

        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        if event.button() == Qt.MouseButton.LeftButton:
            self.vertices.append(point)
            if self.rb:
                self.rb.addPoint(point)
            self.sketcher_message.emit(
                f"ðŸ›£ï¸ Yol Ã‡iz â€” {len(self.vertices)} nokta | "
                f"SaÄŸ tÄ±k: Bitir | Esc: Ä°ptal"
            )

        elif event.button() == Qt.MouseButton.RightButton:
            if len(self.vertices) >= 2:
                self._finish()

    def canvasMoveEvent(self, event):
        if len(self.vertices) > 0 and self.preview_rb:
            point = self.toMapCoordinates(event.pos())
            snapper = self.canvas.snappingUtils()
            if snapper:
                match = snapper.snapToMap(event.pos())
                if match.isValid():
                    point = match.point()

            self.preview_rb.reset(QgsWkbTypes.LineGeometry)
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cleanup()
            self.rb = create_sketcher_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
            )
            self.preview_rb = create_preview_rubberband(
                self.canvas, QgsWkbTypes.LineGeometry
            )
            self.sketcher_message.emit("ðŸ›£ï¸ Yol Ã‡iz â€” Ä°ptal edildi")
        elif event.key() == Qt.Key.Key_Backspace:
            if len(self.vertices) > 0:
                self.vertices.pop()
                if self.rb:
                    self.rb.reset(QgsWkbTypes.LineGeometry)
                    for v in self.vertices:
                        self.rb.addPoint(v)
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.vertices) >= 2:
                self._finish()

    def _finish(self):
        """Orta Ã§izgiyi oluÅŸtur ve yol platformunu Ã¼ret."""
        if len(self.vertices) < 2 or self.params is None:
            return

        center_geom = QgsGeometry.fromPolylineXY(self.vertices)
        count = self.generator.generate(center_geom, self.params)

        if count > 0:
            self.sketcher_message.emit(
                f"âœ… Yol Ã‡iz â€” {count} bileÅŸen Ã¼retildi "
                f"(planx_yol_platformu katmanÄ±na eklendi)"
            )
            self.iface.messageBar().pushSuccess(
                "planX CAD",
                f"Yol platformu oluÅŸturuldu: {count} bileÅŸen"
            )
        else:
            self.sketcher_message.emit("âš ï¸ Yol Ã‡iz â€” Platform Ã¼retilemedi")

        self._cleanup()
        self.rb = create_sketcher_rubberband(
            self.canvas, QgsWkbTypes.LineGeometry, COLOR_ACCENT, 3
        )
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.LineGeometry
        )
        self.sketcher_finished.emit()
