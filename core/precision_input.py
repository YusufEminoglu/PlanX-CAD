# -*- coding: utf-8 -*-
"""Parse and resolve AutoCAD-style precision point input."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from qgis.core import QgsPointXY

from .crs_utils import local_metric_crs, transform_point


_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_CARTESIAN = re.compile(
    rf"^(?P<relative>@)?\s*(?P<x>{_NUMBER})\s*,\s*(?P<y>{_NUMBER})$"
)
_POLAR = re.compile(
    rf"^@\s*(?P<distance>{_NUMBER})\s*<\s*(?P<angle>{_NUMBER})\s*°?$"
)
_SCALAR = re.compile(rf"^(?P<distance>{_NUMBER})$")


class PrecisionInputError(ValueError):
    """Raised when numeric-looking input is invalid for precision drafting."""


@dataclass(frozen=True)
class PrecisionInput:
    kind: str
    first: float
    second: float | None = None


def looks_like_precision_input(text: str) -> bool:
    """Return whether ``text`` should be consumed as numeric CAD input."""
    token = (text or "").strip()
    return bool(token) and token[0] in "@+-.0123456789"


def _finite(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise PrecisionInputError("Coordinate and distance values must be finite")
    return number


def parse_precision_input(text: str) -> PrecisionInput:
    """Parse absolute, relative Cartesian, relative polar, or scalar input."""
    token = (text or "").strip()
    match = _CARTESIAN.fullmatch(token)
    if match:
        return PrecisionInput(
            "relative_cartesian" if match.group("relative") else "absolute",
            _finite(match.group("x")),
            _finite(match.group("y")),
        )

    match = _POLAR.fullmatch(token)
    if match:
        distance = _finite(match.group("distance"))
        if distance <= 0.0:
            raise PrecisionInputError("Polar distance must be greater than zero")
        return PrecisionInput(
            "relative_polar",
            distance,
            _finite(match.group("angle")),
        )

    match = _SCALAR.fullmatch(token)
    if match:
        distance = _finite(match.group("distance"))
        if distance <= 0.0:
            raise PrecisionInputError("Direct distance must be greater than zero")
        return PrecisionInput("direct_distance", distance)

    raise PrecisionInputError(
        "Use x,y; @dx,dy; @distance<angle; or a positive distance"
    )


def resolve_precision_point(
    parsed: PrecisionInput,
    base_point: QgsPointXY | None,
    cursor_point: QgsPointXY | None,
    canvas_crs,
) -> QgsPointXY:
    """Resolve parsed input to canvas CRS; relative distances are metres."""
    if parsed.kind == "absolute":
        return QgsPointXY(parsed.first, parsed.second)
    if base_point is None:
        raise PrecisionInputError(
            "A relative point needs an existing base/last vertex"
        )

    base_point = QgsPointXY(base_point)
    metric_crs = local_metric_crs(base_point, canvas_crs)
    metric_base = transform_point(base_point, canvas_crs, metric_crs)

    if parsed.kind == "relative_cartesian":
        metric_target = QgsPointXY(
            metric_base.x() + parsed.first,
            metric_base.y() + parsed.second,
        )
    elif parsed.kind == "relative_polar":
        angle = math.radians(parsed.second)
        metric_target = QgsPointXY(
            metric_base.x() + parsed.first * math.cos(angle),
            metric_base.y() + parsed.first * math.sin(angle),
        )
    elif parsed.kind == "direct_distance":
        if cursor_point is None:
            raise PrecisionInputError(
                "Move the cursor to define a bearing before entering distance"
            )
        metric_cursor = transform_point(cursor_point, canvas_crs, metric_crs)
        dx = metric_cursor.x() - metric_base.x()
        dy = metric_cursor.y() - metric_base.y()
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise PrecisionInputError(
                "Cursor bearing is undefined at the base point"
            )
        metric_target = QgsPointXY(
            metric_base.x() + parsed.first * dx / length,
            metric_base.y() + parsed.first * dy / length,
        )
    else:
        raise PrecisionInputError(f"Unsupported precision input: {parsed.kind}")

    return transform_point(metric_target, metric_crs, canvas_crs)


__all__ = [
    "PrecisionInput",
    "PrecisionInputError",
    "looks_like_precision_input",
    "parse_precision_input",
    "resolve_precision_point",
]
