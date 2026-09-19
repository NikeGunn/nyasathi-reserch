"""Build NEPVERSA benchmark items from harvested provisions.

    python -m nepversa.build_benchmark corpus/raw/*.jsonl --out benchmark/candidates/

Reads harvested JSONL, expands amendment provenance into provision versions,
and emits deterministically-gradable items. Every item carries the published
statement it was derived from, and every item is `status=unverified` until a
human audits it (the rule that only humans confirm gold).

The statistics this prints are the ones the paper's dataset table needs, and
they are counted from the file rather than asserted — the root `CLAUDE.md`
records a doc that claimed "85 tests passing" against a directory that did not
exist.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .amendments import AmendedUnit, Operation
from .benchmark import BenchmarkItem, generate_for_provision, whole_section_repeal_item
from .versions import build_versions


def _amended_units_from_row(row: dict) -> list[AmendedUnit]:
    return [
        AmendedUnit(
            unit=u["unit"],
            operation=Operation(u["operation"]),
            amendment_ordinal=u.get("amendment_ordinal"),
            footnote_marker=u.get("footnote_marker", ""),
            text=u.get("text", ""),
        )
        for u in row.get("amended_units", [])
    ]


def items_from_row(row: dict) -> list[BenchmarkItem]:
    url = row.get("source_url", "")
    if row.get("repealed_in_full"):
        # A section repealed in full has no surviving clauses to expand, so the
        # clause-level path yields nothing. It is nonetheless the clearest T3
        # item available: the law states the whole provision is gone.
        item = whole_section_repeal_item(row, source_url=url)
        return [item] if item else []
    units = _amended_units_from_row(row)
    if not units:
        return []
    versions = build_versions(row["citation_key"], units)
    return generate_for_provision(versions, source_url=url)


def _row(item: BenchmarkItem) -> dict:
    d = asdict(item)
    d["question_type"] = item.question_type.value
    d["script"] = item.script.value
    d["gold_state"] = item.gold_state.value
    d["gold_nuggets"] = [asdict(n) for n in item.gold_nuggets]
    return d


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Build NEPVERSA benchmark candidates")
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    provisions = 0
    amended_provisions = 0
    items: list[BenchmarkItem] = []
    ops: Counter[str] = Counter()

    for path in args.inputs:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            provisions += 1
            units = _amended_units_from_row(row)
            if units:
                amended_provisions += 1
                ops.update(u.operation.value for u in units)
            items.extend(items_from_row(row))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(_row(item), ensure_ascii=False) + "\n")

    by_type = Counter(i.question_type.value for i in items)
    abstain = sum(1 for i in items if i.should_abstain)
    print(f"provisions read          : {provisions}")
    print(f"  with amendment footnote: {amended_provisions}")
    print(f"amendment operations     : {dict(ops)}")
    print(f"benchmark items written  : {len(items)}  -> {args.out}")
    print(f"  by type                : {dict(by_type)}")
    print(f"  abstention-expected    : {abstain}")
    print("  status                 : all 'unverified' (human audit pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
