# -*- coding: utf-8 -*-
"""
PlanX CAD Toolset.

A lightweight, fast QGIS CAD plugin for urban-planning workflows.
"""

from .main_plugin import PlanXCADPlugin


def classFactory(iface):
    """QGIS plugin entry point."""
    return PlanXCADPlugin(iface)
