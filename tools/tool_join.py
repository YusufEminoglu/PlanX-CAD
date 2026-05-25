# -*- coding: utf-8 -*-
"""planX CAD â€” Join (BirleÅŸtirme) Tool.

Interactive tool to select multiple lines/polylines and weld them together
into a single continuous feature, with customizable gap tolerance.
Supports full Undo/Redo integration.
"""
from __future__ import annotations

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.core import (
    QgsGeometry, QgsPointXY, QgsWkbTypes, QgsFeature, QgsProject
)
from .tool_base import tool_base


def join_polylines(geoms: list[QgsGeometry], tolerance: float = 0.01) -> list[QgsGeometry]:
    """Iteratively welds polylines together that meet within tolerance."""
    paths: list[list[QgsPointXY]] = []
    for geom in geoms:
        if geom.isEmpty():
            continue
        if geom.isMultipart():
            for part in geom.asMultiPolyline():
                paths.append([QgsPointXY(pt) for pt in part])
        else:
            paths.append([QgsPointXY(pt) for pt in geom.asPolyline()])

    if not paths:
        return []

    changed = True
    while changed and len(paths) > 1:
        changed = False
        i = 0
        while i < len(paths) and not changed:
            path_a = paths[i]
            j = i + 1
            while j < len(paths) and not changed:
                path_b = paths[j]
                
                a_start, a_end = path_a[0], path_a[-1]
                b_start, b_end = path_b[0], path_b[-1]
                
                def dist(p1, p2):
                    return math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
                
                # Case 1: A_end touches B_start
                if dist(a_end, b_start) <= tolerance:
                    paths[i] = path_a + path_b[1:]
                    paths.pop(j)
                    changed = True
                # Case 2: A_end touches B_end
                elif dist(a_end, b_end) <= tolerance:
                    paths[i] = path_a + path_b[::-1][1:]
                    paths.pop(j)
                    changed = True
                # Case 3: A_start touches B_start
                elif dist(a_start, b_start) <= tolerance:
                    paths[i] = path_a[::-1] + path_b[1:]
                    paths.pop(j)
                    changed = True
                # Case 4: A_start touches B_end
                elif dist(a_start, b_end) <= tolerance:
                    paths[i] = path_b + path_a[1:]
                    paths.pop(j)
                    changed = True
                else:
                    j += 1
            if not changed:
                i += 1

    # Convert remaining paths back to QgsGeometry
    result_geoms = []
    for path in paths:
        if len(path) >= 2:
            result_geoms.append(QgsGeometry.fromPolylineXY(path))
    return result_geoms


