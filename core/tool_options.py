# -*- coding: utf-8 -*-
"""planX CAD — inline tool settings.

A tool lists its settings once as ``INLINE_OPTIONS``. The dock renders them on
the active-command card, bound to attributes of the live tool, and the tool
skips its modal dialog while the card is showing them. Values are remembered
per tool, so a dialog tool that is re-created on every activation still opens
with the last radius, distance or mode.

Pure Python: no Qt or QGIS imports. Persistence takes any object with
QSettings' ``value(key, default)`` / ``setValue(key, value)`` interface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FLOAT = "float"
INT = "int"
CHOICE = "choice"
BOOL = "bool"
TEXT = "text"
COLOR = "color"

SETTINGS_PREFIX = "tool_options"
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class OptionSpec:
    """One setting of a tool, bound to ``attr`` on the tool instance."""

    attr: str
    label: str
    kind: str
    default: object
    minimum: float | None = None
    maximum: float | None = None
    decimals: int = 2
    suffix: str = ""
    # CHOICE: ((stored value, visible label), ...)
    choices: tuple = field(default_factory=tuple)
    # Show only while another option has this value: (attr, value).
    visible_when: tuple | None = None
    tooltip: str = ""

    def coerce(self, value):
        """Return ``value`` converted and clamped to this option, or the default."""
        if self.kind == BOOL:
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value) if value is not None else bool(self.default)
        if self.kind == TEXT:
            return str(value) if value is not None else str(self.default)
        if self.kind == COLOR:
            text = str(value).strip() if value is not None else ""
            return text.lower() if _HEX_COLOR.match(text) else self.default
        if self.kind == CHOICE:
            allowed = [stored for stored, _label in self.choices]
            if value in allowed:
                return value
            # QSettings may hand back ints as strings.
            for stored in allowed:
                if str(stored) == str(value):
                    return stored
            return self.default
        try:
            number = float(value)
        except (TypeError, ValueError):
            return self.default
        if number != number:  # NaN
            return self.default
        if self.minimum is not None:
            number = max(float(self.minimum), number)
        if self.maximum is not None:
            number = min(float(self.maximum), number)
        if self.kind == INT:
            return int(round(number))
        return round(number, max(0, int(self.decimals)))

    def is_visible(self, values: dict) -> bool:
        if not self.visible_when:
            return True
        attr, expected = self.visible_when
        return values.get(attr) == expected


def option_values(tool, specs) -> dict:
    """Current values of ``specs`` read from ``tool``."""
    return {spec.attr: getattr(tool, spec.attr, spec.default) for spec in specs}


def set_option(tool, spec: OptionSpec, value):
    """Coerce ``value`` and store it on ``tool``. Returns the stored value."""
    value = spec.coerce(value)
    setattr(tool, spec.attr, value)
    return value


def settings_key(tool_key: str, attr: str) -> str:
    return f"{SETTINGS_PREFIX}/{tool_key}/{attr}"


def load_options(tool, tool_key: str, specs, settings) -> None:
    """Apply remembered values (or defaults) from ``settings`` to ``tool``."""
    for spec in specs:
        current = getattr(tool, spec.attr, spec.default)
        stored = settings.value(settings_key(tool_key, spec.attr), None)
        set_option(tool, spec, current if stored is None else stored)


def save_options(tool, tool_key: str, specs, settings) -> None:
    """Remember the tool's current option values."""
    for spec in specs:
        value = spec.coerce(getattr(tool, spec.attr, spec.default))
        settings.setValue(settings_key(tool_key, spec.attr), value)
