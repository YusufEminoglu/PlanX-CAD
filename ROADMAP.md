# PlanX CAD Toolset — Roadmap

> **Status: living plan.** Item 4 shipped in 1.27.0; everything else is still a
> menu of where the toolset *could* go, ordered by impact and fit, so items can
> be accepted, rejected, reshuffled, or refined before they are built.
>
> **Reviewed:** 2026-07-29 · **Current release:** 1.27.0 · **Baseline:** 39 tools,
> AutoCAD-style command line with precision input, urban road/junction tools,
> dual-runtime (QGIS 3.28 LTR ↔ QGIS 4), accessible, zero dependencies.

---

## Guiding principles

Every item on this roadmap must respect the five things that already define the
plugin. If a proposal cannot be built inside these lines, it does not belong here.

1. **Pure QGIS API.** No external dependencies, no build step. If it can't be done
   with `qgis.core` / `qgis.gui` / `qgis.PyQt` (and GDAL/OGR that ship with QGIS),
   it is out of scope.
2. **Keyboard-first.** Every new tool gets a command alias, fits the command-line
   loop (alias → tool key → fuzzy match), and honours empty-Enter-repeat.
3. **Built for planners.** We prefer tools a city planner reaches for weekly over
   generic CAD completeness for its own sake.
4. **Global English workbench.** One consistent English interface; no bilingual
   runtime copy (the release gate enforces this).
5. **Verified before release.** Dual-runtime smoke coverage (QGIS 3 LTR/Qt5 and
   QGIS 4/Qt6), screen-reader parity for every new control, clean Hub security scan.

---

## How to read this

Items are grouped into three honest horizons — **Now / Next / Later** — instead of
hard dates. Version bands are *indicative* only; scope decides the number, not the
calendar. Each item states **what it is**, **why a planner wants it**, and a short
**API note** proving it is buildable with pure QGIS.

---

## Non-goals (so we don't rebuild the ecosystem)

The toolset adds **CAD-level primitives**. Heavier, domain-complete workflows stay
with their dedicated siblings, and we integrate rather than duplicate:

| Out of scope here | Belongs to |
|---|---|
| Full parcel subdivision, frontage rules, yield analysis | **ParcelFlux** |
| Publication cartography, print layouts, title blocks, legends | **CartoLab** |
| Master-plan / settlement-plan automation | **UIP Toolset**, **Settlement Toolset** |
| 3D massing, extrusion, city viewers | **planx_3d_city**, **osm_quick_3d** |
| Spatial statistics, MCDA, data cubes | **GeoStats / Suitability / DataCube** |

Where a CAD primitive overlaps (e.g. "split a polygon by a line"), we ship only the
low-level drafting operation and leave the full workflow to the sibling plugin.

---

## Now — Drafting precision (indicative: 1.28 – 1.30)

The single biggest "this finally feels like real CAD" gap is **precision picking and
constrained drawing**. These four items upgrade *every existing draw and modify tool
at once*, so they come first.

### 1. Object Snap (OSNAP) engine with typed markers
- **What.** A running-snap layer above QGIS's native vertex/segment snapping:
  endpoint, midpoint, centre, quadrant, node, intersection, *apparent* intersection,
  **perpendicular**, **tangent**, **nearest**, and **extension**. Each snap type gets
  its own marker glyph, and a status hint shows which snap is active.
- **Why.** Perpendicular and tangent snaps, midpoints, and true intersections are
  daily CAD moves that native QGIS snapping does not expose. This is the highest-value
  precision upgrade in the whole plan.
- **API note.** `QgsSnappingUtils` / `QgsPointLocator` already give vertex, edge,
  area, centroid and middle-of-segment; perpendicular, tangent, intersection and
  extension are computed geometrically from the located edge and drawn with
  `QgsVertexMarker`. Pure API.

### 2. Ortho & Polar tracking + alignment tracking lines
- **What.** An **Ortho** toggle (constrain the rubber band to 0/90°) and **Polar
  tracking** at configurable increments (15/30/45/…°), with a dashed alignment guide
  and a live "polar: 12.30 m < 45°" readout. Optional object-snap tracking: acquire a
  point, then track horizontal/vertical alignment from it.
- **Why.** Direct-distance entry already exists; ortho/polar tracking is what makes it
  fast — type a distance and the direction is locked visually. Core drafting ergonomics.
- **API note.** Constrain the candidate point in the tool's `canvasMoveEvent`; draw
  guides with `QgsRubberBand`. No new dependencies.

### 3. Dynamic input (cursor heads-up display)
- **What.** A small tooltip that follows the cursor showing live length/angle (and
  Δx/Δy) while drawing, and accepts typed values inline — the AutoCAD dynamic-input feel,
  complementing (not replacing) the dock command line.
- **Why.** Keeps the operator's eyes on the drawing instead of the dock; pairs with
  OSNAP and polar tracking to close the "heads-up drafting" loop.
- **API note.** A frameless follower widget or `QgsMapCanvasItem`; reuses the existing
  `core/precision_input.py` parser.

