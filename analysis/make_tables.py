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


def extraction_stats(acts: set[str]) -> dict:
    """Amended units found by the HTML `<sup>` route vs a Markdown-only reading.

    The corpus is built from the HTML route. The Markdown route is what the
    pipeline used before corpus v2.0.0, re-run here over the same cached pages
    so the two can be compared unit by unit: `md_only` are units Markdown
    inference invents (a plain `10)` read as footnote 1 + unit `0`), and
    `html_only` are units it misses.
    """
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from nepversa.provision import ProvisionParseError, parse_provision

    per_act: dict[str, Counter] = {}
    for cache in sorted((ROOT / "corpus" / "cache").iterdir()):
        index = cache / "_urls.json"
        if not index.exists():
            continue
        for url in json.loads(index.read_text(encoding="utf-8")):
            import hashlib

            stem = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            md_path, html_path = cache / f"{stem}.md", cache / f"{stem}.html"
            if not (md_path.exists() and html_path.exists()):
                continue
            md = md_path.read_text(encoding="utf-8")
            try:
                by_html = parse_provision(md, url, html=html_path.read_text(encoding="utf-8"))
                by_md = parse_provision(md, url)
            except ProvisionParseError:
                continue
            if by_html.act_slug not in acts:
                continue
            h = {(u.footnote_marker, u.path) for u in by_html.amended_units}
            m = {(u.footnote_marker, u.path) for u in by_md.amended_units}
            c = per_act.setdefault(by_html.act_slug, Counter())
            c["units_html"] += len(h)
            c["units_markdown"] += len(m)
            c["agree"] += len(h & m)
            c["md_only"] += len(m - h)
            c["html_only"] += len(h - m)
            c["provisions_disagreeing"] += bool(h ^ m)
    total = Counter()
    for c in per_act.values():
        total.update(c)
    return {
        "per_act": [{"act": a, **dict(c)} for a, c in sorted(per_act.items())],
        **{k: total[k] for k in ("units_html", "units_markdown", "agree", "md_only",
                                 "html_only", "provisions_disagreeing")},
    }


def benchmark_stats() -> dict:
    """Benchmark composition, counted from the generated items."""
    by_type: Counter[str] = Counter()
    abstain_by_type: Counter[str] = Counter()
    abstain = 0
    nugget_kinds: Counter[str] = Counter()
    acts: set[str] = set()
    total = 0

    for path in sorted(BENCH.glob("*.jsonl")):
        for item in _rows(path):
            total += 1
            by_type[item["question_type"]] += 1
            abstain += bool(item["should_abstain"])
            abstain_by_type[item["question_type"]] += bool(item["should_abstain"])
            acts.add(item["citation_key"].split("#")[0])
            nugget_kinds.update(n["kind"] for n in item["gold_nuggets"])

    return {
        "items": total,
        "acts_covered": len(acts),
        "t2_point_in_time": by_type.get("T2_point_in_time", 0),
        "t3_supersession": by_type.get("T3_supersession", 0),
        "t2_abstention": abstain_by_type.get("T2_point_in_time", 0),
        "t3_abstention": abstain_by_type.get("T3_supersession", 0),
        "instrument_anchored": sum(1 for p in sorted(BENCH.glob("*.jsonl"))
                                   for i in _rows(p) if i.get("as_of_amendment") is None
                                   and i["question_type"] == "T2_point_in_time"),
        "abstention_expected": abstain,
        "abstention_pct": round(100 * abstain / max(total, 1), 1),
        "nugget_label": nugget_kinds["label"],
        "nugget_citation": nugget_kinds["citation"],
        "nugget_exact": nugget_kinds["exact"],
        # Status is counted from the items, which only analysis/audit_sheet.py
        # changes; the paper states these numbers, never a claim of its own.
        "status_unverified": sum(1 for p in sorted(BENCH.glob("*.jsonl")) for i in _rows(p)
                                 if i.get("status", "unverified") == "unverified"),
        "status_verified": sum(1 for p in sorted(BENCH.glob("*.jsonl")) for i in _rows(p)
                               if i.get("status") == "verified"),
        "status_rejected_by_audit": sum(1 for p in sorted(BENCH.glob("*.jsonl")) for i in _rows(p)
                                        if i.get("status") == "rejected_by_audit"),
    }


