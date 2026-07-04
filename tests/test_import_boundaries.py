"""Import-boundary checks for the strict L0-L6 architecture."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "stock_lobster"

LAYER_ORDER = {
    "l0_data_access": 0,
    "l1_analysis_snapshot": 1,
    "l2_primitives": 2,
    "l3_labels": 3,
    "l4_strategy_dsl": 4,
    "l5_signal_engine": 5,
    "l6_backtest_engine": 6,
}

ORCHESTRATION_PACKAGES = {"app", "research"}


def layer_for_path(path: Path) -> str | None:
    for part in path.relative_to(PACKAGE_ROOT).parts:
        if part in LAYER_ORDER:
            return part
    if path.relative_to(PACKAGE_ROOT).parts[0] == "core":
        return "core"
    return None


def imported_layer(module_name: str) -> str | None:
    parts = module_name.split(".")
    if len(parts) < 2 or parts[0] != "stock_lobster":
        return None
    if parts[1] == "core":
        return "core"
    if parts[1] in ORCHESTRATION_PACKAGES:
        return parts[1]
    return parts[1] if parts[1] in LAYER_ORDER else None


def imported_modules(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class ImportBoundaryTest(unittest.TestCase):
    def test_layers_do_not_import_upward(self) -> None:
        violations: list[str] = []

        for path in PACKAGE_ROOT.rglob("*.py"):
            current_layer = layer_for_path(path)
            if current_layer is None:
                continue

            tree = ast.parse(path.read_text(encoding="utf-8"))
            for module_name in imported_modules(tree):
                target_layer = imported_layer(module_name)
                if target_layer is None:
                    continue
                if current_layer == "core" and target_layer != "core":
                    violations.append(f"{path}: core imports {module_name}")
                if current_layer in LAYER_ORDER and target_layer in LAYER_ORDER:
                    if LAYER_ORDER[target_layer] > LAYER_ORDER[current_layer]:
                        violations.append(f"{path}: upward import {module_name}")
                if current_layer in LAYER_ORDER and target_layer in ORCHESTRATION_PACKAGES:
                    violations.append(f"{path}: layer imports orchestration {module_name}")

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
