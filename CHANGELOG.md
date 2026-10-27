# Changelog

## [1.29.1] - 2026-10-27

Dock polish after the first desktop test, and the Hub name everywhere.

### Changed
- **Alias badges sit next to the tool name**: each tool row shows its command alias as a small badge right after the name, instead of at the far edge of a wide column.
- **PlanX colours** for the dock in light and dark themes: slate text, one teal accent, a paper-coloured command card. The layer bar is left-aligned and turns amber with "read-only, click to edit" when the active layer cannot be edited. Coordinates, CRS and scale take one line and follow the theme.
- **CAD Drafting Toolset** is the name in the dock, menu, toolbar, panel action and dialog titles, matching the QGIS Hub. The About box lists the tools straight from the tool catalogue.
- The reference manual is published at https://geophilo.com/planX_CAD_arac_Seti/manual.html and is no longer part of the repository or the plugin package.

### Removed
- The developer smoke-test checklist: its menu item, the Ctrl+Alt+M shortcut, the Docs tab and the health-audit entry.

## [1.29.0] - 2026-10-27

A redesigned dock: three tabs, labelled tools, settings inline, drafting aids always visible.

### Changed
- **Dock layout**: the tools now sit in three tabs, *CAD* (Draw, Modify, Transform as foldable sections in a two-column grid), *Measure* and *Urban*, so continuous drafting never switches tabs. Every tool shows its name and command alias. The grid drops to one column, then to icons, in a narrow dock.
- **Regrouped tools** following AutoCAD's Home ribbon: construction lines, Divide, Hatch and Buffer moved to Draw; Align and Array moved to Transform. The old 20-tool "Editing" group is gone. The command palette and shortcut guide use the same groups (Move, Copy and the other transform tools were listed as "Editing" there).
- **Typing in the command line searches every tab**, ranked by alias, then name.
- **Quick strip** replaces the Recent and Favorites rows, the Pin button and the Clear button: pinned tools first, then recent ones; right-click any tool to pin or unpin it.
- **"⋯" menu** holds the command reference, shortcut guide, quick start, layer check, health check, diagnostics, usage statistics, shortcut conflicts and workspace reset, which were 12 coloured buttons.
- **Status bar**: the active layer (click to start or stop editing) and OSNAP / ORTHO / POLAR / DYN toggles.

### Added
- **Five street and parcel design tools** on the Urban tab, each writing to its own managed layer:
  - **Buildable Envelope** (`ENV`): parcel minus front / side / rear setbacks, with a corner-parcel option, exact for concave parcels; records parcel and envelope area, buildable share and the max footprint under a site-coverage limit.
  - **Sight Triangle** (`SIGHT`): corner visibility triangle from the curb intersection, or the virtual intersection at a rounded corner.
  - **Parking Layout** (`PARK`): numbered 90° / 60° / 45° / 30° / parallel stalls along a curb line with a live side preview; no overlaps at bends.
  - **Roundabout** (`RB`): circulatory carriageway, truck apron and central island, plus splitter islands on the active layer's approach lines.
  - **Turning Head** (`CUL`): cul-de-sac turning circle with tapers at a road end.
- **Inline tool settings**: Offset, Multi-Offset, Fillet, Chamfer, Buffer, Array, Divide, Explode, Hatch, Join, Lengthen and Align show their settings on the dock's active-command card and skip their modal dialog while the dock is open. Values are remembered per tool between sessions; without the dock the dialogs still open.
- Distinct icons for Construction Ray and Construction Segment (all three construction tools shared one icon).
- Dock icons are recoloured on dark QGIS themes, where the navy strokes were nearly invisible.

### Fixed
- **Drafting aids are now session-wide.** ORTHO, POLAR, OSNAP and DYN were stored per tool instance, so turning ORTHO on in Line was lost in Polyline, and F3 / F8 / F10 / F12 with no tool active reported a toggle but changed nothing. The state is shared, shown on the dock chips, and remembered between sessions.
- Join remembers its tolerance instead of resetting to 1.0 m every time.
- The Array dialog showed garbled labels ("Î”x") instead of "Δx" / "Δy".

## [1.28.0] - 2026-10-25

Precision Drafting: AutoCAD-grade Object Snap (OSNAP), Ortho and Polar tracking, and Dynamic Input HUD.