### 4. Core modify gap-fillers — ✅ **shipped in 1.27.0**
The modify set was missing several commands every AutoCAD user expects. All six
shipped together:
- **Chamfer (standalone)** `CHA` — distance-distance corner cut, live hover
  preview, both lines auto-trimmed. ✅
- **Stretch** `S` — crossing-window stretch across every editable layer. ✅
- **Break / Break-at-point** `BR` — split a line, optionally with a gap. ✅
- **Lengthen** `LEN` — extend/shorten by delta, percentage, or total length. ✅
- **Align** `AL` — move+rotate(+scale) by source→destination point pairs. ✅
- **Explode** `X` — multipart → single parts; line/polygon boundary → segments. ✅
- **API note.** All are `QgsGeometry` operations on the existing `tool_base.py`
  pick/commit scaffold; each ships with a command alias and dual-runtime smoke test.
- *Deferred:* distance-angle chamfer mode (only distance-distance shipped).

---

## Next — Production & interchange (indicative: 1.30 – 1.33)

Once drawing is precise, the value shifts to **getting drawings out, annotated, and
standardised** — the parts that matter when a plan leaves your screen.

### 5. DXF / DWG interoperability
- **What.** One-click **DXF export** of the current drawing with sensible QGIS-layer →
  CAD-layer mapping, and a guided **DXF import** that lands CAD layers as tidy,
  styled QGIS layers. Round-trip with municipal/architectural CAD.
- **Why.** Most municipalities and architects still exchange in DWG/DXF. This is the
  most requested practical bridge and it reinforces the plugin's promise — CAD work
  *without leaving QGIS*.
- **API note.** `QgsDxfExport` is a built-in QGIS class (layer mapping, symbology,
  dimensions); import via the OGR DXF driver. No third-party CAD library needed.

### 6. Annotation & dimensioning suite
- **What.** Grow the single linear dimension into a real dim set: **aligned**,
  **angular**, **radial/diameter**, **baseline** and **continuous (chain)** dimensions,
  **ordinate / setting-out** dimensions (N/E from a datum), **leaders with text**,
  **multiline text (mtext)**, and a lightweight **dimension style** (arrow size, text
  height, unit precision). Plus auto **area/label tags** for polygons.
- **Why.** Dimensioned, annotated drawings are the deliverable in planning practice;
  ordinate/setting-out output is what surveyors and site engineers ask for.
- **API note.** Managed vector layers + the label engine + geometry-built arrowheads;
  styles stored in project/settings. Pure API.

### 7. Blocks & symbols library
- **What.** An insertable library of reusable planning symbols — trees/vegetation,
  street furniture, parking bays, vehicles, people (for scale), north arrows — placed
  at a point with scale and rotation, plus a "define block from selection" option.
- **Why.** Planners stamp the same symbols constantly; today that means hand-drawing
  or hunting for symbology. A curated set is a real time-saver.
- **API note.** Point layer + `QgsSvgMarkerSymbolLayer` (SVGs ship with the plugin), or
  geometry stamps for real-world-scaled blocks. Pure API.

### 8. Boundary from pick-point
- **What.** Click *inside* an area enclosed by existing lines and auto-build the closed
  polygon (region), so **Hatch** and area tools work on any enclosed space, not only on
  a pre-existing polygon feature.
- **Why.** Removes the biggest friction in hatching and area take-offs — you rarely
  have the closed polygon handy; you have the linework around it.
- **API note.** `QgsGeometry.polygonize()` over nearby lines, then select the polygon
  containing the click point. Pure API.

### 9. CAD layer standard / drawing setup
- **What.** A "New CAD drawing" action that creates a **standard, pre-styled layer
  stack** in one click — axis, curb, buildings, parcels, dimensions, hatch, text,
  construction — following a planning drawing standard, with a save/load template.
- **Why.** Consistent layer naming and styles across projects and teams; today the
  helper layers (`planx_hatch`, `planx_dimensions`, …) are created ad hoc.
- **API note.** Programmatic layer creation + `.qml`/`.qlr` styles bundled with the
  plugin. Pure API.

---

## Later — Planner power tools (indicative: 1.34+, candidate 2.0)

Differentiators that lean into "CAD *for urban planning*" — the things generic CAD
plugins don't do. Bigger scope; sequence after the fundamentals land.

### 10. Buildable envelope from setbacks
- **What.** Select a parcel, enter front/side/rear setbacks (and optional corner
  splay), and generate the **buildable envelope** polygon; optional max-footprint area
  readout for a target coverage ratio.
- **Why.** A core planning check done by hand thousands of times. High-value, distinctly
  "planning CAD."
- **API note.** Per-edge inward offset / negative buffer intersection on `QgsGeometry`.

### 11. Urban geometry expansion
- **What.** **Roundabout generator** (central island + splitter islands per leg),
  **cul-de-sac / turning-head** templates, **parking-layout generator** (bays along a
  line: count, angle, module), **corner sight triangles / visibility splays**, and a
  **cross-section template library** for the existing Road Platform generator
  (save/load named sections).
