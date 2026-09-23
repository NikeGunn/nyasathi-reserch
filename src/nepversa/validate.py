"""Corpus validation: cross-check the signals against each other.

Three silent-miss bugs were found in a single act by hand, each the same shape:
the provision text carried inline amendment markers, the parsed record said the
provision was un-amended, and **nothing in the output disagreed with itself**.
A missed amendment looks exactly like a provision that was never amended.

This module makes that check automatic. It is run over a harvested file and
reports every disagreement between three independent signals:

1. **Inline markers** in the text — `1(d1)`, `२(ङ)`.
2. **Parsed `amended_units`** — what the footnote legend resolved to.
3. **Section numbering** — `12A` / `१२क` exists only because an amendment
   inserted it.

A disagreement is not automatically a bug, but it is always a question worth
answering before the corpus is used. an earlier corpus survey
records the same lesson from the product side: a coverage-only check ("32 of 34,
good enough") shipped an act whose most-cited provision was silently missing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .amendments import _INLINE_RE, _fold_digits, inserted_by_numbering

_ELIDED_RE = re.compile(r"[\.…]{3,}")


@dataclass(frozen=True, slots=True)
class Finding:
    """One disagreement between signals, for a human to resolve."""

    citation_key: str
    kind: str
    detail: str
    source_url: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.citation_key}: {self.detail}\n    {self.source_url}"


def check_row(row: dict) -> list[Finding]:
    """Cross-check one harvested provision."""
    findings: list[Finding] = []
    key = row.get("citation_key", "?")
    url = row.get("source_url", "")
    text = row.get("text", "")
    units = row.get("amended_units", [])
    footnotes = row.get("footnotes", [])

    # 1. Inline markers present but nothing parsed -> the bug class that cost
    #    three provisions in the Banking Offences Act.
    #    With the page HTML, count its `<sup>` markers: that is what the source
    #    states. The Markdown-shape fallback reads `10)` and "(1977)" as
    #    markers; on the five-Act corpus it raised 27 such findings, all noise.
    html_count = row.get("inline_marker_count")
    if html_count is not None:
        # A wholly repealed section's one marker belongs to the section itself
        # (`1……` under "Repealed by ..."), recorded as `repealed_in_full`.
        expected = len(units) + (1 if row.get("repealed_in_full") else 0)
        if html_count > expected:
            findings.append(
                Finding(
                    key,
                    "MARKERS_WITHOUT_UNITS",
                    f"page HTML carries {html_count} inline marker(s) but only "
                    f"{len(units)} amended unit(s) were parsed ({len(footnotes)} footnotes)",
                    url,
                )
            )
        inline: set = set()
    else:
        inline = {m.group(2) or m.group(4) for m in _INLINE_RE.finditer(_fold_digits(text))}
    if inline and not units:
        findings.append(
            Finding(
                key,
                "MARKERS_WITHOUT_UNITS",
                f"text carries inline markers {sorted(inline)} but no amended_units "
                f"were parsed ({len(footnotes)} footnotes found)",
                url,
            )
        )

    # 2. Elided text (a row of dots) with no REPEAL recorded anywhere.
    if _ELIDED_RE.search(text) and not row.get("repealed_in_full"):
        if not any(f.get("operation") == "repeal" for f in footnotes):
            findings.append(
                Finding(
                    key,
                    "ELISION_WITHOUT_REPEAL",
                    "text contains an elision run but no repeal is recorded",
                    url,
                )
            )

    # 3. A lettered section number with no amendment evidence at all.
    number = row.get("number", "")
    if inserted_by_numbering(number) and not (units or footnotes):
        findings.append(
            Finding(
                key,
                "LETTERED_WITHOUT_PROVENANCE",
                f"section {number} is amendment-inserted by numbering, but the "
                f"page records no amendment footnote",
                url,
            )
        )

    # 4. A footnote parsed but attached to nothing.
    attached = {u.get("footnote_marker") for u in units}
    for f in footnotes:
        if f.get("marker") not in attached and not row.get("repealed_in_full"):
            findings.append(
                Finding(
                    key,
                    "ORPHAN_FOOTNOTE",
                    f"footnote {f.get('marker')!r} ({f.get('text', '')!r}) "
                    f"matched no inline marker",
                    url,
                )
            )

    return findings


def check_file(path: Path) -> tuple[list[Finding], dict[str, int]]:
    findings: list[Finding] = []
    stats = {"provisions": 0, "amended": 0, "repealed_in_full": 0, "lettered": 0}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        stats["provisions"] += 1
        if row.get("amended_units"):
            stats["amended"] += 1
        if row.get("repealed_in_full"):
            stats["repealed_in_full"] += 1
        if inserted_by_numbering(row.get("number", "")):
            stats["lettered"] += 1
        findings.extend(check_row(row))
    return findings, stats


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Cross-check a harvested corpus file")
    ap.add_argument("inputs", nargs="+", type=Path)
    args = ap.parse_args(argv)

    total: list[Finding] = []
    for path in args.inputs:
        findings, stats = check_file(path)
        print(f"=== {path.name}")
        print(
            f"    provisions={stats['provisions']} amended={stats['amended']} "
            f"repealed_in_full={stats['repealed_in_full']} lettered={stats['lettered']}"
        )
        for f in findings:
            print(f"    {f}")
        total.extend(findings)

    print(f"\n{len(total)} finding(s)")
    # Findings are questions, not failures: exit 0 so a harvest pipeline can
    # report them without pretending the corpus is unusable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
