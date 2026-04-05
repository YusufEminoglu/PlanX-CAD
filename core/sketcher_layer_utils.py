# -*- coding: utf-8 -*-
"""
planX CAD — Katman Yönetim Yardımcıları
Otomatik katman oluşturma, feature ekleme ve öznitelik yönetimi.
"""

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFields,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsFeatureSink
)


def get_or_create_layer(layer_name, geom_type="MultiLineString", crs=None,
                        fields=None):
    """Katmanı bul veya oluştur.

    Args:
        layer_name: str — katman adı
        geom_type: str — 'Point', 'LineString', 'MultiLineString', 'Polygon'
        crs: QgsCoordinateReferenceSystem (varsayılan: proje CRS)
        fields: list[tuple(name, type)] — öznitelik alanları

    Returns:
        QgsVectorLayer
    """
    project = QgsProject.instance()

    # Mevcut katmanı ara
    existing = project.mapLayersByName(layer_name)
    if existing:
        return existing[0]

    # Yeni katman oluştur
    if crs is None:
        crs = project.crs()

    crs_str = crs.authid()
    uri = f"{geom_type}?crs={crs_str}"
    layer = QgsVectorLayer(uri, layer_name, "memory")

    if not layer.isValid():
        return None

    # Alanları ekle
    if fields:
        dp = layer.dataProvider()
        qgs_fields = []
        for field_name, field_type in fields:
            if field_type == "int":
                qgs_fields.append(QgsField(field_name, QVariant.Int))
            elif field_type == "double":
                qgs_fields.append(QgsField(field_name, QVariant.Double))
            elif field_type == "string":
                qgs_fields.append(QgsField(field_name, QVariant.String))
            elif field_type == "longlong":
                qgs_fields.append(QgsField(field_name, QVariant.LongLong))
        dp.addAttributes(qgs_fields)
        layer.updateFields()

    project.addMapLayer(layer)
    return layer


def add_feature_to_layer(layer, geometry, attributes=None):
    """Katmana feature ekler.

    Args:
        layer: QgsVectorLayer
        geometry: QgsGeometry
        attributes: dict — {alan_adı: değer}

    Returns:
        QgsFeature veya None
    """
    if layer is None or geometry is None:
        return None

    layer.startEditing()
    feat = QgsFeature(layer.fields())
    feat.setGeometry(geometry)

    if attributes:
        for field_name, value in attributes.items():
            idx = layer.fields().indexOf(field_name)
            if idx >= 0:
                feat.setAttribute(idx, value)

    layer.addFeature(feat)
    layer.commitChanges()
    return feat


def add_geometry_to_current_layer(iface, geometry):
    """Aktif düzenlenebilir katmana geometri ekler.

    Args:
        iface: QGIS iface
        geometry: QgsGeometry

    Returns:
        bool — başarılı mı
    """
    layer = iface.activeLayer()
    if layer is None:
        return False

    if not isinstance(layer, QgsVectorLayer):
        return False

    if not layer.isEditable():
        layer.startEditing()

    feat = QgsFeature(layer.fields())
    feat.setGeometry(geometry)
    layer.addFeature(feat)
    layer.triggerRepaint()
    return True


def get_editable_vector_layers(iface, geom_types=None):
    """Düzenlenebilir vektör katmanları listeler.

    Args:
        iface: QGIS iface
        geom_types: list[QgsWkbTypes] — filtre (varsayılan: hepsi)

    Returns:
        list[QgsVectorLayer]
    """
    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if not layer.isEditable():
            continue
        if geom_types is not None:
            if layer.geometryType() not in geom_types:
                continue
        layers.append(layer)
    return layers


def get_road_platform_layer(crs=None):
    """Yol platformu katmanını bul veya oluştur.

    Returns:
        QgsVectorLayer
    """
    fields = [
        ("yol_id", "int"),
        ("yol_tipi", "string"),
        ("bilesen", "string"),
        ("taraf", "string"),
        ("serit_no", "int"),
        ("serit_sayisi", "int"),
        ("serit_genisligi", "double"),
        ("refuj_genislik", "double"),
        ("kaldirim_genislik", "double"),
        ("toplam_genislik", "double"),
        ("gorunur", "int"),
    ]
    layer = get_or_create_layer(
        "planx_yol_platformu",
        geom_type="MultiLineString",
        crs=crs,
        fields=fields
    )
    
    if layer and layer.customProperty("planx_symbology_applied") != "yes":
        from qgis.core import QgsRuleBasedRenderer, QgsSymbol, QgsLineSymbol
        
        symbol_visible = QgsLineSymbol.createSimple({'line_color': '100,100,100,255', 'line_width': '0.4'})
        symbol_hidden = QgsLineSymbol.createSimple({'line_style': 'no'})
        
        root_rule = QgsRuleBasedRenderer.Rule(None)
        
        # Rule for visible (gorunur = 1) or NULL
        rule_vis = QgsRuleBasedRenderer.Rule(symbol_visible)
        rule_vis.setFilterExpression('"gorunur" = 1 OR "gorunur" IS NULL')
        rule_vis.setLabel('Görünür')
        root_rule.appendChild(rule_vis)
        
        # Rule for hidden (gorunur = 0)
        rule_hid = QgsRuleBasedRenderer.Rule(symbol_hidden)
        rule_hid.setFilterExpression('"gorunur" = 0')
        rule_hid.setLabel('Gizli')
        root_rule.appendChild(rule_hid)
        
        renderer = QgsRuleBasedRenderer(root_rule)
        layer.setRenderer(renderer)
        layer.setCustomProperty("planx_symbology_applied", "yes")
        layer.triggerRepaint()
        
    return layer
