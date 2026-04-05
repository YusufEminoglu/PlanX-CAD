# -*- coding: utf-8 -*-
"""
planX CAD — Seç ve Ölç Araçları
Çizgi seçip uzunluk ölçme veya alan seçip alan/çevre ölçme.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from qgis.PyQt.QtWidgets import QMessageBox

from .tool_base import tool_base
from ..core.sketcher_utils import measure_distance, measure_area


class tool_measure_select(tool_base):
    """Obje seçilerek ölçüm yapma aracı."""

    def __init__(self, canvas, iface, mode=0):
        # mode: 0 = Çizgi Seç/Ölç, 1 = Alan Seç/Alan Ölç
        super().__init__(canvas, iface)
        self.mode = mode
        self.require_editable = False

    def tool_name(self):
        return "Seç ve Çizgi Ölç" if self.mode == 0 else "Seç ve Alan Ölç"

    def activate(self):
        super().activate()
        msg = "📏 Ölçülecek çizgiyi seçin" if self.mode == 0 else "📐 Ölçülecek alanı seçin"
        self.tool_message.emit(msg)

    def on_entity_selected(self, layer, feature, point):
        """Feature seçildiğinde çalışır."""
        geom = feature.geometry()
        if geom.isEmpty():
            self._reset()
            return

        if self.mode == 0:
            # Çizgi uzunluğu ölç
            if geom.type() != QgsWkbTypes.LineGeometry:
                self.tool_message.emit("⚠️ Lütfen bir çizgi (LineString) seçin!")
                self._reset()
                return
            
            # DistanceArea QgsGeometry.length() projeksiyona bağlıdır, 
            # düzlemlisini alabiliriz veya measure_distance yapabiliriz
            # QgsGeometry length() harita birimindedir.
            # En iyisi feature.geometry().length() değerini harita biriminde göstermek
            # QGIS transform context ile ellipsoid ölçümü de yapabiliriz.
            from qgis.core import QgsDistanceArea, QgsProject
            da = QgsDistanceArea()
            da.setSourceCrs(QgsProject.instance().crs(), QgsProject.instance().transformContext())
            da.setEllipsoid(QgsProject.instance().ellipsoid())
            
            length = da.measureLength(geom)
            
            # Göster
            QMessageBox.information(
                self.iface.mainWindow(),
                "Çizgi Ölçümü",
                f"Obje ID: {feature.id()}\nUzunluk: {length:,.2f} m"
            )

        elif self.mode == 1:
            # Alan ve çevre ölç
            if geom.type() != QgsWkbTypes.PolygonGeometry:
                self.tool_message.emit("⚠️ Lütfen bir alan (Polygon) seçin!")
                self._reset()
                return

            from qgis.core import QgsDistanceArea, QgsProject
            da = QgsDistanceArea()
            da.setSourceCrs(QgsProject.instance().crs(), QgsProject.instance().transformContext())
            da.setEllipsoid(QgsProject.instance().ellipsoid())
            
            area = da.measureArea(geom)
            perimeter = da.measurePerimeter(geom)
            ha = area / 10000.0
            
            QMessageBox.information(
                self.iface.mainWindow(),
                "Alan Ölçümü",
                f"Obje ID: {feature.id()}\n\n"
                f"Çevre: {perimeter:,.2f} m\n"
                f"Alan: {area:,.2f} m²\n"
                f"Hektar: {ha:,.2f} ha"
            )

        self._reset() # Bir sonraki seçim için sıfırla

    def on_click(self, point, button):
        pass

    def on_move(self, point):
        pass
