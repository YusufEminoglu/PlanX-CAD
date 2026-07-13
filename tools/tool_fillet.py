# -*- coding: utf-8 -*-
"""planX CAD — Fillet Aracı
İki çizgi seçerek köşeyi yuvarlatan gelişmiş fillet.
"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.PyQt.QtWidgets import QInputDialog
from .tool_base import tool_base
from ..core.sketcher_feedback import create_preview_rubberband, COLOR_ACCENT
from ..core.sketcher_utils import create_fillet_and_trims, trim_line_to_point
from ..urban.crs_utils import local_metric_crs, transform_geometry


class tool_fillet(tool_base):
    """İki kesişen çizgi arasında fillet (yuvarlatma) yapar.
    1. Fillet yarıçapı gir
    2. Birinci çizgiyi seç
    3. İkinci çizgiyi seç
    → Kesişim noktasında yarıçaplı ark oluşturulur
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.radius = 2.0
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._activation_cancelled = False

    def tool_name(self):
        return "Fillet"

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        r, ok = QInputDialog.getDouble(
            self.iface.mainWindow(), "Fillet", "Fillet yarıçapı (m):",
            self.radius, 0.01, 10000.0, 2
        )
        if ok:
            self.radius = r
        else:
            self._activation_cancelled = True
            self.tool_message.emit("⌒ Fillet — İptal edildi")
            return
        self.first_layer = None
        self.first_feature = None
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius}m) — Birinci çizgiyi seçin"
        )

    def on_entity_selected(self, layer, feature, point):
        # Birinci çizgi seçildi
        self.first_layer = layer
        self.first_feature = feature
        self.first_point = point
        self._step = 2
        self.tool_message.emit(
            f"⌒ Fillet (R={self.radius}m) — İkinci çizgiyi seçin"
        )

    def on_click(self, point, button):
        if self._step == 2 and button == Qt.MouseButton.LeftButton:
            # Birinci çizgi dışlanır — çizgi kendisiyle fillet edilemez
            result = self._pick_feature(
                self.canvas.mouseLastXY(),
                exclude=(self.first_layer, self.first_feature),
            )
            if result:
                layer, feature = result
                self._do_fillet(layer, feature, point)
            else:
                self.tool_message.emit("⚠️ Fillet — İkinci obje bulunamadı")
            self._cleanup_fillet()

    def _do_fillet(self, second_layer, second_feature, point):
        """İki çizgi arasında fillet uygula (EasyFillet mimarisi)."""
        metric_crs, fillet_result = self._metric_fillet_result(
            self.first_feature.geometry(), self.first_layer,
            second_feature.geometry(), second_layer,
        )
        if metric_crs is None or not fillet_result:
            self.tool_message.emit("⚠️ Fillet — CRS dönüşümü başarısız")
            return

        arc_geom = fillet_result['arc']
        tp1 = fillet_result['tp1']
        tp2 = fillet_result['tp2']
        inter_pt = fillet_result.get('inter_pt')
        metric_geom1 = transform_geometry(
            self.first_feature.geometry(), self.first_layer.crs(), metric_crs
        )
        metric_geom2 = transform_geometry(
            second_feature.geometry(), second_layer.crs(), metric_crs
        )

        new_geom1 = transform_geometry(
            trim_line_to_point(metric_geom1, tp1, inter_pt),
            metric_crs, self.first_layer.crs(),
        )
        new_geom2 = transform_geometry(
            trim_line_to_point(metric_geom2, tp2, inter_pt),
            metric_crs, second_layer.crs(),
        )
        arc_geom = transform_geometry(
            arc_geom, metric_crs, self.first_layer.crs()
        )
        if any(
            geom is None or geom.isEmpty()
            for geom in (new_geom1, new_geom2, arc_geom)
        ):
            self.tool_message.emit("⚠️ Fillet — Geçerli sonuç geometrisi oluşmadı")
            return

        new_geom1 = self._coerce_for_layer(new_geom1, self.first_layer)
        new_geom2 = self._coerce_for_layer(new_geom2, second_layer)
        arc_geom = self._coerce_for_layer(arc_geom, self.first_layer)
        layers = []
        for layer in (self.first_layer, second_layer):
            if layer not in layers:
                layers.append(layer)
        for layer in layers:
            layer.beginEditCommand("PlanX CAD: fillet")

        arc_feature = QgsFeature(self.first_layer.fields())
        arc_feature.setGeometry(arc_geom)
        for index in range(self.first_layer.fields().count()):
            arc_feature.setAttribute(index, self.first_feature.attribute(index))

        success = (
            self.first_layer.changeGeometry(self.first_feature.id(), new_geom1)
            and second_layer.changeGeometry(second_feature.id(), new_geom2)
            and self.first_layer.addFeature(arc_feature)
        )
        if not success:
            for layer in reversed(layers):
                layer.destroyEditCommand()
            self.tool_message.emit(
                "⚠️ Fillet — Katman yazma hatası; tüm değişiklikler geri alındı"
            )
            return
        for layer in layers:
            layer.endEditCommand()
            layer.triggerRepaint()
        self.tool_message.emit(
            f"✅ Fillet (R={self.radius}m) — Başarıyla uygulandı"
        )

    def _metric_fillet_result(self, geom1, layer1, geom2, layer2):
        if not layer1.crs().isValid() or not layer2.crs().isValid():
            return None, None
        centroid = geom1.centroid()
        if centroid is None or centroid.isEmpty():
            return None, None
        metric_crs = local_metric_crs(QgsPointXY(centroid.asPoint()), layer1.crs())
        metric_geom1 = transform_geometry(geom1, layer1.crs(), metric_crs)
        metric_geom2 = transform_geometry(geom2, layer2.crs(), metric_crs)
        if (metric_geom1 is None or metric_geom1.isEmpty() or
                metric_geom2 is None or metric_geom2.isEmpty()):
            return None, None
        return metric_crs, create_fillet_and_trims(
            metric_geom1, metric_geom2, self.radius
        )

    @staticmethod
    def _coerce_for_layer(geometry, layer):
        geometry = QgsGeometry(geometry)
        if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
            geometry.convertToMultiType()
        return geometry

    def on_move(self, point):
        """Fare hareket ettikçe ikinci çizgiyi saptayıp on-the-fly preview (önizleme) oluştur."""
        if self._step != 2:
            return

        # preview_rb, _reset/_cleanup sonrasında None olabilir; map tool olay
        # işleyicileri istisnaları sessizce yutar, bu yüzden burada yeniden
        # oluşturmazsak fillet çalışır ama önizleme hiç görünmez.
        if self.preview_rb is None:
            self.preview_rb = create_preview_rubberband(self.canvas)
        self.preview_rb.reset(QgsWkbTypes.LineGeometry)

        pos = self.canvas.mouseLastXY()
        result = self._pick_feature(
            pos, exclude=(self.first_layer, self.first_feature)
        )
        if not result:
            return
        layer, feature = result
        metric_crs, fillet_result = self._metric_fillet_result(
            self.first_feature.geometry(), self.first_layer,
            feature.geometry(), layer,
        )
        if not fillet_result:
            return
        arc_geom = transform_geometry(
            fillet_result['arc'], metric_crs, self.first_layer.crs()
        )
        if arc_geom and not arc_geom.isEmpty():
            # Belirgin turuncu, kalın kesik çizgi — ince mavi önizleme zor görünüyordu.
            self.preview_rb.setColor(COLOR_ACCENT)
            self.preview_rb.setWidth(3)
            self.preview_rb.setLineStyle(Qt.PenStyle.DashLine)
            self.preview_rb.setToGeometry(arc_geom, self.first_layer)
            self.preview_rb.show()

    def _cleanup_fillet(self):
        self.first_layer = None
        self.first_feature = None
        self.first_point = None
        self._reset()
