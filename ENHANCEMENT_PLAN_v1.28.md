# PlanX CAD Toolset — Enhancement Plan v1.28.0 ("Precision Drafting: OSNAP, Tracking & Dynamic Input")

**Audience:** an external implementation agent. Work through the phases IN ORDER.
**Repository:** `planX_CAD_arac_Seti/` inside the `qgis_plugins` monorepo.
**Current version:** 1.27.5 → **Target version:** 1.28.0 (single release at the end).
**Source:** formalizes items 1–3 of `ROADMAP.md`'s "Now" horizon — Object Snap
(OSNAP) engine, Ortho/Polar tracking, and Dynamic Input — into an
execution-ready plan. Item 4 of that horizon (core modify gap-fillers) already
shipped in 1.27.0; this plan does not touch it.

**Baseline facts (verified against the current tree, not ROADMAP.md's prose):**
- 39 tools total: ~27 files under `tools/*.py` (edit/modify/transform, one
  `QgsMapTool` subclass per file, based on `tools/tool_base.py`) plus 6 files
  under `sketcher/*.py` (draw tools: line, circle, arc, polygon, polyline,
  rectangle, based on `sketcher/sketcher_base.py`), plus urban road/junction
  tools under `urban/`.
- **Two independent base classes, two independent snap implementations.**
  `tools/tool_base.py::_snap_point()` and `sketcher/sketcher_base.py::_snap_point()`
  are separate, near-identical methods, each a thin wrapper:
  `self.canvas.snappingUtils().snapToMap(pos)` → one generic `QgsVertexMarker`
  (a plain circle) shown on any match, with no branching on `match.type()`.
  Neither file computes perpendicular, tangent, nearest, extension, or
  apparent-intersection points — QGIS's native `QgsPointLocator` gives vertex,
  edge, area, and centroid matches, and nothing more.
  **Any OSNAP work landing in only one of these two files silently leaves half
  the toolset on old-style snapping — both must be touched together.**
- `core/precision_input.py` already parses typed distance/angle/coordinate
  entry (`PrecisionInputError`, `looks_like_precision_input()`,
  `parse_precision_input()`, `resolve_precision_point()`) and both base
  classes already call into it from their command-line-driven
  `handle_precision_input()` — Phase 3 (dynamic input) extends this parser's
  reach onto the canvas itself, it does not replace it.
- `dialogs/cad_dock.py` holds the AutoCAD-style command line and
  `_COMMAND_ALIASES` dict (alias → canonical tool key); a new toggle command
  needs an entry here the same way every existing tool does.
  `dialogs/shortcut_help_dialog.py` and `dialogs/command_palette_dialog.py`
  are the other two places a new command's help text must be mirrored (this
  plugin's 3-place-consistency equivalent of suitability_lab's 4-place rule).
- Test suite: `tests/smoke_compat.py`, `tests/smoke_runtime.py`,
  `tests/smoke_geometry.py`, `tests/smoke_geometry_regressions.py`,
  `tests/smoke_junction_geometry.py`, `tests/smoke_modify_geometry.py`,
  `tests/smoke_precision_input.py`, `tests/smoke_urban_workbench.py`, plus 7
  `tests/test_*_pure.py` files run via `pf verify` (`tests_pure` in
  `plugins.toml`). No test file exercises snapping-marker type or
  tracking/dynamic-input behavior today — Phase 4 adds that coverage.
- Docs to keep in sync: `docs/command_reference.html`, `docs/shortcuts.html`,
  `docs/smoke_test_checklist.html`, `README.md`, `CHANGELOG.md` — this is the
  exact file set the 1.27.0 release (commit `9a1b4b2`) touched when it added
  six tools, and is the template for what "add a capability" touches here.

---

## 0. Non-negotiable ground rules (read before touching anything)

1. **Read `qgis_plugins/AGENTS.md` and `qgis_plugins/RELEASING.md` first.**
   LICENSE present, `experimental=False`, release via `release.ps1` are
   mandatory monorepo conventions.
2. **Pure QGIS API, zero new dependencies.** Everything in this plan is
   buildable with `qgis.core` / `qgis.gui` / `qgis.PyQt` and GDAL/OGR as
   shipped with QGIS (see ROADMAP.md's own API notes per item, reproduced in
   each phase below). If an approach needs a pip package, it does not belong
   in this plan.
3. **Keyboard-first.** Every new toggle/mode gets a command alias in
   `dialogs/cad_dock.py::_COMMAND_ALIASES`, fits the existing alias → tool-key
   → fuzzy-match loop, and honours empty-Enter-repeat where applicable.
