# -*- coding: utf-8 -*-
"""
planX CAD — Sketcher Görsel Geri Bildirim Yöneticisi
RubberBand oluşturma, snap noktası gösterimi ve cursor yönetimi.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand


# ── Renk Sabitleri ──────────────────────────────────────────────────────────
COLOR_PRIMARY = QColor(26, 35, 126, 200)      # Koyu mavi
COLOR_ACCENT = QColor(255, 109, 0, 200)       # Turuncu
COLOR_PREVIEW = QColor(100, 149, 237, 150)    # Cornflower blue
COLOR_SNAP = QColor(255, 0, 0, 220)           # Kırmızı


def create_sketcher_rubberband(canvas, geom_type=QgsWkbTypes.LineGeometry,
                               color=None, width=2):
    """Yeni bir RubberBand oluşturur.

    Args:
        canvas: QgsMapCanvas
        geom_type: QgsWkbTypes geometri tipi
        color: QColor (varsayılan: COLOR_PRIMARY)
        width: Çizgi kalınlığı

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

    rb.setLineStyle(Qt.SolidLine)
    return rb


def create_preview_rubberband(canvas, geom_type=QgsWkbTypes.LineGeometry):
    """Önizleme (preview) için yarı saydam RubberBand."""
    rb = QgsRubberBand(canvas, geom_type)
    rb.setColor(COLOR_PREVIEW)
    rb.setWidth(1)
    rb.setLineStyle(Qt.DashLine)

    if geom_type == QgsWkbTypes.PolygonGeometry:
        fill = QColor(COLOR_PREVIEW)
        fill.setAlpha(25)
        rb.setFillColor(fill)
    return rb


def create_snap_marker(canvas):
    """Snap noktası göstergesi oluşturur.

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
    """RubberBand'i temizleyip sahiden kaldırır."""
    if rb is not None:
        rb.reset()
        canvas.scene().removeItem(rb)
