# -*- coding: utf-8 -*-
"""planX CAD — the one ordered list of tools as the user sees them.

The dock, the command palette and the shortcut guide all read this, so a tool
has the same name, alias and group everywhere. Grouping follows AutoCAD's
Home ribbon (Draw / Modify / Transform); the dock folds those three into one
CAD tab so continuous drafting never switches category.

Pure Python: no Qt or QGIS imports.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolEntry:
    key: str        # internal tool key (main_plugin._ALL_TOOL_KEYS)
    label: str      # visible name
    alias: str      # primary command-line alias, shown as a badge
    section: str    # Draw | Modify | Transform | Measure | Urban
    icon: str       # file name in icons/
    hint: str = ""  # one-line prompt shown on the active-command card
    short: str = ""  # shorter name for the two-column grid; tooltip keeps the full one

    @property
    def grid_label(self) -> str:
        return self.short or self.label


TOOL_CATALOG = (
    # ── Draw ────────────────────────────────────────────────────────────
    ToolEntry("line", "Line", "L", "Draw", "cad_line.svg",
              "Click the start point, then the end point."),
    ToolEntry("polyline", "Polyline", "PL", "Draw", "cad_polyline.svg",
              "Click vertices; finish with right-click or Enter."),
    ToolEntry("rectangle", "Rectangle", "REC", "Draw", "cad_rectangle.svg",
              "Click two opposite corners."),
    ToolEntry("polygon", "Regular Polygon", "POL", "Draw", "cad_polygon.svg",
              "Click the centre, then a point that sets the radius and orientation.",
              short="Polygon"),
    ToolEntry("circle", "Circle", "C", "Draw", "cad_circle.svg",
              "Click the centre, then a point that sets the radius."),
    ToolEntry("arc", "Arc", "A", "Draw", "cad_arc.svg",
              "Click the start, an intermediate point, then the end."),
    ToolEntry("construction_inf", "Construction Line", "XL", "Draw",
              "cad_construction.svg", "Click two points to set an infinite axis.",
              short="XLine"),
    ToolEntry("construction_ray", "Construction Ray", "RAY", "Draw",
              "cad_construction_ray.svg", "Click the origin, then the direction.",
              short="Ray"),
    ToolEntry("construction_seg", "Construction Segment", "SEG", "Draw",
              "cad_construction_seg.svg", "Click the start and end of the reference.",
              short="Ref. Segment"),
    ToolEntry("divide", "Divide", "DIV", "Draw", "cad_divide.svg",
              "Pick the line to divide."),
    ToolEntry("hatch", "Hatch", "H", "Draw", "cad_hatch.svg",
              "Pick the closed area to fill."),
    ToolEntry("buffer", "Buffer", "B", "Draw", "cad_buffer.svg",
              "Pick the feature to buffer."),
    # ── Modify ──────────────────────────────────────────────────────────
    ToolEntry("offset", "Offset", "O", "Modify", "cad_offset.svg",
              "Pick the line or polygon, then click the side."),
    ToolEntry("multi_offset", "Multi-Offset", "MO", "Modify", "cad_multi_offset.svg",
              "Pick the line; an offset is made at every distance."),
    ToolEntry("trim", "Trim", "TR", "Modify", "cad_trim.svg",
              "Pick the cutting boundary, then the segment to remove."),
    ToolEntry("extend", "Extend", "EX", "Modify", "cad_extend.svg",
              "Pick the reference edge, then the line to extend."),
    ToolEntry("break", "Break", "BR", "Modify", "cad_break.svg",
              "Pick the line and a first point; a second point makes a gap, Enter breaks there."),
    ToolEntry("lengthen", "Lengthen", "LEN", "Modify", "cad_lengthen.svg",
              "Click the line near the end you want to change."),
    ToolEntry("fillet", "Fillet", "F", "Modify", "cad_fillet.svg",
              "Pick the first line, then the second."),
    ToolEntry("chamfer", "Chamfer", "CHA", "Modify", "cad_chamfer.svg",
              "Pick the two lines that form the corner."),
    ToolEntry("join", "Join", "J", "Modify", "cad_join.svg",
              "Pick the lines to join; Enter or right-click finishes."),
    ToolEntry("explode", "Explode", "X", "Modify", "cad_explode.svg",
              "Pick a multipart feature or a boundary."),
    ToolEntry("stretch", "Stretch", "S", "Modify", "cad_stretch.svg",
              "Drag a crossing window over vertices, then pick base and target points."),
    ToolEntry("vertex_edit", "Vertex Edit", "VE", "Modify", "cad_vertex_edit.svg",
              "Drag a handle to move it, right-click a handle to delete it, click the line to insert one."),
    # ── Transform ───────────────────────────────────────────────────────
    ToolEntry("move", "Move", "M", "Transform", "cad_move.svg",
              "Pick the feature, then click the target point."),
    ToolEntry("copy", "Copy", "CO", "Transform", "cad_copy.svg",
              "Pick the feature, then click the target point."),
    ToolEntry("rotate", "Rotate", "RO", "Transform", "cad_rotate.svg",
              "Pick the feature, click the reference direction, then the target angle. Ctrl snaps to 90°."),
    ToolEntry("scale", "Scale", "SC", "Transform", "cad_scale.svg",
              "Pick the feature, then click the reference distance and the target distance, or type a factor."),
    ToolEntry("mirror", "Mirror", "MI", "Transform", "cad_mirror.svg",
              "Pick the feature, then click both ends of the mirror axis."),
    ToolEntry("align", "Align", "AL", "Transform", "cad_align.svg",
              "Pick the feature, then source and destination point pairs."),
    ToolEntry("array", "Array", "AR", "Transform", "cad_array.svg",
              "Pick the feature; polar arrays then need a centre point."),
    # ── Measure ─────────────────────────────────────────────────────────
    ToolEntry("measure", "Distance", "DI", "Measure", "cad_measure.svg",
              "Click points; right-click finishes. Snap to endpoints for exact values."),
    ToolEntry("measure_area", "Area", "AA", "Measure", "cad_measure_area.svg",
              "Click the vertices; right-click finishes."),
    ToolEntry("dimension", "Dimension", "DIM", "Measure", "cad_dimension.svg",
              "Click the first point, then the second point."),
    ToolEntry("measure_select_line", "Selected Line", "MSL", "Measure",
              "cad_measure_select_line.svg", "Pick a line feature to read its length."),
    ToolEntry("measure_select_area", "Selected Area", "MSA", "Measure",
              "cad_measure_select_area.svg", "Pick a polygon to read its area and perimeter."),
    # ── Urban ───────────────────────────────────────────────────────────
    ToolEntry("road", "Draw Road", "ROAD", "Urban", "cad_road.svg",
              "Draw a clean centreline, then set up the platform."),
    ToolEntry("junction", "Junction", "JUNCTION", "Urban", "cad_junction.svg",
              "Set the junction radius, then click the junction centre."),
    ToolEntry("ada_kirma", "Block Chamfer", "BLOCK", "Urban", "cad_ada_kirma.svg",
              "Click each block corner to resolve; right-click finishes."),
    ToolEntry("envelope", "Buildable Envelope", "ENV", "Urban", "cad_envelope.svg",
              "Click a parcel near its front edge; setbacks come from the settings below."),
    ToolEntry("sight_triangle", "Sight Triangle", "SIGHT", "Urban", "cad_sight_triangle.svg",
              "Pick the curb line on each arm of the corner."),
    ToolEntry("parking", "Parking Layout", "PARK", "Urban", "cad_parking.svg",
              "Pick the curb line, then click the side for the stalls."),
    ToolEntry("roundabout", "Roundabout", "RB", "Urban", "cad_roundabout.svg",
              "Click the junction centre. Lines of the active layer get splitter islands."),
    ToolEntry("turning_head", "Turning Head", "CUL", "Urban", "cad_turning_head.svg",
              "Pick a road centreline near the end that needs a turning head."),
)

SECTIONS = ("Draw", "Modify", "Transform", "Measure", "Urban")

# Dock tabs: (tab id, visible title, sections shown on that tab).
TABS = (
    ("cad", "CAD", ("Draw", "Modify", "Transform")),
    ("measure", "Measure", ("Measure",)),
    ("urban", "Urban", ("Urban",)),
)

_BY_KEY = {entry.key: entry for entry in TOOL_CATALOG}


def tool_entry(key: str) -> ToolEntry | None:
    return _BY_KEY.get(key)


def tools_in_section(section: str) -> tuple:
    return tuple(entry for entry in TOOL_CATALOG if entry.section == section)


def tab_of(key: str) -> str | None:
    entry = _BY_KEY.get(key)
    if entry is None:
        return None
    for tab_id, _title, sections in TABS:
        if entry.section in sections:
            return tab_id
    return None


def section_of(key: str, default: str = "Modify") -> str:
    entry = _BY_KEY.get(key)
    return entry.section if entry else default


def match_tools(query: str) -> tuple:
    """Tools matching ``query`` by alias, name or key; best matches first."""
    q = (query or "").strip().lower()
    if not q:
        return ()
    scored = []
    for order, entry in enumerate(TOOL_CATALOG):
        alias = entry.alias.lower()
        label = entry.label.lower()
        if alias == q or entry.key == q:
            rank = 0
        elif alias.startswith(q):
            rank = 1
        elif label.startswith(q) or any(w.startswith(q) for w in label.split()):
            rank = 2
        elif q in label or q in entry.key:
            rank = 3
        else:
            continue
        scored.append((rank, order, entry))
    scored.sort(key=lambda item: (item[0], item[1]))
    return tuple(entry for _rank, _order, entry in scored)
