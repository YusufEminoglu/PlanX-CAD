# -*- coding: utf-8 -*-
"""Interactive straight-chamfer and curved-fillet tool for block corners."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsFeature,
    QgsFeatureRequest, QgsProject, QgsVectorLayer
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband, cleanup_sketcher_rubberband,
)
from .crs_utils import local_metric_crs, transform_geometry, transform_point
from .ada_kirma_dialog import AdaKirmaDialog


def _geometry_for_layer(layer, geometry):
    geometry = QgsGeometry(geometry)
    if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
        geometry.convertToMultiType()
    return geometry


class AdaKirmaSketcher(QgsMapTool):
    """Resolve a corner between two curb lines.

    1. Collect the mode, distance, tolerance, and cleanup threshold.
    2. Click a corner to find two lines and apply the selected solution.
    3. Finish with right-click or Escape.
    """

    sketcher_finished = pyqtSignal()
    sketcher_message = pyqtSignal(str)

    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.iface = iface
        self.canvas = canvas
        self.params = None
        self.preview_rb = None
        self._step = 0
        self._corner_count = 0
        self._activation_cancelled = False

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        self._step = 0
        self._corner_count = 0

        # Collect operation parameters.
        dlg = AdaKirmaDialog(self.iface.mainWindow())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._activation_cancelled = True
            self.sketcher_message.emit("🔶 Block Chamfer — Cancelled")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.GeometryType.PointGeometry
        )
        self._step = 1

        mode_label = (
            "Curved" if self.params["mode"] == "curved" else "Straight"
        )
        self.sketcher_message.emit(
            f"🔶 Block Chamfer ({mode_label}, {self.params['distance']} m) — "
            "Click a corner to resolve | Right-click: Finish"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        super().deactivate()

    def canvasPressEvent(self, event):
        if self._step != 1:
            return

        point = self.toMapCoordinates(event.pos())

        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        if event.button() == Qt.MouseButton.LeftButton:
            self._chamfer_corner(point)

        elif event.button() == Qt.MouseButton.RightButton:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"✅ Block Chamfer — {self._corner_count} corners resolved"
                )
            self.sketcher_finished.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._corner_count > 0:
                self.sketcher_message.emit(
                    f"✅ Block Chamfer — {self._corner_count} corners resolved"
                )
            else:
                self.sketcher_message.emit("🔶 Block Chamfer — Cancelled")
            self.sketcher_finished.emit()

    # ════════════════════════════════════════════════════════════════════════
    # Main corner operation
    # ════════════════════════════════════════════════════════════════════════

    def _chamfer_corner(self, click_point):
        """Resolve the corner nearest the clicked point."""
        p = self.params
        tolerance = p["tolerance"]
        distance = p["distance"]
        mode = p["mode"]
        cleanup_threshold = p["cleanup_threshold"]

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = local_metric_crs(click_point, canvas_crs)
        metric_click = transform_point(click_point, canvas_crs, metric_crs)

        # Find candidate lines around the clicked point.
        candidates = self._find_lines_near_point(
            metric_click, tolerance * 3, metric_crs
        )

        if len(candidates) < 2:
            self.sketcher_message.emit(
                "⚠️ Block Chamfer — At least two lines are required "
                f"(found: {len(candidates)})"
            )
            return

        # Find the nearest intersecting pair and its intersection point.
        pair = self._find_intersecting_pair(
            candidates, metric_click, tolerance
        )

        if pair is None:
            self.sketcher_message.emit(
                "⚠️ Block Chamfer — No intersecting line pair was found"
            )
            return

        layer1, feat1, geom1, layer2, feat2, geom2, int_point = pair

        # Calculate either a straight setback or tangent fillet.
        if mode == "straight":
            trim_dist = distance
            trim1 = self._trim_line_from_point(geom1, int_point, trim_dist)
            trim2 = self._trim_line_from_point(geom2, int_point, trim_dist)
            
            if trim1 is None or trim2 is None:
                self.sketcher_message.emit(
                    "⚠️ Block Chamfer — Lines could not be trimmed"
                )
                return

            trimmed_geom1, cut_pt1 = trim1
            trimmed_geom2, cut_pt2 = trim2
            connection = QgsGeometry.fromPolylineXY([cut_pt1, cut_pt2])
        else:
            # Curved mode uses the configured distance as the fillet radius.
            from ..core.sketcher_utils import create_fillet_and_trims
            
            fillet_result = create_fillet_and_trims(geom1, geom2, distance)
            if not fillet_result:
                self.sketcher_message.emit(
                    "⚠️ Block Chamfer — Fillet arc could not be calculated"
                )
                return
                
            fillet_intersection = QgsPointXY(fillet_result['inter_pt'])
            trim1 = self._trim_line_from_point(
                geom1,
                fillet_intersection,
                fillet_intersection.distance(fillet_result['tp1']),
            )
            trim2 = self._trim_line_from_point(
                geom2,
                fillet_intersection,
                fillet_intersection.distance(fillet_result['tp2']),
            )
            if trim1 is None or trim2 is None:
                self.sketcher_message.emit(
                    "⚠️ Block Chamfer — Tangent points could not be applied"
                )
                return
            trimmed_geom1, _ = trim1
            trimmed_geom2, _ = trim2
            connection = fillet_result['arc']

        # Apply both trims and the connecting segment as grouped edit commands.
        # Existing user edit sessions remain open and are never committed here.
        if not self._apply_corner_edits(
            layer1, feat1, trimmed_geom1,
            layer2, feat2, trimmed_geom2,
            connection, metric_crs,
        ):
            self.sketcher_message.emit(
                "⚠️ Block Chamfer — Changes could not be saved"
            )
            return

        # Remove short remnants left near the resolved corner.
        if cleanup_threshold > 0:
            cleaned = self._clean_remnants(
                metric_click, tolerance * 5, cleanup_threshold,
                (layer1, layer2), metric_crs, connection,
            )
        else:
            cleaned = 0

        # Result
        self._corner_count += 1
        mode_label = "curved" if mode == "curved" else "straight"
        msg = (
            f"🔶 Corner #{self._corner_count} — "
            f"{mode_label} solution applied ({distance} m)"
        )
        if cleaned > 0:
            msg += f" | {cleaned} remnants removed"
        msg += " | Click to continue"
        self.sketcher_message.emit(msg)

    # ════════════════════════════════════════════════════════════════════════
    # Line search
    # ════════════════════════════════════════════════════════════════════════

    def _find_lines_near_point(self, point, search_radius, metric_crs):
        """Find nearby line features around a point.

        Returns:
            list[(QgsVectorLayer, QgsFeature, distance, metric_geometry)]
        """
        results = []
        pt_geom = QgsGeometry.fromPointXY(point)
        search_area = pt_geom.buffer(search_radius, 8)

        for layer in QgsProject.instance().mapLayers().values():
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() != QgsWkbTypes.GeometryType.LineGeometry:
                continue

            layer_search_area = transform_geometry(
                search_area, metric_crs, layer.crs()
            )
            request = QgsFeatureRequest().setFilterRect(
                layer_search_area.boundingBox()
            )
            for feat in layer.getFeatures(request):
                geom = transform_geometry(feat.geometry(), layer.crs(), metric_crs)
                if geom.isEmpty():
                    continue
                dist = geom.distance(pt_geom)
                if dist <= search_radius:
                    results.append((layer, feat, dist, geom))

        # Nearest candidates are evaluated first.
        results.sort(key=lambda x: x[2])
        return results

    def _find_intersecting_pair(self, candidates, click_point, tolerance):
        """Find the nearest intersecting line pair.

        Returns:
            The two layer/feature/geometry records plus intersection, or
            ``None``.
        """
        best = None
        best_dist = float('inf')

        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                l1, f1, _, g1 = candidates[i]
                l2, f2, _, g2 = candidates[j]

                # Use the true intersection, or a virtual one within tolerance.
                if not g1.intersects(g2):
                    int_pt = self._find_near_intersection(g1, g2, tolerance)
                    if int_pt is None:
                        continue
                else:
                    intersection = g1.intersection(g2)
                    if intersection is None or intersection.isEmpty():
                        continue
                    int_pt = self._extract_nearest_point(
                        intersection, click_point
                    )

                if int_pt:
                    dist = click_point.distance(int_pt)
                    if dist < best_dist:
                        best_dist = dist
                        best = (l1, f1, g1, l2, f2, g2, int_pt)

        return best

    def _find_near_intersection(self, geom1, geom2, tolerance):
        """Find a virtual intersection for lines separated by a small gap."""
        closest = geom1.nearestPoint(geom2)
        if closest is None or closest.isEmpty():
            return None

        dist = geom1.distance(geom2)
        if dist <= tolerance:
            return QgsPointXY(closest.asPoint())
        return None

    def _extract_nearest_point(self, geom, reference_point):
        """Extract the point nearest a reference from any geometry."""
        if geom.type() == QgsWkbTypes.GeometryType.PointGeometry:
            if geom.isMultipart():
                pts = geom.asMultiPoint()
                if not pts:
                    return None
                best = min(pts, key=lambda p: reference_point.distance(QgsPointXY(p)))
                return QgsPointXY(best)
            else:
                return QgsPointXY(geom.asPoint())
        else:
            c = geom.centroid()
            if c and not c.isEmpty():
                return QgsPointXY(c.asPoint())
        return None

    # ════════════════════════════════════════════════════════════════════════
    # Geometry operations
    # ════════════════════════════════════════════════════════════════════════

    def _trim_line_from_point(self, geom, int_point, distance):
        """Trim a line back from an intersection by an along-line distance.

        Returns:
            ``(trimmed_geometry, cut_point)`` or ``None``.
        """
        if geom is None or geom.isEmpty() or distance < 0:
            return None

        # Segmentize curved inputs for deterministic vertex-based trimming.
        # ``QgsGeometry.segmentize`` is not available in QGIS 3.28; the
        # in-place conversion below is supported by both QGIS 3 and 4.
        linear = QgsGeometry(geom)
        if linear.requiresConversionToStraightSegments():
            linear.convertToStraightSegment()
        if linear.isMultipart():
            parts = [list(map(QgsPointXY, line)) for line in linear.asMultiPolyline()]
        else:
            parts = [[QgsPointXY(point) for point in linear.asPolyline()]]
        valid_indexes = [index for index, part in enumerate(parts) if len(part) >= 2]
        if not valid_indexes:
            return None

        # Never concatenate multipart lines: trim only the part whose endpoint
        # is nearest the selected corner and preserve every other part.
        part_index = min(
            valid_indexes,
            key=lambda index: min(
                int_point.distance(parts[index][0]),
                int_point.distance(parts[index][-1]),
            ),
        )
        points = parts[part_index]
        from_start = (
            int_point.distance(points[0]) <= int_point.distance(points[-1])
        )
        trimmed = self._trim_points(points, distance, from_start)
        if trimmed is None:
            return None
        new_points, cut_point = trimmed
        parts[part_index] = new_points

        if linear.isMultipart():
            result = QgsGeometry.fromMultiPolylineXY(parts)
        else:
            result = QgsGeometry.fromPolylineXY(new_points)
        return result, cut_point

    @staticmethod
    def _trim_points(points, distance, from_start):
        """Trim an exact along-line distance and return points plus cut point."""
        ordered = points if from_start else list(reversed(points))
        remaining = distance
        for index in range(len(ordered) - 1):
            start = ordered[index]
            end = ordered[index + 1]
            segment_length = start.distance(end)
            if segment_length <= 1e-12:
                continue
            if remaining <= segment_length:
                ratio = max(0.0, min(1.0, remaining / segment_length))
                cut = QgsPointXY(
                    start.x() + ratio * (end.x() - start.x()),
                    start.y() + ratio * (end.y() - start.y()),
                )
                kept = [cut] + ordered[index + 1:]
                if not from_start:
                    kept.reverse()
                # Avoid zero-length two-point results at an exact endpoint.
                if len(kept) < 2 or kept[0].distance(kept[-1]) <= 1e-12:
                    return None
                return kept, cut
            remaining -= segment_length
        return None

    def _point_along_line(self, pts, distance, from_start=True):
        """Return the point at a distance along a line."""
        if from_start:
            remaining = distance
            for i in range(len(pts) - 1):
                seg_len = pts[i].distance(pts[i + 1])
                if remaining <= seg_len:
                    ratio = remaining / seg_len if seg_len > 0 else 0
                    x = pts[i].x() + ratio * (pts[i + 1].x() - pts[i].x())
                    y = pts[i].y() + ratio * (pts[i + 1].y() - pts[i].y())
                    return QgsPointXY(x, y)
                remaining -= seg_len
        else:
            remaining = distance
            for i in range(len(pts) - 1, 0, -1):
                seg_len = pts[i].distance(pts[i - 1])
                if remaining <= seg_len:
                    ratio = remaining / seg_len if seg_len > 0 else 0
                    x = pts[i].x() + ratio * (pts[i - 1].x() - pts[i].x())
                    y = pts[i].y() + ratio * (pts[i - 1].y() - pts[i].y())
                    return QgsPointXY(x, y)
                remaining -= seg_len
        return None

    def _trim_from_start(self, pts, cut_pt):
        """Remove the section between the start and ``cut_pt``."""
        # Keep vertices after the cut point.
        result = [cut_pt]
        total_to_cut = pts[0].distance(cut_pt)

        accumulated = 0
        for i in range(len(pts) - 1):
            seg_len = pts[i].distance(pts[i + 1])
            accumulated += seg_len
            if accumulated >= total_to_cut:
                result.append(pts[i + 1])

        if len(result) < 2:
            result = [cut_pt, pts[-1]]
        return result

    def _trim_from_end(self, pts, cut_pt):
        """Remove the section between the end and ``cut_pt``."""
        result = []
        total_to_cut = pts[-1].distance(cut_pt)

        accumulated = 0
        for i in range(len(pts) - 1, 0, -1):
            seg_len = pts[i].distance(pts[i - 1])
            accumulated += seg_len
            if accumulated >= total_to_cut:
                result.insert(0, pts[i - 1])

        result.append(cut_pt)

        if len(result) < 2:
            result = [pts[0], cut_pt]
        return result


    def _apply_corner_edits(self, layer1, feature1, geometry1,
                            layer2, feature2, geometry2,
                            connection, metric_crs):
        """Apply a corner operation while preserving existing edit sessions."""
        layers = list(dict.fromkeys((layer1, layer2)))
        started = {}

        for layer in layers:
            started[layer] = not layer.isEditable()
            if started[layer] and not layer.startEditing():
                for opened_layer, was_started in started.items():
                    if was_started and opened_layer.isEditable():
                        opened_layer.rollBack()
                return False

        for layer in layers:
            layer.beginEditCommand("Resolve block corner")

        try:
            native_geometry1 = _geometry_for_layer(
                layer1,
                transform_geometry(geometry1, metric_crs, layer1.crs()),
            )
            native_geometry2 = _geometry_for_layer(
                layer2,
                transform_geometry(geometry2, metric_crs, layer2.crs()),
            )
            if not layer1.changeGeometry(feature1.id(), native_geometry1):
                raise RuntimeError("First line could not be trimmed")
            if not layer2.changeGeometry(feature2.id(), native_geometry2):
                raise RuntimeError("Second line could not be trimmed")

            if connection is not None and not connection.isEmpty():
                new_feature = QgsFeature(layer1.fields())
                # A connector is part of the first source line and should keep
                # its classification/style attributes.
                new_feature.setAttributes(feature1.attributes())
                new_feature.setGeometry(_geometry_for_layer(
                    layer1,
                    transform_geometry(connection, metric_crs, layer1.crs()),
                ))
                if not layer1.addFeature(new_feature):
                    raise RuntimeError("Corner connector could not be added")

            for layer in layers:
                layer.endEditCommand()
        except Exception:
            for layer in reversed(layers):
                layer.destroyEditCommand()
            for layer in layers:
                if started[layer]:
                    layer.rollBack()
            return False

        for layer in layers:
            if started[layer] and not layer.commitChanges():
                layer.rollBack()
                return False
            layer.triggerRepaint()
        return True

    # ════════════════════════════════════════════════════════════════════════
    # Remnant cleanup
    # ════════════════════════════════════════════════════════════════════════

    def _clean_remnants(self, center_point, search_radius, min_length,
                        source_layers, metric_crs, protected_geometry=None):
        """Remove short remnant line segments from the two source layers.

        Returns:
            Number of deleted segments.
        """
        cleaned = 0
        point_geometry = QgsGeometry.fromPointXY(center_point)
        search_area = point_geometry.buffer(search_radius, 8)

        # Cleanup is intentionally limited to the two source layers selected
        # for this corner.  Never delete unrelated short lines project-wide.
        for layer in dict.fromkeys(source_layers):
            layer_search_area = transform_geometry(
                search_area, metric_crs, layer.crs()
            )
            request = QgsFeatureRequest().setFilterRect(
                layer_search_area.boundingBox()
            )

            to_delete = []
            for feat in layer.getFeatures(request):
                geom = transform_geometry(feat.geometry(), layer.crs(), metric_crs)
                if geom.isEmpty():
                    continue

                same_as_protected = False
                if protected_geometry is not None:
                    if hasattr(geom, "isExactlyEqual"):
                        same_as_protected = geom.isExactlyEqual(protected_geometry)
                    else:
                        same_as_protected = geom.equals(protected_geometry)
                if same_as_protected:
                    continue

                length = geom.length()
                if length < min_length:
                    # Delete only remnants close to the selected corner.
                    if geom.distance(point_geometry) <= search_radius:
                        to_delete.append(feat.id())

            if to_delete:
                was_editing = layer.isEditable()
                if not was_editing and not layer.startEditing():
                    continue
                layer.beginEditCommand("Remove short line remnants")
                for fid in to_delete:
                    if layer.deleteFeature(fid):
                        cleaned += 1
                layer.endEditCommand()
                if not was_editing and not layer.commitChanges():
                    layer.rollBack()
                layer.triggerRepaint()

        return cleaned
