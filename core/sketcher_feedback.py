# -*- coding: utf-8 -*-
"""
planX CAD â€” Sketcher GÃ¶rsel Geri Bildirim YÃ¶neticisi
RubberBand oluÅŸturma, snap noktasÄ± gÃ¶sterimi ve cursor yÃ¶netimi.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand


# â”€â”€ Renk Sabitleri â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
COLOR_PRIMARY = QColor(26, 35, 126, 200)      # Koyu mavi
COLOR_ACCENT = QColor(255, 109, 0, 200)       # Turuncu
COLOR_PREVIEW = QColor(100, 149, 237, 150)    # Cornflower blue
COLOR_SNAP = QColor(255, 0, 0, 220)           # KÄ±rmÄ±zÄ±


def create_sketcher_rubberband(canvas, geom_type=QgsWkbTypes.LineGeometry,
                               color=None, width=2):
    """Yeni bir RubberBand oluÅŸturur.

    Args:
        canvas: QgsMapCanvas
        geom_type: QgsWkbTypes geometri tipi
        color: QColor (varsayÄ±lan: COLOR_PRIMARY)
        width: Ã‡izgi kalÄ±nlÄ±ÄŸÄ±

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
    """Ã–nizleme (preview) iÃ§in yarÄ± saydam RubberBand."""
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
    """Snap noktasÄ± gÃ¶stergesi oluÅŸturur.

    Returns:
        QgsRubberBand (nokta tipi)
    """
    rb = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
    rb.setColor(COLOR_SNAP)
    rb.setWidth(3)
    rb.setIcon(QgsRubberBand.ICON_CROSS)
    rb.setIconSize(12)
    return rb


def cleanup_sketcher_rubberband(canvas, rb):
    """RubberBand'i temizleyip sahiden kaldÄ±rÄ±r."""
    if rb is not None:
        rb.reset()
        canvas.scene().removeItem(rb)
