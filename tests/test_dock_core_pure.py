# -*- coding: utf-8 -*-
"""Pure Python tests for the dock's core: shared drafting state, inline tool
settings and the tool catalog. No QGIS runtime needed."""

from __future__ import annotations

import pytest

from planX_CAD_arac_Seti.core.drafting_state import (
    DraftingState,
    TRACKING_OFF,
    TRACKING_ORTHO,
    TRACKING_POLAR,
)
from planX_CAD_arac_Seti.core.tool_options import (
    BOOL, CHOICE, COLOR, FLOAT, INT, TEXT,
    OptionSpec, load_options, option_values, save_options, set_option, settings_key,
)
from planX_CAD_arac_Seti.core.tool_catalog import (
    TABS, TOOL_CATALOG, match_tools, section_of, tab_of, tool_entry,
)


class _Settings:
    """Minimal QSettings stand-in: values come back as strings, as on Windows."""

    def __init__(self):
        self.store = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = str(value)


class _Tool:
    pass


# ── Drafting state ──────────────────────────────────────────────────────────

def test_ortho_and_polar_are_mutually_exclusive():
    state = DraftingState()
    assert state.toggle_ortho() == TRACKING_ORTHO
    assert state.toggle_polar() == TRACKING_POLAR
    assert not state.ortho and state.polar
    assert state.toggle_polar() == TRACKING_OFF


def test_listeners_fire_once_per_real_change():
    state = DraftingState(osnap=True)
    seen = []
    state.add_listener(lambda s: seen.append(s.snapshot()))
    state.set_osnap(True)          # no change, no event
    state.toggle_osnap()
    state.set_tracking("ortho")
    assert [snap["osnap"] for snap in seen] == [False, False]
    assert seen[-1]["tracking"] == TRACKING_ORTHO


def test_dead_listener_is_dropped_without_breaking_others():
    state = DraftingState()
    calls = []

    def dead(_state):
        raise RuntimeError("wrapped C/C++ object has been deleted")

    state.add_listener(dead)
    state.add_listener(lambda s: calls.append(s.dynamic_input))
    state.toggle_dynamic_input()
    state.toggle_dynamic_input()
    assert calls == [False, True]
    assert dead not in state._listeners


def test_restore_accepts_qsettings_strings_and_rejects_junk():
    state = DraftingState()
    state.restore({"osnap": "false", "tracking": "POLAR", "dynamic_input": "true"})
    assert state.snapshot() == {"osnap": False, "tracking": "polar", "dynamic_input": True}
    state.restore({"tracking": "isometric"})
    assert state.tracking == TRACKING_OFF


def test_tracking_accepts_enum_like_values():
    class Mode:
        value = "ortho"
    assert DraftingState().set_tracking(Mode()) == TRACKING_ORTHO


# ── Inline tool settings ────────────────────────────────────────────────────

RADIUS = OptionSpec("radius", "Radius (m)", FLOAT, 2.0, 0.01, 100.0, 2, " m")
COUNT = OptionSpec("count", "Copies", INT, 6, 2, 360, 0)
SIDE = OptionSpec("side", "Side", CHOICE, 2, choices=((0, "Left"), (1, "Right"), (2, "Both")))
FLAG = OptionSpec("flag", "Remove source", BOOL, True)
DIST = OptionSpec("dists", "Distances", TEXT, "3, 6")
INK = OptionSpec("ink", "Colour", COLOR, "#1a237e")


@pytest.mark.parametrize("spec, raw, expected", [
    (RADIUS, "6.256", 6.26),
    (RADIUS, -5, 0.01),          # clamped to minimum
    (RADIUS, 1e9, 100.0),        # clamped to maximum
    (RADIUS, "abc", 2.0),        # junk -> default
    (RADIUS, float("nan"), 2.0),
    (COUNT, "7.6", 8),
    (COUNT, 1, 2),
    (SIDE, "1", 1),              # QSettings string -> stored int
    (SIDE, 9, 2),                # unknown choice -> default
    (FLAG, "false", False),
    (FLAG, "true", True),
    (DIST, None, "3, 6"),
    (INK, "#FFAA00", "#ffaa00"),
    (INK, "red", "#1a237e"),
])
def test_coerce(spec, raw, expected):
    assert spec.coerce(raw) == expected


def test_settings_round_trip_survives_a_fresh_tool():
    """Dialog tools are re-created on every activation; values must persist."""
    specs = (RADIUS, SIDE, FLAG)
    settings = _Settings()
    first = _Tool()
    load_options(first, "fillet", specs, settings)
    assert option_values(first, specs) == {"radius": 2.0, "side": 2, "flag": True}
    set_option(first, RADIUS, 7.5)
    set_option(first, SIDE, 0)
    set_option(first, FLAG, False)
    save_options(first, "fillet", specs, settings)
    assert settings.store[settings_key("fillet", "radius")] == "7.5"

    second = _Tool()
    load_options(second, "fillet", specs, settings)
    assert option_values(second, specs) == {"radius": 7.5, "side": 0, "flag": False}


def test_load_keeps_the_tools_own_default_when_nothing_is_stored():
    tool = _Tool()
    tool.radius = 4.0
    load_options(tool, "fillet", (RADIUS,), _Settings())
    assert tool.radius == 4.0


def test_visible_when():
    rows = OptionSpec("rows", "Rows", INT, 3, 1, 500, visible_when=("mode", "rect"))
    assert rows.is_visible({"mode": "rect"})
    assert not rows.is_visible({"mode": "polar"})
    assert RADIUS.is_visible({})


# ── Tool catalog ────────────────────────────────────────────────────────────

def test_catalog_keys_are_unique_and_every_tool_has_a_tab():
    keys = [entry.key for entry in TOOL_CATALOG]
    assert len(keys) == len(set(keys)) == 44
    assert all(tab_of(key) for key in keys)


def test_drafting_tools_share_one_tab():
    for key in ("line", "offset", "trim", "fillet", "move", "copy", "array", "hatch"):
        assert tab_of(key) == "cad", key
    assert tab_of("measure") == "measure"
    assert tab_of("road") == "urban"
    for key in ("envelope", "sight_triangle", "parking", "roundabout", "turning_head"):
        assert tab_of(key) == "urban", key
    assert [tab_id for tab_id, _t, _s in TABS] == ["cad", "measure", "urban"]


def test_regrouped_tools_left_the_old_editing_pile():
    assert section_of("construction_ray") == "Draw"
    assert section_of("hatch") == "Draw"
    assert section_of("array") == "Transform"
    assert section_of("align") == "Transform"
    assert section_of("unknown", default="Modify") == "Modify"


def test_match_tools_ranks_exact_alias_first():
    assert match_tools("f")[0].key == "fillet"
    assert match_tools("tr")[0].key == "trim"
    names = [entry.key for entry in match_tools("off")]
    assert names[:2] == ["offset", "multi_offset"]
    assert match_tools("seg")[0].key == "construction_seg"
    assert match_tools("") == ()
    assert match_tools("zzz") == ()


def test_construction_tools_have_distinct_icons():
    icons = {tool_entry(k).icon for k in ("construction_inf", "construction_ray", "construction_seg")}
    assert len(icons) == 3
