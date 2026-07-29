# -*- coding: utf-8 -*-
"""Layer creation, feature insertion, and attribute helpers for PlanX CAD."""

from qgis.core import (
    QgsProject, QgsVectorLayer,
    QgsFeature, QgsGeometry, QgsWkbTypes,
    QgsCoordinateTransform
)


# Memory-provider URI field types. Declaring fields in the URI keeps the plugin
# free of QVariant: PyQt6 dropped QVariant.Type, and the QgsField(QMetaType)
# overload only exists from QGIS 3.38, below this plugin's 3.28 floor.
_URI_FIELD_TYPES = {
    "int": "integer",
    "double": "double",
    "string": "string",
    "longlong": "long",
}

ROAD_PLATFORM_LAYER_NAME = "planx_road_platform"
LEGACY_ROAD_PLATFORM_LAYER_NAME = "planx_yol_platformu"

ROAD_PLATFORM_FIELDS = [
    ("road_id", "int"),
    ("road_type", "string"),
    ("component", "string"),
    ("side", "string"),
    ("lane_no", "int"),
    ("lane_count", "int"),
    ("lane_width", "double"),
    ("median_width", "double"),
    ("sidewalk_width", "double"),
    ("total_width", "double"),
    ("visible", "int"),
]

LEGACY_ROAD_PLATFORM_FIELDS = [
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

ROAD_FIELD_ALIASES = {
    "road_id": "yol_id",
    "road_type": "yol_tipi",
    "component": "bilesen",
    "side": "taraf",
    "lane_no": "serit_no",
    "lane_count": "serit_sayisi",
    "lane_width": "serit_genisligi",
    "median_width": "refuj_genislik",
    "sidewalk_width": "kaldirim_genislik",
    "total_width": "toplam_genislik",
    "visible": "gorunur",
}

LEGACY_COMPONENT_VALUES = {
    "center": "centerline",
    "serit": "lane",
    "kaldirim": "sidewalk",
    "refuj": "median",
    "dis_kirma": "junction_chamfer",
    "ic_baglanti": "junction_fillet",
    "refuj_baglanti": "median_connection",
}
LEGACY_SIDE_VALUES = {"sol": "left", "sag": "right", "orta": "center"}
LEGACY_ROAD_TYPE_VALUES = {"kavsak": "junction"}


def _reverse(mapping):
    return {value: key for key, value in mapping.items()}


CANONICAL_COMPONENT_VALUES = _reverse(LEGACY_COMPONENT_VALUES)
CANONICAL_SIDE_VALUES = _reverse(LEGACY_SIDE_VALUES)
CANONICAL_ROAD_TYPE_VALUES = _reverse(LEGACY_ROAD_TYPE_VALUES)


def get_or_create_layer(layer_name, geom_type="MultiLineString", crs=None,
                        fields=None):
    """Find a compatible project layer or create a memory layer.

    Args:
        layer_name: Display name for the layer.
        geom_type: ``Point``, ``LineString``, ``MultiLineString``, or
            ``Polygon``.
        crs: Target CRS; defaults to the project CRS.
        fields: Sequence of ``(name, type)`` field definitions.

    Returns:
        A compatible or newly created ``QgsVectorLayer``.
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
    # Declare the schema in the URI so the provider creates the fields itself.
    for field_name, field_type in (fields or []):
        uri_type = _URI_FIELD_TYPES.get(field_type)
        if uri_type:
            uri += f"&field={field_name}:{uri_type}"
    layer = QgsVectorLayer(uri, layer_name, "memory")

    if not layer.isValid():
        return None

    project.addMapLayer(layer)
    return layer


def add_feature_to_layer(layer, geometry, attributes=None):
    """Add a feature without committing an existing user edit session.

    Args:
        layer: Destination vector layer.
        geometry: Feature geometry.
        attributes: Mapping of field names to values.

    Returns:
        The inserted ``QgsFeature``, or ``None`` on failure.
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
    """Add canvas geometry to the active compatible vector layer.

    Args:
        iface: QGIS interface object.
        geometry: Geometry expressed in the canvas CRS.

    Returns:
        ``True`` when the feature was added.
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
    """Return editable project vector layers, optionally by geometry type.

    Args:
        iface: QGIS interface object.
        geom_types: Optional list of accepted geometry types.

    Returns:
        List of matching vector layers.
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


def _find_compatible_layer(layer_name, geom_type, crs, fields):
    """Return a managed same-name layer with a valid CRS, type, and schema.

    Managed road output is transformed to the layer CRS at every read/write
    boundary, so changing the project CRS must not orphan an existing layer.
    """
    project = QgsProject.instance()
    requested_wkb = QgsWkbTypes.parseType(geom_type)
    required_names = {name for name, _field_type in fields}
    for candidate in project.mapLayersByName(layer_name):
        if not isinstance(candidate, QgsVectorLayer):
            continue
        same_wkb = (
            QgsWkbTypes.flatType(candidate.wkbType()) ==
            QgsWkbTypes.flatType(requested_wkb)
        )
        same_crs = candidate.crs().isValid()
        candidate_names = {field.name() for field in candidate.fields()}
        if same_wkb and same_crs and required_names.issubset(candidate_names):
            return candidate
    return None


def road_field_name(layer, canonical_name):
    """Resolve an English road field to the active canonical or legacy name."""
    if layer.fields().indexOf(canonical_name) >= 0:
        return canonical_name
    legacy_name = ROAD_FIELD_ALIASES.get(canonical_name)
    if legacy_name and layer.fields().indexOf(legacy_name) >= 0:
        return legacy_name
    return canonical_name


def road_attribute(layer, feature, canonical_name):
    """Read a road attribute and normalize legacy values to English."""
    field_name = road_field_name(layer, canonical_name)
    value = feature.attribute(field_name)
    if canonical_name == "component":
        return LEGACY_COMPONENT_VALUES.get(value, value)
    if canonical_name == "side":
        return LEGACY_SIDE_VALUES.get(value, value)
    if canonical_name == "road_type":
        return LEGACY_ROAD_TYPE_VALUES.get(value, value)
    return value


def set_road_attribute(feature, layer, canonical_name, value):
    """Set a canonical road value, translating when a legacy layer is reused."""
    field_name = road_field_name(layer, canonical_name)
    if field_name != canonical_name:
        if canonical_name == "component":
            value = CANONICAL_COMPONENT_VALUES.get(value, value)
        elif canonical_name == "side":
            value = CANONICAL_SIDE_VALUES.get(value, value)
        elif canonical_name == "road_type":
            value = CANONICAL_ROAD_TYPE_VALUES.get(value, value)
    index = layer.fields().indexOf(field_name)
    if index >= 0:
        feature.setAttribute(index, value)


def get_road_platform_layer(crs=None):
    """Find a road-platform layer or create the global English schema.

    Existing projects that contain the pre-1.26 legacy layer and fields are
    reused in place. New projects always receive ``planx_road_platform`` and
    English field names.

    Returns:
        The canonical or compatible legacy road-platform layer.
    """
    if crs is None:
        crs = QgsProject.instance().crs()

    layer = _find_compatible_layer(
        ROAD_PLATFORM_LAYER_NAME, "MultiLineString", crs,
        ROAD_PLATFORM_FIELDS,
    )
    if layer is None:
        layer = _find_compatible_layer(
            LEGACY_ROAD_PLATFORM_LAYER_NAME, "MultiLineString", crs,
            LEGACY_ROAD_PLATFORM_FIELDS,
        )
    if layer is None:
        layer = get_or_create_layer(
            ROAD_PLATFORM_LAYER_NAME,
            geom_type="MultiLineString",
            crs=crs,
            fields=ROAD_PLATFORM_FIELDS,
        )

    if layer and layer.customProperty("planx_symbology_language") != "en":
        from qgis.core import QgsRuleBasedRenderer, QgsLineSymbol

        symbol_visible = QgsLineSymbol.createSimple({'line_color': '100,100,100,255', 'line_width': '0.4'})
        symbol_hidden = QgsLineSymbol.createSimple({'line_style': 'no'})

        root_rule = QgsRuleBasedRenderer.Rule(None)
        visible_field = road_field_name(layer, "visible")

        # Show normal platform components and hide construction centerlines.
        rule_vis = QgsRuleBasedRenderer.Rule(symbol_visible)
        rule_vis.setFilterExpression(
            f'"{visible_field}" = 1 OR "{visible_field}" IS NULL'
        )
        rule_vis.setLabel("Visible")
        root_rule.appendChild(rule_vis)

        rule_hid = QgsRuleBasedRenderer.Rule(symbol_hidden)
        rule_hid.setFilterExpression(f'"{visible_field}" = 0')
        rule_hid.setLabel("Hidden")
        root_rule.appendChild(rule_hid)

        renderer = QgsRuleBasedRenderer(root_rule)
        layer.setRenderer(renderer)
        layer.setCustomProperty("planx_symbology_applied", "yes")
        layer.setCustomProperty("planx_symbology_language", "en")
        layer.triggerRepaint()

    return layer
