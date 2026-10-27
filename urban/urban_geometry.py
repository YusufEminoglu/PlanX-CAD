# -*- coding: utf-8 -*-
"""planX CAD — geometry for the street and parcel design tools.

All functions work in a local metric CRS (metres) and return QgsGeometry
objects; the map tools handle CRS transforms and layer writes.

  buildable_envelope   parcel minus front / side / rear setbacks
  sight_triangle       corner visibility triangle between two curb lines
  parking_bays         stalls along a curb line at a given angle
  roundabout_parts     central island, truck apron, circulatory ring
  splitter_island      triangular island on an approach leg
  turning_head         cul-de-sac bulb with tapers at a road end
"""
from __future__ import annotations

import math

from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes

# Segments per quarter circle for round buffers and circles.
_ARC_SEGMENTS = 16
_EPS = 1e-9


# ── small vector helpers ────────────────────────────────────────────────────

def _sub(a, b):
    return (a.x() - b.x(), a.y() - b.y())


def _unit(dx, dy):
    length = math.hypot(dx, dy)
    if length < _EPS:
        return None
    return (dx / length, dy / length)


def _offset(p, direction, distance):
    return QgsPointXY(p.x() + direction[0] * distance, p.y() + direction[1] * distance)


def _line_intersection(p1, p2, p3, p4):
    """Intersection of the infinite lines p1-p2 and p3-p4, or None if parallel."""
    d1 = _sub(p2, p1)
    d2 = _sub(p4, p3)
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(denom) < _EPS:
        return None
    t = ((p3.x() - p1.x()) * d2[1] - (p3.y() - p1.y()) * d2[0]) / denom
    return QgsPointXY(p1.x() + t * d1[0], p1.y() + t * d1[1])


def _polygon_rings(geom):
    """[(ring points, is_exterior)] for a (multi)polygon geometry."""
    polygons = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
    rings = []
    for polygon in polygons:
        for index, ring in enumerate(polygon):
            if len(ring) >= 4:
                rings.append(([QgsPointXY(p) for p in ring], index == 0))
    return rings


def _polylines(geom):
    if geom is None or geom.isEmpty():
        return []
    lines = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
    return [[QgsPointXY(p) for p in line] for line in lines if len(line) >= 2]


def _nearest_segment(geom, point):
    """(a, b) of the line segment of ``geom`` nearest to ``point``."""
    best = None
    target = QgsGeometry.fromPointXY(point)
    for line in _polylines(geom):
        for a, b in zip(line, line[1:]):
            if a.distance(b) < _EPS:
                continue
            dist = QgsGeometry.fromPolylineXY([a, b]).distance(target)
            if best is None or dist < best[0]:
                best = (dist, a, b)
    return (best[1], best[2]) if best else None


# ── buildable envelope ─────────────────────────────────────────────────────

FRONT = "front"
SIDE = "side"
REAR = "rear"


def classify_parcel_edges(parcel, click_point, corner_parcel=False):
    """Label every boundary edge of ``parcel`` as front, side or rear.

    The exterior edge nearest ``click_point`` is the front. With
    ``corner_parcel`` the adjacent exterior edge nearest the click is a second
    front (click near the street corner). Exterior edges running within 30° of
    parallel to the front and lying in the far half of the parcel are rear;
    every other edge, holes included, is a side.

    Returns ``[(a, b, role)]``.
    """
    rings = _polygon_rings(parcel)
    exterior = []
    edges = []
    target = QgsGeometry.fromPointXY(click_point)
    for ring, is_exterior in rings:
        for a, b in zip(ring, ring[1:]):
            if a.distance(b) < _EPS:
                continue
            edge = [a, b, SIDE]
            edges.append(edge)
            if is_exterior:
                exterior.append(edge)
    if not exterior:
        return []

    def distance(edge):
        return QgsGeometry.fromPolylineXY([edge[0], edge[1]]).distance(target)

    front = min(exterior, key=distance)
    front[2] = FRONT
    fronts = [front]
    if corner_parcel:
        neighbours = [e for e in exterior if e is not front and (
            e[0].distance(front[0]) < 1e-6 or e[0].distance(front[1]) < 1e-6 or
            e[1].distance(front[0]) < 1e-6 or e[1].distance(front[1]) < 1e-6)]
        if neighbours:
            second = min(neighbours, key=distance)
            second[2] = FRONT
            fronts.append(second)

    # Rear: roughly parallel to the (first) front and in the far half.
    a, b = front[0], front[1]
    direction = _unit(*_sub(b, a))
    if direction is not None:
        normal = (-direction[1], direction[0])

        def depth(p):
            return abs((p.x() - a.x()) * normal[0] + (p.y() - a.y()) * normal[1])

        max_depth = max(depth(p) for ring, is_ext in rings if is_ext for p in ring)
        for edge in exterior:
            if edge[2] == FRONT:
                continue
            edge_dir = _unit(*_sub(edge[1], edge[0]))
            if edge_dir is None:
                continue
            parallel = abs(edge_dir[0] * direction[0] + edge_dir[1] * direction[1]) >= math.cos(math.radians(30))
            mid = QgsPointXY((edge[0].x() + edge[1].x()) / 2, (edge[0].y() + edge[1].y()) / 2)
            if parallel and depth(mid) > 0.5 * max_depth:
                edge[2] = REAR
    return [tuple(edge) for edge in edges]


