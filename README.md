# PlanX CAD Toolset

**A lightweight, fast CAD toolset for urban planning in QGIS — part of the PlanX suite**

PlanX CAD Toolset brings 18+ CAD-like drawing and editing operations directly into QGIS through a modern dockable panel. Designed specifically for urban planners and GIS professionals who need drafting-grade tools without leaving QGIS.

---

## Features

### Drawing Tools
- Line, Polyline, Rectangle, Polygon, Circle, Arc

### Editing Tools
- Offset, Trim, Extend, Fillet, Mirror, Move, Copy, Rotate, Scale, Buffer

### Measurement Tools
- Distance and area measurement (standalone and selection-based)

### Urban Planning Tools
- **Road Platform Generator** — interactive road cross-section design with lane configuration
- **Block Chamfering** — EasyFillet-powered corner rounding for urban blocks
- **Junction Topology Fixer** — clean A-B road intersection connections

### UI
- Modern dockable panel with icon-based toolbar
- Native QGIS snapping support
- Custom 'O' cursor for precision placement

## Installation

1. Download the latest `.zip` from [Releases](https://github.com/YusufEminoglu/PlanX-CAD/releases).
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Activate **PlanX CAD Toolset** from the plugin list.

## Compatibility

| Requirement | Value |
|---|---|
| QGIS minimum | 3.28 |
| License | GPL-3.0 |

## Changelog

- **1.1.0** — Fixed intersection topology, EasyFillet integration, custom cursor, improved measurements
- **1.0.0** — Initial release: 18 CAD tools, dockable interface, road platform tool

## Author

**Yusuf Eminoglu** — [GitHub](https://github.com/YusufEminoglu) | geospacephilo@gmail.com

Part of the **[PlanX](https://github.com/YusufEminoglu/PlanX)** urban planning plugin suite.
