# PlanX CAD Toolset — v1.28.0 Release Report
**Theme:** Precision Drafting: OSNAP, Tracking & Dynamic Input  
**Author:** Geophilo  
**Date:** 2026-10-25  

---

## 1. Executive Summary

PlanX CAD Toolset version **1.28.0** delivers a major upgrade to drafting precision, bringing AutoCAD-grade Object Snap (OSNAP) with typed visual glyphs, Ortho and Polar tracking with dashed alignment rays, and a high-contrast floating Dynamic Input Heads-Up Display (HUD) directly to the QGIS canvas.

All implementation goals outlined in `ENHANCEMENT_PLAN_v1.28.md` and `ROADMAP.md` (Items 1–3) were executed and verified end-to-end across both target runtimes (**QGIS 3.44 LTR / PyQt5** and **QGIS 4.2 / PyQt6**) with zero external dependencies and zero Plugin Hub security warnings.

---

## 2. New Features Delivered

### Phase 1: Object Snap (OSNAP) Engine & Typed Visual Glyphs
- **11 Snap Kinds:** Endpoint, Midpoint, Centre, Quadrant, Vertex, Intersection, Apparent Intersection, Perpendicular, Tangent, Nearest, and Extension (`core/osnap_engine.py`).
- **Typed Canvas Glyphs:** High-contrast visual markers rendered via `QgsVertexMarker.IconType` (`core/osnap_markers.py`):
  - **Endpoint:** Box (`ICON_BOX`, Teal)
  - **Midpoint:** Triangle (`ICON_TRIANGLE`, Teal)
  - **Centre:** Circle (`ICON_CIRCLE`, Teal)
  - **Quadrant:** Rhombus / Diamond (`ICON_RHOMBUS`, Teal)
  - **Intersection:** X (`ICON_X`, Rose)
  - **Apparent Intersection:** Double Triangle (`ICON_DOUBLE_TRIANGLE`, Rose)
  - **Perpendicular:** Inverted Triangle (`ICON_INVERTED_TRIANGLE`, Blue)
  - **Tangent:** Circle with tangent indicator (Amber)
  - **Nearest:** Hourglass / Double Triangle (Teal)
  - **Vertex/Node:** Cross (`ICON_CROSS`, Teal)
  - **Extension:** X with projected ray guide (Teal)
- **Accessibility & Guidance:** Status bar and screen-reader accessible snap announcements via `snap_announced` signal.

### Phase 2: Ortho & Polar Tracking Engine
- **Ortho Mode (`F8` / `ORTHO`):** Constrains drafting movement to exact 0°, 90°, 180°, and 270° axes with real-time dashed alignment rays (`core/tracking_engine.py`).
- **Polar Tracking Mode (`F10` / `POLAR`):** Locks cursor angle along configurable radial increments (15°, 30°, 45°, 90°) within snap tolerance, displaying angle and distance readouts.
- **Object Snap Tracking:** Allows acquiring reference snap points by hovering over them, projecting orthogonal alignment rays along X and Y axes.
- **Precedence Rule (S3):** Alignment tracking rays take precedence over generic polar rays to eliminate cursor jitter at ray intersections.

### Phase 3: Dynamic Input Heads-Up Display (HUD)
- **Floating Canvas HUD (`F12` / `DYN`):** Implemented via `DynamicInputHud(QgsMapCanvasItem)` (`dialogs/dynamic_input_hud.py`).
- **Live Metrics:** Renders real-time distance, bearing angle, and relative Δx/Δy coordinates in a high-contrast translucent dark Slate pill (`#0f172a` with 88% opacity) and Teal border (`#0d9488`).
- **Dual-Runtime Geometry:** Positioned with high-DPI scaling offsets next to the cursor; cleanly hidden when idle and safely detached during tool lifecycle transitions.

