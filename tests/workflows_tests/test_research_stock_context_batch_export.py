"""Tests for batch stock-context export used by research backtests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from workflows.jobs.research_stock_context_batch_export import (
    STOCK_CONTEXT_HEADER,
    export_stock_context_batch,
)


class ResearchStockContextBatchExportTest(unittest.TestCase):
    def test_exports_sorted_unique_trade_dates_to_one_tsv_and_manifest(self) -> None:
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            output_path = root / "stock_context.tsv"
            manifest_path = root / "stock_context_manifest.json"
            calls: list[str] = []

            def fetch_rows_for_date(trade_date: str) -> tuple[dict[str, object], ...]:
                calls.append(trade_date)
                return (
                    {
                        "asset_id": f"00000{len(calls)}.SZ",
                        "trade_date": trade_date,
                        "name": "样本",
                        "industry": "行业",
                        "market": "主板",
                        "list_status": "L",
                        "total_mv": 1_000_000,
                        "turnover_rate": 1.2,
                        "max_turnover_rate_20d": 3.4,
                        "avg_turnover_rate_20d": 1.5,
                        "avg_amount_20d": 2_000_000,
                        "strong_industry_hit": 1,
                        "strong_concept_hit": 0,
                        "strong_industry_names": "PCB概念",
                        "strong_concept_names": "",
                        "volume_ratio_5d_20d": 1.25,
                        "max_volume_ratio_5d_20d": 2.13,
                        "turnover_ratio_5d_20d": 1.29,
                        "adj_factor_changed_20d": 0,
                    },
                )

            manifest = export_stock_context_batch(
                fetch_rows_for_date=fetch_rows_for_date,
                trade_dates=("20260103", "20260101", "20260103"),
                output_path=output_path,
                manifest_path=manifest_path,
            )

            lines = output_path.read_text(encoding="utf-8").splitlines()
            persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(["20260101", "20260103"], calls)
            self.assertEqual("\t".join(STOCK_CONTEXT_HEADER), lines[0])
            self.assertEqual(3, len(lines))
            self.assertIn("000001.SZ\t20260101", lines[1])
            self.assertIn("000002.SZ\t20260103", lines[2])
            self.assertEqual("adj_factor_changed_20d", STOCK_CONTEXT_HEADER[-1])
            self.assertTrue(lines[1].endswith("\t1.25\t2.13\t1.29\t0"))
            self.assertEqual(
                {
                    "20260101": 1,
                    "20260103": 1,
                },
                manifest["rows_by_trade_date"],
            )
            self.assertEqual(2, manifest["row_count"])
            self.assertEqual(
                {
                    "total_mv": "ten_thousand_cny",
                    "avg_amount_20d": "thousand_cny",
                },
                manifest["field_units"],
            )
            self.assertEqual("v1", manifest["data_version"])
            self.assertEqual(64, len(manifest["sha256"]))
            self.assertEqual(manifest, persisted_manifest)


if __name__ == "__main__":
    unittest.main()
