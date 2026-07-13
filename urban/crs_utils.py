# -*- coding: utf-8 -*-
"""CRS helpers for metre-based urban design operations.

The map canvas and destination layers are not guaranteed to share a CRS, and
either one may use angular units.  Urban tool parameters are always expressed
in metres, so geometry construction is performed in a local UTM CRS and then
transformed back to the destination layer.
"""

import math

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
)


def transform_geometry(geometry, source_crs, destination_crs):
    """Return a transformed copy of ``geometry`` without mutating the caller."""
    if geometry is None:
        return None
    result = QgsGeometry(geometry)
    if (
        source_crs is not None
        and destination_crs is not None
        and source_crs.isValid()
        and destination_crs.isValid()
        and source_crs != destination_crs
    ):
        transform = QgsCoordinateTransform(
            source_crs,
            destination_crs,
            QgsProject.instance().transformContext(),
        )
        result.transform(transform)
    return result


def transform_point(point, source_crs, destination_crs):
    """Transform a point while keeping the original point untouched."""
    point = QgsPointXY(point)
    if (
        source_crs is None
        or destination_crs is None
        or not source_crs.isValid()
        or not destination_crs.isValid()
        or source_crs == destination_crs
    ):
        return point
    transform = QgsCoordinateTransform(
        source_crs,
        destination_crs,
        QgsProject.instance().transformContext(),
    )
    return QgsPointXY(transform.transform(point))


def local_metric_crs(point, source_crs):
    """Return a local UTM CRS suitable for metre-based work around ``point``.

    UTM is valid from 80 degrees south to 84 degrees north.  Web Mercator is
    used only as a defensive polar fallback, where these drafting tools are
    unlikely to be used but must still avoid treating degrees as metres.
    """
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    lon_lat = transform_point(point, source_crs, geographic)
    longitude = max(-180.0, min(180.0, lon_lat.x()))
    latitude = max(-90.0, min(90.0, lon_lat.y()))

    if -80.0 <= latitude <= 84.0:
        zone = max(1, min(60, int(math.floor((longitude + 180.0) / 6.0)) + 1))
        epsg = (32600 if latitude >= 0.0 else 32700) + zone
    else:
        epsg = 3857
    return QgsCoordinateReferenceSystem.fromEpsgId(epsg)
