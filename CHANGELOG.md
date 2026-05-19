# Changelog

All notable changes to **PlanX CAD Toolset** are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · versioning: [SemVer](https://semver.org/).

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
