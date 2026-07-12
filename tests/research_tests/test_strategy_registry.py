"""Contracts for the repository strategy selection registry."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "configs/strategies/strategy_registry.example.json"


class StrategyRegistryTest(unittest.TestCase):
    def test_exactly_one_strategy_is_enabled_for_routine_selection(self) -> None:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual("business_selection_policies_only", payload["scope"])
        entries = payload["strategies"]
        enabled = [entry for entry in entries if entry["routine_selection_enabled"]]

        self.assertEqual(1, len(enabled))
        current = enabled[0]
        self.assertEqual("strategy.steady_uptrend_mvp", current["strategy_id"])
        self.assertEqual("v1", current["version"])
        self.assertEqual("test_tracking", current["status"])
        self.assertEqual("routine_primary", current["role"])
        self.assertNotIn("/archive/", current["config_path"])

        config_path = PROJECT_ROOT / current["config_path"]
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(current["strategy_id"], config["strategy_id"])
        self.assertEqual(current["version"], config["version"])
        self.assertEqual(current["status"], config["status"])

    def test_every_archived_strategy_is_registered_as_replay_only(self) -> None:
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        entries = payload["strategies"]
        by_path = {entry["config_path"]: entry for entry in entries}
        archive_root = PROJECT_ROOT / "configs/strategies/archive"
        archived_paths = {
            str(path.relative_to(PROJECT_ROOT))
            for path in archive_root.rglob("*.json")
        }

        self.assertTrue(archived_paths)
        self.assertEqual(archived_paths, set(by_path).intersection(archived_paths))
        for path in archived_paths:
            entry = by_path[path]
            self.assertFalse(entry["routine_selection_enabled"])
            self.assertEqual("replay_only", entry["role"])

    def test_only_mvp_schedule_is_enabled_for_routine_selection(self) -> None:
        legacy_path = (
            PROJECT_ROOT
            / "configs/schedules/daily_strategy_signal_production.example.json"
        )
        mvp_path = (
            PROJECT_ROOT
            / "configs/schedules/daily_steady_uptrend_mvp_tracking.example.json"
        )
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        mvp = json.loads(mvp_path.read_text(encoding="utf-8"))

        self.assertFalse(legacy["enabled"])
        self.assertEqual("deprecated", legacy["status"])
        self.assertEqual(
            "legacy_business_schedule_binding", legacy["artifact_type"]
        )
        self.assertEqual("supported", legacy["workflow_capability_status"])
        self.assertTrue(mvp["enabled"])
        self.assertEqual("test_tracking", mvp["status"])
        self.assertEqual(
            "routine_business_schedule_binding", mvp["artifact_type"]
        )
        self.assertEqual(
            "/home/ubuntu/token_parse_sys_mvp/configs/strategies/steady_uptrend_mvp.json",
            mvp["strategy_config_path"],
        )
        self.assertEqual(
            "workflows/jobs/daily_steady_uptrend_mvp_tracking.py",
            mvp["job"],
        )
        self.assertEqual(
            "/home/ubuntu/token_parse_sys/runtime/strategy_tracking/reports",
            mvp["report_root"],
        )
        self.assertEqual(440, mvp["daily_lookback_calendar_days"])
        self.assertEqual(950, mvp["weekly_lookback_calendar_days"])


if __name__ == "__main__":
    unittest.main()
