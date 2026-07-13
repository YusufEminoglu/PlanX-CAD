# -*- coding: utf-8 -*-
"""
planX CAD — Geometri Yardımcı Fonksiyonları
Offset, trim, extend, fillet, buffer ve ölçüm işlemleri.
"""

import math
from qgis.PyQt.QtGui import QTransform
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsLineString, QgsPoint,
    QgsWkbTypes, QgsDistanceArea, QgsProject, QgsFeature, Qgis
)


def offset_geometry(geom, distance, side="left"):
    """Geometriyi belirtilen mesafe kadar offset yapar.

    Args:
        geom: QgsGeometry (LineString)
        distance: float (metre)
        side: "left" veya "right"

    Returns:
        QgsGeometry veya None
    """
    if geom is None or geom.isEmpty():
        return None

    d = abs(distance)
    if side == "right":
        d = -d

    # The legacy QgsGeometry.JoinStyleRound SIP alias is not available in
    # every QGIS 4/PyQt6 build. Qgis.JoinStyle is public in QGIS 3.28+ and 4.
    result = geom.offsetCurve(d, 8, Qgis.JoinStyle.Round, 2.0)
    if result and not result.isEmpty():
        return result
    return None


def buffer_geometry(geom, distance, segments=16):
    """Geometriye tampon bölge uygular.

    Args:
        geom: QgsGeometry
        distance: float (metre)
        segments: Segment sayısı

    Returns:
        QgsGeometry (Polygon)
    """
    if geom is None or geom.isEmpty():
        return None

    result = geom.buffer(distance, segments)
    if result and not result.isEmpty():
        return result
    return None


def extend_geometry_to_boundary(target_geom, boundary_geom):
    """Hedef geometriyi sınır geometrisine kadar uzatır.

    Args:
        target_geom: QgsGeometry (LineString)
        boundary_geom: QgsGeometry

    Returns:
        QgsGeometry veya None
    """
    if (target_geom is None or boundary_geom is None or
            target_geom.isEmpty() or boundary_geom.isEmpty()):
        return None

    # Multi-part safe: take the first part if multi.
    if target_geom.isMultipart():
        parts = target_geom.asMultiPolyline()
        if not parts or not parts[0]:
            return None
        line = list(parts[0])
    else:
        line = target_geom.asPolyline()
    if len(line) < 2:
        return None

    # Son segmentin yönünü al
    p1 = line[-2]
    p2 = line[-1]
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    length = math.sqrt(dx * dx + dy * dy)

    if length == 0:
        return None

    # Build a ray long enough to cross the boundary's complete extent. The
    # old fixed ``10 * final segment`` ray missed distant boundaries whenever
    # the target had a short final segment.
    bbox = boundary_geom.boundingBox()
    # A valid vertical/horizontal line has a zero-width/height rectangle, for
    # which QgsRectangle.isEmpty() is true. Only a null extent is invalid.
    if bbox.isNull():
        return None
    corners = (
        QgsPointXY(bbox.xMinimum(), bbox.yMinimum()),
        QgsPointXY(bbox.xMinimum(), bbox.yMaximum()),
        QgsPointXY(bbox.xMaximum(), bbox.yMinimum()),
        QgsPointXY(bbox.xMaximum(), bbox.yMaximum()),
    )
    ray_length = max(point_distance(p2, corner) for corner in corners)
    if not math.isfinite(ray_length) or ray_length <= 0:
        return None
    ux, uy = dx / length, dy / length
    ray_end = QgsPointXY(
        p2.x() + ux * (ray_length * 1.01 + length),
        p2.y() + uy * (ray_length * 1.01 + length),
    )
    ray = QgsGeometry.fromPolylineXY([QgsPointXY(p2), ray_end])

    intersection = ray.intersection(boundary_geom)
    if intersection is None or intersection.isEmpty():
        return None

    # Point/MultiPoint, overlap lines, and geometry collections all expose a
    # vertex iterator. Only keep intersections in front of the endpoint so an
    # Extend operation can never accidentally shorten the target.
    candidates = []
    try:
        for vertex in intersection.vertices():
            candidate = QgsPointXY(vertex)
            along = ((candidate.x() - p2.x()) * ux +
                     (candidate.y() - p2.y()) * uy)
            if along > max(length * 1e-9, 1e-12):
                candidates.append((along, candidate))
    except (AttributeError, TypeError):
        return None

    if not candidates:
        return None

    _, best = min(candidates, key=lambda item: item[0])
    new_line = list(line) + [best]
    return QgsGeometry.fromPolylineXY(new_line)


