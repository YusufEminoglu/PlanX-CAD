# -*- coding: utf-8 -*-
"""PlanX CAD Trim tool.

Uses geometry splitting with a difference fallback for robust trimming across
intersection types.
"""

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsFeature, QgsWkbTypes, QgsGeometry, QgsPointXY
from .tool_base import tool_base


class tool_trim(tool_base):
    """Trim a line against a selected cutting boundary.

    1. Select the cutting boundary | 2. Click the side of the line to remove
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.cutting_layer = None
        self.cutting_feature = None

    def tool_name(self):
        return "Trim"

    def activate(self):
        super().activate()
        self.tool_message.emit("✂️ Trim — Select the cutting boundary")

    def on_entity_selected(self, layer, feature, point):
        self.cutting_layer = layer
        self.cutting_feature = feature
        self._step = 2
        self.tool_message.emit(
            "✂️ Trim — Click the side of the target line to remove"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # Exclude the cutting boundary; a feature cannot trim itself.
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.cutting_layer, self.cutting_feature),
            )
            if result:
                layer, feature = result
                # ``point`` is in the first (cutting) layer CRS because
                # tool_base selected that layer first. Convert it to the
                # target feature CRS before distance-based side selection.
                canvas_point = self.to_canvas_coordinates(
                    point, self.cutting_layer
                )
                target_point = self.to_layer_coordinates(canvas_point, layer)
                self._do_trim(layer, feature, target_point)
            else:
                self.tool_message.emit("⚠️ Trim — No target feature found")

            self._reset()
            self.cutting_layer = None
            self.cutting_feature = None

    def _do_trim(self, layer, feature, click_point):
        """Apply the trim operation in the target layer CRS."""
        target_geom = feature.geometry()
        cutting_geom = self.geometry_to_layer_crs(
            self.cutting_feature.geometry(), self.cutting_layer, layer
        )
        if cutting_geom is None:
            self.tool_message.emit("⚠️ Trim — CRS transformation failed")
            return

        # Verify that the target and cutting boundary intersect.
        if not target_geom.intersects(cutting_geom):
            self.tool_message.emit("⚠️ Trim — The target does not intersect the boundary")
            return

        # Calculate the intersection regardless of its geometry type.
        intersection = target_geom.intersection(cutting_geom)
        if intersection is None or intersection.isEmpty():
            self.tool_message.emit("⚠️ Trim — Could not calculate the intersection")
            return

        # Extract usable split points from the intersection.
        int_points = self._extract_points(intersection)
        if not int_points:
            self.tool_message.emit("⚠️ Trim — Could not extract an intersection point")
            return

        # Split the target line at the intersection points.
        line_pts = self._get_line_points(target_geom)
        if not line_pts or len(line_pts) < 2:
            self.tool_message.emit("⚠️ Trim — Could not read the target line vertices")
            return

        # Sort intersection points by their position along the target line.
        locations = []
        for ip in int_points:
            loc = target_geom.lineLocatePoint(QgsGeometry.fromPointXY(ip))
            locations.append((loc, ip))
        locations.sort(key=lambda x: x[0])

        # Split the line into segments.
        segments = self._split_line_at_points(target_geom, [p for _, p in locations])

        if not segments or len(segments) < 2:
            # Fallback: subtract a narrow buffer around the cutting boundary.
            small_buf = cutting_geom.buffer(0.001, 4)
            diff = target_geom.difference(small_buf)
            if diff and not diff.isEmpty():
                parts = self._explode_multipart(diff)
                if parts:
                    kept = self._keep_farthest(parts, click_point)
                    if kept:
                        if self._apply_edit(layer, feature, kept):
                            self.tool_message.emit("✅ Trim — Trim applied")
                        return
            self.tool_message.emit("⚠️ Trim — Could not split the target line")
            return

        # Remove the segment nearest the click and preserve the others.
        click_geom = QgsGeometry.fromPointXY(click_point)
        min_dist = float('inf')
        remove_idx = 0

        for i, seg in enumerate(segments):
            d = seg.distance(click_geom)
            if d < min_dist:
                min_dist = d
                remove_idx = i

        # Collect the remaining segments.
        remaining = [seg for i, seg in enumerate(segments) if i != remove_idx]

        if remaining:
            if len(remaining) == 1:
                if self._apply_edit(layer, feature, remaining[0]):
                    self.tool_message.emit("✅ Trim — Trim applied")
                return

            if QgsWkbTypes.isMultiType(layer.wkbType()):
                keep_geom = QgsGeometry.collectGeometry(remaining)
                if self._apply_edit(layer, feature, keep_geom):
                    self.tool_message.emit("✅ Trim — Trim applied")
            else:
                # A single-part LineString layer cannot accept a disconnected
                # MultiLineString. Keep one part on the original feature and
                # add the other valid parts as features with copied attributes.
                if self._replace_single_part_feature(layer, feature, remaining):
                    self.tool_message.emit("✅ Trim — Trim applied")
                else:
                    self.tool_message.emit(
                        "⚠️ Trim — Write failed; all changes were rolled back"
                    )
        else:
            self.tool_message.emit("⚠️ Trim — No geometry remains after trimming")

    @staticmethod
    def _replace_single_part_feature(layer, feature, geometries):
        new_features = []
        for geometry in geometries[1:]:
            new_feature = QgsFeature(layer.fields())
            new_feature.setGeometry(geometry)
            for index in range(layer.fields().count()):
                new_feature.setAttribute(index, feature.attribute(index))
            new_features.append(new_feature)

        layer.beginEditCommand("PlanX CAD: trim")
        success = layer.changeGeometry(feature.id(), geometries[0])
        if success and new_features:
            success = layer.addFeatures(new_features)
        if not success:
            layer.destroyEditCommand()
            return False
        layer.endEditCommand()
        layer.triggerRepaint()
        return True

    def _extract_points(self, geom):
        """Extract a point list from any intersection geometry."""
        points = []
        if geom is None or geom.isEmpty():
            return points

        # Expand multipart input into individual geometry parts.
        if geom.isMultipart():
            parts = geom.asGeometryCollection()
        else:
            parts = [geom]

        for part in parts:
            if part.type() == QgsWkbTypes.PointGeometry:
                if part.isMultipart():
                    for p in part.asMultiPoint():
                        points.append(QgsPointXY(p))
                else:
                    points.append(QgsPointXY(part.asPoint()))
            elif part.type() == QgsWkbTypes.LineGeometry:
                # For linear intersections, use their vertices.
                if part.isMultipart():
                    for line in part.asMultiPolyline():
                        for p in line:
                            points.append(QgsPointXY(p))
                else:
                    for p in part.asPolyline():
                        points.append(QgsPointXY(p))
            else:
                # Use a centroid for other geometry types.
                c = part.centroid()
                if c and not c.isEmpty():
                    points.append(QgsPointXY(c.asPoint()))

        return points

    def _get_line_points(self, geom):
        """Return the line vertices from a geometry."""
        if geom.isMultipart():
            lines = geom.asMultiPolyline()
            if lines:
                pts = []
                for line in lines:
                    pts.extend([QgsPointXY(p) for p in line])
                return pts
        else:
            return [QgsPointXY(p) for p in geom.asPolyline()]
        return []

    def _split_line_at_points(self, line_geom, split_points):
        """Split a line at the supplied points."""
        # Apply each split to every current part. splitGeometry mutates only
        # the geometry it is invoked on; the old implementation kept newly
        # created parts aside, so a second intersection falling on one of
        # those parts was silently ignored.
        all_parts = [QgsGeometry(line_geom)]
        for sp in split_points:
            next_parts = []
            for part in all_parts:
                candidate = QgsGeometry(part)
                # QGIS 3/4 returns (OperationResult, new_geoms, topo_pts).
                result = candidate.splitGeometry([sp], False)
                new_geoms = result[1] if len(result) > 1 else []
                next_parts.append(candidate if new_geoms else part)
                next_parts.extend(new_geoms)
            all_parts = next_parts

        # Discard empty parts.
        return [p for p in all_parts if p and not p.isEmpty()]

    def _explode_multipart(self, geom):
        """Expand multipart geometry into individual parts."""
        if geom.isMultipart():
            return geom.asGeometryCollection()
        return [geom]

    def _keep_farthest(self, parts, click_point):
        """Return the part farthest from the clicked point."""
        click_geom = QgsGeometry.fromPointXY(click_point)
        max_dist = -1
        best = None
        for p in parts:
            d = p.distance(click_geom)
            if d > max_dist:
                max_dist = d
                best = p
        return best
