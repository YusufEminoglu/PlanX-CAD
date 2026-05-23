# PlanX CAD Toolset

**A lightweight, fast CAD toolset for urban planning in QGIS - part of the PlanX suite**

PlanX CAD Toolset brings 18+ CAD-like drawing and editing operations directly into QGIS through a modern dockable panel. Designed for urban planners and GIS professionals who need drafting-grade tools without leaving QGIS.

---

## Features

### Drawing Tools
- Line, Polyline, Rectangle, Polygon, Circle, Arc

### Editing Tools
- Offset, Trim, Extend, Fillet, Buffer, Hatch, Construction Line, Divide, Join, Multi-Offset, Vertex Edit

### Transform Tools
- Move, Copy, Rotate, Scale, Mirror, Array

### Measurement Tools
- Distance and area measurement (standalone and selection-based)
- Persistent linear dimensions with label attributes

### Urban Planning Tools
- **Road Platform Generator** - interactive road cross-section design with lane configuration
- **Block Chamfering** - EasyFillet-powered corner rounding for urban blocks
- **Junction Topology Fixer** - clean A-B road intersection connections

### UI and Productivity
- Modern dockable panel with icon-based toolbar
- Native QGIS snapping support and custom precision cursor
- Quick tool search (`Find tool / Arac ara`) with Enter-to-activate
- Last-3 recent tools strip for rapid tool switching
- Favorites row with `Pin Last` for persistent one-click access
- Ctrl+Shift keyboard workflow with repeat-last-tool action
- Dedicated construction modes in dock (infinite/ray/segment) and built-in shortcut guide dialog
- Built-in HTML command manual and separate shortcut reference page (open via Docs/Keys buttons)
- English-primary / Turkish-secondary documentation standard
- Searchable shortcut center with category filtering
- Live per-tool workflow hints in dock and global docs shortcut (`Ctrl+Alt+H`)
- Global command palette (`Ctrl+Alt+P`) for type-to-activate command access
- Dock quick reset controls (Reset filter + Clear recent)
- Active-layer editing toggle action (`Ctrl+Alt+E` + Edit ON/OFF button)
- Dock preflight checks for vector/editable readiness (`Ctrl+Alt+F`)
- Cancel active tool action (`Ctrl+Alt+C`) for immediate safe exit
- Quick Start onboarding dialog (`Ctrl+Alt+Q`) and dock Start button
- Runtime diagnostics dialog (`Ctrl+Alt+D`) with copyable support report
- Workspace state reset (`Ctrl+Alt+R`) to clear search/recent/favorites/usage in one step
- Usage analytics dialog (`Ctrl+Alt+T`) with per-tool session distribution
- Context help jump (`Help Tool`) that opens the relevant command-reference section
- Runtime health check (`Ctrl+Alt+W`) for layer/edit/snap/workflow readiness
- Shortcut audit (`Ctrl+Alt+Y`) for conflict visibility and safer keymap evolution
- Activation guardrails that block invalid starts (no layer/non-vector/read-only) with guided status messages
- Session checklist (`Ctrl+Alt+G`) to run beta-start controls from one window
- Command palette upgraded with category filter, TR aliases, and usage-priority sorting
- Built-in QGIS smoke test checklist tab in docs for release-candidate verification
- Direct smoke-test opener (`Ctrl+Alt+M`) for one-click QGIS RC validation flow
- Issue template dialog (`Ctrl+Alt+N`) with diagnostics payload for consistent bug reports
- Release readiness dashboard (`Ctrl+Alt+V`) for beta acceptance checks in one view
- Live usage counter in dock for session activity tracking
- Active-layer editability indicator in dock (editable/read-only awareness)
- Dock state persistence between sessions (search/recent/favorites/usage)

## Installation

1. Download the latest `.zip` from [Releases](https://github.com/YusufEminoglu/PlanX-CAD/releases).
2. In QGIS: **Plugins -> Manage and Install Plugins -> Install from ZIP**.
3. Activate **PlanX CAD Toolset** from the plugin list.

## Compatibility

| Requirement | Value |
|---|---|
| QGIS minimum | 3.28 |
| License | GPL-3.0 |

## Changelog

- **1.16.0** - Quick Start onboarding, usage metrics panel, Ctrl+Alt+Q shortcut
- **1.15.0** - Edit ON/OFF + Preflight controls, Ctrl+Alt+F shortcut, layer-state lifecycle hardening
- **1.14.0** - Layer editing toggle, preflight checks, auto layer-state refresh
- **1.13.0** - Cancel active tool, layer edit-state indicator, dock state sync improvements
- **1.12.0** - Global command palette, dock reset controls, shortcut reference sync

## Author

**Yusuf Eminoglu** - [GitHub](https://github.com/YusufEminoglu) | yusuf.eminoglu@deu.edu.tr

Part of the **[PlanX](https://github.com/YusufEminoglu/PlanX)** urban planning plugin suite.
