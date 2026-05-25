# -*- coding: utf-8 -*-
"""
planX CAD â€” Tool Base Class
DÃ¼zenleme ve dÃ¶nÃ¼ÅŸÃ¼m araÃ§larÄ±nÄ±n temel sÄ±nÄ±fÄ±.
Feature seÃ§imi, preview, undo desteÄŸi.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QCursor, QPixmap, QPainter, QPen, QBrush
from qgis.core import (
    QgsWkbTypes, QgsPointXY, QgsGeometry, QgsFeature,
    QgsProject, QgsVectorLayer, QgsRectangle
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsVertexMarker

from ..core.sketcher_feedback import (
    create_sketcher_rubberband, create_preview_rubberband,
    cleanup_sketcher_rubberband, COLOR_ACCENT
)


class tool_base(QgsMapTool):
    """Edit/Transform araÃ§larÄ±nÄ±n temel sÄ±nÄ±fÄ±.

    Alt sÄ±nÄ±flar ÅŸunlarÄ± override etmelidir:
        - tool_name(): str
        - on_entity_selected(layer, feature, point): feature seÃ§ildiÄŸinde
        - on_click(point, button): ek tÄ±klama iÅŸlemi
        - on_move(point): fare hareketi (opsiyonel)
    """

    tool_finished = pyqtSignal()
    tool_message = pyqtSignal(str)

    # Feature seÃ§im toleransÄ± (piksel)
    PICK_TOLERANCE = 10

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.selected_layer = None
        self.selected_feature = None
        self.selected_point = None
        self.preview_rb = None
        self._step = 0  # AraÃ§ adÄ±mÄ±
        self.require_editable = True  # VarsayÄ±lan olarak dÃ¼zenlenebilir katmanlarda ara

        # GÃ¶rsel geri bildirimler (Snap Marker ve Obje Vurgusu)
        self.snap_marker = QgsVertexMarker(self.canvas)
        self.snap_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        self.snap_marker.setColor(QColor(13, 148, 136))
        self.snap_marker.setIconSize(12)
        self.snap_marker.setPenWidth(2)
        self.snap_marker.hide()

        self.highlight_rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.highlight_rb.setWidth(4)
        self.highlight_rb.setColor(QColor(13, 148, 136, 160))

        self._set_cursor()

    def _set_cursor(self):
        """EasyFillet stili ÅŸeffaf pembe dolgulu yeÅŸil halkalÄ± cursor (Aperture)."""
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        pen = QPen(QColor('#3ad6a1'))
        brush = QColor('#f0c2d3')
        brush.setAlphaF(0.3)
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawEllipse(6, 6, size-12, size-12)
        painter.end()
        self.setCursor(QCursor(pixmap))

    # â”€â”€ Override edilecek â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def tool_name(self):
        return "AraÃ§"

    def on_entity_selected(self, layer, feature, point):
        """Feature seÃ§ildiÄŸinde Ã§aÄŸrÄ±lÄ±r."""
        pass

    def on_click(self, point, button):
        """TÄ±klama iÅŸlemi."""
        pass

    def on_move(self, point):
        """Fare hareketi."""
        pass

    # â”€â”€ YaÅŸam DÃ¶ngÃ¼sÃ¼ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def activate(self):
        super().activate()
        self._step = 0
        self.preview_rb = create_preview_rubberband(self.canvas)

        if getattr(self, 'snap_marker', None) is None:
            self.snap_marker = QgsVertexMarker(self.canvas)
            self.snap_marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.snap_marker.setColor(QColor(13, 148, 136))
            self.snap_marker.setIconSize(12)
            self.snap_marker.setPenWidth(2)
            self.snap_marker.hide()

        if getattr(self, 'highlight_rb', None) is None:
            self.highlight_rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
            self.highlight_rb.setWidth(4)
            self.highlight_rb.setColor(QColor(13, 148, 136, 160))
            
        self._set_cursor()

        self.tool_message.emit(
            f"ðŸ”§ {self.tool_name()} â€” Bir obje seÃ§in"
        )

    def deactivate(self):
        self._cleanup()
        if self.snap_marker:
            self.canvas.scene().removeItem(self.snap_marker)
            self.snap_marker = None
        if self.highlight_rb:
            self.canvas.scene().removeItem(self.highlight_rb)
            self.highlight_rb = None
        super().deactivate()

    def _cleanup(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        if self.highlight_rb:
            self.highlight_rb.reset()
        if self.snap_marker:
            self.snap_marker.hide()
        self.preview_rb = None
        self.selected_layer = None
        self.selected_feature = None
        self.selected_point = None
        self._step = 0

    # â”€â”€ Olay Ä°ÅŸleyiciler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())

        # Snap uygula
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        if self._step == 0 and event.button() == Qt.MouseButton.LeftButton:
            # Feature seÃ§
            result = self._pick_feature(event.pos())
            if result:
                layer, feature = result
                self.selected_layer = layer
                self.selected_feature = feature
                self.selected_point = point
                self._step = 1

                # Obje vurgusu
                geom = feature.geometry()
                self.highlight_rb.reset(geom.type())
                self.highlight_rb.setToGeometry(geom, None)

                self.on_entity_selected(layer, feature, point)
            else:
                self.tool_message.emit(
                    f"âš ï¸ {self.tool_name()} â€” Obje bulunamadÄ±, tekrar deneyin"
                )
        else:
            self.on_click(point, event.button())

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped
            if self.snap_marker:
                self.snap_marker.setCenter(point)
                self.snap_marker.show()
        else:
            if self.snap_marker:
                self.snap_marker.hide()

        # Obje Ã¼zerine gelince vurgulama (Opsiyonel hover efekti eklenebilir)
        # Åžimdilik sadece on_move tetikliyoruz.
        self.on_move(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._reset()

    # â”€â”€ YardÄ±mcÄ± â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _snap_point(self, pos):
        snapper = self.canvas.snappingUtils()
        if snapper is None:
            return None
        match = snapper.snapToMap(pos)
        if match.isValid():
            return match.point()
        return None

    def _pick_feature(self, pos):
        """TÄ±klanan noktadaki feature'Ä± bul."""
        point = self.toMapCoordinates(pos)

        # Tolerans hesapla
        map_tol = self.canvas.mapUnitsPerPixel() * self.PICK_TOLERANCE
        search_rect = QgsRectangle(
            point.x() - map_tol, point.y() - map_tol,
            point.x() + map_tol, point.y() + map_tol
        )

        # Aktif katmanda ara (Aktif layer her zaman Ã¶nceliklidir)
        layer = self.iface.activeLayer()
        if layer and isinstance(layer, QgsVectorLayer):
            if not self.require_editable or layer.isEditable():
                result = self._search_layer(layer, search_rect, point)
                if result:
                    return result

        # TÃ¼m vektÃ¶r katmanlarÄ±nda ara
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer):
                if self.require_editable and not lyr.isEditable():
                    continue
                result = self._search_layer(lyr, search_rect, point)
                if result:
                    return result

        return None

    def _search_layer(self, layer, search_rect, point):
        """Bir katmanda feature ara."""
        features = layer.getFeatures(search_rect)
        best_dist = float('inf')
        best_feat = None

        for feat in features:
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            dist = geom.distance(QgsGeometry.fromPointXY(point))
            if dist < best_dist:
                best_dist = dist
                best_feat = feat

        if best_feat is not None:
            return (layer, best_feat)
        return None

    def _reset(self):
        """AracÄ± sÄ±fÄ±rla."""
        self._cleanup()
        self.preview_rb = create_preview_rubberband(self.canvas)
        self.tool_message.emit(f"ðŸ”§ {self.tool_name()} â€” Bir obje seÃ§in")

    def _apply_edit(self, layer, feature, new_geometry):
        """Feature geometrisini gÃ¼ncelle."""
        if layer is None or feature is None:
            return False

        if not layer.isEditable():
            layer.startEditing()

        layer.changeGeometry(feature.id(), new_geometry)
        layer.triggerRepaint()
        self.tool_message.emit(f"âœ… {self.tool_name()} â€” DÃ¼zenleme uygulandÄ±")
        return True

    def _add_feature(self, layer, geometry, source_feature=None):
        """Katmana yeni feature ekle."""
        if not layer.isEditable():
            layer.startEditing()

        feat = QgsFeature(layer.fields())
        feat.setGeometry(geometry)

        if source_feature:
            for i, field in enumerate(layer.fields()):
                try:
                    feat.setAttribute(i, source_feature.attribute(i))
                except Exception:
                    pass

        layer.addFeature(feat)
        layer.triggerRepaint()
        return feat