### Added
- **Precision Drafting Workbench**: Unified controller (DraftingWorkbench) coordinating Object Snap (OSNAP), Ortho and Polar tracking, guide rays, and Dynamic Input HUD across both `tool_base` and `sketcher_base`.
- **AutoCAD-grade Object Snap (OSNAP)** (F3, OSNAP): 11 geometric snap modes (Endpoint, Midpoint, Centre, Quadrant, Vertex, Intersection, Apparent Intersection, Perpendicular, Tangent, Nearest, Extension) with AutoCAD-standard typed glyph markers (Box, Triangle, Circle, Diamond, Cross, X, Inverted Triangle, Tangent, Hourglass) and screen-reader status announcements.
- **Ortho & Polar Tracking Engine**: F8 / ORTHO constrains movement to 0 deg, 90 deg, 180 deg, 270 deg with live dashed guide rays. F10 / POLAR tracks configurable rays (15 deg, 30 deg, 45 deg, 90 deg). Object Snap Tracking allows acquiring points by hovering, with alignment rays taking precedence (S3 rule).
- **Dynamic Input HUD** (F12, DYN): Floating cursor overlay rendering live distance, angle, and delta coordinates in a high-contrast translucent dark slate pill with teal accent.
- **Shortcuts & Aliases**: Application-wide shortcuts F3, F8, F10, F12 and command-line aliases OSNAP, ORTHO, POLAR, DYN.
- **Comprehensive Test Suite**: Added pure pytest suite `tests/test_drafting_pure.py` (17 tests) and unified QGIS test runner `tests/smoke_plugin.py` running all 8 QGIS suites on both QGIS 3 LTR and QGIS 4.

## [1.27.6] - 2026-09-16

- Redesign plugin icon to high-end 3D tactile brand design with circular teal pedestal, zero margin, and refreshed documentation links.

## [1.27.5] - 2026-09-06

- Migrate repository and documentation URLs to GitLab and Cloudflare Pages.

## [1.27.4] - 2026-08-07

