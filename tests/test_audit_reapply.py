"""Restoring audit verdicts where the audit sheet is not available.

The public release ships `AUDIT/audit_log.json` but not the sheet, because the
sheet quotes statutory text. `build_benchmark` writes every item as
`unverified`, so before this path existed a reviewer's rebuild from the public
repository either stopped at `audit_sheet.py reapply` (sheet missing) or, had
the step been skipped, reported 0 verified items against the paper's 181.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

import audit_sheet  # noqa: E402


def _bench(tmp_path: Path, ids: list[str]) -> Path:
    bench = tmp_path / "benchmark" / "candidates"
    bench.mkdir(parents=True)
    rows = [{"item_id": i, "status": "unverified"} for i in ids]
    (bench / "act.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return bench


def _statuses(bench: Path) -> dict[str, str]:
    rows = [json.loads(line) for line in (bench / "act.jsonl").read_text(encoding="utf-8").splitlines()]
    return {r["item_id"]: r["status"] for r in rows}


def _log(verdicts: dict[str, str]) -> dict:
    return {
        "counts": {"correct": 0, "incorrect": 0, "unsure": 0},
        "verdicts": {k: {"verdict": v, "corrected_answer": "", "note": ""} for k, v in verdicts.items()},
    }


def test_verdicts_become_statuses(tmp_path, monkeypatch):
    bench = _bench(tmp_path, ["a", "b", "c", "d"])
    monkeypatch.setattr(audit_sheet, "BENCH", bench)
    rc = audit_sheet.reapply_from_log(_log({"a": "correct", "b": "incorrect", "c": "unsure"}))
    assert rc == 0
    assert _statuses(bench) == {
        "a": "verified",
        "b": "rejected_by_audit",
        "c": "unverified",
        "d": "unverified",  # no verdict recorded
    }


def test_verdict_for_unknown_item_is_refused_and_writes_nothing(tmp_path, monkeypatch):
    bench = _bench(tmp_path, ["a"])
    monkeypatch.setattr(audit_sheet, "BENCH", bench)
    rc = audit_sheet.reapply_from_log(_log({"a": "correct", "ghost": "correct"}))
    assert rc == 1
    assert _statuses(bench) == {"a": "unverified"}


def test_reapply_uses_the_log_when_the_sheet_is_absent(tmp_path, monkeypatch):
    bench = _bench(tmp_path, ["a"])
    audit = tmp_path / "AUDIT"
    audit.mkdir()
    log = {**_log({"a": "correct"}), "sheet": "audit_sheet_v2.csv",
           "auditor": "x", "qualification": "y", "applied_at": "2026-09-23T00:00:00+00:00"}
    (audit / "audit_log.json").write_text(json.dumps(log), encoding="utf-8")
    monkeypatch.setattr(audit_sheet, "BENCH", bench)
    monkeypatch.setattr(audit_sheet, "AUDIT", audit)
    monkeypatch.setattr(audit_sheet, "LOG", audit / "audit_log.json")
    monkeypatch.setattr(sys, "argv", ["audit_sheet.py", "reapply"])
    assert audit_sheet.main() == 0
    assert _statuses(bench) == {"a": "verified"}