def buildable_envelope(parcel, click_point, front, side, rear, corner_parcel=False):
    """Area of ``parcel`` at least ``front``/``side``/``rear`` metres from
    the matching boundary edges.

    Each edge is buffered by its own setback with round caps, so the result is
    exactly the set of points that keep every required distance; it is correct
    for concave parcels, where intersecting offset lines is not.

    Returns ``(envelope geometry or None, edges)``.
    """
    if parcel is None or parcel.isEmpty():
        return None, []
    edges = classify_parcel_edges(parcel, click_point, corner_parcel)
    distances = {FRONT: front, SIDE: side, REAR: rear}
    buffers = []
    for a, b, role in edges:
        d = float(distances[role])
        if d > 0:
            buffers.append(QgsGeometry.fromPolylineXY([a, b]).buffer(d, _ARC_SEGMENTS))
    if not buffers:
        return QgsGeometry(parcel), edges
    excluded = QgsGeometry.unaryUnion(buffers)
    envelope = parcel.difference(excluded)
    if envelope is None or envelope.isEmpty() or envelope.area() < 1e-6:
        return None, edges
    return envelope, edges


# ── sight triangle ─────────────────────────────────────────────────────────

def sight_triangle(geom1, pick1, geom2, pick2, leg1, leg2):
    """Visibility triangle at the corner formed by two curb lines.

    The corner is where the two picked segments meet, or where their
    extensions would meet if the curbs stop short (a rounded corner). Each
    leg runs from the corner toward the point where that line was picked.
    Returns ``(triangle, corner)`` or ``(None, None)``.
    """
    if leg1 <= 0 or leg2 <= 0:
        return None, None
    seg1 = _nearest_segment(geom1, pick1)
    seg2 = _nearest_segment(geom2, pick2)
    if seg1 is None or seg2 is None:
        return None, None
    corner = _line_intersection(seg1[0], seg1[1], seg2[0], seg2[1])
    if corner is None:
        return None, None

    def leg_direction(segment, pick):
        a, b = segment
        seg_dir = _unit(*_sub(b, a))
        toward = _sub(pick, corner)
        # Project the pick onto the segment's line; the leg follows the line.
        along = toward[0] * seg_dir[0] + toward[1] * seg_dir[1]
        if abs(along) < 1e-6:
            # Picked at the corner itself: take the segment's far end.
            far = a if a.distance(corner) > b.distance(corner) else b
            return _unit(*_sub(far, corner))
        return (seg_dir[0] * math.copysign(1, along), seg_dir[1] * math.copysign(1, along))

    u1 = leg_direction(seg1, pick1)
    u2 = leg_direction(seg2, pick2)
    if u1 is None or u2 is None:
        return None, None
    p1 = _offset(corner, u1, leg1)
    p2 = _offset(corner, u2, leg2)
    triangle = QgsGeometry.fromPolygonXY([[corner, p1, p2, corner]])
    if triangle.isEmpty() or triangle.area() < 1e-6:
        return None, None
    return triangle, corner


# ── parking layout ─────────────────────────────────────────────────────────

def parking_bays(line, side_point, angle_deg, width, length, start_offset=0.0):
    """Parking stalls along ``line`` on the side of ``side_point``.

    ``angle_deg`` is the angle between the curb and the stall axis: 90 is
    perpendicular parking, 60/45/30 are angled (stalls lean forward along the
    line direction), 0 is parallel parking. ``width`` is the stall width and
    ``length`` the stall length along its axis (for parallel parking the
    length runs along the curb). Stalls never wrap round a bend: each line
    segment holds only the stalls that fit on it entirely, and at a bend
    toward the stalls any stall overlapping the previous segment's is dropped.

    Returns a list of polygons in drawing order.
    """
    if width <= 0 or length <= 0:
        return []
    angle = math.radians(max(0.0, min(90.0, float(angle_deg))))
    line_parts = _polylines(line)
    if not line_parts:
        return []

    # Which side of the line: sign of the cross product at the nearest segment.
    seg = _nearest_segment(line, side_point)
    if seg is None:
        return []
    seg_dir = _unit(*_sub(seg[1], seg[0]))
    rel = _sub(side_point, seg[0])
    side = 1.0 if seg_dir[0] * rel[1] - seg_dir[1] * rel[0] >= 0 else -1.0

    bays = []
    for points in line_parts:
        previous_segment = []
        for a, b in zip(points, points[1:]):
            segment_bays = []
            direction = _unit(*_sub(b, a))
            if direction is None:
                continue
            seg_len = a.distance(b)
            normal = (-direction[1] * side, direction[0] * side)
            if angle < math.radians(1):  # parallel
                step, depth_axis, depth = length, normal, width
                lean = 0.0
            else:
                step = width / math.sin(angle)
                axis = (direction[0] * math.cos(angle) + normal[0] * math.sin(angle),
                        direction[1] * math.cos(angle) + normal[1] * math.sin(angle))
                depth_axis, depth = axis, length
                lean = length * math.cos(angle)  # back corners shift along the curb
            s = max(0.0, float(start_offset))
            while s + step + max(0.0, lean) <= seg_len + 1e-9:
                p0 = _offset(a, direction, s)
                p1 = _offset(a, direction, s + step)
                p2 = _offset(p1, depth_axis, depth)
                p3 = _offset(p0, depth_axis, depth)
                bay = QgsGeometry.fromPolygonXY([[p0, p1, p2, p3, p0]])
                # Only the stalls next to the bend can collide, so compare
                # against the previous segment's stalls, nearest first.
                if not any(bay.intersection(other).area() > 1e-6
                           for other in reversed(previous_segment[-40:])):
                    segment_bays.append(bay)
                s += step
            bays.extend(segment_bays)
            previous_segment = segment_bays
    return bays