4. **No literal `%` in `metadata.txt`** — breaks the QGIS Hub upload
   (configparser interpolation). `grep -n "%" metadata.txt` must return
   nothing before you finish.
5. **No self-praise wording** anywhere in user-facing copy: never "elite",
   "best", "ultimate", "world-class". Show quality; don't claim it.
6. **No AI attribution:** never add `Co-Authored-By:` (or any AI) trailers to
   commits.
7. **Never weaken an existing test, assertion, or count pin.** If a test
   asserts a tool count or shortcut count, the count may only go up. If a
   gate blocks you, fix the code, not the test. Any changed expectation must
   be justified in the report (Section R) — silent loosening invalidates the
   delivery.
8. **Global English workbench** — no bilingual runtime copy anywhere
   (matches this plugin's existing release gate).
9. **Screen-reader / accessibility parity for every new control** — this
   plugin's existing guiding principle (ROADMAP.md), not optional here: new
   markers, HUD text and tracking guides must have an accessible-name or
   status-bar equivalent, not rely on color/shape alone.
10. **Security scan:** run `bandit -r . -x tests,__pycache__` before
    declaring done; the QGIS Hub hard-blocks Critical findings.
11. **Do not bump the version or write the changelog until Phase 5. Do not
    tag, run `release.ps1`, or upload** — the maintainer releases manually
    after reviewing your report.
12. **Dual-runtime verification is mandatory**, not optional: every phase
    must be smoke-tested on both `python-qgis-ltr.bat` (QGIS 3.28 LTR / Qt5)
    and `python-qgis.bat` (QGIS 4.x / Qt6) before being marked done.
13. One commit per completed phase, messages like
    `phase-1: add OSNAP engine with typed markers`.

---

## Phase 1 — Object Snap (OSNAP) engine with typed markers

**What.** A running-snap layer above QGIS's native vertex/segment snapping:
endpoint, midpoint, centre, quadrant, node, intersection, apparent
intersection, **perpendicular**, **tangent**, **nearest**, and **extension**.
Each snap type gets its own marker glyph, and the tool's status message
(`tool_message` signal, already wired) reports which snap is currently
active.

**Why.** Perpendicular and tangent snaps, true midpoints, and true
intersections are daily CAD moves that native QGIS snapping does not expose
end-to-end today (native snapping gives the raw vertex/edge/area/centroid
matches; nothing currently classifies or displays *which* geometric relation
was found). This is the highest-value precision upgrade in the whole
ROADMAP.

**Design.**
- New module `core/osnap_engine.py`: given a `QgsPointLocator.Match` (from
  `canvas.snappingUtils().snapToMap(pos)`) plus the located layer/geometry,
  compute the richer snap set:
  - Endpoint / midpoint / vertex / centre / quadrant: derivable directly from
    the matched geometry's vertices and `QgsGeometry.centroid()` /
    bounding-circle math — no new QGIS API needed.
  - Perpendicular / tangent: given a reference point (the tool's last picked
    point, when one exists) and the located edge/circle, compute the foot of
    the perpendicular (`QgsGeometry.closestSegmentWithContext` on a
    constructed perpendicular line) or the tangent point (standard
    point-to-circle tangent construction) in plain geometry, no QGIS-specific
    trick required.
  - Extension: project the located edge's direction ray forward/backward and
    offer a snap point along it within a configurable tolerance.
  - Apparent intersection: intersect the two nearest located edges'
    infinite-line extensions when they don't physically cross within the
    tolerance window.
  - Returns a small `SnapResult(point, kind, layer)` dataclass; `kind` is one
    of a fixed `SnapKind` enum (endpoint, midpoint, centre, quadrant, node,
    intersection, apparent_intersection, perpendicular, tangent, nearest,
    extension).
- `core/osnap_markers.py`: one `QgsVertexMarker`-based glyph factory per
  `SnapKind` (reuse `QgsVertexMarker.IconType` where a built-in shape fits —
  e.g. `ICON_X` for intersection, `ICON_BOX` for nodes — and fall back to a
  small custom `QgsRubberBand` shape, e.g. a triangle for perpendicular, an
  arc for tangent, matching AutoCAD's familiar OSNAP glyph vocabulary in
  spirit, not pixel-for-pixel).
- **Both** `tools/tool_base.py::_snap_point()` and
  `sketcher/sketcher_base.py::_snap_point()` are replaced with a call into
  `core/osnap_engine.py`, and both classes' single generic `snap_marker` are
  replaced with the typed-marker factory. Do not add a third copy of this
  logic — if the duplication between the two base classes becomes awkward,
  factor the shared snapping/marker logic into a mixin under `core/` that
  both `tool_base` and `sketcher_base` compose, but do not change either
  class's existing public method names/signatures that tools already call.
- A dock toggle (`dialogs/cad_dock.py`) lets the user enable/disable
  individual snap kinds, persisted the same way other dock settings persist
  today (check the existing settings-persistence pattern in `cad_dock.py`
  before inventing a new one).

**API note.** `QgsSnappingUtils` / `QgsPointLocator` already give vertex,
edge, area, centroid and middle-of-segment; perpendicular, tangent,
intersection and extension are computed geometrically from the located edge
and drawn with `QgsVertexMarker` / `QgsRubberBand`. Pure API, confirmed
against the current `_snap_point()` implementations in both base classes.

---

## Phase 2 — Ortho & Polar tracking + alignment tracking lines

**What.** An **Ortho** toggle (constrain the rubber band to 0/90°) and
**Polar tracking** at configurable increments (15/30/45/…°), with a dashed
alignment guide (`QgsRubberBand` with a dashed pen) and a live
"polar: 12.30 m < 45°" readout via the existing `tool_message` signal.
Optional object-snap tracking: acquire a point (via Phase 1's OSNAP), then
track horizontal/vertical alignment from it.

**Why.** Direct-distance entry already exists via `core/precision_input.py`;
ortho/polar tracking is what makes it fast in practice — type a distance and
the direction is locked visually instead of needing a precise mouse angle.

**Design.**
- New module `core/tracking_engine.py`: given the tool's anchor point (last
  picked point) and the raw cursor map point, compute the constrained
  candidate point for the active mode (Ortho: snap to the nearest of
  0/90/180/270°; Polar: snap to the nearest configured increment; Object-snap
  tracking: snap to horizontal/vertical rays from a previously acquired
  OSNAP point).
- Both base classes' `canvasMoveEvent` (the method that currently calls
  `_snap_point`) route the OSNAP-adjusted point through the tracking engine
  before it becomes the tool's working point, and draw the dashed guide with
  a dedicated `QgsRubberBand` (separate from the existing preview rubber
  band, so toggling tracking on/off doesn't disturb the tool's own preview
  geometry).
