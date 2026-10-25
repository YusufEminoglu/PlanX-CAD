# -*- coding: utf-8 -*-
"""planX CAD — Precision Object Snap (OSNAP) Engine.

Computes running geometric snap points from QGIS point locator matches and
feature geometries:
  - Endpoints, Midpoints, Centroids/Centres, Quadrants, Nodes/Vertices
  - Intersections, Apparent Intersections
  - Perpendiculars (from tool anchor point)
  - Tangents (to circular/curved elements from anchor point)
  - Nearest points on segments
  - Extensions along straight segment rays

Dual-runtime compatible (QGIS 3 LTR / PyQt5 and QGIS 4 / PyQt6).
Zero external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointLocator,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .crs_utils import local_metric_crs, transform_geometry, transform_point


class SnapKind(str, Enum):
    """Categorization of geometric object snap types."""
    ENDPOINT = "endpoint"
    MIDPOINT = "midpoint"
    CENTRE = "centre"
    QUADRANT = "quadrant"
    VERTEX = "vertex"
    INTERSECTION = "intersection"
    APPARENT_INTERSECTION = "apparent_intersection"
    PERPENDICULAR = "perpendicular"
    TANGENT = "tangent"
    NEAREST = "nearest"
    EXTENSION = "extension"


@dataclass(frozen=True)
class SnapResult:
    """The result of an object snap query."""
    point: QgsPointXY
    kind: SnapKind
    layer: QgsVectorLayer | None = None
    feature_id: int | None = None
    description: str = ""


# ── Pure geometric math helpers ───────────────────────────────────────────────

def _dist(p1: QgsPointXY, p2: QgsPointXY) -> float:
    return math.hypot(p1.x() - p2.x(), p1.y() - p2.y())


def _foot_of_perpendicular(
    p: QgsPointXY, a: QgsPointXY, b: QgsPointXY
) -> tuple[QgsPointXY | None, float]:
    """Return the foot of perpendicular from p onto segment a-b and its ratio t."""
    dx = b.x() - a.x()
    dy = b.y() - a.y()
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-12:
        return None, 0.0
    t = ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / length_sq
    foot = QgsPointXY(a.x() + t * dx, a.y() + t * dy)
    return foot, t


def _line_intersection(
    p1: QgsPointXY, p2: QgsPointXY, p3: QgsPointXY, p4: QgsPointXY, infinite: bool = False
) -> QgsPointXY | None:
    """Compute the intersection of segment or infinite line p1-p2 with p3-p4."""
    d1x, d1y = p2.x() - p1.x(), p2.y() - p1.y()
    d2x, d2y = p4.x() - p3.x(), p4.y() - p3.y()
    denom = d1x * d2y - d1y * d2x
    if abs(denom) <= 1e-10:
        return None  # Parallel or collinear

    num_s = (p3.x() - p1.x()) * d2y - (p3.y() - p1.y()) * d2x
    num_t = (p3.x() - p1.x()) * d1y - (p3.y() - p1.y()) * d1x
    s = num_s / denom
    t = num_t / denom

    if not infinite:
        if not (-1e-6 <= s <= 1.0 + 1e-6 and -1e-6 <= t <= 1.0 + 1e-6):
            return None

    return QgsPointXY(p1.x() + s * d1x, p1.y() + s * d1y)


def _circle_tangents_from_point(
    anchor: QgsPointXY, center: QgsPointXY, radius: float
) -> list[QgsPointXY]:
    """Compute up to 2 tangent points on a circle from an external anchor point."""
    d = _dist(anchor, center)
    if d <= radius or radius <= 1e-7:
        return []
    base_angle = math.atan2(anchor.y() - center.y(), anchor.x() - center.x())
    alpha = math.acos(min(1.0, max(-1.0, radius / d)))
    pts = []
    for sign in (1.0, -1.0):
        ang = base_angle + sign * alpha
        pts.append(QgsPointXY(center.x() + radius * math.cos(ang), center.y() + radius * math.sin(ang)))
    return pts


# ── OSNAP Engine Implementation ───────────────────────────────────────────────

class OsnapEngine:
    """Evaluates canvas cursor position against native snapping and geometry primitives."""

    DEFAULT_ENABLED: set[SnapKind] = {
        SnapKind.ENDPOINT,
        SnapKind.MIDPOINT,
        SnapKind.CENTRE,
        SnapKind.QUADRANT,
        SnapKind.VERTEX,
        SnapKind.INTERSECTION,
        SnapKind.APPARENT_INTERSECTION,
        SnapKind.PERPENDICULAR,
        SnapKind.TANGENT,
        SnapKind.NEAREST,
        SnapKind.EXTENSION,
    }

    def __init__(self, canvas):
        self.canvas = canvas
        self.enabled_kinds: set[SnapKind] = set(self.DEFAULT_ENABLED)

    def is_enabled(self, kind: SnapKind) -> bool:
        return kind in self.enabled_kinds

    def set_enabled(self, kind: SnapKind, enabled: bool) -> None:
        if enabled:
            self.enabled_kinds.add(kind)
        else:
            self.enabled_kinds.discard(kind)

    def snap(
        self,
        event_pos,
        anchor_point: QgsPointXY | None = None,
        tolerance_px: float = 12.0,
    ) -> SnapResult | None:
        """Find the most specific geometric snap candidate at event_pos."""
        if not self.enabled_kinds:
            return None

        snapper = self.canvas.snappingUtils()
        if snapper is None:
            return None

        cursor_map = self.canvas.getCoordinateTransform().toMapCoordinates(event_pos)
        map_tol = self.canvas.mapUnitsPerPixel() * tolerance_px

        match = snapper.snapToMap(event_pos)
        candidates: list[tuple[float, SnapResult]] = []

        if match.isValid():
            layer = match.layer()
            feature_id = match.featureId()
            point = match.point()
            mtype = match.type()

            # Vertex matches: classify into Endpoint vs Vertex/Node
            if mtype == QgsPointLocator.Type.Vertex:
                kind = SnapKind.VERTEX
                if layer and feature_id is not None:
                    feat = layer.getFeature(feature_id)
                    if feat.isValid() and feat.geometry():
                        geom = feat.geometry()
                        # Inspect vertices
                        is_end = self._is_geometry_endpoint(geom, point, map_tol)
                        if is_end and self.is_enabled(SnapKind.ENDPOINT):
                            kind = SnapKind.ENDPOINT
                        elif not is_end and self.is_enabled(SnapKind.VERTEX):
                            kind = SnapKind.VERTEX
                if self.is_enabled(kind):
                    candidates.append((_dist(cursor_map, point), SnapResult(point, kind, layer, feature_id, kind.value)))

            # Midpoint of segment
            elif mtype == QgsPointLocator.Type.MiddleOfSegment and self.is_enabled(SnapKind.MIDPOINT):
                candidates.append((_dist(cursor_map, point), SnapResult(point, SnapKind.MIDPOINT, layer, feature_id, "midpoint")))

            # Centroid
            elif mtype == QgsPointLocator.Type.Centroid and self.is_enabled(SnapKind.CENTRE):
                candidates.append((_dist(cursor_map, point), SnapResult(point, SnapKind.CENTRE, layer, feature_id, "centre")))

            # Edge match: can evaluate Perpendicular, Tangent, Midpoint, or Nearest
            elif mtype == QgsPointLocator.Type.Edge:
                edge_cand = self._evaluate_edge_match(match, cursor_map, anchor_point, map_tol)
                if edge_cand:
                    candidates.extend(edge_cand)

        # Also inspect geometric intersections, perpendiculars, extensions, and apparent intersections
        # around the search rect if not already matched with high precision
        derived = self._evaluate_contextual_geometry(cursor_map, anchor_point, map_tol)
        if derived:
            candidates.extend(derived)

        if not candidates:
            return None

        # Sort candidates by distance from cursor, but prioritize specific CAD types
        # over generic "nearest" or "vertex"
        priority_map = {
            SnapKind.INTERSECTION: 0,
            SnapKind.ENDPOINT: 1,
            SnapKind.MIDPOINT: 2,
            SnapKind.CENTRE: 3,
            SnapKind.QUADRANT: 4,
            SnapKind.PERPENDICULAR: 5,
            SnapKind.TANGENT: 6,
            SnapKind.APPARENT_INTERSECTION: 7,
            SnapKind.EXTENSION: 8,
            SnapKind.VERTEX: 9,
            SnapKind.NEAREST: 10,
        }

        # Keep candidates within tolerance
        valid = [c for c in candidates if c[0] <= map_tol * 1.5]
        if not valid:
            valid = candidates

        valid.sort(key=lambda item: (priority_map.get(item[1].kind, 99), item[0]))
        return valid[0][1]

    def _is_geometry_endpoint(self, geom: QgsGeometry, pt: QgsPointXY, tol: float) -> bool:
        """Return True if pt is the start or end vertex of an unclosed line."""
        if geom.isEmpty():
            return False
        if geom.type() == QgsWkbTypes.GeometryType.LineGeometry:
            if geom.isMultipart():
                lines = geom.asMultiPolyline()
                for line in lines:
                    if line:
                        if _dist(pt, line[0]) <= tol or _dist(pt, line[-1]) <= tol:
                            return True
            else:
                line = geom.asPolyline()
                if line:
                    if _dist(pt, line[0]) <= tol or _dist(pt, line[-1]) <= tol:
                        return True
        return False

    def _evaluate_edge_match(
        self, match, cursor_map: QgsPointXY, anchor_point: QgsPointXY | None, tol: float
    ) -> list[tuple[float, SnapResult]]:
        results = []
        layer = match.layer()
        feature_id = match.featureId()
        point = match.point()

        if layer and feature_id is not None:
            feat = layer.getFeature(feature_id)
            if feat.isValid() and feat.geometry():
                geom = feat.geometry()
                # Check perpendicular from anchor
                if anchor_point and self.is_enabled(SnapKind.PERPENDICULAR):
                    perp = self._find_perpendicular_to_geometry(geom, anchor_point, cursor_map, tol)
                    if perp:
                        results.append((_dist(cursor_map, perp), SnapResult(perp, SnapKind.PERPENDICULAR, layer, feature_id, "perpendicular")))

                # Check circle / arc center and quadrant
                if self.is_enabled(SnapKind.CENTRE) or self.is_enabled(SnapKind.QUADRANT) or self.is_enabled(SnapKind.TANGENT):
                    c_results = self._find_curved_snaps(geom, anchor_point, cursor_map, tol, layer, feature_id)
                    results.extend(c_results)

        # Fallback to nearest if enabled
        if self.is_enabled(SnapKind.NEAREST):
            results.append((_dist(cursor_map, point), SnapResult(point, SnapKind.NEAREST, layer, feature_id, "nearest")))

        return results

    def _find_perpendicular_to_geometry(
        self, geom: QgsGeometry, anchor: QgsPointXY, cursor: QgsPointXY, tol: float
    ) -> QgsPointXY | None:
        """Find foot of perpendicular from anchor onto any segment of geom near cursor."""
        vertices = [QgsPointXY(v) for v in geom.vertices()]
        best_pt = None
        best_dist = tol
        for i in range(len(vertices) - 1):
            p1, p2 = vertices[i], vertices[i + 1]
            foot, t = _foot_of_perpendicular(anchor, p1, p2)
            if foot and 0.0 <= t <= 1.0:
                d = _dist(cursor, foot)
                if d <= best_dist:
                    best_dist = d
                    best_pt = foot
        return best_pt

    def _find_curved_snaps(
        self,
        geom: QgsGeometry,
        anchor: QgsPointXY | None,
        cursor: QgsPointXY,
        tol: float,
        layer: QgsVectorLayer | None,
        feature_id: int | None,
    ) -> list[tuple[float, SnapResult]]:
        """Extract Centre, Quadrant, and Tangent snaps if geometry exhibits circular/arc shape."""
        results: list[tuple[float, SnapResult]] = []
        rect = geom.boundingBox()
        w, h = rect.width(), rect.height()
        if w <= 1e-6 or h <= 1e-6:
            return results

        # If bounding box is roughly square (circle or regular polygon)
        aspect = w / h if h > 0 else 0
        if 0.85 <= aspect <= 1.15:
            center = rect.center()
            radius = (w + h) / 4.0
            # Centre snap
            if self.is_enabled(SnapKind.CENTRE):
                d = _dist(cursor, center)
                if d <= tol:
                    results.append((d, SnapResult(center, SnapKind.CENTRE, layer, feature_id, "centre")))

            # Quadrant snaps (0, 90, 180, 270)
            if self.is_enabled(SnapKind.QUADRANT):
                quads = [
                    QgsPointXY(center.x() + radius, center.y()),
                    QgsPointXY(center.x(), center.y() + radius),
                    QgsPointXY(center.x() - radius, center.y()),
                    QgsPointXY(center.x(), center.y() - radius),
                ]
                for q in quads:
                    dq = _dist(cursor, q)
                    if dq <= tol:
                        results.append((dq, SnapResult(q, SnapKind.QUADRANT, layer, feature_id, "quadrant")))

            # Tangent snaps from anchor
            if anchor and self.is_enabled(SnapKind.TANGENT):
                tangents = _circle_tangents_from_point(anchor, center, radius)
                for tp in tangents:
                    dt = _dist(cursor, tp)
                    if dt <= tol:
                        results.append((dt, SnapResult(tp, SnapKind.TANGENT, layer, feature_id, "tangent")))

        return results

    def _evaluate_contextual_geometry(
        self, cursor_map: QgsPointXY, anchor_point: QgsPointXY | None, map_tol: float
    ) -> list[tuple[float, SnapResult]]:
        """Look for Extension rays, Intersections, and Apparent Intersections."""
        results: list[tuple[float, SnapResult]] = []
        canvas_crs = self.canvas.mapSettings().destinationCrs()

        search_rect = QgsRectangle(
            cursor_map.x() - map_tol * 3,
            cursor_map.y() - map_tol * 3,
            cursor_map.x() + map_tol * 3,
            cursor_map.y() + map_tol * 3,
        )

        segments: list[tuple[QgsPointXY, QgsPointXY, QgsVectorLayer, int]] = []

        # Collect visible segments from editable and visible vector layers
        for lyr in QgsProject.instance().mapLayers().values():
            if not isinstance(lyr, QgsVectorLayer) or not lyr.isSpatial():
                continue
            if not lyr.isValid() or lyr.featureCount() == 0:
                continue

            # Transform search_rect to layer CRS
            lyr_rect = search_rect
            if canvas_crs.isValid() and lyr.crs().isValid() and canvas_crs != lyr.crs():
                try:
                    tr = QgsCoordinateTransform(canvas_crs, lyr.crs(), QgsProject.instance())
                    lyr_rect = tr.transformBoundingBox(search_rect)
                except Exception:
                    lyr_rect = None
            if lyr_rect is None:
                continue

            req = QgsFeatureRequest().setFilterRect(lyr_rect)
            for feat in lyr.getFeatures(req):
                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    continue
                # Transform geometry to canvas CRS
                geom_canvas = QgsGeometry(geom)
                transform_failed = False
                if canvas_crs.isValid() and lyr.crs().isValid() and canvas_crs != lyr.crs():
                    try:
                        tr_inv = QgsCoordinateTransform(lyr.crs(), canvas_crs, QgsProject.instance())
                        geom_canvas.transform(tr_inv)
                    except Exception:
                        transform_failed = True
                if transform_failed:
                    continue

                vertices = [QgsPointXY(v) for v in geom_canvas.vertices()]
                for i in range(len(vertices) - 1):
                    p1, p2 = vertices[i], vertices[i + 1]
                    if _dist(p1, p2) > 1e-7:
                        segments.append((p1, p2, lyr, feat.id()))

        # 1. Extensions along segments
        if self.is_enabled(SnapKind.EXTENSION):
            for p1, p2, lyr, fid in segments:
                foot, t = _foot_of_perpendicular(cursor_map, p1, p2)
                if foot is not None:
                    # Projection past endpoints (t < 0 or t > 1) within extension distance
                    if (t < -0.01 or t > 1.01) and _dist(cursor_map, foot) <= map_tol:
                        # Only within a reasonable extension reach (up to 20x map_tol)
                        seg_len = _dist(p1, p2)
                        ext_dist = _dist(foot, p1 if t < 0 else p2)
                        if ext_dist <= max(seg_len * 2.0, map_tol * 15.0):
                            results.append((_dist(cursor_map, foot), SnapResult(foot, SnapKind.EXTENSION, lyr, fid, "extension")))

        # 2. Intersections and Apparent Intersections
        check_intersection = self.is_enabled(SnapKind.INTERSECTION)
        check_apparent = self.is_enabled(SnapKind.APPARENT_INTERSECTION)
        if (check_intersection or check_apparent) and len(segments) >= 2:
            limit = min(len(segments), 30)
            for i in range(limit):
                s1_a, s1_b, l1, fid1 = segments[i]
                for j in range(i + 1, limit):
                    s2_a, s2_b, l2, fid2 = segments[j]
                    # Direct intersection
                    pt_real = _line_intersection(s1_a, s1_b, s2_a, s2_b, infinite=False)
                    if pt_real and check_intersection:
                        d = _dist(cursor_map, pt_real)
                        if d <= map_tol:
                            results.append((d, SnapResult(pt_real, SnapKind.INTERSECTION, l1, fid1, "intersection")))
                    # Apparent intersection (infinite line extensions)
                    elif check_apparent:
                        pt_inf = _line_intersection(s1_a, s1_b, s2_a, s2_b, infinite=True)
                        if pt_inf:
                            d = _dist(cursor_map, pt_inf)
                            if d <= map_tol:
                                results.append((d, SnapResult(pt_inf, SnapKind.APPARENT_INTERSECTION, l1, fid1, "apparent intersection")))

        return results
