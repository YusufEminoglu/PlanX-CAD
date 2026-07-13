# -*- coding: utf-8 -*-
"""Road-platform generation from a sketched centre line."""

from qgis.core import (
    QgsFeature, QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsWkbTypes,
)

from ..core.sketcher_layer_utils import get_road_platform_layer
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

        yol_tipi = params["yol_tipi"]
        serit_sayisi = int(params["serit_sayisi"])
        serit_gen = float(params["serit_genisligi"])
        refuj_gen = float(params.get("refuj_genislik", 0.0))
        sol_k = float(params["sol_kaldirim"])
        sag_k = float(params["sag_kaldirim"])
        toplam_gen = float(params["toplam_genislik"])
        tek_yon = bool(params.get("tek_yon", False))
        if serit_sayisi < 1 or serit_gen <= 0.0:
            return 0

        base_attrs = {
            "yol_id": self._next_road_id(layer),
            "yol_tipi": yol_tipi,
            "serit_sayisi": serit_sayisi,
            "serit_genisligi": serit_gen,
            "refuj_genislik": refuj_gen,
            "toplam_genislik": toplam_gen,
        }

        started_editing = not layer.isEditable()
        if started_editing and not layer.startEditing():
            return 0

        count = 0
        layer.beginEditCommand("Yol platformu oluştur")

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
                "bilesen": "center",
                "taraf": "none",
                "serit_no": 0,
                "kaldirim_genislik": 0,
                "gorunur": 0,
            }
            add(metric_center, center_attrs)

            if tek_yon:
                self._generate_one_way(
                    metric_center, base_attrs, serit_sayisi, serit_gen,
                    sol_k, sag_k, add,
                )
            else:
                self._generate_two_way(
                    metric_center, base_attrs, serit_sayisi, serit_gen,
                    refuj_gen, sol_k, sag_k, add,
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
                "bilesen": "serit",
                "taraf": (
                    "sol" if lane_index == 0
                    else "sag" if lane_index == lane_count
                    else "orta"
                ),
                "serit_no": lane_index,
                "kaldirim_genislik": 0,
                "gorunur": int(lane_index in (0, lane_count)),
            }
            add(geometry, attributes)

        for side, taraf, width in (
            ("left", "sol", left_sidewalk),
            ("right", "sag", right_sidewalk),
        ):
            if width > 0:
                add(
                    offset_geometry(center_geom, left_edge + width, side),
                    {
                        **base_attrs,
                        "bilesen": "kaldirim",
                        "taraf": taraf,
                        "serit_no": 0,
                        "kaldirim_genislik": width,
                        "gorunur": 1,
                    },
                )

    @staticmethod
    def _generate_two_way(center_geom, base_attrs, lane_count, lane_width,
                          median_width, left_sidewalk, right_sidewalk, add):
        if median_width > 0:
            for taraf, side in (("sol", "left"), ("sag", "right")):
                add(
                    offset_geometry(center_geom, median_width / 2.0, side),
                    {
                        **base_attrs,
                        "bilesen": "refuj",
                        "taraf": taraf,
                        "serit_no": 0,
                        "kaldirim_genislik": 0,
                        "gorunur": 1,
                    },
                )

        for lane_index in range(1, lane_count + 1):
            distance = median_width / 2.0 + lane_index * lane_width
            for taraf, side in (("sol", "left"), ("sag", "right")):
                add(
                    offset_geometry(center_geom, distance, side),
                    {
                        **base_attrs,
                        "bilesen": "serit",
                        "taraf": taraf,
                        "serit_no": lane_index,
                        "kaldirim_genislik": 0,
                        "gorunur": int(lane_index == lane_count),
                    },
                )

        road_edge = median_width / 2.0 + lane_count * lane_width
        for side, taraf, width in (
            ("left", "sol", left_sidewalk),
            ("right", "sag", right_sidewalk),
        ):
            if width > 0:
                add(
                    offset_geometry(center_geom, road_edge + width, side),
                    {
                        **base_attrs,
                        "bilesen": "kaldirim",
                        "taraf": taraf,
                        "serit_no": 0,
                        "kaldirim_genislik": width,
                        "gorunur": 1,
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
            index = layer.fields().indexOf(field_name)
            if index >= 0:
                feature.setAttribute(index, value)
        return layer.addFeature(feature)

    @staticmethod
    def _next_road_id(layer):
        index = layer.fields().indexOf("yol_id")
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