def measure_distance(point1, point2, crs=None):
    """İki nokta arasındaki mesafeyi ölçer.

    Args:
        point1: QgsPointXY
        point2: QgsPointXY
        crs: QgsCoordinateReferenceSystem (varsayılan: proje CRS)

    Returns:
        float — mesafe (metre)
    """
    da = QgsDistanceArea()
    if crs:
        da.setSourceCrs(crs, QgsProject.instance().transformContext())
    else:
        da.setSourceCrs(
            QgsProject.instance().crs(),
            QgsProject.instance().transformContext()
        )
    da.setEllipsoid(QgsProject.instance().ellipsoid())
    return da.measureLine(point1, point2)


def measure_area(geom, crs=None):
    """Geometrinin alanını ölçer.

    Args:
        geom: QgsGeometry (Polygon)
        crs: QgsCoordinateReferenceSystem

    Returns:
        float — alan (m²)
    """
    da = QgsDistanceArea()
    if crs:
        da.setSourceCrs(crs, QgsProject.instance().transformContext())
    else:
        da.setSourceCrs(
            QgsProject.instance().crs(),
            QgsProject.instance().transformContext()
        )
    da.setEllipsoid(QgsProject.instance().ellipsoid())
    return da.measureArea(geom)


def rotate_geometry(geom, center, angle_degrees):
    """Geometriyi merkez etrafında döndürür.

    Args:
        geom: QgsGeometry
        center: QgsPointXY — dönüş merkezi
        angle_degrees: float — derece cinsinden açı

    Returns:
        QgsGeometry
    """
    result = QgsGeometry(geom)
    operation = result.rotate(angle_degrees, center)
    if operation != Qgis.GeometryOperationResult.Success:
        return None
    return result


def _affine_transform(geom, transform):
    """Transform a detached geometry while preserving curves and Z/M values."""
    if geom is None or geom.isEmpty():
        return None
    result = QgsGeometry(geom)
    operation = result.transform(transform)
    if operation != Qgis.GeometryOperationResult.Success:
        return None
    return result


def scale_geometry(geom, center, factor):
    """Scale around ``center`` without linearizing curves or dropping Z/M."""
    transform = QTransform(
        factor, 0.0,
        0.0, factor,
        center.x() * (1.0 - factor),
        center.y() * (1.0 - factor),
    )
    return _affine_transform(geom, transform)


def mirror_geometry(geom, line_start, line_end):
    """Mirror across a line without linearizing curves or dropping Z/M."""
    dx = line_end.x() - line_start.x()
    dy = line_end.y() - line_start.y()
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return None

    ux = dx / math.sqrt(length_sq)
    uy = dy / math.sqrt(length_sq)
    a = 2.0 * ux * ux - 1.0
    b = 2.0 * ux * uy
    d = 2.0 * uy * uy - 1.0
    tx = line_start.x() - (a * line_start.x() + b * line_start.y())
    ty = line_start.y() - (b * line_start.x() + d * line_start.y())
    transform = QTransform(a, b, b, d, tx, ty)
    return _affine_transform(geom, transform)


def point_distance(p1, p2):
    """İki QgsPointXY arasındaki Öklid mesafesi."""
    return math.sqrt((p1.x() - p2.x()) ** 2 + (p1.y() - p2.y()) ** 2)


def angle_between_points(p1, p2):
    """İki nokta arasındaki açıyı derece olarak döndürür."""
    return math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))