- Added online user manual link (https://yusufeminoglu.github.io/PlanX-CAD/) and GitHub repository star call-to-action.

## [1.27.3] - 2026-08-07

- Expand reference manual 3x with theory, math, 8 DOI refs

## [1.27.2] - 2026-08-07

- Add floating Save as PDF button to reference manual

## [1.27.1] - 2026-08-07

- Add comprehensive academic reference manual

## [1.27.0] - 2026-07-29

Core modify gap-fillers: the six commands every AutoCAD user reaches for, now
native to the CAD dock. The toolset grows from 33 to 39 tools.

### Added
- **Chamfer** (`CHA`) — straight distance-distance corner cut between two lines. Enter both cutbacks (or tick *equal distances*), pick the two lines, and the tool trims both to the corner and adds the chamfer segment, all in one undo step. A live dashed hover preview shows the cut before you commit, and a cutback longer than the retained leg is rejected instead of corrupting the source line. Distances stay metre-accurate in geographic projects.
- **Break** (`BR`) — split a line at a picked point, or remove the span between two picked points. Enter or right-click after the first point breaks there with no gap. The picked feature keeps the first part; the remainder is added with the same attributes. Intermediate polyline vertices survive the split, and a break on an endpoint is refused.
- **Lengthen** (`LEN`) — change a line by delta, percent, or total length. The end you click is the end that moves, extension follows the terminal segment direction, and shortening trims cleanly through intermediate vertices.
- **Align** (`AL`) — move and rotate a feature onto source/destination point pairs, with optional scaling by the pair length ratio. Enter after the first pair moves without rotating. Curves and Z/M values survive because the whole operation is a single affine transform.
- **Stretch** (`S`) — drag a crossing window, pick a base and target point, and only the vertices inside the window move. Every editable layer crossing the window is stretched in one pass, and polygon rings stay closed.
- **Explode** (`X`) — split a multipart feature into single parts, or a line/polygon boundary into single segments. Polygon segments (including interior rings) are written to a managed `planx_explode` line layer, and removing the source feature is optional.
- All six commands join the command line, the command palette, the shortcut guide, the tool hints, and the in-app command reference.

### Changed
- `CHAMFER` and `CHA` now start the general two-line Chamfer tool, matching AutoCAD. The urban Block Chamfer keeps its own `BLOCK` and `BLOCKCHAMFER` aliases.
- The command palette alias for Extend changed from `lengthen` to `extend to boundary`, so it no longer collides with the new Lengthen command.

### Compatibility
- Managed memory layers now declare their schema in the provider URI instead of building `QgsField` objects, removing the last `QVariant` usage from the plugin. PyQt6 dropped `QVariant.Type`, and the Hub's Qt6 checker flags `QVariant` regardless, while the `QgsField(QMetaType)` alternative would have required QGIS 3.38 and broken the 3.28 floor.

### Quality
- New `tests/smoke_modify_geometry.py`: 21 geometry checks for the chamfer, break, lengthen, align, stretch, and explode helpers, verified on QGIS 3.44 LTR and QGIS 4.2.
- `tests/smoke_runtime.py` grew from 20 to 30 checks, including layer-write verification for each new tool (edit commands, part creation, and managed output layers) and a guarantee that every registered tool key has a dock button.
- `tests/smoke_compat.py` now enforces that every command alias resolves to a real tool key, so a future rename cannot leave an alias silently dead.

## [1.26.2] - 2026-07-15

- Revert author spelling to Yusuf Eminoglu

## [1.26.1] - 2026-07-13

- Plugin Hub compatibility and security-scan maintenance release; no functional changes.

### Compatibility
- Scoped every QGIS enum access for Qt6 / QGIS 4: geometry types now resolve through `QgsWkbTypes.GeometryType.*`, and vertex and rubber-band markers through `QgsVertexMarker.IconType.*` and `QgsRubberBand.IconType.*`. This clears all 90 Qt6 enum-compatibility warnings while staying compatible with QGIS 3.28 LTR.

### Quality
- Replaced defensive `try/except: pass` wrappers with `contextlib.suppress`, resolving the Plugin Hub Bandit security-scan findings that blocked 1.26.0. The same best-effort operations remain guarded, with no change in behavior.

## [1.26.0] - 2026-07-13

- Target release: PlanX CAD Toolset 1.26.0 — global English workbench and documentation

### Changed
- Standardized the complete user-facing workbench on concise English terminology, including dock labels, tooltips, status messages, setup dialogs, onboarding, diagnostics, release-readiness views, menus, and About content.
- Removed bilingual labels and legacy localized search aliases so command discovery, shortcut guidance, and support screenshots present one consistent global interface.
- Rebuilt the command reference, shortcut map, smoke-test checklist, and README as English-only resources while preserving the existing CAD concepts, precision-input examples, and accessibility guidance.
- Refreshed Plugin Hub release notes and citation metadata for the 1.26 release line.
- Standardized newly generated road-platform, junction-island, and buffer layers on descriptive English layer names, field names, and attribute values.

### Fixed
- Made empty Enter finish a valid in-progress sketch instead of restarting the active tool and discarding vertices; incomplete sketches now remain intact and request the missing points.
- Made Escape from the focused command line clear the input and safely cancel the active CAD operation.
- Made Rotate and Mirror operate in a local metric CRS so high-latitude geographic projects preserve physical lengths, curved geometry, and Z/M values.
- Corrected Multi-Offset previews when the map canvas and selected layer use different CRSs.

### Compatibility
- Preserved internal tool keys, module names, and stored settings keys used by existing projects.
- Added compatibility mapping for legacy road-platform and junction-island layers, fields, CRSs, and attribute values so existing projects are reused in place—even after a project-CRS change—while new projects receive the English schemas.
- Retained the established AutoCAD-style command aliases, keyboard shortcuts, project formats, and QGIS 3.28 through QGIS 4 compatibility range.

### Quality
- Expanded release checks to detect accidental bilingual user-facing copy while allowing author and institution proper names.
- Kept all help tables, dialog controls, and workbench feedback screen-reader accessible after the terminology consolidation.

## [1.25.1] - 2026-07-13

- AutoCAD-style precision input and geographic drafting accuracy

### Added
- Added AutoCAD-style precision input to the dock command line and direct canvas typing: absolute `x,y`, relative Cartesian `@dx,dy`, relative polar `@distance<angle`, and distance-along-cursor entry.
- Enabled precision point entry across Line, Polyline, Rectangle, Circle, Polygon and Arc, plus coordinate input for Move/Copy, signed degree input for Rotate and direct factor input for Scale.

### Changed
- Interpreted relative, polar and direct-distance values consistently in metres, including geographic project CRSs; absolute coordinates remain in the map canvas CRS.
- Made Circle, Rectangle, Polygon and Arc construction metric-safe in geographic projects, including polar caps, and consolidated shared CRS transformations in `core/crs_utils.py`.

### Quality
- Added parser, state-safety, projected/geographic/polar geometry, transform-tool, dock-routing and direct-key runtime coverage for QGIS 3.44 and QGIS 4.2.

## [1.25.0] - 2026-07-13

- True junction corner solver and curve/ZM-safe transforms

### Added
- Added an explicit Chamfer/Fillet junction-corner mode with live parameter controls and schematic feedback.
- Added a deterministic half-edge junction solver for X, T and skew intersections using true curb support-line intersections.

### Fixed
- Made the Junction chamfer distance effective and made the previously unreachable fillet workflow available.
- Kept opposite approaches of the same through-road separate and matched connection endpoints exactly to transactionally trimmed curb endpoints.
- Prevented single-road, incomplete-arm, reflex-sector and unsafe acute-angle junction attempts from changing geometry.
- Closed median/refuge ends per directional road arm instead of drawing caps across the junction.
- Added exception-safe road rollback and compensating island cleanup when a road commit fails; island creation now refuses mixed user-owned edit sessions.
- Rebuilt teardrop islands as valid, approach-aligned bulb-and-nose polygons whose length parameter changes the actual shape and area.
- Preserved CircularString, CompoundCurve, CurvePolygon and Z/M values through Scale and Mirror affine transforms.

### Quality
- Added dual-runtime pure junction, geographic X-junction integration, gap-free endpoint, refuge/island, injected-failure rollback and curved Z/M regression coverage for QGIS 3.44 and QGIS 4.2.

## [1.24.0] - 2026-07-13

- Metric-safe CAD, transactional edits, and workbench reliability

### Fixed
- Made cross-layer Trim, Extend and Fillet operations CRS-safe; measurement now uses the selected feature layer CRS.
- Extended short lines reliably to distant boundaries and ignored intersections behind the endpoint.
- Preserved all multipart components in Divide/Trim and prevented incompatible same-name output layers from being reused.
- Checked edit, add, change, delete and commit results throughout the toolset; plugin-owned edits now roll back on failure and user-owned edit sessions remain open.
- Made Buffer, Hatch, Offset, Multi-Offset, Fillet, Road and Junction distances metre-accurate in projected and geographic projects through a local metric work CRS.
- Restricted junction trimming and block-remnant cleanup to PlanX/selected layers instead of modifying unrelated project layers.
- Prevented cancelled setup dialogs from leaving an inert map tool active.
- Removed ghost toolbar/menu objects and stale signal connections on plugin reload.
- Grouped Fillet, Divide, Trim, Hatch and Junction road edits into rollback-capable undo commands so partial provider failures cannot leave half-written geometry.

### Workbench
- Drawing tools now start a writable target layer's edit session automatically and reject incompatible target geometry types with a clear status message.
- Buffer, Hatch, Dimension, Construction and Road workflows are no longer blocked by an unrelated read-only active layer.
- The dock now follows QGIS map-tool and edit-state changes, resets command/session state completely, and exposes explicit Edit ON/Edit OFF controls.
- Command Palette and Shortcut Guide now list all 33 workbench tools, including commands without dedicated shortcuts.
- Added keyboard-accessible diagnostics tables, read-only measurement aliases, and live CRS-label updates.

### Performance and quality
- Batched Array, Multi-Offset, Divide and Hatch writes into single undoable operations, with 10,000-item Array and 20,000-line Hatch safety limits.
- Added dual-runtime lifecycle, geometry-regression and urban-workbench smoke suites for QGIS 3.44 LTR/Qt5 and QGIS 4.2/Qt6.

## [1.23.3] - 2026-06-18

- docs: add CITATION.cff for Zenodo DOI integration

## [1.23.2] - 2026-06-17

- Fix fillet trimming closest corner endpoints and zero vector corner bug

## [1.23.1] - 2026-06-17

- Fix CRS mismatch bug when project and layer CRS differ

## [1.23.0] - 2026-06-09

### Fixed
- **Pick aperture is now enforced.** `_pick_feature` filtered candidates only by bounding-box intersection, so a long diagonal line or large polygon could be selected even when the click was far from its actual geometry (its bbox covered the click). The 10-px aperture (`PICK_TOLERANCE`) is now also enforced on the real geometry distance — picks behave like AutoCAD's pickbox.
- **Two-step tools can no longer operate a feature on itself.** In Fillet, Trim and Extend, the second pick could return the *first* feature again (click near the first line → fillet/trim a line with itself, producing garbage geometry or a confusing failure). The second pick now excludes the first feature (`_pick_feature(..., exclude=...)`); Fillet's hover preview uses the same layer-aware exclusion instead of a fragile id-only comparison.

### Changed
- **New crisp PNG icon.** Replaced `icons/icon_main.svg` with a generated 256×256 `icons/icon.png` (teal drafting tile, white lines joined by an orange fillet arc, AutoCAD-style grips). SVG icons render blank/muddy in some QGIS builds and have caused Plugin Hub rejections.

### Quality
- `tests/smoke_compat.py` gains an 11th check that statically verifies the pick-aperture enforcement and the Fillet/Trim/Extend self-pick exclusion.

## [1.22.0] - 2026-05-26

### Fixed
- **Line/Polyline now finish correctly on QGIS 4.** `sketcher_base.keyPressEvent` referenced the unscoped `Qt.Key_Z` enum, which raises `AttributeError` under PyQt6 — and because it sat in the `elif` chain before the Enter branch, pressing Enter (or any non-Escape key) crashed the handler and the sketch never completed. Switched to the scoped `Qt.Key.Key_Z`.
- **Fillet preview is now visible.** The preview rubber band is recreated if it was cleared, and the candidate arc is drawn as a bold orange dashed line. Previously a thin cornflower-blue line (or a silently-swallowed `None` rubber band) made the preview effectively invisible even though the fillet itself worked.

### Command line (more AutoCAD-like)
- **Empty Enter repeats the last command** (AutoCAD muscle memory).
- **The input clears after each run**, so you can chain commands: type `L` ↵, draw, type `O` ↵, …

### Quality
- New runtime check exercises the full Line/Polyline draw pipeline (rubber-band construction → geometry build → feature insertion) on **both QGIS 3 LTR and QGIS 4**.
- Static Qt-enum scan now also catches unscoped `Qt.Key_*`, mouse-button, and modifier members (the exact bug class fixed above).

## [1.21.0] - 2026-05-26

### AutoCAD-style command line
- The dock search box is now an **AutoCAD-style command line**. Type a command alias and press Enter to launch the tool: `L`→Line, `PL`→Polyline, `REC`→Rectangle, `O`→Offset, `TR`→Trim, `EX`→Extend, `F`→Fillet, `CO`/`CP`→Copy, `MI`→Mirror, `RO`→Rotate, `SC`→Scale, `AR`→Array, `H`→Hatch, `DIM`→Dimension, `XL`→Construction line, and more.
- **Autocomplete popup** suggests commands as you type (case-insensitive prefix match over aliases + tool names).
- **Command history**: Up/Down arrows recall previously entered commands like a terminal (50-entry ring, consecutive duplicates skipped).
- **Resolution precedence**: AutoCAD alias → exact tool key → fuzzy name match. Unknown input echoes `Unknown command: …` instead of doing nothing.
- The alias→tool mapping and resolution precedence are asserted on **both QGIS 3 LTR and QGIS 4** in the runtime smoke probe.

## [1.20.0] - 2026-05-26

Stable release — full accessibility coverage, verified on QGIS 3 LTR and QGIS 4.

### Accessibility (completed)
- The tool **search box** and the **Road / Junction / Block Chamfer** buttons now expose `accessibleName` / `accessibleDescription`. Combined with 1.19.0, every interactive control in the dock (tool buttons, quick actions, urban buttons, search, usage counter) is now screen-reader friendly with no bare-emoji announcements.

### Quality
- Verified clean CAD dock construction on **both QGIS 3.x LTR and QGIS 4** runtimes through the full release gate (doctor + encoding audit + dual-runtime smoke + zip verification).

## [1.19.0] - 2026-05-26

### Accessibility
- **Screen readers**: icon-only tool buttons and quick-action buttons now set `accessibleName` / `accessibleDescription`, so assistive technology announces a useful tool description instead of a bare "button". The dock itself has an accessible name.
- **Keyboard navigation**: tool buttons are now tab-focusable (`Qt.FocusPolicy.TabFocus`) with a visible focus ring on both tool buttons and quick-action buttons.

### Compactness
- **Status strip consolidation**: the layer-state label and the session usage counter now share a single horizontal row (3:1 width split) instead of two full-width stacked rows, reclaiming vertical space in the dock.

### Tests
- `tests/smoke_compat.py` gains a dock-accessibility check (9 checks total).

## [1.18.0] - 2026-05-26

### Improvements
- **Compact GUI**: Replaced the 15-button single-row overflow layout (broken at 160px dock width) with a semantic 3×4 `QGridLayout`. Buttons are grouped by function: workflow controls (Edit / Cancel / Repeat / Preflight), help & docs (Docs / Keys / Start / Health), and diagnostics (Stats / Diag / Pin / Reset WS).
- **Static smoke test**: Added `tests/smoke_compat.py` — an 8-check static compatibility smoke test runnable without a QGIS installation (`py -3 tests/smoke_compat.py`). Verifies Qt6 enum safety, split-geometry unpack safety, metadata correctness, icon existence, classFactory presence, and qgis.PyQt import discipline.

## [1.17.7] - 2026-05-26

- Qt6 compatibility fixes (DialogCode/EditTrigger/NoWrap), Help Tool fallback behavior, and compact dock spacing refresh.

## [1.17.6] - 2026-05-26

- Qt5/Qt6 compatibility hardening for dock UI, rich-text enum fixes, and QGIS 3.40+/4 runtime validation.

## [1.17.5] - 2026-05-26

- Maintenance release: refreshed Plugin Hub package with QGIS 4 compatibility fixes and repaired CAD UI text encoding.

## [1.17.4] - 2026-05-26

- Repair mojibake in CAD UI text and tool messages.

## [1.17.3] - 2026-05-26

- Fix QGIS 4 / Qt6 enum compatibility for the CAD dock and dialogs.

## [1.17.2] - 2026-05-26

- fix: Qt.ApplicationShortcut to Qt.ShortcutContext.ApplicationShortcut for PyQt6/QGIS 4

## [1.17.0] - 2026-05-23

- Beta completion release: readiness, diagnostics, smoke test, issue template, UX and shortcuts

### Added
- Dock favorites flow (`Pin Last` + Favorites row) for persistent one-click tool access.
- Dock state persistence across sessions (search text, recent tools, favorites, usage counter).
- Diagnostics report dialog (dock `Diag` button + `Ctrl+Alt+D`) with copy-ready support text.
- Workspace state reset flow (`Reset WS` button + `Ctrl+Alt+R`) for rapid clean-session recovery.
- Usage statistics dialog (`Stats` button + `Ctrl+Alt+T`) with per-tool activation share.
- Contextual help jump (`Help Tool`) that opens command docs at relevant sections.
- Health check panel (`Health` button + `Ctrl+Alt+W`) for runtime readiness validation.
- Shortcut audit report (`Key Audit` button + `Ctrl+Alt+Y`) to detect keymap conflicts.
- Tool activation guardrails to prevent invalid launches on missing/non-vector/read-only layers.
- Session checklist dialog (`Ctrl+Alt+G`) for one-window beta startup control.
- Command palette upgraded with category filtering, additional search aliases, and usage-based ordering.
- New docs tab with QGIS smoke test checklist for release-candidate validation.
- Direct smoke-test opener (`Ctrl+Alt+M`) for faster RC verification in QGIS.
- Issue template dialog (`Ctrl+Alt+N`) that includes diagnostics text for structured bug reporting.
- Release readiness dashboard (`Ctrl+Alt+V`) combining health, shortcut, docs, and metadata checks.

## [1.16.0] - 2026-05-23

Onboarding and operational visibility pass.

### Added
- **Quick Start dialog** (menu, dock Start button, and `Ctrl+Alt+Q` shortcut).
- **Live usage counter** in dock to track session tool-activation volume.
- Shortcut references updated for quick-start access.

## [1.15.0] - 2026-05-23

Session control and readiness pass for daily production use.

### Added
- **Dock editing controls**: `Edit ON/OFF` and `Preflight` quick actions.
- **System shortcuts**:
  - `Ctrl+Alt+E` toggle active-layer editing
  - `Ctrl+Alt+F` run preflight checks
- **Current-layer auto refresh** in plugin lifecycle (including safe disconnect on unload).

## [1.14.0] - 2026-05-23

Editing workflow and preflight safety pass.

### Added
- **Toggle Layer Editing** action (`Ctrl+Alt+E`) and dock `Edit ON/OFF` control.
- **Dock Preflight button** for quick checks (active layer present + vector + editable).
- **Auto layer-state refresh** when current layer changes.


## [1.13.0] - 2026-05-23

Operational control and safety pass for production drafting sessions.

### Added
- **Cancel Active Tool** action (dock button + `Ctrl+Alt+C`) for immediate safe exit from current tool.
- **Layer edit-state indicator** in dock showing active layer name + editable/read-only status.
- Dock status sync enhancements after cancel/activate to reduce ambiguous tool state.

## [1.12.0] - 2026-05-23

Beta acceleration pass with command access and workflow reset controls.

### Added
- **Global Command Palette** (`Ctrl+Alt+P`) for fast command activation by typing.
- **Dock quick controls**:
  - `Reset` button clears active tool filter
  - `Clear` button clears recent-tools strip
- Shortcut references updated with command palette entry in dialog and HTML docs.

## [1.11.0] - 2026-05-23

English-first documentation revision + beta usability upgrades.

### Added
- **English-primary documentation** in both command and shortcut HTML references.
- **Searchable shortcut center** (`dialogs/shortcut_help_dialog.py`) with command/category filters.
- **Live workflow hint panel** in the dock (`Tip`) that updates per active tool.
- **Global docs shortcut**: `Ctrl+Alt+H` opens Command Reference.

## [1.10.0] - 2026-05-23

HTML documentation and in-dock help integration for command mastery.

### Added
- New in-plugin HTML docs dialog (`dialogs/docs_dialog.py`) with two tabs:
  - `docs/command_reference.html` (detailed command usage and workflow tips)
  - `docs/shortcuts.html` (full keyboard map)
- Dock quick actions now include `Docs` and `Keys` buttons for one-click help access.
- New menu entry: `Command Reference`.

## [1.9.0] - 2026-05-23

Beta completion hardening pass for CAD accessibility and operator speed.

### Added
- **Construction mode direct access in dock**: `construction_ray` and `construction_seg` are now visible as dedicated buttons next to infinite construction lines.
- **Advanced shortcut layer**:
  - `Ctrl+Alt+K` -> Construction Ray
  - `Ctrl+Alt+L` -> Construction Segment
  - `Ctrl+Shift+S` -> Focus dock tool search
  - `Ctrl+Shift+/` -> Open shortcut guide
- **Shortcut guide dialog** (`dialogs/shortcut_help_dialog.py`) for discoverability and onboarding.

## [1.8.0] - 2026-05-23

Beta completion release candidate for high-speed CAD workflows.

### Added
- **Dock quick search**: type tool names or aliases in the new `Find tool` box and press Enter to launch the first match.
- **Recent tools strip**: last 3 activated tools are pinned in the dock for one-click reactivation.
- **Activation sync**: tools launched from keyboard shortcuts now sync back to dock button state and recent history.

## [1.7.0] - 2026-05-20

Hatch / Pattern Fill + Construction Lines.

### Added
- **Hatch tool** (`tools/tool_hatch.py`): pick a closed polygon, configure pattern (parallel, cross, diagonal up/down), spacing (m), angle (°) and colour. Hatch lines are computed by sweeping the polygon's bounding box and clipping each line to the polygon, then written to the auto-created `planx_hatch` layer with attributes `source_layer`, `pattern`, `spacing_m`, `angle_deg`, `color`. Multipart-safe (multi-line intersections are split per part).
- **Construction Line tool** (`tools/tool_construction_line.py`): 2-click reference line with three dispatch modes:
  - `construction_inf` — extends `_INF_EXTEND_FACTOR × canvas diagonal` past both reference points (infinite reference).
  - `construction_ray` — extends only past the second point.
  - `construction_seg` — bounded segment.
  Writes to the auto-created `planx_construction` layer; the dashed cyan style is applied on first use.
- New icons `cad_hatch.svg` and `cad_construction.svg` registered in the dock's Edit group.
- Shortcuts: Hatch = `Ctrl+Shift+H`, Construction (infinite) = `Ctrl+Shift+K`.

## [1.6.0] - 2026-05-20

- Add Join, Divide, and Multi-Offset tools, and make the interface compact

All notable changes to **PlanX CAD Toolset** are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · versioning: [SemVer](https://semver.org/).

## [1.5.0] - 2026-05-20

Vertex Edit + Live coordinate read-out.

### Added
- **Vertex Edit tool** (`tools/tool_vertex_edit.py`):
  - Click a line or polygon feature to render every vertex as an orange handle.
  - Drag a handle to **move** a vertex; release to commit.
  - Click anywhere on the line itself (within ~8 px) to **insert** a new vertex at the click position.
  - Right-click a handle to **delete** that vertex; deletions are refused if they would invalidate the ring (line < 2 vertices or polygon ring < 4).
  - Multipart-safe via per-part vertex IDs.
- **Live coordinate widget** (`dialogs/coord_widget.py`) inside the dock:
  - Real-time cursor X / Y from the canvas' `xyCoordinates` signal.
  - Current CRS auth-id and scale denominator from `mapSettings()` and `scaleChanged`.
  - Compact monospace read-out styled to the dock palette.
- Vertex Edit keyboard shortcut: `Ctrl+Shift+V`.
- New icon `cad_vertex_edit.svg` in the Edit group.

## [1.4.0] - 2026-05-20

Keyboard shortcuts framework + tool history.

### Added
- **15 `Ctrl+Shift+<letter>` shortcuts** registered as `Qt.ApplicationShortcut` on the QGIS main window:
  - Drawing: `L`ine, `P`olyline, `R`ectangle, polyGon (`G`), `C`ircle, `A`rc
  - Editing: `O`ffset, `T`rim, `E`xtend, `F`illet, `B`uffer, arra`Y`
  - Transform: `M`ove
  - Measure: `D`imension, `I` (distance measurement)
- **`Ctrl+Shift+Space`**: repeat the last activated tool (CAD convention).
- Dock: new **"Repeat Last Tool"** button next to the status bar.
- Tool-button tooltips now show their keyboard shortcut as a `[Ctrl+Shift+X]` suffix.

### Changed
- `main_plugin` tracks `self._last_tool_key` updated on every activation.
- `_activate_tool` recognises an `__repeat__` sentinel emitted by the dock's repeat button and reroutes it through `_repeat_last_tool`.
- Plugin owns the `QShortcut` instances; they are disabled and deleted on `unload`.

## [1.3.0] - 2026-05-20

Two new tools added to the dock.

### Added
- **Array tool** (`tools/tool_array.py`):
  - Rectangular mode: rows × cols with independent Δx / Δy spacing
  - Polar mode: count + sweep angle, with on-canvas center click and live preview of all rotated copies
  - Copies inherit source attributes; uses `rotate_geometry` (multipart-safe)
- **Linear Dimension tool** (`tools/tool_dimension.py`):
  - Click two points (snap-aware); commits a dimension line on the auto-created `planx_dimensions` memory layer
  - Attributes: `distance_m`, `label` (`12.34 m` or `1.234 km`), `from_x/y`, `to_x/y`
  - Auto-enables labels showing the `label` field on first use
  - Right-click resets between dimensions; Esc cancels current segment
- New icons `cad_array.svg`, `cad_dimension.svg` in the dock (Edit and Measure groups respectively).

### Changed
- `main_plugin._create_tool` now dispatches `array` and `dimension`; `array` joins the dialog-tool set so each invocation re-asks parameters.

## [1.2.0] - 2026-05-19

UI overhaul + correctness pass.

### Added
- Dock panel now scrolls (vertical `QScrollArea`) so all categories fit on small/narrow screens; min width 180 px.

### Fixed
- **Trim:** `splitGeometry` 3-tuple unpack error on QGIS 3.x — now handles 2- and 3-return-value APIs.
- **Fillet:** `create_fillet_and_trims` always drew the counter-clockwise (long) arc; now picks the shortest arc between tangent points.
- **Scale / Mirror:** multipart polygons (with holes or multi-rings) were silently flattened to a single ring. New `_transform_vertices` helper preserves topology for point/line/polygon, single- and multi-part.
- **Extend:** crashed on multi-part input (`asPolyline` on multi); now reads the first part safely. Multi-intersection chooses the closest landing point to the line's tip.
- **add_feature_to_layer:** committed unconditionally, prematurely persisting the user's in-progress edits. Now commits only if it started the edit session.
- **Buffer:** attributes were written via "last feature in `getFeatures()`" which is order-fragile — attributes are now set on the `QgsFeature` before insert.
- **QInputDialog** parent set to QGIS main window for Fillet, Offset, Polygon (previously `None` → off-screen positioning on multi-monitor setups).

### Fixed (urban)
- **Block Chamfer** and **Junction**: premature `commitChanges` could persist the user's open edits on their own road layers. All three sites now use the "preserve user's edit session" pattern (`was_editing` guard).

### Removed
- `sketcher_utils.trim_geometry_at_point` (broken: `click_point` was unused, function returned the input unchanged).
- `sketcher_utils.fillet_corner` (broken: used `smooth()` not a real fillet; `vertex_index` was unused).
- Dead helpers in `tool_fillet`: `_get_line_points`, `_find_direction_from_intersection`, `_trim_line_at_point` — superseded by `create_fillet_and_trims` / `trim_line_to_point`.

## [1.1.1] - 2026

- Standardized Plugin Hub metadata, aligned icon metadata, added educational context, and refreshed the stable release package.

## [1.1.0]

- Added advanced urban planning, UX, and measurement enhancements.
- Fixed intersection topology (A-B road connection).
- Renewed block chamfering logic via EasyFillet integration.
- Custom 'O' cursor added.
- Improved distance and area measurements by selection.

## [1.0.0]

- Initial release.
- 18 CAD tools, dockable interface, interactive road platform.