- Ortho and Polar are mutually exclusive modes; both get command-line
  aliases (e.g. `ORTHO`, `POLAR`) in `_COMMAND_ALIASES`, toggled the same way
  other boolean dock settings toggle today, and a status-bar indicator so the
  active mode is announced for accessibility (ground rule 9).

**API note.** Constrain the candidate point in the tool's existing
`canvasMoveEvent`; draw guides with `QgsRubberBand`. No new dependencies.

---

## Phase 3 — Dynamic input (cursor heads-up display)

**What.** A small tooltip that follows the cursor showing live length/angle
(and Δx/Δy) while drawing, and accepts typed values inline — the AutoCAD
dynamic-input feel, complementing (not replacing) the existing dock command
line.

**Why.** Keeps the operator's eyes on the drawing instead of the dock; pairs
with Phases 1–2 to close the "heads-up drafting" loop the ROADMAP describes.

**Design.**
- New widget `dialogs/dynamic_input_hud.py`: a frameless follower widget (or
  a `QgsMapCanvasItem` if a canvas-native overlay proves smoother across both
  Qt5/Qt6 runtimes — decide based on a quick spike, not assumption, and
  record which was chosen and why in the report) positioned near the cursor,
  showing live length/angle/Δx/Δy computed from the tool's anchor point and
  the tracking-engine-adjusted candidate point from Phase 2.
- Typed input inside the HUD parses through the **existing**
  `core/precision_input.py` functions
  (`looks_like_precision_input`/`parse_precision_input`/`resolve_precision_point`)
  — do not write a second parser. The HUD is a second entry point into the
  same parsing/resolution path the dock command line already uses via
  `handle_precision_input()`.
- The HUD is additive: every tool must keep working with the HUD hidden
  (a dock toggle, default may be either state — decide and justify in the
  report) and with only the existing command-line precision input, so this
  phase cannot regress current keyboard-only workflows.

**API note.** A frameless follower widget or `QgsMapCanvasItem`; reuses the
existing `core/precision_input.py` parser. No new dependencies.

---

## Phase 4 — Regression coverage across every draw and modify tool

Phases 1–2 change behaviour inside both shared base classes, which every one
of the ~33 `tools/*.py` and `sketcher/*.py` subclasses inherits. This phase
exists so that claim is actually verified, not assumed.

