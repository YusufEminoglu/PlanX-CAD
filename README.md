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
- Ctrl+Shift keyboard workflow with repeat-last-tool action
- Dedicated construction modes in dock (infinite/ray/segment) and built-in shortcut guide dialog
- Built-in HTML command manual and separate shortcut reference page (open via Docs/Keys buttons)

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

- **1.10.0** - HTML command reference, HTML shortcut map, Docs/Keys quick buttons, command-reference menu action
- **1.9.0** - Beta hardening: construction mode buttons, advanced shortcuts, shortcut guide dialog
- **1.8.0** - Beta completion candidate: quick tool search, recent tools strip, dock/shortcut activation sync
- **1.7.0** - Hatch and construction line tools
- **1.6.0** - Join, divide, multi-offset and compact bilingual UI pass

## Author

**Yusuf Eminoglu** - [GitHub](https://github.com/YusufEminoglu) | yusuf.eminoglu@deu.edu.tr

Part of the **[PlanX](https://github.com/YusufEminoglu/PlanX)** urban planning plugin suite.
