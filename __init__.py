# -*- coding: utf-8 -*-
"""
planX — CAD Araç Seti
Şehir planlama süreçleri için hafif ve hızlı QGIS CAD eklentisi.
"""

from .main_plugin import PlanXCADPlugin


def classFactory(iface):
    """QGIS plugin entry point."""
    return PlanXCADPlugin(iface)