def calc_tangent_fillet_arc(int_pt, angle1, angle2, radius, segments=16):
    """İki doğru parçası arasına (kesişim noktasından dışa doğru) teğet yay oluşturur.
    Doğru parçaları int_pt'den angle1 ve angle2 yönünde uzaklaşıyor varsayılır.

    Args:
        int_pt: QgsPointXY - Kesişim noktası
        angle1: float - 1. çizginin yönü (radyan)
        angle2: float - 2. çizginin yönü (radyan)
        radius: float - Yay yarıçapı
        segments: int - Yay bölüm sayısı

    Returns:
        tuple (list[QgsPointXY], float): (Yay noktaları dizisi, kesişimden kesilme mesafesi)
    """
    if radius <= 0:
        return [], 0.0

    # Adım 1: Açılardan (radyan) üniter vektörleri oluştur
    v1_x, v1_y = math.cos(angle1), math.sin(angle1)
    v2_x, v2_y = math.cos(angle2), math.sin(angle2)

    # İki vektör arasındaki açıyı hesapla (dot product)
    dot = v1_x * v2_x + v1_y * v2_y
    # Kayan nokta (float) hatalarına karşı sınırla (-1.0 ile 1.0 arasına)
    dot_clamped = max(-1.0, min(1.0, dot))
    angle = math.acos(dot_clamped)

    if abs(angle) < 1e-6 or abs(angle - math.pi) < 1e-6:
        return [], 0.0  # Paralel veya doğrusal hatası

    # Adım 2: Kesişimden teğet noktasına olan mesafe
    tan_dist = radius / math.tan(angle / 2.0)
    
    tp1 = QgsPointXY(int_pt.x() + v1_x * tan_dist, int_pt.y() + v1_y * tan_dist)
    tp2 = QgsPointXY(int_pt.x() + v2_x * tan_dist, int_pt.y() + v2_y * tan_dist)

    # Adım 3: İki vektörün tam ortasından (açıortay) merkeze giden vektör ('v1 + v2')
    bisec_angle = math.atan2(v1_y + v2_y, v1_x + v2_x)
    center_dist = radius / math.sin(angle / 2.0)
    
    center = QgsPointXY(int_pt.x() + math.cos(bisec_angle) * center_dist,
                        int_pt.y() + math.sin(bisec_angle) * center_dist)

    # Adım 4: Yayları oluştur
    a1 = math.atan2(tp1.y() - center.y(), tp1.x() - center.x())
    a2 = math.atan2(tp2.y() - center.y(), tp2.x() - center.x())

    # Dönüş yönünü en kısa ark olacak şekilde güvenceye al
    diff = a2 - a1
    while diff > math.pi:
        diff -= 2 * math.pi
    while diff <= -math.pi:
        diff += 2 * math.pi

    pts = []
    for i in range(segments + 1):
        t = i / float(segments)
        a = a1 + diff * t
        px = center.x() + radius * math.cos(a)
        py = center.y() + radius * math.sin(a)
        pts.append(QgsPointXY(px, py))
        
    return pts, tan_dist

def line_intersection(p1, p2, p3, p4):
    """
    İki doğru parçasının kesişim noktasını döndürür.
    Paralelse None döner.
    """
    x1, y1 = p1.x(), p1.y()
    x2, y2 = p2.x(), p2.y()
    x3, y3 = p3.x(), p3.y()
    x4, y4 = p4.x(), p4.y()
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None
    px = ((x1*y2 - y1*x2) * (x3 - x4) - (x1 - x2) * (x3*y4 - y3*x4)) / denom
    py = ((x1*y2 - y1*x2) * (y3 - y4) - (y1 - y2) * (x3*y4 - y3*x4)) / denom
    return QgsPointXY(px, py)

