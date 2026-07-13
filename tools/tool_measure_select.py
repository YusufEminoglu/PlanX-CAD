# -*- coding: utf-8 -*-
"""Measure a selected line or polygon feature."""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsWkbTypes, QgsGeometry
from qgis.PyQt.QtWidgets import QMessageBox

from .tool_base import tool_base
from ..core.sketcher_utils import measure_distance, measure_area


class tool_measure_select(tool_base):
    """Measure length or area from a selected feature."""

    def __init__(self, canvas, iface, mode=0):
        # mode: 0 = selected line, 1 = selected polygon
        super().__init__(canvas, iface)
        self.mode = mode
        self.require_editable = False

    def tool_name(self):
        return "Measure Selected Line" if self.mode == 0 else "Measure Selected Area"

    def activate(self):
        super().activate()
        msg = "📏 Select a line to measure" if self.mode == 0 else "📐 Select a polygon to measure"
        self.tool_message.emit(msg)

    def on_entity_selected(self, layer, feature, point):
        """Measure the selected feature in its layer CRS."""
        geom = feature.geometry()
        if geom.isEmpty():
            self._reset()
            return

        if self.mode == 0:
            # Measure line length.
            if geom.type() != QgsWkbTypes.LineGeometry:
                self.tool_message.emit("⚠️ Select a line feature")
                self._reset()
                return
            
            # QgsDistanceArea reports ellipsoidal length from layer coordinates.
            from qgis.core import QgsDistanceArea, QgsProject
            da = QgsDistanceArea()
            # Feature geometry coordinates are stored in the feature layer
            # CRS, not necessarily the project/canvas CRS.
            da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
            da.setEllipsoid(QgsProject.instance().ellipsoid())
            
            length = da.measureLength(geom)
            
            QMessageBox.information(
                self.iface.mainWindow(),
                "Line Measurement",
                f"Feature ID: {feature.id()}\nLength: {length:,.2f} m"
            )

        elif self.mode == 1:
            # Measure polygon area and perimeter.
            if geom.type() != QgsWkbTypes.PolygonGeometry:
                self.tool_message.emit("⚠️ Select a polygon feature")
                self._reset()
                return

            from qgis.core import QgsDistanceArea, QgsProject
            da = QgsDistanceArea()
            da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
            da.setEllipsoid(QgsProject.instance().ellipsoid())
            
            area = da.measureArea(geom)
            perimeter = da.measurePerimeter(geom)
            ha = area / 10000.0
            
            QMessageBox.information(
                self.iface.mainWindow(),
                "Area Measurement",
                f"Feature ID: {feature.id()}\n\n"
                f"Perimeter: {perimeter:,.2f} m\n"
                f"Area: {area:,.2f} m²\n"
                f"Hectares: {ha:,.2f} ha"
            )

        self._reset()

    def on_click(self, point, button):
        pass

    def on_move(self, point):
        pass
