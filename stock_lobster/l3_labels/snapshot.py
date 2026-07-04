"""Label snapshot schema."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from stock_lobster.core.ids import RunId


@dataclass(frozen=True, slots=True)
class LabelSnapshot:
    """Deterministic label result for one stock and date."""

    label_id: str
    label_version: str
    stock_code: str
    snapshot_date: str
    run_id: RunId
    values: Mapping[str, bool | float]
