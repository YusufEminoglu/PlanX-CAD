# -*- coding: utf-8 -*-
"""
planX CAD — Yol Platformu Üretici
Orta çizgiden offset ile yol bileşenlerini üreten modül.
"""

from qgis.core import QgsGeometry, QgsFeature, QgsFeatureSink
from ..core.sketcher_utils import offset_geometry
from ..core.sketcher_layer_utils import get_road_platform_layer, add_feature_to_layer


class RoadGenerator:
    """Orta çizgiden yol platformu üretir."""

    def __init__(self, iface):
        self.iface = iface

    def generate(self, center_geom, params):
        """Orta çizgiden yol platformu üretir.

        Args:
            center_geom: QgsGeometry — yol orta çizgisi
            params: dict — RoadDialog'dan gelen parametreler

        Returns:
            int — üretilen feature sayısı
        """
        if center_geom is None or center_geom.isEmpty():
            return 0

        layer = get_road_platform_layer()
        if layer is None:
            return 0

        yol_tipi = params["yol_tipi"]
        serit_sayisi = params["serit_sayisi"]
        serit_gen = params["serit_genisligi"]
        refuj_gen = params.get("refuj_genislik", 0.0)
        sol_k = params["sol_kaldirim"]
        sag_k = params["sag_kaldirim"]
        toplam_gen = params["toplam_genislik"]
        tek_yon = params.get("tek_yon", False)

        # Yol ID'si hesapla (mevcut max + 1)
        yol_id = self._next_road_id(layer)

        count = 0
        base_attrs = {
            "yol_id": yol_id,
            "yol_tipi": yol_tipi,
            "serit_sayisi": serit_sayisi,
            "serit_genisligi": serit_gen,
            "refuj_genislik": refuj_gen,
            "toplam_genislik": toplam_gen,
        }

        layer.startEditing()

        # ── 1. Tek Yönlü (One-Way) Çizim Mantığı ─────────────────────────
        if tek_yon:
            # Tek yön ise tüm şeritler yan yanadır. Merkez çizgi yol platformunun tam ortasından geçer.
            platform_genisligi = serit_sayisi * serit_gen
            left_edge = platform_genisligi / 2.0
            
            # Merkez çizgiyi (Center) çiz (gorunmaz)
            attrs = {**base_attrs, "bilesen": "center", "taraf": "none", "serit_no": 0, "kaldirim_genislik": 0, "gorunur": 0}
            self._add(layer, center_geom, attrs)
            count += 1
            
            # Şerit Sınırları
            for i in range(serit_sayisi + 1):
                offset_dist = left_edge - (i * serit_gen)
                # offset > 0 means left, offset < 0 means right
                side = "left" if offset_dist > 0 else "right"
                dist = abs(offset_dist)
                
                gorunur = 1 if (i == 0 or i == serit_sayisi) else 0
                taraf = "sol" if i == 0 else ("sag" if i == serit_sayisi else "orta")
                
                geom = center_geom if dist < 0.001 else offset_geometry(center_geom, dist, side)
                if geom:
                    attrs = {**base_attrs, "bilesen": "serit", "taraf": taraf, "serit_no": i, "kaldirim_genislik": 0, "gorunur": gorunur}
                    self._add(layer, geom, attrs)
                    count += 1

            # Sol kaldırım
            if sol_k > 0:
                geom = offset_geometry(center_geom, left_edge + sol_k, "left")
                if geom:
                    attrs = {**base_attrs, "bilesen": "kaldirim", "taraf": "sol", "kaldirim_genislik": sol_k, "gorunur": 1}
                    self._add(layer, geom, attrs)
                    count += 1

            # Sağ kaldırım
            if sag_k > 0:
                geom = offset_geometry(center_geom, left_edge + sag_k, "right")
                if geom:
                    attrs = {**base_attrs, "bilesen": "kaldirim", "taraf": "sag", "kaldirim_genislik": sag_k, "gorunur": 1}
                    self._add(layer, geom, attrs)
                    count += 1

        # ── 2. Çift Yönlü (Two-Way) Çizim Mantığı ────────────────────────
        else:
            # Merkez çizgi
            attrs = {**base_attrs, "bilesen": "center", "taraf": "none", "serit_no": 0, "kaldirim_genislik": 0, "gorunur": 0}
            self._add(layer, center_geom, attrs)
            count += 1

            # Refüj çizgileri
            if refuj_gen > 0:
                half_refuj = refuj_gen / 2.0
                for taraf, side in [("sol", "left"), ("sag", "right")]:
                    geom = offset_geometry(center_geom, half_refuj, side)
                    if geom:
                        attrs = {**base_attrs, "bilesen": "refuj", "taraf": taraf, "serit_no": 0, "kaldirim_genislik": 0, "gorunur": 1}
                        self._add(layer, geom, attrs)
                        count += 1

            # Şerit çizgileri
            for i in range(1, serit_sayisi + 1):
                offset_dist = (refuj_gen / 2.0) + (i * serit_gen)
                for taraf, side in [("sol", "left"), ("sag", "right")]:
                    geom = offset_geometry(center_geom, offset_dist, side)
                    if geom:
                        gorunur = 1 if i == serit_sayisi else 0
                        attrs = {**base_attrs, "bilesen": "serit", "taraf": taraf, "serit_no": i, "kaldirim_genislik": 0, "gorunur": gorunur}
                        self._add(layer, geom, attrs)
                        count += 1

            # Kaldırım çizgileri
            yol_kenari = (refuj_gen / 2.0) + (serit_sayisi * serit_gen)

            if sol_k > 0:
                geom = offset_geometry(center_geom, yol_kenari + sol_k, "left")
                if geom:
                    attrs = {**base_attrs, "bilesen": "kaldirim", "taraf": "sol", "serit_no": 0, "kaldirim_genislik": sol_k, "gorunur": 1}
                    self._add(layer, geom, attrs)
                    count += 1

            if sag_k > 0:
                geom = offset_geometry(center_geom, yol_kenari + sag_k, "right")
                if geom:
                    attrs = {**base_attrs, "bilesen": "kaldirim", "taraf": "sag", "serit_no": 0, "kaldirim_genislik": sag_k, "gorunur": 1}
                    self._add(layer, geom, attrs)
                    count += 1

        layer.commitChanges()
        layer.triggerRepaint()
        return count

    def _add(self, layer, geometry, attributes):
        """Katmana feature ekle."""
        feat = QgsFeature(layer.fields())
        feat.setGeometry(geometry)
        for field_name, value in attributes.items():
            idx = layer.fields().indexOf(field_name)
            if idx >= 0:
                feat.setAttribute(idx, value)
        layer.addFeature(feat)

    def _next_road_id(self, layer):
        """Bir sonraki yol ID'sini hesapla."""
        max_id = 0
        idx = layer.fields().indexOf("yol_id")
        if idx < 0:
            return 1
        for feat in layer.getFeatures():
            val = feat.attribute(idx)
            if val and int(val) > max_id:
                max_id = int(val)
        return max_id + 1
