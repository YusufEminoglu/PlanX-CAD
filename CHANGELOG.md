# Changelog

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

## [Unreleased]

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
- Command palette upgraded with category filter, Turkish aliases, and usage-based ordering.
- New docs tab with QGIS smoke test checklist for release-candidate validation.
- Direct smoke-test opener (`Ctrl+Alt+M`) for faster RC verification in QGIS.
- Issue template dialog (`Ctrl+Alt+N`) that includes diagnostics text for structured bug reporting.
- Release readiness dashboard (`Ctrl+Alt+V`) combining health, shortcut, docs, and metadata checks.

## [1.16.0] - 2026-05-23

- Quick Start onboarding, usage metrics, Ctrl+Alt+Q

## [1.16.0] - 2026-05-23

Onboarding and operational visibility pass.

### Added
- **Quick Start dialog** (menu, dock Start button, and `Ctrl+Alt+Q` shortcut).
- **Live usage counter** in dock to track session tool-activation volume.
- Shortcut references updated for quick-start access.

## [1.15.0] - 2026-05-23

- Edit ON/OFF controls, preflight shortcut, layer-state lifecycle refresh

## [1.15.0] - 2026-05-23

Session control and readiness pass for daily production use.

### Added
- **Dock editing controls**: `Edit ON/OFF` and `Preflight` quick actions.
- **System shortcuts**:
  - `Ctrl+Alt+E` toggle active-layer editing
  - `Ctrl+Alt+F` run preflight checks
- **Current-layer auto refresh** in plugin lifecycle (including safe disconnect on unload).

## [1.14.0] - 2026-05-23

- Layer editing toggle, preflight checks, auto layer-state refresh

## [1.14.0] - 2026-05-23

Editing workflow and preflight safety pass.

### Added
- **Toggle Layer Editing** action (`Ctrl+Alt+E`) and dock `Edit ON/OFF` control.
- **Dock Preflight button** for quick checks (active layer present + vector + editable).
- **Auto layer-state refresh** when current layer changes.


## [1.13.0] - 2026-05-23

- Cancel active tool, layer state indicator, dock sync

## [1.13.0] - 2026-05-23

Operational control and safety pass for production drafting sessions.

### Added
- **Cancel Active Tool** action (dock button + `Ctrl+Alt+C`) for immediate safe exit from current tool.
- **Layer edit-state indicator** in dock showing active layer name + editable/read-only status.
- Dock status sync enhancements after cancel/activate to reduce ambiguous tool state.

## [1.12.0] - 2026-05-23

- Command palette, dock reset controls, shortcut sync

## [1.12.0] - 2026-05-23

Beta acceleration pass with command access and workflow reset controls.

### Added
- **Global Command Palette** (`Ctrl+Alt+P`) for fast command activation by typing.
- **Dock quick controls**:
  - `Reset` button clears active tool filter
  - `Clear` button clears recent-tools strip
- Shortcut references updated with command palette entry in dialog and HTML docs.

## [1.11.0] - 2026-05-23

- English-first docs, searchable shortcut center, live dock hints

## [1.11.0] - 2026-05-23

English-first documentation revision + beta usability upgrades.

### Added
- **English-primary docs with Turkish secondary notes** in both command and shortcut HTML references.
- **Searchable shortcut center** (`dialogs/shortcut_help_dialog.py`) with command/category filters.
- **Live workflow hint panel** in dock (`Tip / Ipucu`) that updates per active tool.
- **Global docs shortcut**: `Ctrl+Alt+H` opens Command Reference.

## [1.10.0] - 2026-05-23

- HTML command reference, shortcuts page, Docs/Keys dock integration

## [1.10.0] - 2026-05-23

HTML documentation and in-dock help integration for command mastery.

### Added
- New in-plugin HTML docs dialog (`dialogs/docs_dialog.py`) with two tabs:
  - `docs/command_reference.html` (detailed command usage and workflow tips)
  - `docs/shortcuts.html` (full keyboard map)
- Dock quick actions now include `Docs` and `Keys` buttons for one-click help access.
- New menu entry: `Command Reference / Komut Kilavuzu`.

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
- **Dock quick search**: type tool names/aliases in the new `Find tool / Arac ara` box and press Enter to launch the first match.
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

- Add Join, Divide, Multi-Offset tools and make UI bilingual/compact

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
  - Measure: `D`imension, `I` (mesafe ölç)
- **`Ctrl+Shift+Space`**: repeat the last activated tool (CAD convention).
- Dock: new **"↻ Son aracı tekrarla"** button next to the status bar.
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
- **Ada Kırma** & **Kavşak**: premature `commitChanges` could persist the user's open edits on their own road layers. All three sites now use the "preserve user's edit session" pattern (`was_editing` guard).

### Removed
- `sketcher_utils.trim_geometry_at_point` (broken: `click_point` was unused, function returned the input unchanged).
- `sketcher_utils.fillet_corner` (broken: used `smooth()` not a real fillet; `vertex_index` was unused).
- Dead helpers in `tool_fillet`: `_get_line_points`, `_find_direction_from_intersection`, `_trim_line_at_point` — superseded by `create_fillet_and_trims` / `trim_line_to_point`.

## [1.1.1] - 2026

- Standardized Plugin Hub metadata, aligned icon metadata, added DEU educational context, and refreshed the stable release package.

## [1.1.0]

- Added advanced urban planning, UX, and measurement enhancements.
- Fixed intersection topology (A-B road connection).
- Renewed block chamfering logic via EasyFillet integration.
- Custom 'O' cursor added.
- Improved distance and area measurements by selection.

## [1.0.0]

- Initial release.
- 18 CAD tools, dockable interface, interactive road platform.
