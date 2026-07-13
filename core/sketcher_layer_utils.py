# -*- coding: utf-8 -*-
"""
planX CAD — Katman Yönetim Yardımcıları
Otomatik katman oluşturma, feature ekleme ve öznitelik yönetimi.
"""

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFields,
    QgsFeature, QgsGeometry, QgsWkbTypes, QgsFeatureSink,
    QgsCoordinateTransform
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

    if crs is None:
        crs = project.crs()

    # Do not blindly reuse the first same-name layer. A user layer (or a layer
    # left by an older plugin version) can have an incompatible CRS, WKB type,
    # or schema, causing every subsequent addFeature() to fail silently.
    requested_wkb = QgsWkbTypes.parseType(geom_type)
    required_names = {name for name, _field_type in (fields or [])}
    for candidate in project.mapLayersByName(layer_name):
        if not isinstance(candidate, QgsVectorLayer):
            continue
        same_wkb = (
            QgsWkbTypes.flatType(candidate.wkbType()) ==
            QgsWkbTypes.flatType(requested_wkb)
        )
        same_crs = (not crs.isValid() or candidate.crs() == crs)
        candidate_names = {field.name() for field in candidate.fields()}
        if same_wkb and same_crs and required_names.issubset(candidate_names):
            return candidate

    # No compatible layer exists; QGIS safely supports duplicate display
    # names, and callers retain the correct layer object directly.

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
    if (layer is None or geometry is None or geometry.isEmpty() or
            not isinstance(layer, QgsVectorLayer) or not layer.isValid()):
        return None

    was_editing = layer.isEditable()
    if not was_editing and not layer.startEditing():
        return None

    feat = QgsFeature(layer.fields())
    feat.setGeometry(QgsGeometry(geometry))

    if attributes:
        for field_name, value in attributes.items():
            idx = layer.fields().indexOf(field_name)
            if idx >= 0:
                feat.setAttribute(idx, value)

    layer.beginEditCommand("PlanX CAD: add feature")
    if not layer.addFeature(feat):
        layer.destroyEditCommand()
        if not was_editing:
            layer.rollBack()
        return None
    layer.endEditCommand()
    # Only commit if we started the edit session; otherwise leave the user's
    # in-progress edits intact.
    if not was_editing and not layer.commitChanges():
        # This helper owns the edit session in this branch, so rollback cannot
        # discard any pre-existing user edits and prevents a failed write from
        # lingering in the layer buffer.
        layer.rollBack()
        return None
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

    started_editing = False
    if not layer.isEditable():
        if not layer.startEditing():
            return False
        started_editing = True

    if geometry is None or geometry.isEmpty():
        if started_editing:
            layer.rollBack()
        return False

    # Work on a detached copy: transforming the caller's preview geometry in
    # place corrupts subsequent reuse when canvas and layer CRSs differ.
    target_geometry = QgsGeometry(geometry)

    canvas = iface.mapCanvas()
    canvas_crs = canvas.mapSettings().destinationCrs()
    layer_crs = layer.crs()
    if canvas_crs != layer_crs:
        if not canvas_crs.isValid() or not layer_crs.isValid():
            if started_editing:
                layer.rollBack()
            return False
        transform = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
        try:
            target_geometry.transform(transform)
        except Exception:
            if started_editing:
                layer.rollBack()
            return False

    if target_geometry.type() != layer.geometryType():
        if started_editing:
            layer.rollBack()
        return False

    feat = QgsFeature(layer.fields())
    feat.setGeometry(target_geometry)
    layer.beginEditCommand("PlanX CAD: draw geometry")
    if not layer.addFeature(feat):
        layer.destroyEditCommand()
        if started_editing:
            layer.rollBack()
        return False
    layer.endEditCommand()
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
