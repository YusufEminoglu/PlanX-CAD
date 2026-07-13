# -*- coding: utf-8 -*-
"""Road-platform generation from a sketched centre line."""

from qgis.core import (
    QgsFeature, QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsWkbTypes,
)

from ..core.sketcher_layer_utils import (
    get_road_platform_layer,
    road_field_name,
    set_road_attribute,
)
from ..core.sketcher_utils import offset_geometry
from .crs_utils import local_metric_crs, transform_geometry


class RoadGenerator:
    """Generate road-platform components without disturbing user edits."""

    def __init__(self, iface):
        self.iface = iface

    def generate(self, center_geom, params):
        """Generate components and return the number successfully added.

        Canvas coordinates are transformed to a local UTM CRS because dialog
        distances are metres.  Generated geometries are transformed to the
        output layer CRS only at the write boundary.
        """
        if center_geom is None or center_geom.isEmpty():
            return 0

        layer = get_road_platform_layer()
        if layer is None:
            return 0

        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        centroid = center_geom.centroid()
        if centroid is None or centroid.isEmpty():
            return 0
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), canvas_crs)
        metric_center = transform_geometry(center_geom, canvas_crs, metric_crs)
        if metric_center is None or metric_center.isEmpty():
            return 0

        road_type = params["road_type"]
        lane_count = int(params["lane_count"])
        lane_width = float(params["lane_width"])
        median_width = float(params.get("median_width", 0.0))
        left_sidewalk = float(params["left_sidewalk"])
        right_sidewalk = float(params["right_sidewalk"])
        total_width = float(params["total_width"])
        one_way = bool(params.get("one_way", False))
        if lane_count < 1 or lane_width <= 0.0:
            return 0

        base_attrs = {
            "road_id": self._next_road_id(layer),
            "road_type": road_type,
            "lane_count": lane_count,
            "lane_width": lane_width,
            "median_width": median_width,
            "total_width": total_width,
        }

        started_editing = not layer.isEditable()
        if started_editing and not layer.startEditing():
            return 0

        count = 0
        layer.beginEditCommand("Create road platform")

        def add(geometry, attributes):
            nonlocal count
            if geometry is None or geometry.isEmpty():
                raise RuntimeError("Required road component has no geometry")
            output_geometry = transform_geometry(geometry, metric_crs, layer.crs())
            if output_geometry is None or output_geometry.isEmpty():
                raise RuntimeError("Road component transform returned no geometry")
            if not self._add(layer, output_geometry, attributes):
                raise RuntimeError("Road component could not be added")
            count += 1

        try:
            center_attrs = {
                **base_attrs,
                "component": "centerline",
                "side": "none",
                "lane_no": 0,
                "sidewalk_width": 0,
                "visible": 0,
            }
            add(metric_center, center_attrs)

            if one_way:
                self._generate_one_way(
                    metric_center, base_attrs, lane_count, lane_width,
                    left_sidewalk, right_sidewalk, add,
                )
            else:
                self._generate_two_way(
                    metric_center, base_attrs, lane_count, lane_width,
                    median_width, left_sidewalk, right_sidewalk, add,
                )

            layer.endEditCommand()
            if started_editing and not layer.commitChanges():
                layer.rollBack()
                return 0
        except Exception:
            layer.destroyEditCommand()
            if started_editing:
                layer.rollBack()
            return 0

        layer.triggerRepaint()
        return count

    @staticmethod
    def _generate_one_way(center_geom, base_attrs, lane_count, lane_width,
                          left_sidewalk, right_sidewalk, add):
        platform_width = lane_count * lane_width
        left_edge = platform_width / 2.0

        for lane_index in range(lane_count + 1):
            signed_offset = left_edge - lane_index * lane_width
            side = "left" if signed_offset > 0 else "right"
            distance = abs(signed_offset)
            geometry = (
                center_geom if distance < 0.001
                else offset_geometry(center_geom, distance, side)
            )
            attributes = {
                **base_attrs,
                "component": "lane",
                "side": (
                    "left" if lane_index == 0
                    else "right" if lane_index == lane_count
                    else "center"
                ),
                "lane_no": lane_index,
                "sidewalk_width": 0,
                "visible": int(lane_index in (0, lane_count)),
            }
            add(geometry, attributes)

        for side, side_label, width in (
            ("left", "left", left_sidewalk),
            ("right", "right", right_sidewalk),
        ):
            if width > 0:
                add(
                    offset_geometry(center_geom, left_edge + width, side),
                    {
                        **base_attrs,
                        "component": "sidewalk",
                        "side": side_label,
                        "lane_no": 0,
                        "sidewalk_width": width,
                        "visible": 1,
                    },
                )

    @staticmethod
    def _generate_two_way(center_geom, base_attrs, lane_count, lane_width,
                          median_width, left_sidewalk, right_sidewalk, add):
        if median_width > 0:
            for side_label, side in (("left", "left"), ("right", "right")):
                add(
                    offset_geometry(center_geom, median_width / 2.0, side),
                    {
                        **base_attrs,
                        "component": "median",
                        "side": side_label,
                        "lane_no": 0,
                        "sidewalk_width": 0,
                        "visible": 1,
                    },
                )

        for lane_index in range(1, lane_count + 1):
            distance = median_width / 2.0 + lane_index * lane_width
            for side_label, side in (("left", "left"), ("right", "right")):
                add(
                    offset_geometry(center_geom, distance, side),
                    {
                        **base_attrs,
                        "component": "lane",
                        "side": side_label,
                        "lane_no": lane_index,
                        "sidewalk_width": 0,
                        "visible": int(lane_index == lane_count),
                    },
                )

        road_edge = median_width / 2.0 + lane_count * lane_width
        for side, side_label, width in (
            ("left", "left", left_sidewalk),
            ("right", "right", right_sidewalk),
        ):
            if width > 0:
                add(
                    offset_geometry(center_geom, road_edge + width, side),
                    {
                        **base_attrs,
                        "component": "sidewalk",
                        "side": side_label,
                        "lane_no": 0,
                        "sidewalk_width": width,
                        "visible": 1,
                    },
                )

    @staticmethod
    def _add(layer, geometry, attributes):
        geometry = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
            geometry.convertToMultiType()
        feature = QgsFeature(layer.fields())
        feature.setGeometry(geometry)
        for field_name, value in attributes.items():
            set_road_attribute(feature, layer, field_name, value)
        return layer.addFeature(feature)

    @staticmethod
    def _next_road_id(layer):
        index = layer.fields().indexOf(road_field_name(layer, "road_id"))
        if index < 0:
            return 1
        maximum = 0
        request = QgsFeatureRequest()
        request.setSubsetOfAttributes([index])
        request.setFlags(QgsFeatureRequest.Flag.NoGeometry)
        for feature in layer.getFeatures(request):
            value = feature.attribute(index)
            try:
                maximum = max(maximum, int(value))
            except (TypeError, ValueError):
                continue
        return maximum + 1
