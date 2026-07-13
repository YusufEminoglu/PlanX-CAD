# -*- coding: utf-8 -*-
"""
planX CAD — Kavşak Oluşturma Aracı (Gelişmiş)
NetCAD tarzı kavşak çözümü:
 - Kaldırım köşeleri: seçilebilir düz kırma (chamfer) veya teğet fillet
 - Kavşak adası: yuvarlak veya su damlası

Oluşturulan katmanlar:
 - kavsak (LineString): kırma ve bağlantı çizgileri
 - kavsak_ada (Polygon): kavşak adaları
"""

import math
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsPointXY, QgsFeature,
    QgsFeatureRequest,
)
from qgis.gui import QgsMapTool

from ..core.sketcher_feedback import (
    create_preview_rubberband, cleanup_sketcher_rubberband, COLOR_ACCENT
)
from ..core.sketcher_layer_utils import get_or_create_layer, get_road_platform_layer
from .crs_utils import local_metric_crs, transform_geometry, transform_point
from .junction_dialog import JunctionDialog
from .junction_geometry import (
    CurbHalfEdge,
    cluster_approaches,
    solve_sector_corners,
)


def _geometry_for_layer(layer, geometry):
    """Return a geometry whose single/multi type matches ``layer``."""
    geometry = QgsGeometry(geometry)
    if QgsWkbTypes.isMultiType(layer.wkbType()) and not geometry.isMultipart():
        geometry.convertToMultiType()
    return geometry


