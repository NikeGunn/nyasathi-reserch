"""Human audit of benchmark items: export a sheet, then apply the verdicts.

    python analysis/audit_sheet.py export                 # -> AUDIT/audit_sheet_v2.csv
    python analysis/audit_sheet.py apply AUDIT/audit_sheet_v2.csv \
        --auditor "Nikhil Bhagat" --qualification "BCA; not legally trained"

The ONLY route by which an item becomes `status=verified`. A person opens the
sheet (Excel reads it: UTF-8 with BOM), follows each row's source link, and
writes `correct`, `incorrect` or `unsure` in the `verdict` column.

`apply` then:
  * sets `status=verified` for `correct` rows only;
  * sets `status=rejected_by_audit` for `incorrect` rows (kept, not deleted, so
    the error is countable and the item can be fixed);
  * leaves blank and `unsure` rows `unverified`;
  * refuses rows whose item text changed since export (the sheet must describe
    the item that is being certified), unknown verdicts, and duplicate ids;
  * writes `AUDIT/audit_log.json`: who, qualification, when, and per-item
    verdicts. The release manifest's `items_verified_by_human` is read from it,
    and CI fails if more items say `verified` than the log records.

Nothing here decides a verdict. A row nobody filled in stays unverified.

    python analysis/audit_sheet.py reapply                # after build_benchmark

`build_benchmark` rewrites every item as `unverified`; `reapply` restores the
recorded verdicts from the sheet named in the log, keeping the original auditor
and date, and refuses (as `apply` does) if any item changed since the audit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark" / "candidates"
AUDIT = ROOT / "AUDIT"
SHEET = AUDIT / "audit_sheet_v2.csv"
LOG = AUDIT / "audit_log.json"
VERDICTS = {"correct", "incorrect", "unsure", ""}
FIELDS = ["item_id", "act_section_unit", "question_type", "question",
          "expected_answer", "licensed_by_footnote", "source_url",
          "verdict", "corrected_answer", "note", "item_fingerprint"]


def _items() -> list[tuple[Path, dict]]:
    out = []
    for f in sorted(BENCH.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append((f, json.loads(line)))
    return out


def _fingerprint(it: dict) -> str:
    core = {k: it[k] for k in ("item_id", "question", "gold_state", "gold_nuggets", "provenance")}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _expected(it: dict) -> str:
    if it["gold_state"] == "absent":
        return "NOT IN FORCE at that point: a correct system refuses / says it did not exist"
    exact = next((n["value"] for n in it["gold_nuggets"] if n["kind"] == "exact"), "")
    return f"In force; the text begins: \"{exact} ...\" (cite {it['citation_key']})"


def export() -> int:
    AUDIT.mkdir(exist_ok=True)
    with SHEET.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for _, it in _items():
            w.writerow({
                "item_id": it["item_id"],
                "act_section_unit": f"{it['citation_key'].split(':', 1)[1]} ({it['unit'] or 'whole section'})",
                "question_type": it["question_type"],
                "question": it["question"],
                "expected_answer": _expected(it),
                "licensed_by_footnote": it["provenance"],
                "source_url": it.get("source_url", ""),
                "verdict": "", "corrected_answer": "", "note": "",
                "item_fingerprint": _fingerprint(it),
            })
    print(f"wrote {SHEET} ({len(_items())} rows). Fill the 'verdict' column: correct / incorrect / unsure.")
    return 0


def apply(sheet: Path, auditor: str, qualification: str, applied_at: str | None = None) -> int:
    rows = list(csv.DictReader(sheet.open(encoding="utf-8-sig")))
    by_id = {it["item_id"]: (f, it) for f, it in _items()}
    problems, seen, verdicts = [], set(), {}
    for n, r in enumerate(rows, start=2):
        iid, v = r["item_id"], r["verdict"].strip().lower()
        if iid in seen:
            problems.append(f"row {n}: duplicate item {iid}")
        seen.add(iid)
        if v not in VERDICTS:
            problems.append(f"row {n}: verdict {r['verdict']!r} is not correct/incorrect/unsure/blank")
        if iid not in by_id:
            problems.append(f"row {n}: item {iid} is not in the current benchmark")
        elif _fingerprint(by_id[iid][1]) != r["item_fingerprint"]:
            problems.append(f"row {n}: item {iid} changed after the sheet was exported; re-export")
        if v:
            verdicts[iid] = {"verdict": v, "corrected_answer": r["corrected_answer"], "note": r["note"]}
    if problems:
        print("audit sheet refused:", *problems, sep="\n  ")
        return 1

    status = {"correct": "verified", "incorrect": "rejected_by_audit"}
    touched: dict[Path, list[dict]] = {}
    for f, it in _items():
        v = verdicts.get(it["item_id"], {}).get("verdict", "")
        it["status"] = status.get(v, "unverified")
        touched.setdefault(f, []).append(it)
    for f, items in touched.items():
        f.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")

    counts = {k: sum(1 for x in verdicts.values() if x["verdict"] == k)
              for k in ("correct", "incorrect", "unsure")}
    LOG.write_text(json.dumps({
        "auditor": auditor,
        "qualification": qualification,
        "applied_at": applied_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sheet": sheet.name,
        "items_total": len(by_id),
        "items_with_verdict": len(verdicts),
        "counts": counts,
        "items_verified_by_human": counts["correct"],
        "verdicts": verdicts,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"applied: {counts} of {len(by_id)} items; {len(by_id) - len(verdicts)} left unverified -> {LOG}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export")
    sub.add_parser("reapply")
    a = sub.add_parser("apply")
    a.add_argument("sheet", type=Path)
    a.add_argument("--auditor", required=True)
    a.add_argument("--qualification", required=True,
                   help="stated plainly, e.g. 'BCA; not legally trained' or 'Advocate, Nepal Bar Council'")
    args = ap.parse_args()
    if args.cmd == "export":
        return export()
    if args.cmd == "reapply":
        if not LOG.exists():
            print("no audit log; nothing to reapply")
            return 0
        log = json.loads(LOG.read_text(encoding="utf-8"))
        return apply(AUDIT / log["sheet"], log["auditor"], log["qualification"], log["applied_at"])
    return apply(args.sheet, args.auditor, args.qualification)


if __name__ == "__main__":
    sys.exit(main())