### Phase 4 & 5: Unified Controller & UX Wiring
- **Unified Workbench:** Created `DraftingWorkbench` (`core/drafting_workbench.py`) composed by both `tools/tool_base.py` and `sketcher/sketcher_base.py`, establishing a single source of truth for snapping, tracking, and HUD state.
- **Global Shortcuts & Aliases:** Application-wide `F3`, `F8`, `F10`, `F12` shortcuts and dock command-line aliases (`OSNAP`, `ORTHO`, `POLAR`, `DYN`).
- **Updated Documentation:** Comprehensive updates to `docs/command_reference.html`, `docs/shortcuts.html`, `docs/smoke_test_checklist.html`, `README.md`, and `CHANGELOG.md`.

---

## 3. Shortcomings Resolved

| ID | Issue Description | Resolution | Status |
|:---|:---|:---|:---:|
| **S1** | Duplicate snapping code across `tool_base.py` and `sketcher_base.py` | Abstracted into unified `DraftingWorkbench` composed by both hierarchies | **RESOLVED** |
| **S2** | Missing visual indicator distinguishing snap types (all appeared identical) | Implemented `OsnapMarkerManager` with 11 distinct AutoCAD-standard typed glyphs | **RESOLVED** |
| **S3** | No tracking priority when Polar and Object Tracking overlap | Implemented strict S3 precedence: Object tracking ray > Polar angle ray > free cursor | **RESOLVED** |
| **S4** | HUD lag / scene leaks during rapid mouse movement | Reused persistent `QgsMapCanvasItem` with `update()` and safe scene detach | **RESOLVED** |
| **S5** | Stale test suite entries in `plugins.toml` | Created `tests/smoke_plugin.py` and `test_drafting_pure.py`; registered in `plugins.toml` | **RESOLVED** |
| **S6** | Non-English anchor tag in `REFERENCE_MANUAL.html` | Renamed to English `#alg-block-chamfer`, passing `smoke_compat.py` | **RESOLVED** |

---

## 4. Test & Verification Matrix

### Static & Security Gates
- **`validate_plugin`:** PASSED (0 warnings)
- **`packaging/hub_security_scan.py`:** CLEAN (0 critical, 0 warnings across 120 shipped files)
- **`hub_qt6_scan.py`:** PASSED (Advisory only; zero blocking errors)
- **`tests/smoke_compat.py`:** PASSED (13/13 static compatibility checks)

### Pure Logic Unit Tests (`pytest`)
- **`tests/test_drafting_pure.py`:** 17/17 PASSED in 0.02s
  - Absolute, relative Cartesian, relative polar, and direct distance precision parsing
  - SnapKind enum completeness
  - Geometric primitives: perpendicular foot, line-line intersection (direct and infinite apparent), circle tangents
  - Ortho and Polar tracking math, tolerance bounds, and S3 precedence

### Headless QGIS Runtime Smoke Suites (`smoke_plugin.py`)
Executed on both **QGIS 3.44.2 LTR (PyQt5)** and **QGIS 4.2.0 (PyQt6)**:
1. `smoke_runtime.py`: **30/30 PASSED**
2. `smoke_geometry.py`: **4/4 PASSED**
3. `smoke_geometry_regressions.py`: **14/14 PASSED**
4. `smoke_junction_geometry.py`: **41/41 PASSED**
5. `smoke_modify_geometry.py`: **21/21 PASSED**
6. `smoke_precision_input.py`: **28/28 PASSED**
7. `smoke_urban_workbench.py`: **45/45 PASSED**
8. `smoke_osnap_tracking.py`: **45/45 PASSED**

**Overall Verification Result:** `VERIFY OK: 1 plugin(s)`

---

## 5. Rule 0 Compliance Statement

In strict adherence to repository Rule 0:
- All commits, tags, and release metadata are authored solely under **Yusuf Eminoğlu** (`yusuf.eminoglu@deu.edu.tr`).
- Zero AI attribution, signatures, or co-author trailers are present in any commit or file.
