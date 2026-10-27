# -*- coding: utf-8 -*-
"""Master test runner for PlanX CAD Toolset QGIS runtime smoke suites."""

from __future__ import annotations

import sys
import subprocess

SUITES = [
    "planX_CAD_arac_Seti.tests.smoke_runtime",
    "planX_CAD_arac_Seti.tests.smoke_geometry",
    "planX_CAD_arac_Seti.tests.smoke_geometry_regressions",
    "planX_CAD_arac_Seti.tests.smoke_junction_geometry",
    "planX_CAD_arac_Seti.tests.smoke_modify_geometry",
    "planX_CAD_arac_Seti.tests.smoke_precision_input",
    "planX_CAD_arac_Seti.tests.smoke_urban_workbench",
    "planX_CAD_arac_Seti.tests.smoke_osnap_tracking",
    "planX_CAD_arac_Seti.tests.smoke_urban_tools",
]


def run_all() -> bool:
    print("=" * 70)
    print(" PlanX CAD Toolset - Running all QGIS runtime smoke suites")
    print("=" * 70)

    results = []
    for suite in SUITES:
        suite_name = suite.split(".")[-1]
        print(f"\n>>> Running suite: {suite_name} ...")
        proc = subprocess.run([sys.executable, "-m", suite])
        ok = (proc.returncode == 0)
        results.append((suite_name, ok))
        print(f">>> {suite_name}: {'PASS' if ok else 'FAIL'}")

    print("\n" + "=" * 70)
    print(" PlanX CAD Toolset - Test Summary")
    print("=" * 70)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print("-" * 70)
    print(f"  {passed}/{total} suites passed")

    return passed == total


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