- **Why.** Extends the plugin's real differentiator (road/junction tooling) into the
  next set of everyday street-design tasks.
- **API note.** Parametric geometry construction on the existing urban scaffold.

### 12. COGO — bearing & distance entry
- **What.** Survey-style **traverse input**: enter a start point then a sequence of
  bearing/azimuth + distance legs to plot deeds/boundaries; point-by-intersection
  (bearing-bearing, bearing-distance).
- **Why.** Cadastral and boundary work is described in bearings and distances; typing
  a traverse is far faster and exact than clicking.
- **API note.** Parse legs → build polyline in the metric work CRS; reuses precision-input
  plumbing.

### 13. Split polygon by line / by area (CAD primitive)
- **What.** Cut a polygon with a drawn line, or divide it into parts of a **target
  area** (equal or specified). The drafting primitive only — full subdivision workflows
  stay in ParcelFlux.
- **Why.** Quick, exact cuts during drafting without leaving the CAD dock.
- **API note.** `QgsGeometry.splitGeometry`; area targeting by iterative offset/search.

### 14. UCS — local origin & rotation
- **What.** Set a **user coordinate system**: a local origin and rotation so you can
  draft a rotated site "square to the screen," with ortho/polar and coordinate readout
  following the UCS.
- **Why.** Sites are rarely aligned to grid north; drafting in the site's own frame is a
  major precision and speed win.
- **API note.** Affine transform applied to input/display; store origin+angle in project.

### 15. Grips editing
- **What.** Select a feature to show draggable grips (endpoints, midpoints, centre);
  drag to stretch/move, with a grip menu for rotate/scale/mirror — a superset of the
  current Vertex Edit.
- **Why.** The fastest, most familiar CAD editing gesture; no dialog, no tool switch.
- **API note.** Canvas grip items + drag handling; extends `tool_vertex_edit.py`.

### 16. Draw-tool additions
- **What.** **Ellipse / elliptical arc**, **spline** (through/control points),
  **revision cloud** (review markups), **double line / parallel line** (walls, road
  edges), **point / node** with styles, **donut/ring**.
- **Why.** Rounds out the drawing palette; revision clouds and double-lines are
  especially useful in plan review and street sections.
- **API note.** Geometry construction on the existing sketcher base.

### 17. Workflow modernisation
- **What.** A persistent **tool-options bar** for the active tool (retire the modal
  `QInputDialog` prompts in favour of an always-visible options panel / dynamic-input
  options), plus **selection sets**, **quick-select by attribute/type**, and
  **crossing/window selection** semantics so modify tools can act on many features.
- **Why.** Modal dialogs interrupt the drafting flow; batch selection is table stakes
  for editing at scale.
- **API note.** Dock/panel widgets + selection handling on `tool_base.py`.

---

## Cross-cutting (continuous, not a phase)

Carried through every release, not scheduled separately:

- **Performance.** Spatial-index-backed picking and snapping so OSNAP and modify tools
  stay responsive on large layers.
- **Accessibility parity.** Every new dialog/panel exposes `accessibleName` /
  `accessibleDescription` and keyboard focus, matching today's standard.
- **Test coverage.** Each new tool ships with dual-runtime smoke coverage (QGIS 3
  LTR/Qt5 + QGIS 4/Qt6) and a static `smoke_compat.py` assertion where it applies.
- **Docs in sync.** Command reference, shortcut map, and README updated in the same PR
  as the feature — never after.
- **Hub-clean.** Every release passes the Bandit/secrets/Flake8 security scan and the
  Qt6 enum static check before upload.

---

## If we only ship five things

Ranked by impact × fit × effort, the shortlist that would move the needle most:

1. **OSNAP engine** (#1) — precision that lifts every existing tool.
2. **DXF/DWG interoperability** (#5) — the most-requested practical bridge; low risk
   (`QgsDxfExport` is built in).
3. **Ortho/Polar tracking + dynamic input** (#2, #3) — fast, heads-up drafting.
4. **Annotation & dimensioning suite** (#6) — turns drawings into deliverables.
5. **Buildable envelope from setbacks** (#10) — the standout "planning CAD" tool.

---

## Open questions (decide before we start)

- **Version framing.** ~~2.0 headline or steady 1.x?~~ **Settled for now:** the
  modify gap-fillers shipped as 1.27.0, keeping the 1.x cadence. Revisit if the
  OSNAP + tracking work lands as one large release.
- **DXF priority.** Is DWG/DXF interchange urgent enough to pull forward *ahead* of the
  OSNAP work? (It's independent and low-risk, so it could go first.)
- **Symbol library scope.** Which symbol sets matter most for your teaching/practice
  context (vegetation, furniture, parking, vehicles, people, north arrows)?
- **Sibling boundaries.** Are the split-by-line/area and setback-envelope primitives
  comfortably clear of ParcelFlux, or should they defer to it entirely?
```
