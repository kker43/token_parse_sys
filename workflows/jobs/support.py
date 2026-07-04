"""Shared helpers for workflow job result rendering."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string for job metadata."""

    return datetime.now(timezone.utc).isoformat()


def write_json_payload(path: str | Path, payload: Mapping[str, object]) -> None:
    """Write one structured JSON result payload."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
