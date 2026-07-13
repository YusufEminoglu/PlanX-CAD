# -*- coding: utf-8 -*-
"""Shared CRS helpers for metre-based CAD and urban operations."""

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
    """Return a local metre CRS suitable for work around ``point``."""
    geographic = QgsCoordinateReferenceSystem.fromEpsgId(4326)
    lon_lat = transform_point(point, source_crs, geographic)
    longitude = max(-180.0, min(180.0, lon_lat.x()))
    latitude = max(-90.0, min(90.0, lon_lat.y()))

    if latitude > 84.0 or latitude < -80.0:
        # UTM is undefined in the polar caps and Web Mercator scale becomes
        # unusable there. A point-centred azimuthal equidistant work CRS keeps
        # drafting radii and relative point distances true to metres.
        return QgsCoordinateReferenceSystem.fromProj(
            "+proj=aeqd "
            f"+lat_0={latitude:.12f} +lon_0={longitude:.12f} "
            "+datum=WGS84 +units=m +no_defs"
        )

    zone = max(1, min(60, int(math.floor((longitude + 180.0) / 6.0)) + 1))
    epsg = (32600 if latitude >= 0.0 else 32700) + zone
    return QgsCoordinateReferenceSystem.fromEpsgId(epsg)


__all__ = ["local_metric_crs", "transform_geometry", "transform_point"]
