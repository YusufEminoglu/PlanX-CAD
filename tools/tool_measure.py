# -*- coding: utf-8 -*-
"""planX CAD — Ölç (Measure) Aracı
Geliştirilmiş: Canlı ölçüm, Alan Ölç modu, harita üzeri etiketler.
"""

from qgis.PyQt.QtCore import Qt, QPointF, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsTextAnnotation,
)
from qgis.gui import QgsMapTool, QgsRubberBand

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT, COLOR_PRIMARY
)
from ..core.sketcher_utils import measure_distance, measure_area


class tool_measure(QgsMapTool):
    """Mesafe ve alan ölçüm aracı.
    Sol tık: Nokta ekle | Sağ tık: Bitir | ESC: İptal
    Canlı önizleme ile ölçüm göstergesi.
    """

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)

    MODE_DISTANCE = 0
    MODE_AREA = 1

    def __init__(self, canvas, iface, mode=0):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.vertices = []
        self.rb = None
        self.preview_rb = None
        self.total_distance = 0.0
        self.mode = mode  # 0=mesafe, 1=alan

    def tool_name(self):
        return "Ölç" if self.mode == self.MODE_DISTANCE else "Alan Ölç"

    def activate(self):
        super().activate()
        self.vertices = []
        self.total_distance = 0.0

        geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
        self.rb = create_sketcher_rubberband(self.canvas, geom_type, COLOR_ACCENT, 2)
        self.preview_rb = create_preview_rubberband(self.canvas, geom_type)

        if self.mode == self.MODE_DISTANCE:
            self.tool_message.emit("📏 Mesafe Ölç — Noktaları tıklayın | Sağ tık: Bitir")
        else:
            self.tool_message.emit("📐 Alan Ölç — Alanın köşelerini tıklayın | Sağ tık: Bitir")

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.rb)
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.rb = None
        self.preview_rb = None
        self.vertices = []
        super().deactivate()

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())

        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        if event.button() == Qt.LeftButton:
            self.vertices.append(point)
            if self.rb:
                self.rb.addPoint(point)

            if self.mode == self.MODE_DISTANCE:
                self._show_distance_info()
            else:
                self._show_area_info()

        elif event.button() == Qt.RightButton:
            self._finish_measurement()

    def canvasMoveEvent(self, event):
        """Canlı önizleme."""
        if not self.vertices:
            return

        point = self.toMapCoordinates(event.pos())
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        # Preview rubberband
        if self.preview_rb:
            geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
            self.preview_rb.reset(geom_type)
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(point)

            if self.mode == self.MODE_AREA and len(self.vertices) >= 2:
                self.preview_rb.addPoint(self.vertices[0])  # Kapatma

        # Canlı mesafe göstergesi
        if self.mode == self.MODE_DISTANCE and len(self.vertices) >= 1:
            live_dist = measure_distance(self.vertices[-1], point)
            total_live = self.total_distance + live_dist
            self.tool_message.emit(
                f"📏 Segment: {live_dist:.2f} m | "
                f"Toplam: {total_live:.2f} m | "
                f"{len(self.vertices)} nokta"
            )
        elif self.mode == self.MODE_AREA and len(self.vertices) >= 2:
            temp_pts = self.vertices + [point, self.vertices[0]]
            geom = QgsGeometry.fromPolygonXY([temp_pts])
            area = measure_area(geom)
            self.tool_message.emit(
                f"📐 Alan: {self._format_area(area)} | "
                f"{len(self.vertices)} köşe"
            )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key_Backspace:
            self._undo_last()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._finish_measurement()

    def _show_distance_info(self):
        if len(self.vertices) >= 2:
            seg_dist = measure_distance(self.vertices[-2], self.vertices[-1])
            self.total_distance += seg_dist
            self.tool_message.emit(
                f"📏 Segment: {seg_dist:.2f} m | "
                f"Toplam: {self.total_distance:.2f} m | "
                f"{len(self.vertices)} nokta"
            )
        else:
            self.tool_message.emit("📏 İkinci noktayı tıklayın")

    def _show_area_info(self):
        if len(self.vertices) >= 3:
            geom = QgsGeometry.fromPolygonXY(
                [self.vertices + [self.vertices[0]]]
            )
            area = measure_area(geom)
            self.tool_message.emit(
                f"📐 Alan: {self._format_area(area)} | "
                f"{len(self.vertices)} köşe"
            )
        else:
            n = len(self.vertices)
            self.tool_message.emit(
                f"📐 {3 - n} nokta daha gerekli | {n} köşe"
            )

    def _finish_measurement(self):
        if self.mode == self.MODE_DISTANCE:
            if len(self.vertices) >= 2:
                msg = f"📏 Toplam mesafe: {self.total_distance:.2f} m"
                self.tool_message.emit(msg)
                self.iface.messageBar().pushInfo("planX CAD Ölçüm", msg)
        else:
            if len(self.vertices) >= 3:
                geom = QgsGeometry.fromPolygonXY(
                    [self.vertices + [self.vertices[0]]]
                )
                area = measure_area(geom)

                # Çevre de hesapla
                perimeter = 0.0
                pts = self.vertices + [self.vertices[0]]
                for i in range(len(pts) - 1):
                    perimeter += measure_distance(pts[i], pts[i + 1])

                msg = (
                    f"📐 Alan: {self._format_area(area)} | "
                    f"Çevre: {perimeter:.2f} m"
                )
                self.tool_message.emit(msg)
                self.iface.messageBar().pushInfo("planX CAD Ölçüm", msg)

        # Temizle
        self.vertices = []
        self.total_distance = 0.0
        if self.rb:
            geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
            self.rb.reset(geom_type)
        if self.preview_rb:
            geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
            self.preview_rb.reset(geom_type)

    def _cancel(self):
        self.vertices = []
        self.total_distance = 0.0
        geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
        if self.rb:
            self.rb.reset(geom_type)
        if self.preview_rb:
            self.preview_rb.reset(geom_type)
        self.tool_message.emit(f"{'📏' if self.mode == 0 else '📐'} Ölçüm iptal edildi")

    def _undo_last(self):
        if self.vertices:
            removed = self.vertices.pop()
            if len(self.vertices) >= 2:
                self.total_distance -= measure_distance(
                    self.vertices[-1], removed
                )
            else:
                self.total_distance = 0.0

            geom_type = QgsWkbTypes.LineGeometry if self.mode == 0 else QgsWkbTypes.PolygonGeometry
            if self.rb:
                self.rb.reset(geom_type)
                for v in self.vertices:
                    self.rb.addPoint(v)

            self.tool_message.emit(
                f"Son nokta silindi. {len(self.vertices)} nokta kaldı"
            )

    def _format_area(self, area):
        """Alanı okunabilir formata çevir."""
        if area >= 10000:
            return f"{area / 10000:.4f} ha ({area:.2f} m²)"
        return f"{area:.2f} m²"
