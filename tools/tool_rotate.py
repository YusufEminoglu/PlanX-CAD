# -*- coding: utf-8 -*-
"""planX CAD â€” DÃ¶ndÃ¼r (Rotate) AracÄ±
Ctrl basÄ±lÄ±yken 90Â° snap desteÄŸi.
"""

import math
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsGeometry, QgsPointXY
from .tool_base import tool_base
from ..core.sketcher_utils import rotate_geometry, angle_between_points


class tool_rotate(tool_base):
    """Objeyi dÃ¶ndÃ¼rme aracÄ±.
    1. Objeyi seÃ§ | 2. Referans yÃ¶nÃ¼ | 3. Hedef aÃ§Ä±
    Ctrl basÄ±lÄ± tutunca 90Â° artÄ±ÅŸlarla (0/90/180/270) snap yapar.
    """

    def __init__(self, canvas, iface):
        super().__init__(canvas, iface)
        self.center = None
        self.ref_angle = None

    def tool_name(self):
        return "DÃ¶ndÃ¼r"

    def on_entity_selected(self, layer, feature, point):
        self.center = point
        self._step = 2
        self.tool_message.emit(
            "â†» DÃ¶ndÃ¼r â€” Referans yÃ¶nÃ¼nÃ¼ belirleyin (tÄ±klayÄ±n)"
        )

    def on_click(self, point, button):
        if button == Qt.MouseButton.LeftButton:
            if self._step == 2:
                self.ref_angle = angle_between_points(self.center, point)
                self._step = 3
                self.tool_message.emit(
                    "â†» DÃ¶ndÃ¼r â€” Hedef aÃ§Ä±yÄ± belirleyin | "
                    "Ctrl: 90Â° snap"
                )
            elif self._step == 3:
                rotation = self._calc_rotation(point)

                geom = self.selected_feature.geometry()
                rotated = rotate_geometry(geom, self.center, -rotation)

                self._apply_edit(self.selected_layer, self.selected_feature,
                                 rotated)

                angle_deg = abs(rotation)
                self.tool_message.emit(
                    f"âœ… DÃ¶ndÃ¼r â€” {angle_deg:.1f}Â° dÃ¶ndÃ¼rÃ¼ldÃ¼"
                )
                self.center = None
                self.ref_angle = None
                self._reset()

    def on_move(self, point):
        if self._step == 3 and self.preview_rb and self.selected_feature:
            rotation = self._calc_rotation(point)

            geom = self.selected_feature.geometry()
            preview = rotate_geometry(geom, self.center, -rotation)

            self.preview_rb.reset(geom.type())
            self.preview_rb.setToGeometry(preview)

            # AÃ§Ä±yÄ± gÃ¶ster
            angle_deg = rotation
            ctrl = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier
            snap_text = " [90Â° SNAP]" if ctrl else ""
            self.tool_message.emit(
                f"â†» DÃ¶ndÃ¼r â€” AÃ§Ä±: {angle_deg:.1f}Â°{snap_text} | "
                f"Ctrl: 90Â° snap"
            )

    def _calc_rotation(self, point):
        """DÃ¶nÃ¼ÅŸ aÃ§Ä±sÄ±nÄ± hesapla. Ctrl basÄ±lÄ±ysa 90Â° snap."""
        target_angle = angle_between_points(self.center, point)
        rotation = target_angle - self.ref_angle

        # Ctrl basÄ±lÄ±ysa 90Â° artÄ±ÅŸlarla snap
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            rotation = round(rotation / 90.0) * 90.0

        return rotation
