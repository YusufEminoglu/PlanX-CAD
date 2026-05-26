"""Static compatibility smoke tests — no QGIS runtime required.

Checks PlanX CAD Toolset for QGIS 3 / QGIS 4 dual-compatibility patterns
without needing a live QGIS installation. Run with:

    py -3 tests/smoke_compat.py

Exit 0 = all checks pass. Exit 1 = one or more failures.
"""
from __future__ import annotations

import ast
import configparser
import re
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", "tests", ".git"}

# Qt5-only short-form enum aliases that break under PyQt6 (QGIS 4)
_QT6_BAD_ALIASES: dict[tuple[str, str], str] = {
    ("Qt", "LeftDockWidgetArea"): "Qt.DockWidgetArea.LeftDockWidgetArea",
    ("Qt", "RightDockWidgetArea"): "Qt.DockWidgetArea.RightDockWidgetArea",
    ("Qt", "AlignLeft"): "Qt.AlignmentFlag.AlignLeft",
    ("Qt", "AlignRight"): "Qt.AlignmentFlag.AlignRight",
    ("Qt", "AlignCenter"): "Qt.AlignmentFlag.AlignCenter",
    ("Qt", "AlignHCenter"): "Qt.AlignmentFlag.AlignHCenter",
    ("Qt", "ScrollBarAsNeeded"): "Qt.ScrollBarPolicy.ScrollBarAsNeeded",
    ("Qt", "ScrollBarAlwaysOff"): "Qt.ScrollBarPolicy.ScrollBarAlwaysOff",
    ("QFrame", "NoFrame"): "QFrame.Shape.NoFrame",
    ("QFrame", "HLine"): "QFrame.Shape.HLine",
    ("QFrame", "Sunken"): "QFrame.Shadow.Sunken",
    ("QFrame", "Raised"): "QFrame.Shadow.Raised",
    ("QSizePolicy", "Expanding"): "QSizePolicy.Policy.Expanding",
    ("QSizePolicy", "Preferred"): "QSizePolicy.Policy.Preferred",
    ("QSizePolicy", "Fixed"): "QSizePolicy.Policy.Fixed",
    ("QDialogButtonBox", "Ok"): "QDialogButtonBox.StandardButton.Ok",
    ("QDialogButtonBox", "Cancel"): "QDialogButtonBox.StandardButton.Cancel",
    ("QFont", "Bold"): "QFont.Weight.Bold",
    ("Qt", "ApplicationShortcut"): "Qt.ShortcutContext.ApplicationShortcut",
    ("Qt", "WidgetWithChildrenShortcut"): "Qt.ShortcutContext.WidgetWithChildrenShortcut",
}

_SPLIT_GEOM_RE = re.compile(r"\w+\s*,\s*\w+\s*=\s*\w+\.splitGeometry\(")


def _attribute_chain(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return tuple(reversed(parts))
    return ()


def _python_files() -> list[Path]:
    files = []
    for py in PLUGIN_DIR.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py.parts):
            continue
        files.append(py)
    return files


def _ok(name: str, passed: bool, detail: str = "") -> bool:
    tag = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{tag}] {name}{suffix}")
    return passed


# ── individual checks ─────────────────────────────────────────────────────────

def check_syntax() -> bool:
    """All .py files must parse without SyntaxError."""
    failures: list[str] = []
    for py in _python_files():
        src = py.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(src, filename=str(py))
        except SyntaxError as exc:
            failures.append(f"{py.name}:{exc.lineno}: {exc.msg}")
    return _ok("Python syntax", not failures,
               "; ".join(failures) if failures else f"{len(_python_files())} files OK")


def check_qt6_enum_aliases() -> bool:
    """No PyQt5-only short enum aliases that break in PyQt6/QGIS 4."""
    hits: list[str] = []
    for py in _python_files():
        src = py.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src, filename=str(py))
        except SyntaxError:
            continue
        rel = py.relative_to(PLUGIN_DIR).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                chain = _attribute_chain(node)
                replacement = _QT6_BAD_ALIASES.get(chain)
                if replacement:
                    hits.append(f"{rel}:{node.lineno}: {'.'.join(chain)} → use {replacement}")
    return _ok("Qt6 enum compatibility", not hits,
               f"{len(hits)} issues found" if hits else "no Qt5-only aliases detected")


def check_split_geometry_unpack() -> bool:
    """No 2-value splitGeometry unpack (QGIS 3 returns 3-tuple)."""
    hits: list[str] = []
    for py in _python_files():
        src = py.read_text(encoding="utf-8", errors="replace")
        rel = py.relative_to(PLUGIN_DIR).as_posix()
        for lineno, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if _SPLIT_GEOM_RE.search(line):
                hits.append(f"{rel}:{lineno}")
    return _ok("splitGeometry 2-tuple unpack safety", not hits,
               f"risky unpack at: {'; '.join(hits)}" if hits else "clean")