class tool_join(tool_base):
    """Welds multiple separate line segments into a continuous line."""

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.require_editable = True
        self.features_to_join: list[QgsFeature] = []

    def tool_name(self):
        return "Join / BirleÅŸtir"

    def activate(self):
        super().activate()
        self.features_to_join = []
        if self.highlight_rb:
            self.highlight_rb.reset()
        self.tool_message.emit(
            "ðŸ”— Join â€” Select first line / Ã‡izgileri BirleÅŸtir â€” Ä°lk Ã§izgiyi seÃ§in"
        )

    def deactivate(self):
        self.features_to_join = []
        if self.highlight_rb:
            self.highlight_rb.reset()
        super().deactivate()

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        snapped = self._snap_point(event.pos())
        if snapped is not None:
            point = snapped

        if event.button() == Qt.MouseButton.LeftButton:
            result = self._pick_feature(event.pos())
            if result:
                layer, feature = result
                geom = feature.geometry()
                if geom is None or geom.isEmpty() or geom.type() != QgsWkbTypes.LineGeometry:
                    self.tool_message.emit(
                        "âš ï¸ Only line/polyline features can be joined / Sadece Ã§izgiler birleÅŸtirilebilir"
                    )
                    return
                
                # Check if already added
                feat_ids = [f.id() for f in self.features_to_join]
                if feature.id() not in feat_ids:
                    if not self.features_to_join:
                        self.selected_layer = layer
                    elif layer != self.selected_layer:
                        # Must be from the same layer
                        self.tool_message.emit(
                            "âš ï¸ Features must belong to the same layer / Objeler aynÄ± katmana ait olmalÄ±"
                        )
                        return
                    
                    self.features_to_join.append(feature)
                    self.tool_message.emit(
                        f"ðŸ”— Join â€” {len(self.features_to_join)} lines selected. Right-click or Enter to weld | "
                        f"Ã‡izgileri BirleÅŸtir â€” {len(self.features_to_join)} Ã§izgi seÃ§ildi. BirleÅŸtirmek iÃ§in SaÄŸ TÄ±k veya Enter."
                    )
                    self._update_highlights()
                else:
                    self.tool_message.emit(
                        "âš ï¸ Line already selected / Bu Ã§izgi zaten seÃ§ildi"
                    )
            else:
                self.tool_message.emit(
                    "âš ï¸ No feature found / Obje bulunamadÄ±"
                )
                
        elif event.button() == Qt.MouseButton.RightButton:
            if len(self.features_to_join) >= 2:
                self._do_join()
            else:
                self.tool_message.emit(
                    "âš ï¸ Select at least 2 lines to join / BirleÅŸtirmek iÃ§in en az 2 Ã§izgi seÃ§melisiniz"
                )
                self._reset()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if len(self.features_to_join) >= 2:
                self._do_join()
            else:
                self.tool_message.emit(
                    "âš ï¸ Select at least 2 lines to join / BirleÅŸtirmek iÃ§in en az 2 Ã§izgi seÃ§melisiniz"
                )
                self._reset()
        elif event.key() == Qt.Key.Key_Escape:
            self._reset()

    def _update_highlights(self):
        if not self.features_to_join or not self.highlight_rb:
            if self.highlight_rb:
                self.highlight_rb.reset()
            return
        
        geoms = [f.geometry() for f in self.features_to_join]
        combined = QgsGeometry.collectGeometry(geoms)
        self.highlight_rb.reset(QgsWkbTypes.LineGeometry)
        self.highlight_rb.setToGeometry(combined, None)

    def _do_join(self):
        layer = self.selected_layer
        if layer is None:
            self._reset()
            return

        # Prompt for tolerance
        tolerance, ok = QInputDialog.getDouble(
            self.iface.mainWindow(),
            "Join / BirleÅŸtir",
            "Join Tolerance / BirleÅŸtirme ToleransÄ± (m):",
            1.0, 0.0, 1000.0, 2
        )
        if not ok:
            self.tool_message.emit(
                "âš ï¸ Join cancelled / BirleÅŸtirme iptal edildi"
            )
            self._reset()
            return

        geoms = [f.geometry() for f in self.features_to_join]
        joined_geoms = join_polylines(geoms, tolerance)

        if not joined_geoms:
            self.tool_message.emit(
                "âš ï¸ Join failed: No matching endpoints / BirleÅŸtirme baÅŸarÄ±sÄ±z: UÃ§lar eÅŸleÅŸmedi"
            )
            self._reset()
            return

        # Merge geometries
        if len(joined_geoms) == 1:
            final_geom = joined_geoms[0]
        else:
            final_geom = QgsGeometry.collectGeometry(joined_geoms)

        # Start edit block
        if not layer.isEditable():
            layer.startEditing()

        layer.beginEditCommand("Join / Ã‡izgileri BirleÅŸtir")
        try:
            # Update first feature in-place
            f1 = self.features_to_join[0]
            layer.changeGeometry(f1.id(), final_geom)
            
            # Delete other features
            other_ids = [f.id() for f in self.features_to_join[1:]]
            layer.deleteFeatures(other_ids)
            
            layer.endEditCommand()
            layer.triggerRepaint()
            
            self.tool_message.emit(
                f"âœ… Joined {len(self.features_to_join)} segments into {len(joined_geoms)} polylines / "
                f"{len(self.features_to_join)} segment {len(joined_geoms)} Ã§izgi olarak birleÅŸtirildi"
            )
        except Exception as e:
            layer.destroyEditCommand()
            self.tool_message.emit(
                f"âš ï¸ Error joining / BirleÅŸtirme hatasÄ±: {e}"
            )

        self._reset()

    def _reset(self):
        self.features_to_join = []
        if self.highlight_rb:
            self.highlight_rb.reset()
        super()._reset()
