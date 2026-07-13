"""Pure geometry primitives for deterministic road-junction corners.

The map tool owns layer discovery, edit commands, and feature writes.  This
module deliberately knows nothing about layers: callers provide one half-edge
for every curb crossing of the junction boundary.  A road which crosses the
junction therefore contributes two *approaches*, even when both approaches
share the same road id.

All coordinates and distances passed here must use the same projected,
metric CRS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Optional, Sequence

from qgis.core import QgsGeometry, QgsPointXY


_EPSILON = 1e-9


def _length(vector: tuple[float, float]) -> float:
    return math.hypot(vector[0], vector[1])


def _normalise(vector: tuple[float, float]) -> tuple[float, float]:
    length = _length(vector)
    if length <= _EPSILON:
        raise ValueError("A junction half-edge requires a non-zero tangent")
    return vector[0] / length, vector[1] / length


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _dot(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[0] + first[1] * second[1]


def _angle(vector: tuple[float, float]) -> float:
    return math.atan2(vector[1], vector[0]) % (2.0 * math.pi)


def _angle_distance(first: float, second: float) -> float:
    difference = abs(first - second) % (2.0 * math.pi)
    return min(difference, 2.0 * math.pi - difference)


def _mean_direction(edges: Sequence["CurbHalfEdge"]) -> tuple[float, float]:
    x = sum(edge.outward[0] for edge in edges)
    y = sum(edge.outward[1] for edge in edges)
    return _normalise((x, y))


@dataclass(frozen=True)
class CurbHalfEdge:
    """One outward curb ray at an effect-boundary crossing.

    ``source_id`` and ``source_ref`` are opaque references returned unchanged
    in :class:`CornerSolution`.  They let the editing layer map the calculated
    cut point back to the exact feature and geometry part without introducing
    a QGIS layer dependency here.
    """

    road_id: Any
    component: str
    source_id: Any
    source_part: int
    cut_point: QgsPointXY
    outward: tuple[float, float]
    source_ref: Any = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cut_point", QgsPointXY(self.cut_point))
        object.__setattr__(self, "outward", _normalise(self.outward))

    @property
    def angle(self) -> float:
        return _angle(self.outward)

    def lateral_offset(self, center: QgsPointXY) -> float:
        """Signed curb offset: positive is left of the outward road axis."""
        relative = (
            self.cut_point.x() - center.x(),
            self.cut_point.y() - center.y(),
        )
        return _cross(self.outward, relative)


@dataclass(frozen=True)
class Approach:
    """Curb half-edges which leave the junction in one direction."""

    road_id: Any
    branch_index: int
    outward: tuple[float, float]
    curbs: tuple[CurbHalfEdge, ...]

    @property
    def angle(self) -> float:
        return _angle(self.outward)

    def left_curb(self, center: QgsPointXY) -> CurbHalfEdge:
        return max(self.curbs, key=lambda edge: edge.lateral_offset(center))

    def right_curb(self, center: QgsPointXY) -> CurbHalfEdge:
        return min(self.curbs, key=lambda edge: edge.lateral_offset(center))


@dataclass(frozen=True)
class CornerSolution:
    """A connection geometry and the exact source-geometry cut points."""

    mode: str
    first: CurbHalfEdge
    second: CurbHalfEdge
    support_intersection: QgsPointXY
    cut_first: QgsPointXY
    cut_second: QgsPointXY
    connection: QgsGeometry
    tangent_distance: float
    radius: float = 0.0
    arc_center: Optional[QgsPointXY] = None


def cluster_approaches(
    half_edges: Iterable[CurbHalfEdge],
    angular_tolerance_degrees: float = 12.0,
) -> list[Approach]:
    """Cluster curb rays by road id and outward direction.

    Direction, rather than road id alone, is the essential branch identity.
    Consequently antipodal crossings of a through-road cannot collapse into
    one approach.  The wrap-around merge keeps directions close to 0/360
    degrees together.
    """
    tolerance = math.radians(angular_tolerance_degrees)
    if tolerance < 0.0 or tolerance >= math.pi / 2.0:
        raise ValueError("Angular tolerance must be in the range [0, 90) degrees")

    by_road: dict[Any, list[CurbHalfEdge]] = {}
    for edge in half_edges:
        by_road.setdefault(edge.road_id, []).append(edge)

    approaches: list[Approach] = []
    for road_id, road_edges in by_road.items():
        ordered = sorted(road_edges, key=lambda edge: edge.angle)
        clusters: list[list[CurbHalfEdge]] = []
        for edge in ordered:
            if not clusters:
                clusters.append([edge])
                continue
            current_angle = _angle(_mean_direction(clusters[-1]))
            if _angle_distance(edge.angle, current_angle) <= tolerance:
                clusters[-1].append(edge)
            else:
                clusters.append([edge])

        if len(clusters) > 1:
            first_angle = _angle(_mean_direction(clusters[0]))
            last_angle = _angle(_mean_direction(clusters[-1]))
            if _angle_distance(first_angle, last_angle) <= tolerance:
                clusters[0] = clusters[-1] + clusters[0]
                clusters.pop()

        road_clusters = sorted(
            ((_mean_direction(cluster), cluster) for cluster in clusters),
            key=lambda item: _angle(item[0]),
        )
        for branch_index, (direction, cluster) in enumerate(road_clusters):
            # A corner needs distinct sector-facing curbs.  Reusing a single
            # curb in both neighbouring sectors would produce conflicting
            # trim points and a guaranteed topology gap.
            if len(cluster) < 2:
                continue
            approaches.append(Approach(
                road_id=road_id,
                branch_index=branch_index,
                outward=direction,
                curbs=tuple(cluster),
            ))

    return sorted(approaches, key=lambda approach: approach.angle)


def sector_facing_pairs(
    approaches: Sequence[Approach], center: QgsPointXY
) -> list[tuple[CurbHalfEdge, CurbHalfEdge]]:
    """Return the two curbs facing every counter-clockwise approach sector."""
    if len(approaches) < 2:
        return []
    ordered = sorted(approaches, key=lambda approach: approach.angle)
    pairs: list[tuple[CurbHalfEdge, CurbHalfEdge]] = []
    for index, first in enumerate(ordered):
        second = ordered[(index + 1) % len(ordered)]
        directed_sweep = (second.angle - first.angle) % (2.0 * math.pi)
        # A straight/reflex gap is not a local road corner.  Solving its minor
        # angle would route the connection through an occupied approach.
        if directed_sweep >= math.pi - 1e-7:
            continue
        # The sector counter-clockwise from first to second faces the left
        # curb of first and the right curb of second.
        pairs.append((first.left_curb(center), second.right_curb(center)))
    return pairs


def support_line_intersection(
    first: CurbHalfEdge,
    second: CurbHalfEdge,
    parallel_tolerance: float = 1e-7,
) -> Optional[QgsPointXY]:
    """Intersect the infinite support lines of two curb half-edges safely."""
    direction_first = first.outward
    direction_second = second.outward
    denominator = _cross(direction_first, direction_second)
    if abs(denominator) <= parallel_tolerance:
        return None

    between = (
        second.cut_point.x() - first.cut_point.x(),
        second.cut_point.y() - first.cut_point.y(),
    )
    distance = _cross(between, direction_second) / denominator
    return QgsPointXY(
        first.cut_point.x() + distance * direction_first[0],
        first.cut_point.y() + distance * direction_first[1],
    )


def _outward_ray_from_intersection(
    edge: CurbHalfEdge, intersection: QgsPointXY
) -> Optional[tuple[float, float]]:
    # The virtual support intersection may fall on either side of the effect
    # circle (wide roads commonly put it outside).  Corner cutback must always
    # follow the road's retained/outward tangent; integration validates that
    # the resulting cut point lies on the available source geometry.
    return edge.outward


def solve_chamfer(
    first: CurbHalfEdge,
    second: CurbHalfEdge,
    distance: float,
    parallel_tolerance: float = 1e-7,
) -> Optional[CornerSolution]:
    """Create a straight chamfer with equal support-line cutback distances."""
    if distance <= 0.0:
        return None
    intersection = support_line_intersection(first, second, parallel_tolerance)
    if intersection is None:
        return None
    ray_first = _outward_ray_from_intersection(first, intersection)
    ray_second = _outward_ray_from_intersection(second, intersection)
    if ray_first is None or ray_second is None:
        return None

    cut_first = QgsPointXY(
        intersection.x() + ray_first[0] * distance,
        intersection.y() + ray_first[1] * distance,
    )
    cut_second = QgsPointXY(
        intersection.x() + ray_second[0] * distance,
        intersection.y() + ray_second[1] * distance,
    )
    connection = QgsGeometry.fromPolylineXY([cut_first, cut_second])
    return CornerSolution(
        mode="chamfer",
        first=first,
        second=second,
        support_intersection=intersection,
        cut_first=cut_first,
        cut_second=cut_second,
        connection=connection,
        tangent_distance=distance,
    )


def solve_fillet(
    first: CurbHalfEdge,
    second: CurbHalfEdge,
    radius: float,
    segments: int = 16,
    parallel_tolerance: float = 1e-7,
) -> Optional[CornerSolution]:
    """Create a tangent circular fillet at the true support-line intersection."""
    if radius <= 0.0 or segments < 2:
        return None
    intersection = support_line_intersection(first, second, parallel_tolerance)
    if intersection is None:
        return None
    ray_first = _outward_ray_from_intersection(first, intersection)
    ray_second = _outward_ray_from_intersection(second, intersection)
    if ray_first is None or ray_second is None:
        return None

    cosine = max(-1.0, min(1.0, _dot(ray_first, ray_second)))
    included_angle = math.acos(cosine)
    if included_angle <= 1e-7 or abs(math.pi - included_angle) <= 1e-7:
        return None

    tangent_distance = radius / math.tan(included_angle / 2.0)
    center_distance = radius / math.sin(included_angle / 2.0)
    bisector = _normalise((
        ray_first[0] + ray_second[0],
        ray_first[1] + ray_second[1],
    ))

    cut_first = QgsPointXY(
        intersection.x() + ray_first[0] * tangent_distance,
        intersection.y() + ray_first[1] * tangent_distance,
    )
    cut_second = QgsPointXY(
        intersection.x() + ray_second[0] * tangent_distance,
        intersection.y() + ray_second[1] * tangent_distance,
    )
    arc_center = QgsPointXY(
        intersection.x() + bisector[0] * center_distance,
        intersection.y() + bisector[1] * center_distance,
    )

    start_angle = math.atan2(
        cut_first.y() - arc_center.y(), cut_first.x() - arc_center.x()
    )
    end_angle = math.atan2(
        cut_second.y() - arc_center.y(), cut_second.x() - arc_center.x()
    )
    sweep = end_angle - start_angle
    while sweep > math.pi:
        sweep -= 2.0 * math.pi
    while sweep <= -math.pi:
        sweep += 2.0 * math.pi

    points = []
    for index in range(segments + 1):
        fraction = index / float(segments)
        angle = start_angle + sweep * fraction
        points.append(QgsPointXY(
            arc_center.x() + radius * math.cos(angle),
            arc_center.y() + radius * math.sin(angle),
        ))
    # Make topology exact at the source trim boundary, avoiding harmless
    # trigonometric round-off becoming a visible micro-gap.
    points[0] = QgsPointXY(cut_first)
    points[-1] = QgsPointXY(cut_second)

    return CornerSolution(
        mode="fillet",
        first=first,
        second=second,
        support_intersection=intersection,
        cut_first=cut_first,
        cut_second=cut_second,
        connection=QgsGeometry.fromPolylineXY(points),
        tangent_distance=tangent_distance,
        radius=radius,
        arc_center=arc_center,
    )


def solve_sector_corners(
    half_edges: Iterable[CurbHalfEdge],
    center: QgsPointXY,
    mode: str,
    value: float,
    angular_tolerance_degrees: float = 12.0,
    segments: int = 16,
) -> list[CornerSolution]:
    """Cluster, pair, and solve every valid sector in one deterministic call."""
    half_edges = tuple(half_edges)
    approaches = cluster_approaches(half_edges, angular_tolerance_degrees)
    boundary_radius = max(
        (center.distance(edge.cut_point) for edge in half_edges),
        default=0.0,
    )
    # Very shallow support angles can intersect hundreds of metres away from
    # a small effect circle.  Do not turn a local click into a remote edit.
    max_support_distance = max(
        boundary_radius * 4.0,
        boundary_radius + abs(value) * 4.0,
    )
    max_tangent_distance = max(
        boundary_radius * 2.0,
        abs(value) * 4.0,
    )
    solutions: list[CornerSolution] = []
    used_edges = set()
    for first, second in sector_facing_pairs(approaches, center):
        if mode == "chamfer":
            solution = solve_chamfer(first, second, value)
        elif mode == "fillet":
            solution = solve_fillet(first, second, value, segments)
        else:
            raise ValueError("Junction corner mode must be 'chamfer' or 'fillet'")
        if (
            solution is not None
            and center.distance(solution.support_intersection)
            <= max_support_distance
            and solution.tangent_distance <= max_tangent_distance
            and id(solution.first) not in used_edges
            and id(solution.second) not in used_edges
        ):
            solutions.append(solution)
            used_edges.add(id(solution.first))
            used_edges.add(id(solution.second))
    return solutions


__all__ = [
    "Approach",
    "CornerSolution",
    "CurbHalfEdge",
    "cluster_approaches",
    "sector_facing_pairs",
    "solve_chamfer",
    "solve_fillet",
    "solve_sector_corners",
    "support_line_intersection",
]