def create_fillet_and_trims(geom1, geom2, radius):
    """
    İki QgsGeometry (LineString) arasında fillet yayı oluşturur.
    Returns: { 'arc': QgsGeometry, 'tp1': QgsPointXY, 'tp2': QgsPointXY, 'inter_pt': QgsPointXY }
    """
    if geom1.isMultipart():
        pts1 = geom1.asMultiPolyline()[0]
    else:
        pts1 = geom1.asPolyline()
    if geom2.isMultipart():
        pts2 = geom2.asMultiPolyline()[0]
    else:
        pts2 = geom2.asPolyline()
    if len(pts1) < 2 or len(pts2) < 2:
        return None

    inter = geom1.intersection(geom2)
    if not inter.isEmpty() and inter.type() == QgsWkbTypes.PointGeometry:
        inter_pt = inter.asPoint()
    else:
        inter_pt = line_intersection(pts1[0], pts1[-1], pts2[0], pts2[-1])
        if inter_pt is None:
            return None

    def unit_vec(a, b):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        d = math.hypot(dx, dy)
        return (dx/d, dy/d) if d > 1e-12 else (0.0, 0.0)

    i1 = 0 if QgsPointXY(pts1[0]).distance(inter_pt) < QgsPointXY(pts1[-1]).distance(inter_pt) else -1
    i2 = 0 if QgsPointXY(pts2[0]).distance(inter_pt) < QgsPointXY(pts2[-1]).distance(inter_pt) else -1
    v1 = unit_vec(inter_pt, pts1[-1 if i1 == 0 else 0])
    v2 = unit_vec(inter_pt, pts2[-1 if i2 == 0 else 0])

    dot = v1[0]*v2[0] + v1[1]*v2[1]
    if abs(abs(dot) - 1.0) < 1e-6:
        return None

    angle = math.acos(max(-1.0, min(1.0, dot)))
    if abs(angle) < 1e-6:
        return None

    tan_len = radius / math.tan(angle/2)
    tp1 = QgsPointXY(inter_pt.x() + v1[0]*tan_len, inter_pt.y() + v1[1]*tan_len)
    tp2 = QgsPointXY(inter_pt.x() + v2[0]*tan_len, inter_pt.y() + v2[1]*tan_len)

    bisec = math.atan2(v1[1] + v2[1], v1[0] + v2[0])
    center_dist = radius / math.sin(angle/2)
    center = QgsPointXY(inter_pt.x() + math.cos(bisec)*center_dist,
                        inter_pt.y() + math.sin(bisec)*center_dist)

    def angle_of(p):
        return math.atan2(p.y() - center.y(), p.x() - center.x())
    
    a1 = angle_of(tp1)
    a2 = angle_of(tp2)
    # Pick the SHORTEST arc between tp1 and tp2 — previous version always
    # forced CCW, producing the long way around for half the configurations.
    diff = a2 - a1
    while diff > math.pi:
        diff -= 2 * math.pi
    while diff <= -math.pi:
        diff += 2 * math.pi

    segments = 20
    arc_pts = [QgsPointXY(center.x() + radius*math.cos(a1 + diff*i/segments),
                          center.y() + radius*math.sin(a1 + diff*i/segments))
               for i in range(segments+1)]
               
    arc_pts[0] = tp1
    arc_pts[-1] = tp2
    return {
        'arc': QgsGeometry.fromPolylineXY(arc_pts),
        'tp1': tp1,
        'tp2': tp2,
        'inter_pt': inter_pt
    }

def trim_line_to_point(geom, pt, inter_pt=None):
    """
    Çizgiyi belirtilen noktaya kadar (kesişim noktasına en yakın uçundan) budar.
    """
    if geom.isMultipart():
        pts = geom.asMultiPolyline()[0]
    else:
        pts = geom.asPolyline()
    if len(pts) < 2:
        return geom

    ref_pt = inter_pt if inter_pt is not None else pt
    d0 = QgsGeometry.fromPointXY(pts[0]).distance(QgsGeometry.fromPointXY(ref_pt))
    d1 = QgsGeometry.fromPointXY(pts[-1]).distance(QgsGeometry.fromPointXY(ref_pt))
    
    if d0 < d1:
        new_pts = [pt] + pts[1:]
        new_pts[0] = pt
    else:
        new_pts = pts[:-1] + [pt]
        new_pts[-1] = pt

    return QgsGeometry.fromPolylineXY(new_pts)