def check_metadata() -> bool:
    """metadata.txt has required fields and valid QGIS 4 max version."""
    meta_path = PLUGIN_DIR / "metadata.txt"
    if not meta_path.exists():
        return _ok("metadata.txt present", False, "file missing")

    cfg = configparser.ConfigParser()
    raw = meta_path.read_text(encoding="utf-8")
    if not raw.lstrip().startswith("[general]"):
        raw = "[general]\n" + raw
    cfg.read_string(raw)
    sec = cfg["general"]

    required = ("name", "version", "qgisMinimumVersion", "description", "author", "email")
    missing = [f for f in required if not sec.get(f, "").strip()]
    if missing:
        return _ok("metadata required fields", False, f"missing: {', '.join(missing)}")

    version = sec.get("version", "")
    if not re.match(r"^\d+\.\d+\.\d+", version):
        return _ok("metadata semver", False, f"version='{version}' not semver")

    max_ver = sec.get("qgisMaximumVersion", "")
    qgis4_ready = max_ver.startswith("4.") or max_ver == "4.99"
    return _ok("metadata QGIS 4 max version", qgis4_ready,
               f"qgisMaximumVersion={max_ver!r}" + (" (covers QGIS 4)" if qgis4_ready else " (does NOT cover QGIS 4)"))


def _read_meta_cfg() -> configparser.ConfigParser | None:
    meta_path = PLUGIN_DIR / "metadata.txt"
    if not meta_path.exists():
        return None
    raw = meta_path.read_text(encoding="utf-8")
    if not raw.lstrip().startswith("[general]"):
        raw = "[general]\n" + raw
    cfg = configparser.ConfigParser()
    cfg.read_string(raw)
    return cfg


def check_icon_exists() -> bool:
    """Icon declared in metadata.txt must exist on disk."""
    cfg = _read_meta_cfg()
    if cfg is None:
        return _ok("icon file", False, "metadata.txt missing")
    icon_rel = cfg["general"].get("icon", "").strip()
    if not icon_rel:
        return _ok("icon file", True, "no icon declared")
    icon_path = PLUGIN_DIR / icon_rel
    return _ok("icon file exists", icon_path.exists(), str(icon_rel))


def check_class_factory() -> bool:
    """__init__.py must export classFactory."""
    init = PLUGIN_DIR / "__init__.py"
    if not init.exists():
        return _ok("classFactory", False, "__init__.py missing")
    src = init.read_text(encoding="utf-8")
    found = "classFactory" in src
    return _ok("classFactory in __init__.py", found)


def check_qgis_pyside_import_guard() -> bool:
    """Plugin uses 'qgis.PyQt' (not raw 'PyQt5'/'PyQt6'/'PySide6') for Qt imports."""
    raw_qt_re = re.compile(r"^\s*(?:from|import)\s+(PyQt5|PyQt6|PySide6)\b", re.MULTILINE)
    hits: list[str] = []
    for py in _python_files():
        src = py.read_text(encoding="utf-8", errors="replace")
        rel = py.relative_to(PLUGIN_DIR).as_posix()
        for m in raw_qt_re.finditer(src):
            line_no = src[: m.start()].count("\n") + 1
            hits.append(f"{rel}:{line_no}: imports {m.group(1)} directly (use qgis.PyQt)")
    return _ok("Qt import via qgis.PyQt only", not hits,
               f"{len(hits)} direct Qt imports" if hits else "all imports through qgis.PyQt")


def check_dock_quick_actions_grid() -> bool:
    """Quick actions in cad_dock.py must use QGridLayout, not a single QHBoxLayout."""
    dock_path = PLUGIN_DIR / "dialogs" / "cad_dock.py"
    if not dock_path.exists():
        return _ok("dock quick actions grid", False, "cad_dock.py missing")
    src = dock_path.read_text(encoding="utf-8")
    has_grid = "qa_grid = QGridLayout()" in src
    no_overflow_hbox = "quick_row = QHBoxLayout()" not in src
    ok = has_grid and no_overflow_hbox
    detail = "grid layout in use" if ok else (
        "qa_grid missing" if not has_grid else "old overflow QHBoxLayout still present"
    )
    return _ok("dock quick actions: compact QGridLayout", ok, detail)


# ── runner ────────────────────────────────────────────────────────────────────

def run_all() -> bool:
    print("=" * 60)
    print(" PlanX CAD Toolset — static compatibility smoke tests")
    print(f" Plugin: {PLUGIN_DIR}")
    print("=" * 60)
    results = [
        check_syntax(),
        check_qt6_enum_aliases(),
        check_split_geometry_unpack(),
        check_metadata(),
        check_icon_exists(),
        check_class_factory(),
        check_qgis_pyside_import_guard(),
        check_dock_quick_actions_grid(),
    ]
    passed = sum(results)
    total = len(results)
    print("-" * 60)
    print(f"  {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
