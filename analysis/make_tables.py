"""Generate every table and number the manuscript reports.

    python analysis/make_tables.py

Reads `corpus/raw/*.jsonl` and `benchmark/candidates/*.jsonl` and writes:

    paper/shared/numbers.json        every reported number, keyed
    paper/shared/tables/*.md         Markdown tables for the APA build

PAPER_PLAN.md §1 rule 1 and §14 rule 1: no number is typed into a manuscript by
hand. If a value is not in `numbers.json` it does not appear in the paper. The
root `CLAUDE.md` records a product doc that claimed "85 tests passing" against a
directory that did not exist — count from the artefact, always.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus" / "raw"
BENCH = ROOT / "benchmark" / "candidates"
SHARED = ROOT / "paper" / "shared"


def _rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def corpus_stats() -> tuple[dict, list[dict]]:
    """Per-act and aggregate corpus statistics, counted from the files."""
    per_act: list[dict] = []
    totals = Counter()
    ops = Counter()

    for path in sorted(CORPUS.glob("*.jsonl")):
        rows = _rows(path)
        if not rows:
            continue
        act_ops: Counter[str] = Counter()
        amended = lettered = repealed = 0
        for r in rows:
            units = r.get("amended_units", [])
            if units:
                amended += 1
                act_ops.update(u["operation"] for u in units)
            if r.get("inserted_by_amendment_numbering"):
                lettered += 1
            if r.get("repealed_in_full"):
                repealed += 1

        per_act.append(
            {
                "act": rows[0]["act_slug"],
                "provisions": len(rows),
                "amended": amended,
                "amended_pct": round(100 * amended / len(rows), 1),
                "lettered": lettered,
                "repealed_in_full": repealed,
                "insert": act_ops["insert"],
                "substitute": act_ops["substitute"],
                "repeal": act_ops["repeal"],
                "units_total": sum(act_ops.values()),
            }
        )
        totals["provisions"] += len(rows)
        totals["amended"] += amended
        totals["lettered"] += lettered
        totals["repealed_in_full"] += repealed
        ops.update(act_ops)

    agg = {
        "acts": len(per_act),
        "provisions": totals["provisions"],
        "amended_provisions": totals["amended"],
        "amended_pct": round(100 * totals["amended"] / max(totals["provisions"], 1), 1),
        "lettered_sections": totals["lettered"],
        "repealed_in_full": totals["repealed_in_full"],
        "amendment_units": sum(ops.values()),
        "op_insert": ops["insert"],
        "op_substitute": ops["substitute"],
        "op_repeal": ops["repeal"],
    }
    return agg, per_act


def benchmark_stats() -> dict:
    """Benchmark composition, counted from the generated items."""
    by_type: Counter[str] = Counter()
    abstain = 0
    nugget_kinds: Counter[str] = Counter()
    acts: set[str] = set()
    total = 0

    for path in sorted(BENCH.glob("*.jsonl")):
        for item in _rows(path):
            total += 1
            by_type[item["question_type"]] += 1
            abstain += bool(item["should_abstain"])
            acts.add(item["citation_key"].split("#")[0])
            nugget_kinds.update(n["kind"] for n in item["gold_nuggets"])

    return {
        "items": total,
        "acts_covered": len(acts),
        "t2_point_in_time": by_type.get("T2_point_in_time", 0),
        "t3_supersession": by_type.get("T3_supersession", 0),
        "abstention_expected": abstain,
        "abstention_pct": round(100 * abstain / max(total, 1), 1),
        "nugget_label": nugget_kinds["label"],
        "nugget_citation": nugget_kinds["citation"],
        "nugget_exact": nugget_kinds["exact"],
        "status_unverified": total,  # nothing audited yet
    }


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def main() -> int:
    agg, per_act = corpus_stats()
    bench = benchmark_stats()

    (SHARED / "tables").mkdir(parents=True, exist_ok=True)

    # Table 1 — corpus composition by act
    (SHARED / "tables" / "table1_corpus.md").write_text(
        _md_table(
            ["Act", "Provisions", "Amended", "%", "Lettered", "Repealed in full",
             "INS", "SUB", "REP"],
            [
                [
                    a["act"].replace("-", " ").title(),
                    str(a["provisions"]), str(a["amended"]), f'{a["amended_pct"]}',
                    str(a["lettered"]), str(a["repealed_in_full"]),
                    str(a["insert"]), str(a["substitute"]), str(a["repeal"]),
                ]
                for a in per_act
            ]
            + [[
                "**Total**", f'**{agg["provisions"]}**', f'**{agg["amended_provisions"]}**',
                f'**{agg["amended_pct"]}**', f'**{agg["lettered_sections"]}**',
                f'**{agg["repealed_in_full"]}**', f'**{agg["op_insert"]}**',
                f'**{agg["op_substitute"]}**', f'**{agg["op_repeal"]}**',
            ]],
        ),
        encoding="utf-8",
    )

    # Table 2 — benchmark composition
    (SHARED / "tables" / "table2_benchmark.md").write_text(
        _md_table(
            ["Question type", "Items", "Abstention expected"],
            [
                ["T2 point-in-time", str(bench["t2_point_in_time"]), "—"],
                ["T3 supersession", str(bench["t3_supersession"]),
                 str(bench["t3_supersession"])],
                ["**Total**", f'**{bench["items"]}**',
                 f'**{bench["abstention_expected"]}** ({bench["abstention_pct"]}%)'],
            ],
        ),
        encoding="utf-8",
    )

    numbers = {"corpus": agg, "per_act": per_act, "benchmark": bench}
    (SHARED / "numbers.json").write_text(
        json.dumps(numbers, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