# ── roundabout ─────────────────────────────────────────────────────────────

def circle(center, radius, segments=_ARC_SEGMENTS):
    return QgsGeometry.fromPointXY(center).buffer(radius, segments)


def roundabout_parts(center, outer_radius, lane_width, apron_width=0.0):
    """Concentric roundabout parts as ``[(part name, geometry)]``.

    ``outer_radius`` is the inscribed circle (outer kerb). Inward from it come
    the circulatory carriageway (``lane_width``), an optional mountable truck
    apron (``apron_width``) and the central island.
    """
    inner = outer_radius - lane_width
    island = inner - max(0.0, apron_width)
    if lane_width <= 0 or island <= 0.5:
        return []
    outer_disc = circle(center, outer_radius)
    inner_disc = circle(center, inner)
    parts = [("circulatory", outer_disc.difference(inner_disc))]
    if apron_width > 0:
        parts.append(("apron", inner_disc.difference(circle(center, island))))
    parts.append(("central_island", circle(center, island)))
    return parts


def approach_directions(center, outer_radius, line_geometries):
    """Unit directions from ``center`` to each point where an approach line
    crosses the outer circle (duplicates within 10° are merged)."""
    ring = QgsGeometry.fromPolylineXY(
        [QgsPointXY(p) for p in circle(center, outer_radius).asPolygon()[0]]
    )
    directions = []
    for geom in line_geometries:
        if geom is None or geom.isEmpty():
            continue
        hits = geom.intersection(ring)
        if hits is None or hits.isEmpty():
            continue
        if hits.type() != QgsWkbTypes.GeometryType.PointGeometry:
            continue
        points = hits.asMultiPoint() if hits.isMultipart() else [hits.asPoint()]
        for p in points:
            u = _unit(*_sub(QgsPointXY(p), center))
            if u is None:
                continue
            if all(math.degrees(math.acos(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))) > 10
                   for v in directions):
                directions.append(u)
    return directions


def splitter_island(center, outer_radius, direction, length, base_width, gap=1.0):
    """Triangular splitter island on an approach leg: base at the outer kerb
    (plus ``gap``), apex ``length`` metres out along the approach."""
    if length <= 0 or base_width <= 0:
        return None
    normal = (-direction[1], direction[0])
    base = _offset(center, direction, outer_radius + gap)
    left = _offset(base, normal, base_width / 2.0)
    right = _offset(base, normal, -base_width / 2.0)
    apex = _offset(center, direction, outer_radius + gap + length)
    return QgsGeometry.fromPolygonXY([[left, apex, right, left]])


# ── turning head ───────────────────────────────────────────────────────────

def turning_head(line, pick_point, radius, road_width, taper_length):
    """Cul-de-sac bulb at the end of ``line`` nearest ``pick_point``.

    A turning circle of ``radius`` is centred on the road end and joined to
    the carriageway (``road_width``) by straight tapers that start
    ``taper_length`` metres back along the road. Returns ``(polygon, end)``.
    """
    lines = _polylines(line)
    if not lines or radius <= 0 or road_width <= 0:
        return None, None
    best = None
    for points in lines:
        for end, previous in ((points[0], points[1]), (points[-1], points[-2])):
            dist = end.distance(pick_point)
            if best is None or dist < best[0]:
                best = (dist, end, previous)
    _dist, end, previous = best
    outward = _unit(*_sub(end, previous))
    if outward is None:
        return None, None
    normal = (-outward[1], outward[0])
    back = _offset(end, outward, -max(0.0, taper_length))
    half = road_width / 2.0
    throat = QgsGeometry.fromPolygonXY([[
        _offset(back, normal, half), _offset(end, normal, half),
        _offset(end, normal, -half), _offset(back, normal, -half),
        _offset(back, normal, half),
    ]])
    bulb = QgsGeometry.unaryUnion([circle(end, radius), throat]).convexHull()
    return bulb, end