- Extend `tests/smoke_geometry.py` / `tests/smoke_modify_geometry.py` (or add
  a new `tests/smoke_osnap_tracking.py`, whichever fits the existing file
  organization better — check before choosing) with: a snap-kind
  classification test per `SnapKind` against constructed fixture geometry,
  an Ortho/Polar candidate-point test for a matrix of anchor/cursor angles,
  and a dynamic-input parse-and-resolve round-trip test reusing
  `tests/smoke_precision_input.py`'s existing fixtures.
- Add a **pin test**: iterate every registered tool class (the same
  enumeration `main_plugin.py` uses to register actions) and assert each one
  still constructs and its `canvasMoveEvent`/`canvasPressEvent` still run
  end-to-end with OSNAP+tracking active, so a future change to either base
  class can't silently break one specific tool without a test noticing.
- Run the existing full suite unchanged (`tests/smoke_compat.py`,
  `smoke_runtime.py`, `smoke_junction_geometry.py`, `smoke_urban_workbench.py`,
  the 7 `test_*_pure.py` files) and confirm zero regressions — these already
  exercise the tools this phase's changes flow through.

---

## Phase 5 — Documentation, version bump, changelog

Only after Phases 1–4 are done and tested:
- Update `docs/command_reference.html` and `docs/shortcuts.html` with the new
  `ORTHO`/`POLAR` aliases and the OSNAP toggle commands (the same two files
  the 1.27.0 release updated for its six new tools).
- Update `docs/smoke_test_checklist.html` with the new manual QA steps for
  OSNAP glyphs, tracking guides, and the dynamic-input HUD.
- Update `README.md`'s feature list and `CHANGELOG.md` with a new
  `## [1.28.0]` entry describing the three features.
- Bump `metadata.txt`'s `version=1.28.0` and re-run
  `grep -n "%" metadata.txt` to confirm it is still empty.
- Do **not** tag, run `release.ps1`, or upload — stop after committing and
  hand the report to the maintainer.

---

## Known shortcomings register (fix or explicitly defer with reason)

| # | Shortcoming | Severity | Phase |
|---|---|---|---|
| S1 | `tool_base.py` and `sketcher_base.py` each have their own `_snap_point`; any future snapping change must touch both unless Phase 1 factors a shared mixin | High | 1 |
| S2 | No test today exercises snap-marker type, tracking-guide geometry, or dynamic-input parsing | High | 4 |
| S3 | Ortho/Polar and Object-Snap Tracking interact (tracking from an acquired OSNAP point while Polar is also active) — define and test the precedence rule explicitly, don't leave it implicit | Medium | 2 |
| S4 | Accessibility: new markers/HUD/tracking guides must not rely on color alone (ground rule 9) — verify with a screen-reader pass, not just a visual check | Medium | 1–3 |
| S5 | `plugins.toml`'s `tests_qgis` entry references `-m planX_CAD_arac_Seti.tests.smoke_plugin`, but no `tests/smoke_plugin.py` file exists in the current tree — flag this to the maintainer in your report (out of this plan's scope to fix, but worth surfacing since it means the QGIS-runtime gate may be pointing at a stale/renamed module) | Low | — |
| S6 | Dynamic-input HUD implementation choice (frameless widget vs. `QgsMapCanvasItem`) affects Qt5/Qt6 rendering parity — the report must state which was chosen, why, and confirm both runtimes render it correctly | Medium | 3 |

---

## R. Required response format (your report back to the reviewer)

Deliver a single file `REPORT_v1.28.md` in the plugin root:

```markdown
# Implementation Report v1.28.0
## 1. Phase status
Phase 1: DONE|PARTIAL — <one line>
... (all 5 phases)
## 2. Shortcomings register outcomes
S1: FIXED|DEFERRED — <evidence>
... (S1–S6, plus any NEW shortcomings discovered, numbered S7+)
## 3. Tool coverage table
| tool file (tools/ or sketcher/) | OSNAP kinds verified | Ortho/Polar verified | Dynamic input verified |
(one row per tool file touched by the shared base classes)
## 4. Test evidence
### 4.1 pure test output (verbatim, complete)
### 4.2 e2e QGIS 3.28 LTR output (verbatim, complete)
### 4.3 e2e QGIS 4.x output (verbatim, complete)
## 5. Gate outputs
bandit / `%`-in-metadata grep (verbatim)
## 6. Changed-test justifications
(empty if none; otherwise every test whose expectation changed, old vs new, why)
## 7. Deviations from this plan
(every place you did something differently and why, including the S6 HUD
implementation choice)
## 8. Commit list
(hash + message, one per line)
```

**Honesty over completeness:** a PARTIAL with truthful evidence is
acceptable; a DONE that the reviewer's re-run contradicts invalidates the
delivery.