_TITLES = {
    "banking-offence-and-punishment-act-2064": "Banking Offence and Punishment Act, 2064",
    "bonus-act-2030": "Bonus Act, 2030",
    "companies-act-2063-2006": "Companies Act, 2063",
    "foreign-exchange-regulation-act-2019": "Foreign Exchange (Regulation) Act, 2019",
    "income-tax-act-2058-2002": "Income Tax Act, 2058",
}


def _title(slug: str) -> str:
    """The Act's short title (BS year). An unknown slug fails loudly."""
    if slug not in _TITLES:
        raise KeyError(f"no display title for Act {slug!r}; add it to _TITLES")
    return _TITLES[slug]


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    # Dash counts set Pandoc's relative column widths: the first column holds an
    # Act's full title and, at equal widths, wrapped one word per line.
    widths = [14] + [max(3, len(h) // 2 + 2) for h in headers[1:]]
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("-" * w for w in widths) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def main() -> int:
    agg, per_act = corpus_stats()
    bench = benchmark_stats()

    (SHARED / "tables").mkdir(parents=True, exist_ok=True)

    # Table 1 — corpus composition by act
    (SHARED / "tables" / "table1_corpus.md").write_text(
        _md_table(
            ["Act", "Provisions", "Amended", "Density (%)", "Lettered", "Repealed in full",
             "INS", "SUB", "REP"],
            [
                [
                    _title(a["act"]),
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
                ["T2 point-in-time", str(bench["t2_point_in_time"]), str(bench["t2_abstention"])],
                ["T3 supersession", str(bench["t3_supersession"]), str(bench["t3_abstention"])],
                ["**Total**", f'**{bench["items"]}**',
                 f'**{bench["abstention_expected"]}** ({bench["abstention_pct"]}%)'],
            ],
        ),
        encoding="utf-8",
    )

    extraction = extraction_stats({a["act"] for a in per_act})
    # Marker accounting: every `<sup>` marker in the page HTML must be on a
    # unit, on a wholly repealed section, or reported by the validator.
    acc = Counter()
    for path in sorted(CORPUS.glob("*.jsonl")):
        for r in _rows(path):
            c = r.get("inline_marker_count") or 0
            u = len(r.get("amended_units", []))
            w = 1 if (r.get("repealed_in_full") and c) else 0
            acc["html_markers"] += c
            acc["markers_on_units"] += u
            acc["markers_whole_section"] += w
            extra = max(0, c - u - w)
            acc["markers_unattached"] += extra
            acc["provisions_unattached"] += extra > 0
    extraction.update(acc)
    (SHARED / "tables" / "table3_extraction.md").write_text(
        _md_table(
            ["Act", "Units (HTML)", "Units (Markdown only)", "Agree", "Markdown only",
             "HTML only", "Provisions disagreeing"],
            [
                [_title(e["act"]), str(e.get("units_html", 0)),
                 str(e.get("units_markdown", 0)), str(e.get("agree", 0)),
                 str(e.get("md_only", 0)), str(e.get("html_only", 0)),
                 str(e.get("provisions_disagreeing", 0))]
                for e in extraction["per_act"]
            ]
            + [["**Total**"] + [f'**{extraction[k]}**' for k in
                ("units_html", "units_markdown", "agree", "md_only", "html_only",
                 "provisions_disagreeing")]],
        ),
        encoding="utf-8",
    )

    numbers = {"corpus": agg, "per_act": per_act, "benchmark": bench,
               "extraction_by_act": extraction["per_act"],
               "extraction": {k: v for k, v in extraction.items() if k != "per_act"}}
    (SHARED / "numbers.json").write_text(
        json.dumps(numbers, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(json.dumps(numbers, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
