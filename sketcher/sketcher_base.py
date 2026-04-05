# -*- coding: utf-8 -*-
"""
planX CAD — Sketcher Base Class
Tüm çizim araçlarının temel sınıfı. QgsMapTool tabanlı.
RubberBand yönetimi, snap desteği, ESC ile iptal.
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
    """Tüm sketcher'ların miras aldığı temel sınıf.

    Alt sınıflar şunları override etmelidir:
        - tool_name(): str — araç adı
        - geom_type(): QgsWkbTypes — geometri tipi
        - on_click(point, button): tıklama işlemi
        - on_move(point): fare hareketi (opsiyonel)
        - build_geometry(): QgsGeometry — son geometri
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

    # ── Override edilecek metodlar ────────────────────────────────────────

    def tool_name(self):
        """Araç adı."""
        return "Sketcher"

    def geom_type(self):
        """Geometri tipi (QgsWkbTypes)."""
        return QgsWkbTypes.LineGeometry

    def on_click(self, point, button):
        """Tıklama işlemi. Alt sınıf override eder."""
        pass

    def on_move(self, point):
        """Fare hareketi. Alt sınıf override eder."""
        pass

    def build_geometry(self):
        """Son geometriyi oluştur. Alt sınıf override eder."""
        return None

    # ── Yaşam Döngüsü ───────────────────────────────────────────────────

    def activate(self):
        """Araç aktifleştiğinde."""
        super().activate()
        self._is_active = True
        self.vertices = []
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(f"✏️ {self.tool_name()} — Tıklayarak çizime başlayın")

    def deactivate(self):
        """Araç deaktifleştiğinde."""
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

    # ── Olay İşleyiciler ─────────────────────────────────────────────────

    def canvasPressEvent(self, event):
        """Harita tuval tıklama olayı."""
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
        """Tuş basma olayı."""
        if event.key() == Qt.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Z:
            self._undo_last_vertex()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._finish()

    # ── Yardımcı Metodlar ────────────────────────────────────────────────

    def _snap_point(self, pos):
        """QGIS native snap ile en yakın noktayı bul."""
        snapper = self.canvas.snappingUtils()
        if snapper is None:
            return None
        match = snapper.snapToMap(pos)
        if match.isValid():
            return match.point()
        return None

    def add_vertex(self, point):
        """Yeni köşe noktası ekle."""
        self.vertices.append(point)
        if self.rb:
            self.rb.addPoint(point)
        self.sketcher_message.emit(
            f"✏️ {self.tool_name()} — {len(self.vertices)} nokta | "
            f"Enter: Bitir | Esc: İptal | Backspace: Geri"
        )

    def _undo_last_vertex(self):
        """Son köşeyi geri al."""
        if len(self.vertices) > 0:
            self.vertices.pop()
            self._rebuild_sketcher_rubberband()
            self.sketcher_message.emit(
                f"✏️ {self.tool_name()} — Son nokta silindi. "
                f"{len(self.vertices)} nokta kaldı"
            )

    def _rebuild_sketcher_rubberband(self):
        """RubberBand'i köşe listesinden yeniden oluştur."""
        if self.rb:
            self.rb.reset(self.geom_type())
            for v in self.vertices:
                self.rb.addPoint(v)

    def _finish(self):
        """Çizimi bitir ve katmana ekle."""
        geom = self.build_geometry()
        if geom and not geom.isEmpty():
            success = add_geometry_to_current_layer(self.iface, geom)
            if success:
                self.sketcher_message.emit(
                    f"✅ {self.tool_name()} — Geometri eklendi"
                )
                self.iface.mapCanvas().refresh()
            else:
                self.sketcher_message.emit(
                    "⚠️ Aktif düzenlenebilir katman bulunamadı!"
                )
        else:
            self.sketcher_message.emit(
                "⚠️ Geçerli geometri oluşturulamadı"
            )

        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_finished.emit()

    def _cancel(self):
        """Çizimi iptal et."""
        self._cleanup()
        self.rb = create_sketcher_rubberband(self.canvas, self.geom_type())
        self.preview_rb = create_preview_rubberband(self.canvas, self.geom_type())
        self.sketcher_message.emit(f"❌ {self.tool_name()} — İptal edildi")
        self.sketcher_finished.emit()

    def update_preview(self, current_point):
        """Önizleme RubberBand'ini güncelle."""
        if self.preview_rb and len(self.vertices) > 0:
            self.preview_rb.reset(self.geom_type())
            for v in self.vertices:
                self.preview_rb.addPoint(v)
            self.preview_rb.addPoint(current_point)
