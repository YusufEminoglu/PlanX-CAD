# -*- coding: utf-8 -*-
"""planX CAD — session-wide drafting aid state (OSNAP, ORTHO/POLAR, DYN).

Every map tool owns its own ``DraftingWorkbench``, and dialog-based tools are
re-created on every activation. Keeping the toggles on the workbench meant
F8 in Line was forgotten by Polyline, and pressing F8 with no tool active
changed nothing. This module holds the one shared state that all workbenches
read, and that the dock's status chips display.

Pure Python: no Qt or QGIS imports, so it is unit-testable on plain Python.
"""
from __future__ import annotations

TRACKING_OFF = "off"
TRACKING_ORTHO = "ortho"
TRACKING_POLAR = "polar"
_TRACKING_MODES = (TRACKING_OFF, TRACKING_ORTHO, TRACKING_POLAR)


class DraftingState:
    """Shared drafting toggles with change listeners.

    ORTHO and POLAR are mutually exclusive, as in AutoCAD: turning one on
    turns the other off.
    """

    def __init__(self, osnap: bool = True, tracking: str = TRACKING_OFF,
                 dynamic_input: bool = True):
        self._osnap = bool(osnap)
        self._tracking = tracking if tracking in _TRACKING_MODES else TRACKING_OFF
        self._dynamic_input = bool(dynamic_input)
        self._listeners: list = []

    # ── Read ────────────────────────────────────────────────────────────
    @property
    def osnap(self) -> bool:
        return self._osnap

    @property
    def tracking(self) -> str:
        return self._tracking

    @property
    def ortho(self) -> bool:
        return self._tracking == TRACKING_ORTHO

    @property
    def polar(self) -> bool:
        return self._tracking == TRACKING_POLAR

    @property
    def dynamic_input(self) -> bool:
        return self._dynamic_input

    def snapshot(self) -> dict:
        return {
            "osnap": self._osnap,
            "tracking": self._tracking,
            "dynamic_input": self._dynamic_input,
        }

    # ── Write ───────────────────────────────────────────────────────────
    def set_osnap(self, enabled: bool) -> bool:
        enabled = bool(enabled)
        if enabled != self._osnap:
            self._osnap = enabled
            self._notify()
        return self._osnap

    def set_tracking(self, mode: str) -> str:
        mode = str(getattr(mode, "value", mode) or TRACKING_OFF).lower()
        if mode not in _TRACKING_MODES:
            mode = TRACKING_OFF
        if mode != self._tracking:
            self._tracking = mode
            self._notify()
        return self._tracking

    def set_dynamic_input(self, enabled: bool) -> bool:
        enabled = bool(enabled)
        if enabled != self._dynamic_input:
            self._dynamic_input = enabled
            self._notify()
        return self._dynamic_input

    def toggle_osnap(self) -> bool:
        return self.set_osnap(not self._osnap)

    def toggle_ortho(self) -> str:
        return self.set_tracking(TRACKING_OFF if self.ortho else TRACKING_ORTHO)

    def toggle_polar(self) -> str:
        return self.set_tracking(TRACKING_OFF if self.polar else TRACKING_POLAR)

    def toggle_dynamic_input(self) -> bool:
        return self.set_dynamic_input(not self._dynamic_input)

    def restore(self, values: dict | None) -> None:
        """Apply persisted values without notifying per field."""
        values = values or {}
        self._osnap = _as_bool(values.get("osnap"), self._osnap)
        tracking = str(values.get("tracking", self._tracking)).lower()
        self._tracking = tracking if tracking in _TRACKING_MODES else TRACKING_OFF
        self._dynamic_input = _as_bool(values.get("dynamic_input"), self._dynamic_input)
        self._notify()

    # ── Listeners ───────────────────────────────────────────────────────
    def add_listener(self, callback) -> None:
        if callable(callback) and callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        for callback in list(self._listeners):
            # A listener whose widget was deleted must not break the others.
            try:
                callback(self)
            except RuntimeError:
                self.remove_listener(callback)


def _as_bool(value, default: bool) -> bool:
    """QSettings returns 'true'/'false' strings on some platforms."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


# The one instance shared by every workbench, the plugin and the dock.
DRAFTING_STATE = DraftingState()
