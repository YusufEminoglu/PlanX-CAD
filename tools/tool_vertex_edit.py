# -*- coding: utf-8 -*-
"""planX CAD — Vertex Edit (insert / move / delete) for polylines & polygons.

Workflow:
  1. Click a feature to pick it. All vertices are rendered as round handles.
  2. Click on a handle and drag to MOVE it; release to commit.
  3. Click between two existing vertices on the line itself to INSERT a new
     vertex at the click point.
  4. Right-click on a handle to DELETE that vertex. Geometry stays valid; if
     fewer than 2 vertices would remain for a line (or < 3 for a polygon),
     the deletion is refused.
  5. Esc clears the selection.

Multipart-safe: edits are applied to the *closest* part.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.gui import QgsRubberBand, QgsVertexMarker

from .tool_base import tool_base


_INSERT_TOL_PX = 8
_HANDLE_HIT_PX = 10


class tool_vertex_edit(tool_base):
    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self._handles: list[QgsVertexMarker] = []
        self._part_indices: list[tuple[int, int]] = []  # (part_idx, vertex_idx) per handle
        self._dragging_index: int | None = None
        self._geom: QgsGeometry | None = None
        self.require_editable = True

    def tool_name(self):
        return "Vertex Edit"

    # ───────────────────────── tool_base hooks ─────────────────────────

    def on_entity_selected(self, layer, feature, point):
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            self.tool_message.emit("⚠️ Vertex Edit — empty geometry")
            self._reset()
            return
        if geom.type() not in (QgsWkbTypes.LineGeometry, QgsWkbTypes.PolygonGeometry):
            self.tool_message.emit("⚠️ Vertex Edit — pick a line or polygon")
            self._reset()
            return
        self._geom = QgsGeometry(geom)
        self._render_handles()
        self._step = 2
        self.tool_message.emit(
            "✏️ Vertex Edit — drag a handle to move | right-click handle to delete | "
            "click on the line to insert | Esc to finish"
        )

    def on_click(self, point, button):
        if self._step != 2 or self._geom is None:
            return
        if button == Qt.LeftButton:
            hit = self._handle_at(point)
            if hit is not None:
                self._dragging_index = hit
                return
            # Otherwise: insert a new vertex if the click is near the line.
            self._try_insert(point)
        elif button == Qt.RightButton:
            hit = self._handle_at(point)
            if hit is not None:
                self._delete_vertex(hit)

    def on_move(self, point):
        if self._dragging_index is None or self._geom is None:
            return
        part_idx, v_idx = self._part_indices[self._dragging_index]
        self._geom.moveVertex(point.x(), point.y(), self._vertex_id_for(part_idx, v_idx))
        # Snap visible markers
        self._handles[self._dragging_index].setCenter(point)
        # Live preview rb mirrors current geometry
        self.preview_rb.reset(self._geom.type())
        self.preview_rb.setToGeometry(self._geom, None)

    def canvasReleaseEvent(self, event):  # type: ignore[override]
        # Commit a move on mouse release
        if self._dragging_index is not None and self._geom is not None:
            self._commit()
            self._dragging_index = None

    # ───────────────────────── Internals ─────────────────────────

    def _clear_handles(self):
        for m in self._handles:
            self.canvas.scene().removeItem(m)
        self._handles.clear()
        self._part_indices.clear()

    def _render_handles(self):
        self._clear_handles()
        if self._geom is None:
            return
        if self._geom.isMultipart():
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                parts = self._geom.asMultiPolyline()
            else:
                parts = [ring for poly in self._geom.asMultiPolygon() for ring in poly]
        else:
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                parts = [self._geom.asPolyline()]
            else:
                parts = self._geom.asPolygon()
        for part_idx, ring in enumerate(parts):
            for v_idx, pt in enumerate(ring):
                marker = QgsVertexMarker(self.canvas)
                marker.setIconType(QgsVertexMarker.ICON_BOX)
                marker.setIconSize(9)
                marker.setPenWidth(2)
                marker.setColor(QColor("#ff6d00"))
                marker.setCenter(QgsPointXY(pt))
                self._handles.append(marker)
                self._part_indices.append((part_idx, v_idx))

    def _vertex_id_for(self, part_idx: int, v_idx: int) -> int:
        """Best-effort linear vertex id by walking ring sizes."""
        if self._geom is None:
            return 0
        offset = 0
        if self._geom.isMultipart():
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                parts = self._geom.asMultiPolyline()
            else:
                parts = [ring for poly in self._geom.asMultiPolygon() for ring in poly]
        else:
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                parts = [self._geom.asPolyline()]
            else:
                parts = self._geom.asPolygon()
        for i, ring in enumerate(parts):
            if i == part_idx:
                return offset + v_idx
            offset += len(ring)
        return 0

    def _handle_at(self, point: QgsPointXY) -> int | None:
        """Return the index of a handle within hit tolerance of `point`."""
        tol = self.canvas.mapUnitsPerPixel() * _HANDLE_HIT_PX
        best, best_d = None, float("inf")
        for i, marker in enumerate(self._handles):
            c = marker.center()
            d = (c.x() - point.x()) ** 2 + (c.y() - point.y()) ** 2
            if d < tol * tol and d < best_d:
                best, best_d = i, d
        return best

    def _try_insert(self, point: QgsPointXY) -> None:
        if self._geom is None:
            return
        tol = self.canvas.mapUnitsPerPixel() * _INSERT_TOL_PX
        # Distance from the click to the geometry; if close enough, insert.
        pt_geom = QgsGeometry.fromPointXY(point)
        if self._geom.distance(pt_geom) > tol:
            return
        # Find the closest segment vertex
        closest = self._geom.closestSegmentWithContext(point)
        # signature: (squaredDistance, minDistPoint, afterVertex, leftOf, epsilon)
        if not closest or len(closest) < 3:
            return
        after_vertex = closest[2]
        self._geom.insertVertex(point.x(), point.y(), after_vertex)
        self._render_handles()
        self.preview_rb.reset(self._geom.type())
        self.preview_rb.setToGeometry(self._geom, None)
        self._commit()
        self.tool_message.emit("✅ Vertex Edit — vertex inserted")

    def _delete_vertex(self, handle_index: int) -> None:
        if self._geom is None:
            return
        part_idx, v_idx = self._part_indices[handle_index]
        # Refuse if it would invalidate the ring
        min_required = 2 if self._geom.type() == QgsWkbTypes.LineGeometry else 4  # ring needs ≥4 (closed)
        # crude per-part length check
        if self._geom.isMultipart():
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                ring_len = len(self._geom.asMultiPolyline()[part_idx])
            else:
                rings_flat = [r for poly in self._geom.asMultiPolygon() for r in poly]
                ring_len = len(rings_flat[part_idx])
        else:
            if self._geom.type() == QgsWkbTypes.LineGeometry:
                ring_len = len(self._geom.asPolyline())
            else:
                ring_len = len(self._geom.asPolygon()[part_idx])
        if ring_len <= min_required:
            self.tool_message.emit("⚠️ Vertex Edit — cannot delete (too few vertices)")
            return
        self._geom.deleteVertex(self._vertex_id_for(part_idx, v_idx))
        self._render_handles()
        self.preview_rb.reset(self._geom.type())
        self.preview_rb.setToGeometry(self._geom, None)
        self._commit()
        self.tool_message.emit("✅ Vertex Edit — vertex deleted")

    def _commit(self) -> None:
        if self._geom is None or self.selected_layer is None or self.selected_feature is None:
            return
        self._apply_edit(self.selected_layer, self.selected_feature, self._geom)

    def deactivate(self):
        self._clear_handles()
        self._geom = None
        super().deactivate()
