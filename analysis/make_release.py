"""Build the public release bundle.

    python analysis/make_release.py --out release/

The licence status of Nepali statutory text is unresolved (see
`corpus/SOURCES.md`). Government legal texts are typically freely reproducible,
but "typically" is not a licence, and the source aggregator publishes no terms.

So the release carries **everything except the statutory text itself**:

* citation keys, section numbers, headings
* amendment provenance — operation, ordinal, footnote sentence
* validity windows and benchmark items
* SHA-256 of each provision's text, so a rebuild can be verified byte-for-byte
* offsets and lengths, so annotations can be re-anchored
* the harvester, which reconstructs the full corpus from the live source

A verbatim span is replaced by its SHA-256 and length. That keeps the nugget
checkable after a rebuild — hash the candidate span and compare — without
redistributing the text. Anyone who runs the harvester gets the same corpus and
can verify it matches ours by hash.

If the licence is later clarified, `--include-text` produces the full bundle
without changing any identifier.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_TEXT_FIELDS = ("text",)
"""Fields holding statutory text verbatim."""


def _digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def redact_corpus_row(row: dict) -> dict:
    """Drop statutory text, keep everything that identifies and verifies it."""
    out = dict(row)
    for field in _TEXT_FIELDS:
        text = out.pop(field, "")
        out[f"{field}_sha256"] = _digest(text)
        out[f"{field}_length"] = len(text)

    # Amendment units carry the post-amendment clause text.
    out["amended_units"] = [
        {
            **{k: v for k, v in u.items() if k != "text"},
            "text_sha256": _digest(u.get("text", "")),
            "text_length": len(u.get("text", "")),
        }
        for u in row.get("amended_units", [])
    ]
    # Footnote sentences are editorial apparatus naming the amendment, not
    # statutory text, and they are the provenance a reviewer must be able to
    # check. They are kept.
    return out


def redact_item(item: dict) -> dict:
    """Replace verbatim gold spans with a verifiable digest."""
    out = dict(item)
    out["gold_nuggets"] = [
        (
            {
                "kind": n["kind"],
                "value_sha256": _digest(n["value"]),
                "value_length": len(n["value"]),
            }
            if n["kind"] == "exact"
            else n
        )
        for n in item.get("gold_nuggets", [])
    ]
    return out


def _copy_jsonl(src: Path, dst: Path, fn) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with dst.open("w", encoding="utf-8") as fh:
        for line in src.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fh.write(json.dumps(fn(json.loads(line)), ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Build the public release bundle")
    ap.add_argument("--out", type=Path, default=ROOT / "release")
    ap.add_argument(
        "--include-text",
        action="store_true",
        help="include statutory text (only once the licence is confirmed)",
    )
    args = ap.parse_args(argv)

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    corpus_fn = (lambda r: r) if args.include_text else redact_corpus_row
    item_fn = (lambda r: r) if args.include_text else redact_item

    totals = {"provisions": 0, "items": 0}
    for src in sorted((ROOT / "corpus" / "raw").glob("*.jsonl")):
        totals["provisions"] += _copy_jsonl(src, out / "corpus" / src.name, corpus_fn)
    for src in sorted((ROOT / "benchmark" / "candidates").glob("*.jsonl")):
        totals["items"] += _copy_jsonl(src, out / "benchmark" / src.name, item_fn)

    # Code, docs and provenance travel verbatim.
    for rel in ("src", "tests", "analysis", "configs"):
        shutil.copytree(ROOT / rel, out / rel, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # `logs/decisions.md` is deliberately NOT released: it records private
    # decisions about the author's separate commercial tool.
    for rel in ("corpus/SOURCES.md", "benchmark/guidelines.md",
                "logs/PROVENANCE.md", "logs/citations_verified.md",
                "logs/lit_notes.md",
                "paper/shared/references.bib", "paper/shared/numbers.json"):
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)

    (out / "RELEASE_MANIFEST.json").write_text(
        json.dumps(
            {
                "statutory_text_included": args.include_text,
                "provisions": totals["provisions"],
                "benchmark_items": totals["items"],
                "redaction": "text replaced by sha256 + length; rebuild with src/nepversa/harvest.py",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(totals, indent=2))
    print(f"release written to {out}")
    print(f"statutory text included: {args.include_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
