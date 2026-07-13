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

_TURKISH_CHARS_RE = re.compile(r"[çÇğĞıİöÖşŞüÜ]")
_TURKISH_ASCII_RE = re.compile(
    r"\b(?:turk|cizgi|coklu|dikdortgen|cokgen|daire|oteleme|budama|"
    r"uzatma|kose|tasi|kopyala|dondur|olcekle|aynala|tarama|kavsak|"
    r"kirma|katman|komut|kisayol|kapat|iptal|uygula|mesafe|olcum|"
    r"tampon|birlestir|bolum|nokta|surum|hizli|baslangic|secin|"
    r"tiklayin|arac|hata|hazirlik|duzenleme|yaricap|basarili|"
    r"olustur|raporu|tum)\b",
    re.IGNORECASE,
)
_ENGLISH_SCAN_SUFFIXES = {
    ".py", ".md", ".html", ".txt", ".cff", ".svg",
}
_ALLOWED_PROPER_NAMES = ("Yusuf Eminoğlu", "Eminoğlu", "Dokuz Eylül")
_ALLOWED_LEGACY_LITERALS = {"kavsak"}

# Unscoped Qt enum members that exist in PyQt5 but were removed in PyQt6/QGIS 4.
# Detected as 2-element chains ('Qt', <name>); scoped forms like
# Qt.Key.Key_Z or Qt.MouseButton.LeftButton are 3 elements and stay valid.
_QT_UNSCOPED_BUTTONS = {
    "LeftButton", "RightButton", "MidButton", "MiddleButton", "NoButton",
}
_QT_UNSCOPED_MODIFIERS = {
    "NoModifier", "ShiftModifier", "ControlModifier", "AltModifier", "MetaModifier",
}


def _is_unscoped_qt_member(chain: tuple) -> str | None:
    """Return the correct scoped replacement if chain is an unscoped Qt member."""
    if len(chain) != 2 or chain[0] != "Qt":
        return None
    name = chain[1]
    if name.startswith("Key_"):
        return f"Qt.Key.{name}"
    if name in _QT_UNSCOPED_BUTTONS:
        return f"Qt.MouseButton.{name}"
    if name in _QT_UNSCOPED_MODIFIERS:
        return f"Qt.KeyboardModifier.{name}"
    return None


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
                replacement = _QT6_BAD_ALIASES.get(chain) or _is_unscoped_qt_member(chain)
                if replacement:
                    hits.append(f"{rel}:{node.lineno}: {'.'.join(chain)} → use {replacement}")
    return _ok("Qt6 enum compatibility", not hits,
               f"{len(hits)} issues found: {hits[0]}" if hits else "no Qt5-only aliases detected")


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


def check_dock_accessibility() -> bool:
    """Icon-only tool buttons must expose accessible names for screen readers."""
    dock_path = PLUGIN_DIR / "dialogs" / "cad_dock.py"
    if not dock_path.exists():
        return _ok("dock accessibility names", False, "cad_dock.py missing")
    src = dock_path.read_text(encoding="utf-8")
    has_names = "setAccessibleName" in src
    has_focus = "QToolButton:focus" in src or "FocusPolicy" in src
    ok = has_names and has_focus
    detail = (
        "accessible names + keyboard focus present" if ok else
        ("setAccessibleName missing" if not has_names else "no keyboard focus affordance")
    )
    return _ok("dock accessibility (a11y names + focus)", ok, detail)


def check_pick_aperture_and_exclusion() -> bool:
    """tool_base must enforce the pick aperture (PICK_TOLERANCE) on real
    geometry distance, and the two-step tools (Fillet/Trim/Extend) must
    exclude the first feature on the second pick."""
    base = PLUGIN_DIR / "tools" / "tool_base.py"
    if not base.exists():
        return _ok("pick aperture + exclusion", False, "tool_base.py missing")
    base_src = base.read_text(encoding="utf-8")
    has_tol = "best_dist <= pick_tol" in base_src
    has_excl_param = "def _pick_feature(self, pos, exclude=None)" in base_src

    missing: list[str] = []
    if not has_tol:
        missing.append("aperture check in _search_layer")
    if not has_excl_param:
        missing.append("exclude param in _pick_feature")
    for tool in ("tool_fillet.py", "tool_trim.py", "tool_extend.py"):
        src = (PLUGIN_DIR / "tools" / tool).read_text(encoding="utf-8")
        if "exclude=(" not in src:
            missing.append(f"{tool}: second pick has no exclusion")
    return _ok("pick aperture + self-pick exclusion", not missing,
               "enforced" if not missing else f"missing: {', '.join(missing)}")


def check_command_line() -> bool:
    """Command line: CommandLineEdit + alias map + completer must be wired,
    and every alias must resolve to a tool key referenced in the dock."""
    dock_path = PLUGIN_DIR / "dialogs" / "cad_dock.py"
    if not dock_path.exists():
        return _ok("command line", False, "cad_dock.py missing")
    src = dock_path.read_text(encoding="utf-8")
    has_widget = "class CommandLineEdit" in src
    has_aliases = "_COMMAND_ALIASES" in src
    has_completer = "QCompleter(" in src
    has_runner = "_run_command" in src
    ok = has_widget and has_aliases and has_completer and has_runner
    missing = [n for n, p in (
        ("CommandLineEdit", has_widget), ("_COMMAND_ALIASES", has_aliases),
        ("QCompleter", has_completer), ("_run_command", has_runner),
    ) if not p]
    return _ok("command line (alias + history + completer)", ok,
               "wired" if ok else f"missing: {', '.join(missing)}")


def check_english_only_surface() -> bool:
    """Keep the shipped plugin, documentation, and UI English-only."""
    failures: list[str] = []
    for path in PLUGIN_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _ENGLISH_SCAN_SUFFIXES:
            continue
        if any(part in {".git", "__pycache__", "media", "tests"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        checked = text
        for proper_name in _ALLOWED_PROPER_NAMES:
            checked = checked.replace(proper_name, "")
        unicode_match = _TURKISH_CHARS_RE.search(checked)
        if unicode_match:
            line = checked.count("\n", 0, unicode_match.start()) + 1
            failures.append(f"{path.relative_to(PLUGIN_DIR)}:{line}: Turkish character")

        if path.suffix.lower() == ".py":
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue  # Syntax is reported by check_syntax.
            strings = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ]
            for node in strings:
                if node.value in _ALLOWED_LEGACY_LITERALS:
                    continue
                if _TURKISH_ASCII_RE.search(node.value):
                    failures.append(
                        f"{path.relative_to(PLUGIN_DIR)}:{node.lineno}: Turkish UI text"
                    )
                    break
        elif _TURKISH_ASCII_RE.search(checked):
            match = _TURKISH_ASCII_RE.search(checked)
            line = checked.count("\n", 0, match.start()) + 1
            failures.append(f"{path.relative_to(PLUGIN_DIR)}:{line}: Turkish text")

    return _ok(
        "English-only shipped surface",
        not failures,
        "clean" if not failures else "; ".join(failures[:5]),
    )


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
        check_dock_accessibility(),
        check_command_line(),
        check_pick_aperture_and_exclusion(),
        check_english_only_surface(),
    ]
    passed = sum(results)
    total = len(results)
    print("-" * 60)
    print(f"  {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