class JunctionSketcher(QgsMapTool):
    """Kavşak oluşturma aracı.

    İş akışı:
    1. Dialog açılır → parametreler girilir
    2. Kavşak merkezi tıklanır
    3. Otomatik olarak:
       a) Etki yarıçapı içindeki çizgiler trimlenir
       b) Kaldırım köşeleri seçilen chamfer/fillet yöntemiyle çözülür
       c) Kavşak adası oluşturulur (yuvarlak/su damlası)
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
        self._activation_cancelled = False
        self._junction_edit_state = None

    def activate(self):
        super().activate()
        self._activation_cancelled = False
        self._step = 0

        # Parametre dialog'u
        dlg = JunctionDialog(self.iface.mainWindow())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._activation_cancelled = True
            self.sketcher_message.emit("🔵 Kavşak — İptal edildi")
            self.sketcher_finished.emit()
            return

        self.params = dlg.get_params()
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self._step = 1
        mode_label = (
            f"Kırma={self.params['chamfer_dist']}m"
            if self.params.get("corner_mode", "chamfer") == "chamfer"
            else f"Fillet R={self.params['fillet_radius']}m"
        )
        self.sketcher_message.emit(
            f"🔵 Kavşak (R={self.params['radius']}m, "
            f"{mode_label}) — "
            f"Kavşak merkezini tıklayın"
        )

    def deactivate(self):
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = None
        super().deactivate()

    def canvasPressEvent(self, event):
        if self._step != 1 or event.button() != Qt.MouseButton.LeftButton:
            return

        point = self.toMapCoordinates(event.pos())
        # Snap
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        self._create_junction(point)

    def canvasMoveEvent(self, event):
        if self._step != 1 or not self.preview_rb:
            return

        point = self.toMapCoordinates(event.pos())
        snapper = self.canvas.snappingUtils()
        if snapper:
            match = snapper.snapToMap(event.pos())
            if match.isValid():
                point = match.point()

        # Preview metre-based radii correctly even in geographic projects.
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = local_metric_crs(point, canvas_crs)
        metric_point = transform_point(point, canvas_crs, metric_crs)
        pts = [
            transform_point(pt, metric_crs, canvas_crs)
            for pt in self._make_circle(
                metric_point, self.params["radius"], 48
            )
        ]
        self.preview_rb.reset(QgsWkbTypes.PolygonGeometry)
        for pt in pts:
            self.preview_rb.addPoint(pt)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
            self.preview_rb = None
            self.sketcher_message.emit("🔵 Kavşak — İptal edildi")
            self.sketcher_finished.emit()

    # ════════════════════════════════════════════════════════════════════════
    # Kavşak Oluşturma
    # ════════════════════════════════════════════════════════════════════════

    def _create_junction(self, center):
        """Run a junction operation with exception-safe edit cleanup."""
        self._junction_edit_state = {"road": None, "island": None}
        try:
            return self._create_junction_impl(center)
        except Exception as error:
            self._rollback_open_junction_edits()
            message = (
                "⚠️ Kavşak — Beklenmeyen geometri/provider hatası; "
                f"işlem geri alındı ({type(error).__name__})"
            )
            self.sketcher_message.emit(message)
            self.iface.messageBar().pushWarning("planX CAD", message)
            return None

    def _create_junction_impl(self, center):
        """Ana kavşak oluşturma işlemi."""
        p = self.params
        radius = p["radius"]
        chamfer_dist = p["chamfer_dist"]
        fillet_radius = p["fillet_radius"]
        ada_tipi = p["ada_tipi"]
        ada_radius = p["ada_radius"]

        canvas_crs = self.canvas.mapSettings().destinationCrs()
        metric_crs = local_metric_crs(center, canvas_crs)
        center = transform_point(center, canvas_crs, metric_crs)
        center_geom = QgsGeometry.fromPointXY(center)
        junction_buffer = center_geom.buffer(radius, 48)
        outer_buffer = center_geom.buffer(radius + 1.0, 48)

        # ── Katmanları hazırla ───────────────────────────────────────────
        kavsak_line_layer = get_road_platform_layer()
        kavsak_ada_layer = None

        if not kavsak_line_layer:
            self.sketcher_message.emit("⚠️ Kavşak — Yol katmanı oluşturulamadı")
            return

        kavsak_id = self._next_id(kavsak_line_layer, "yol_id")

        # ── 1. Yolları analiz et ve tek atomik edit komutunu başlat ─────
        layer = kavsak_line_layer
        features_hit = []
        layer_search_geometry = transform_geometry(
            junction_buffer, metric_crs, layer.crs()
        )
        request = QgsFeatureRequest().setFilterRect(
            layer_search_geometry.boundingBox()
        )
        for feat in layer.getFeatures(request):
            geom = transform_geometry(feat.geometry(), layer.crs(), metric_crs)
            if geom and not geom.isEmpty() and geom.intersects(junction_buffer):
                features_hit.append(feat)

        feature_records = []
        curb_records = []
        curb_edges = []
        refuj_edges = []

        for feat in features_hit:
            geom = transform_geometry(feat.geometry(), layer.crs(), metric_crs)
            component = self._feature_attribute(layer, feat, "bilesen")
            road_id = self._feature_attribute(layer, feat, "yol_id")
            feature_records.append((feat, geom, component, road_id))

            if component == "kaldirim":
                edges = self._extract_half_edges(
                    geom, junction_buffer, center, feat.id(), road_id,
                    component="kaldirim",
                )
                curb_edges.extend(edges)
                curb_records.append((feat, geom, edges))
                continue

            if component == "refuj":
                refuj_edges.extend(self._extract_half_edges(
                    geom, junction_buffer, center, feat.id(), road_id,
                    component="refuj",
                ))

        # Solve and validate every requested corner before opening an edit
        # command. A single road or an unsafe acute layout must be a no-op.
        corner_mode = p.get("corner_mode", "chamfer")
        corner_value = chamfer_dist if corner_mode == "chamfer" else fillet_radius
        proposed_solutions = solve_sector_corners(
            curb_edges, center, corner_mode, corner_value, segments=24
        )
        corner_solutions = []
        edge_cut_points = {}
        for solution in proposed_solutions:
            if not (
                self._cut_point_available(solution.first, solution.cut_first)
                and self._cut_point_available(solution.second, solution.cut_second)
            ):
                continue
            corner_solutions.append(solution)
            edge_cut_points[id(solution.first)] = solution.cut_first
            edge_cut_points[id(solution.second)] = solution.cut_second

        if not corner_solutions:
            message = (
                "⚠️ Kavşak — En az iki tam yol kolu ve güvenli bir köşe "
                "çözümü bulunamadı; hiçbir geometri değiştirilmedi"
            )
            self.sketcher_message.emit(message)
            self.iface.messageBar().pushWarning("planX CAD", message)
            return

        if ada_tipi != "yok":
            kavsak_ada_layer = self._get_kavsak_ada_layer()
            if not kavsak_ada_layer:
                message = "⚠️ Kavşak — Ada katmanı oluşturulamadı"
                self.sketcher_message.emit(message)
                self.iface.messageBar().pushWarning("planX CAD", message)
                return

        if ada_tipi != "yok" and (
            layer.isEditable() or kavsak_ada_layer.isEditable()
        ):
            message = (
                "⚠️ Kavşak — Ada ile yol değişikliklerini birlikte kaydetmek "
                "için açık yol/ada düzenlemelerini önce kaydedin veya geri alın; "
                "hiçbir geometri değiştirilmedi"
            )
            self.sketcher_message.emit(message)
            self.iface.messageBar().pushWarning("planX CAD", message)
            return

        layer_was_editing = layer.isEditable()
        if not layer_was_editing and not layer.startEditing():
            self.sketcher_message.emit("⚠️ Kavşak — Yol katmanı düzenlenemedi")
            return
        layer.beginEditCommand("Kavşak köşe çözümü")
        output_was_editing = layer_was_editing
        self._junction_edit_state["road"] = {
            "layer": layer,
            "was_editing": layer_was_editing,
            "command_open": True,
        }
        trimmed_count = 0

        # ── 2. Doğrulanmış çözümü tek edit komutunda uygula ─────────────
        for feat, geom, component, _road_id in feature_records:
            if component == "kaldirim":
                continue
            parts = self._annular_trim_parts(
                geom, junction_buffer, outer_buffer
            )
            if not self._replace_feature_with_metric_parts(
                layer, feat, parts, metric_crs
            ):
                self._abort_edit_command(
                    layer, layer_was_editing,
                    "⚠️ Kavşak — Yol geometrisi güncellenemedi; işlem geri alındı",
                )
                return
            trimmed_count += 1

        # Kaldırımlar dairesel tampon yerine gerçek çözüm teğet noktalarında
        # kesilir. Çözülemeyen kollar güvenli biçimde etki sınırında kalır.
        for feat, geom, edges in curb_records:
            parts = self._trim_curb_parts(
                geom, edges, edge_cut_points, junction_buffer
            )
            if not self._replace_feature_with_metric_parts(
                layer, feat, parts, metric_crs
            ):
                self._abort_edit_command(
                    layer, layer_was_editing,
                    "⚠️ Kavşak — Kaldırım kesimi uygulanamadı; işlem geri alındı",
                )
                return
            trimmed_count += 1

        connection_component = (
            "dis_kirma" if corner_mode == "chamfer" else "ic_baglanti"
        )
        for solution in corner_solutions:
            feat = QgsFeature(kavsak_line_layer.fields())
            feat.setGeometry(_geometry_for_layer(
                kavsak_line_layer,
                transform_geometry(
                    solution.connection, metric_crs, kavsak_line_layer.crs()
                ),
            ))
            feat.setAttribute("yol_id", kavsak_id)
            feat.setAttribute("yol_tipi", "kavsak")
            feat.setAttribute("bilesen", connection_component)
            if not kavsak_line_layer.addFeature(feat):
                self._abort_edit_command(
                    kavsak_line_layer, output_was_editing,
                    "⚠️ Kavşak — Köşe bağlantısı eklenemedi; işlem geri alındı",
                )
                return

        # Keep this edit command open through island creation so any later
        # provider failure rolls back trims and connections together.
        layer.triggerRepaint()

        # ── 3.5 Refüj Kapatma Yayları (Yuvarlak kavşaklar için) ─────────
        if ada_tipi != "yok" and refuj_edges:
            refuj_caps = self._create_refuj_caps(center, refuj_edges)
            for cap_line in refuj_caps:
                feat = QgsFeature(kavsak_line_layer.fields())
                feat.setGeometry(_geometry_for_layer(
                    kavsak_line_layer,
                    transform_geometry(cap_line, metric_crs, kavsak_line_layer.crs()),
                ))
                feat.setAttribute("yol_id", kavsak_id)
                feat.setAttribute("yol_tipi", "kavsak")
                feat.setAttribute("bilesen", "refuj_baglanti")
                feat.setAttribute("gorunur", 1)  # Kapatma için görünür
                if not kavsak_line_layer.addFeature(feat):
                    self._abort_edit_command(
                        kavsak_line_layer, output_was_editing,
                        "⚠️ Kavşak — Refüj bağlantısı eklenemedi; işlem geri alındı",
                    )
                    return

        # ── 4. Kavşak adası ──────────────────────────────────────────────
        if ada_tipi != "yok":
            island_was_editing = kavsak_ada_layer.isEditable()
            existing_island_ids = {
                feature.id() for feature in kavsak_ada_layer.getFeatures()
            }
            if not island_was_editing and not kavsak_ada_layer.startEditing():
                self._abort_edit_command(
                    kavsak_line_layer, output_was_editing,
                    "⚠️ Kavşak — Ada katmanı düzenlenemedi; yol işlemi geri alındı",
                )
                return
            kavsak_ada_layer.beginEditCommand("Kavşak adası oluştur")
            self._junction_edit_state["island"] = {
                "layer": kavsak_ada_layer,
                "was_editing": island_was_editing,
                "command_open": True,
                "committed": False,
                "junction_id": kavsak_id,
                "existing_feature_ids": existing_island_ids,
                "created_feature_ids": set(),
            }

            if ada_tipi == "yuvarlak":
                ada_geom = center_geom.buffer(ada_radius, 48)
            elif ada_tipi == "su_damlasi":
                approaches = cluster_approaches(curb_edges)
                direction = (
                    approaches[0].outward if approaches else (0.0, -1.0)
                )
                ada_geom = self._create_teardrop(
                    center, ada_radius, p["teardrop_uzunluk"], direction
                )
            else:
                ada_geom = None

            if ada_geom and not ada_geom.isEmpty():
                feat = QgsFeature(kavsak_ada_layer.fields())
                feat.setGeometry(
                    transform_geometry(ada_geom, metric_crs, kavsak_ada_layer.crs())
                )
                feat.setAttribute("kavsak_id", kavsak_id)
                feat.setAttribute("ada_tipi", ada_tipi)
                feat.setAttribute("ada_radius", ada_radius)
                if not kavsak_ada_layer.addFeature(feat):
                    kavsak_ada_layer.destroyEditCommand()
                    if not island_was_editing:
                        kavsak_ada_layer.rollBack()
                    self._abort_edit_command(
                        kavsak_line_layer, output_was_editing,
                        "⚠️ Kavşak — Ada eklenemedi; yol işlemi geri alındı",
                    )
                    return

            kavsak_ada_layer.endEditCommand()
            self._junction_edit_state["island"]["command_open"] = False
            if not island_was_editing and not kavsak_ada_layer.commitChanges():
                kavsak_ada_layer.rollBack()
                self._abort_edit_command(
                    kavsak_line_layer, output_was_editing,
                    "⚠️ Kavşak — Ada kaydedilemedi; yol işlemi geri alındı",
                )
                return
            self._junction_edit_state["island"]["committed"] = True
            self._junction_edit_state["island"]["created_feature_ids"] = {
                feature.id() for feature in kavsak_ada_layer.getFeatures()
            } - existing_island_ids
            kavsak_ada_layer.triggerRepaint()

        # Finalize road edits only after every requested output layer has
        # accepted its changes. This keeps trim + connections rollback-able
        # when island creation fails.
        kavsak_line_layer.endEditCommand()
        self._junction_edit_state["road"]["command_open"] = False
        if not output_was_editing and not kavsak_line_layer.commitChanges():
            kavsak_line_layer.rollBack()
            compensated = self._compensate_committed_island()
            message = "⚠️ Kavşak — Yol ve bağlantılar kaydedilemedi"
            if not compensated:
                message += (
                    f"; kavsak_ada içindeki yeni ada (ID {kavsak_id}) "
                    "otomatik temizlenemedi, manuel kontrol edin"
                )
                self.iface.messageBar().pushWarning("planX CAD", message)
            self.sketcher_message.emit(message)
            self._junction_edit_state["road"] = None
            return
        self._junction_edit_state["road"] = None
        self._junction_edit_state["island"] = None
        kavsak_line_layer.triggerRepaint()

        # ── Sonuç ────────────────────────────────────────────────────────
        corner_label = "kırma" if corner_mode == "chamfer" else "fillet"
        msg = (
            f"✅ Kavşak — {trimmed_count} çizgi trimlendi | "
            f"{len(corner_solutions)} {corner_label} bağlantısı"
        )
        skipped_corners = len(proposed_solutions) - len(corner_solutions)
        if skipped_corners:
            msg += f" | {skipped_corners} yetersiz kol atlandı"
        if ada_tipi != "yok":
            msg += f" | Ada: {ada_tipi}"
        self.sketcher_message.emit(msg)

        self.iface.messageBar().pushSuccess("planX CAD", msg)

        # Temizle
        cleanup_sketcher_rubberband(self.canvas, self.preview_rb)
        self.preview_rb = create_preview_rubberband(
            self.canvas, QgsWkbTypes.PolygonGeometry
        )
        self.sketcher_finished.emit()
        self._junction_edit_state = None

    def _abort_edit_command(self, layer, was_editing, message):
        layer.destroyEditCommand()
        if not was_editing:
            layer.rollBack()
        if self._junction_edit_state:
            for key in ("road", "island"):
                state = self._junction_edit_state.get(key)
                if state and state["layer"] is layer:
                    self._junction_edit_state[key] = None
        self.sketcher_message.emit(message)

    def _rollback_open_junction_edits(self):
        """Close only commands/sessions owned by the interrupted operation."""
        if not self._junction_edit_state:
            return
        for key in ("island", "road"):
            state = self._junction_edit_state.get(key)
            if not state:
                continue
            layer = state["layer"]
            try:
                if state["command_open"]:
                    layer.destroyEditCommand()
                if state.get("committed"):
                    if not self._compensate_committed_island():
                        self.iface.messageBar().pushWarning(
                            "planX CAD",
                            "Kavşak yol işlemi geri alındı fakat yeni ada "
                            "otomatik temizlenemedi; kavsak_ada katmanını "
                            "manuel kontrol edin",
                        )
                elif not state["was_editing"] and layer.isEditable():
                    layer.rollBack()
            except Exception:
                pass
            self._junction_edit_state[key] = None

    def _compensate_committed_island(self):
        """Delete this operation's island if the road side cannot be saved."""
        if not self._junction_edit_state:
            return False
        state = self._junction_edit_state.get("island")
        if not state or not state.get("committed"):
            return True
        layer = state["layer"]
        feature_ids = set(state.get("created_feature_ids", ()))
        # If the provider did not expose the inserted identity after commit,
        # fail safe and report compensation failure. Never delete by a shared
        # kavsak_id because an older/manual island may legitimately use it.
        if not feature_ids or not layer.startEditing():
            return False
        layer.beginEditCommand("Başarısız kavşak adasını geri al")
        deleted = all(layer.deleteFeature(feature_id) for feature_id in feature_ids)
        if not deleted:
            layer.destroyEditCommand()
            layer.rollBack()
            return False
        layer.endEditCommand()
        if not layer.commitChanges():
            layer.rollBack()
            return False
        state["committed"] = False
        return True

    # ════════════════════════════════════════════════════════════════════════
    # Geometri İşlemleri
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _feature_attribute(layer, feature, field_name):
        index = layer.fields().indexOf(field_name)
        return feature.attribute(index) if index >= 0 else None

    @staticmethod
    def _line_parts(geometry):
        """Return detached single-line parts from any line collection."""
        if geometry is None or geometry.isEmpty():
            return []
        collection = geometry.asGeometryCollection()
        candidates = collection if collection else [QgsGeometry(geometry)]
        return [
            QgsGeometry(part) for part in candidates
            if part and not part.isEmpty()
            and part.type() == QgsWkbTypes.LineGeometry
        ]

    def _annular_trim_parts(self, geometry, inner_buffer, outer_buffer):
        """Keep the outside road plus the legacy one-metre boundary band."""
        parts = self._line_parts(geometry.difference(outer_buffer))
        band = geometry.intersection(outer_buffer).difference(inner_buffer)
        parts.extend(self._line_parts(band))
        return parts

    def _replace_feature_with_metric_parts(
        self, layer, feature, metric_parts, metric_crs
    ):
        """Replace one feature with zero or more metric line parts."""
        parts = [
            part for part in metric_parts
            if part and not part.isEmpty()
            and part.type() == QgsWkbTypes.LineGeometry
        ]
        if not parts:
            return layer.deleteFeature(feature.id())

        first = transform_geometry(parts[0], metric_crs, layer.crs())
        if first is None or first.isEmpty():
            return False
        if not layer.changeGeometry(
            feature.id(), _geometry_for_layer(layer, first)
        ):
            return False

        for part in parts[1:]:
            output = transform_geometry(part, metric_crs, layer.crs())
            if output is None or output.isEmpty():
                return False
            new_feature = QgsFeature(layer.fields())
            new_feature.setGeometry(_geometry_for_layer(layer, output))
            for index in range(layer.fields().count()):
                new_feature.setAttribute(index, feature.attribute(index))
            if not layer.addFeature(new_feature):
                return False
        return True

    def _extract_half_edges(
        self, geometry, junction_buffer, center, source_id, road_id,
        component="kaldirim",
    ):
        """Build one outward half-edge for each curb/buffer crossing."""
        buffer_boundary = junction_buffer.convertToType(
            QgsWkbTypes.LineGeometry
        )
        edges = []
        effective_road_id = (
            road_id if road_id is not None else f"feature:{source_id}"
        )

        for part_index, source_part in enumerate(self._line_parts(geometry)):
            part_length = source_part.length()
            if part_length <= 1e-8:
                continue
            outside = source_part.difference(junction_buffer)
            for outside_part in self._line_parts(outside):
                if outside_part.isMultipart():
                    lines = outside_part.asMultiPolyline()
                    points = lines[0] if lines else []
                else:
                    points = outside_part.asPolyline()
                if len(points) < 2:
                    continue
                start = QgsPointXY(points[0])
                end = QgsPointXY(points[-1])
                start_distance = QgsGeometry.fromPointXY(start).distance(
                    buffer_boundary
                )
                end_distance = QgsGeometry.fromPointXY(end).distance(
                    buffer_boundary
                )
                if min(start_distance, end_distance) > 0.1:
                    continue

                if start_distance <= end_distance:
                    boundary_point = start
                    neighbour = QgsPointXY(points[1])
                else:
                    boundary_point = end
                    neighbour = QgsPointXY(points[-2])
                outward = (
                    neighbour.x() - boundary_point.x(),
                    neighbour.y() - boundary_point.y(),
                )
                if math.hypot(*outward) <= 1e-9:
                    continue

                boundary_measure = source_part.lineLocatePoint(
                    QgsGeometry.fromPointXY(boundary_point)
                )
                if boundary_measure < 0:
                    continue
                delta = min(0.1, max(part_length * 1e-5, 1e-4))
                if boundary_measure + delta <= part_length:
                    sample = source_part.interpolate(
                        boundary_measure + delta
                    ).asPoint()
                    increasing_vector = (
                        sample.x() - boundary_point.x(),
                        sample.y() - boundary_point.y(),
                    )
                elif boundary_measure - delta >= 0:
                    sample = source_part.interpolate(
                        boundary_measure - delta
                    ).asPoint()
                    increasing_vector = (
                        boundary_point.x() - sample.x(),
                        boundary_point.y() - sample.y(),
                    )
                else:
                    continue
                increasing_outward = (
                    increasing_vector[0] * outward[0]
                    + increasing_vector[1] * outward[1]
                ) > 0

                edges.append(CurbHalfEdge(
                    road_id=effective_road_id,
                    component=component,
                    source_id=source_id,
                    source_part=part_index,
                    cut_point=boundary_point,
                    outward=outward,
                    source_ref={
                        "part_geometry": QgsGeometry(source_part),
                        "boundary_measure": boundary_measure,
                        "increasing_outward": increasing_outward,
                    },
                ))
        return edges

    @staticmethod
    def _cut_point_available(edge, cut_point, tolerance=0.05):
        """Return whether a solved cut lies on the referenced source part."""
        if edge.source_ref is None:
            return False
        source_part = edge.source_ref.get("part_geometry")
        if source_part is None or source_part.isEmpty():
            return False
        if not (math.isfinite(cut_point.x()) and math.isfinite(cut_point.y())):
            return False
        point_geometry = QgsGeometry.fromPointXY(cut_point)
        return (
            source_part.distance(point_geometry) <= tolerance
            and source_part.lineLocatePoint(point_geometry) >= 0
        )

    @staticmethod
    def _merge_intervals(intervals, tolerance=1e-8):
        merged = []
        for start, end in sorted(intervals):
            if end - start <= tolerance:
                continue
            if merged and start <= merged[-1][1] + tolerance:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def _trim_curb_parts(
        self, geometry, edges, edge_cut_points, junction_buffer
    ):
        """Trim each curb part at solved cut points, preserving outward sides."""
        edges_by_part = {}
        for edge in edges:
            edges_by_part.setdefault(edge.source_part, []).append(edge)

        output_parts = []
        for part_index, source_part in enumerate(self._line_parts(geometry)):
            part_edges = edges_by_part.get(part_index, [])
            if not part_edges:
                output_parts.extend(self._line_parts(
                    source_part.difference(junction_buffer)
                ))
                continue

            length = source_part.length()
            intervals = []
            for edge in part_edges:
                cut_point = edge_cut_points.get(id(edge), edge.cut_point)
                point_geometry = QgsGeometry.fromPointXY(cut_point)
                measure = source_part.lineLocatePoint(point_geometry)
                if measure < 0:
                    measure = edge.source_ref["boundary_measure"]
                measure = max(0.0, min(length, measure))
                if edge.source_ref["increasing_outward"]:
                    intervals.append((measure, length))
                else:
                    intervals.append((0.0, measure))

            for start, end in self._merge_intervals(intervals):
                curve = source_part.constGet().curveSubstring(start, end)
                if curve is not None:
                    part = QgsGeometry(curve)
                    if not part.isEmpty() and part.length() > 1e-8:
                        output_parts.append(part)
        return output_parts

    def _create_refuj_caps(self, center, half_edges):
        """Close each directional median arm locally, never across the junction."""
        caps = []
        for approach in cluster_approaches(half_edges):
            first = approach.left_curb(center).cut_point
            second = approach.right_curb(center).cut_point
            if first.distance(second) > 1e-8:
                caps.append(QgsGeometry.fromPolylineXY([first, second]))
        return caps

    def _create_teardrop(self, center, radius, length, direction=(0.0, -1.0)):
        """Create a symmetric bulb-and-nose island aligned to a road arm."""
        direction_length = math.hypot(direction[0], direction[1])
        if radius <= 0 or length <= 0 or direction_length <= 1e-9:
            return QgsGeometry()
        ux = direction[0] / direction_length
        uy = direction[1] / direction_length
        vx, vy = -uy, ux

        def map_local(x, y):
            return QgsPointXY(
                center.x() + ux * x + vx * y,
                center.y() + uy * x + vy * y,
            )

        pts = []
        segments = 32
        # Rounded rear half: top shoulder -> rear -> bottom shoulder.
        for i in range(segments + 1):
            angle = math.pi / 2 + math.pi * i / segments
            pts.append(map_local(
                radius * math.cos(angle), radius * math.sin(angle)
            ))
        pts.append(map_local(length, 0.0))
        pts.append(pts[0])
        return QgsGeometry.fromPolygonXY([pts])

    # ════════════════════════════════════════════════════════════════════════
    # Katman Yönetimi
    # ════════════════════════════════════════════════════════════════════════


    def _get_kavsak_ada_layer(self):
        """kavsak_ada (Polygon) katmanını bul veya oluştur."""
        return get_or_create_layer(
            "kavsak_ada",
            geom_type="Polygon",
            fields=[
                ("kavsak_id", "int"),
                ("ada_tipi", "string"),     # yuvarlak / su_damlasi
                ("ada_radius", "double"),
            ]
        )

    def _make_circle(self, center, radius, segments=48):
        pts = []
        for i in range(segments + 1):
            angle = 2 * math.pi * i / segments
            x = center.x() + radius * math.cos(angle)
            y = center.y() + radius * math.sin(angle)
            pts.append(QgsPointXY(x, y))
        return pts

    def _next_id(self, layer, field_name):
        max_id = 0
        idx = layer.fields().indexOf(field_name)
        if idx < 0:
            return 1
        request = QgsFeatureRequest()
        request.setSubsetOfAttributes([idx])
        request.setFlags(QgsFeatureRequest.Flag.NoGeometry)
        for feat in layer.getFeatures(request):
            val = feat.attribute(idx)
            try:
                max_id = max(max_id, int(val))
            except (TypeError, ValueError):
                continue
        return max_id + 1
