# -*- coding: utf-8 -*-
"""Pytest configuration and environment shims for PlanX CAD Toolset."""

from __future__ import annotations

import sys
import types


class _FakePointXY:
    def __init__(self, x: float = 0.0, y: float = 0.0):
        if hasattr(x, "x") and hasattr(x, "y"):
            self._x = float(x.x())
            self._y = float(x.y())
        else:
            self._x = float(x)
            self._y = float(y)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def __repr__(self) -> str:
        return f"QgsPointXY({self._x}, {self._y})"

    def __eq__(self, other) -> bool:
        if not hasattr(other, "x") or not hasattr(other, "y"):
            return False
        return abs(self._x - other.x()) < 1e-7 and abs(self._y - other.y()) < 1e-7


class _FakeCRS:
    def __init__(self, *a, **k):
        pass

    @classmethod
    def fromEpsgId(cls, id):
        return cls()

    @classmethod
    def fromProj(cls, proj):
        return cls()

    def isValid(self):
        return True

    def isGeographic(self):
        return False


class _FakeTransform:
    def __init__(self, *a, **k):
        pass

    def transform(self, pt):
        return pt


def pytest_configure(config):
    """Install lightweight mock shims for qgis if running outside QGIS."""
    if "qgis" in sys.modules and "qgis.core" in sys.modules:
        return

    qgis = types.ModuleType("qgis")
    qgis_core = types.ModuleType("qgis.core")
    qgis_gui = types.ModuleType("qgis.gui")
    qgis_pyqt = types.ModuleType("qgis.PyQt")
    qgis_qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qgis_qtgui = types.ModuleType("qgis.PyQt.QtGui")
    qgis_qtwidgets = types.ModuleType("qgis.PyQt.QtWidgets")

    qgis_core.QgsPointXY = _FakePointXY
    qgis_core.QgsGeometry = type("QgsGeometry", (), {})
    qgis_core.QgsCoordinateReferenceSystem = _FakeCRS
    qgis_core.QgsCoordinateTransform = _FakeTransform
    qgis_core.QgsProject = type("QgsProject", (), {
        "instance": classmethod(lambda cls: type("QgsProjectInst", (), {"transformContext": lambda s: None})())
    })
    qgis_core.QgsSettings = type("QgsSettings", (), {})
    qgis_core.QgsFeature = type("QgsFeature", (), {})
    qgis_core.QgsFeatureRequest = type("QgsFeatureRequest", (), {})
    qgis_core.QgsPointLocator = type("QgsPointLocator", (), {
        "Types": type("Types", (), {}),
        "Match": type("Match", (), {}),
        "Vertex": 1,
        "Edge": 2,
        "Area": 4,
        "All": 7,
    })
    qgis_core.QgsRectangle = type("QgsRectangle", (), {})
    qgis_core.QgsVectorLayer = type("QgsVectorLayer", (), {})
    qgis_core.QgsWkbTypes = type("QgsWkbTypes", (), {
        "PointGeometry": 1,
        "LineGeometry": 2,
        "PolygonGeometry": 3,
        "NullGeometry": 4,
    })

    qgis_gui.QgsMapCanvas = type("QgsMapCanvas", (), {})
    qgis_gui.QgsMapCanvasItem = type("QgsMapCanvasItem", (), {})
    qgis_gui.QgsVertexMarker = type("QgsVertexMarker", (), {"IconType": type("IconType", (), {})})
    qgis_gui.QgsRubberBand = type("QgsRubberBand", (), {})

    qgis_qtcore.QObject = type("QObject", (), {"__init__": lambda self, *a, **k: None})
    qgis_qtcore.pyqtSignal = lambda *a: None
    qgis_qtcore.Qt = type("Qt", (), {"PenStyle": type("PenStyle", (), {"DashLine": 2})})
    qgis_qtcore.QSettings = type("QSettings", (), {})
    qgis_qtgui.QColor = type("QColor", (), {"__init__": lambda self, *a, **k: None})

    sys.modules["qgis"] = qgis
    sys.modules["qgis.core"] = qgis_core
    sys.modules["qgis.gui"] = qgis_gui
    sys.modules["qgis.PyQt"] = qgis_pyqt
    sys.modules["qgis.PyQt.QtCore"] = qgis_qtcore
    sys.modules["qgis.PyQt.QtGui"] = qgis_qtgui
    sys.modules["qgis.PyQt.QtWidgets"] = qgis_qtwidgets
