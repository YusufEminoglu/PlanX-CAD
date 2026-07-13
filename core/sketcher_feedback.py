# -*- coding: utf-8 -*-
"""Visual feedback helpers for PlanX CAD sketching tools.

Creates rubber bands, snap markers, and consistent drawing previews.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand


# ── Colour constants ──────────────────────────────────────────────────────────
COLOR_PRIMARY = QColor(26, 35, 126, 200)      # Dark blue
COLOR_ACCENT = QColor(255, 109, 0, 200)       # Orange
COLOR_PREVIEW = QColor(100, 149, 237, 150)    # Cornflower blue
COLOR_SNAP = QColor(255, 0, 0, 220)           # Red


def create_sketcher_rubberband(canvas, geom_type=QgsWkbTypes.LineGeometry,
                               color=None, width=2):
    """Create a new sketch rubber band.

    Args:
        canvas: QgsMapCanvas
        geom_type: QgsWkbTypes geometry type
        color: QColor (defaults to COLOR_PRIMARY)
        width: Line width

    Returns:
        QgsRubberBand
    """
    rb = QgsRubberBand(canvas, geom_type)
    c = color or COLOR_PRIMARY
    rb.setColor(c)
    rb.setWidth(width)

    if geom_type == QgsWkbTypes.PolygonGeometry:
        fill = QColor(c)
        fill.setAlpha(40)
        rb.setFillColor(fill)

    rb.setLineStyle(Qt.PenStyle.SolidLine)
    return rb


def create_preview_rubberband(canvas, geom_type=QgsWkbTypes.LineGeometry):
    """Create a translucent rubber band for live previews."""
    rb = QgsRubberBand(canvas, geom_type)
    rb.setColor(COLOR_PREVIEW)
    rb.setWidth(1)
    rb.setLineStyle(Qt.PenStyle.DashLine)

    if geom_type == QgsWkbTypes.PolygonGeometry:
        fill = QColor(COLOR_PREVIEW)
        fill.setAlpha(25)
        rb.setFillColor(fill)
    return rb


def create_snap_marker(canvas):
    """Create the snap-point marker.

    Returns:
        QgsRubberBand configured for point geometry
    """
    rb = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
    rb.setColor(COLOR_SNAP)
    rb.setWidth(3)
    rb.setIcon(QgsRubberBand.ICON_CROSS)
    rb.setIconSize(12)
    return rb


def cleanup_sketcher_rubberband(canvas, rb):
    """Reset a rubber band and remove it from the canvas scene."""
    if rb is not None:
        rb.reset()
        canvas.scene().removeItem(rb)
