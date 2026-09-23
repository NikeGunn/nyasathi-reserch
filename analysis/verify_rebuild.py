"""Check a rebuilt corpus and benchmark against the released hashes.

    python analysis/verify_rebuild.py --released corpus_released/ --rebuilt corpus/raw/
    python analysis/verify_rebuild.py --released-items benchmark_released/ \
                                      --rebuilt-items benchmark/candidates/

The release omits statutory text and carries `text_sha256` per provision (and
per amended unit, and per verbatim nugget). After re-harvesting, this script
hashes the rebuilt text and reports, per provision: MATCH, DIFFERENT (the site
changed the text since our retrieval date, or a parser differs), MISSING (in
the release, not rebuilt) or EXTRA. For items it compares ids, gold states and
nugget hashes. Exit status 0 only when everything matches.

A mismatch is not automatically an error in your rebuild: nepallaws.com edits
its pages, and every record carries the `retrieved_at` it was fetched at.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _load(d: Path) -> dict[str, dict]:
    out = {}
    for f in sorted(d.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r.get("citation_key") or r["item_id"]] = r
    return out


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def corpus(released: Path, rebuilt: Path) -> int:
    rel, reb = _load(released), _load(rebuilt)
    counts = {"MATCH": 0, "DIFFERENT": 0, "MISSING": 0, "EXTRA": 0}
    for key, r in rel.items():
        if key not in reb:
            counts["MISSING"] += 1
            print("MISSING  ", key)
            continue
        got = reb[key].get("text_sha256") or _sha(reb[key].get("text", ""))
        want = r.get("text_sha256") or _sha(r.get("text", ""))
        if got == want:
            counts["MATCH"] += 1
        else:
            counts["DIFFERENT"] += 1
            print("DIFFERENT", key, "(released retrieved_at", r.get("retrieved_at"), ")")
    for key in reb.keys() - rel.keys():
        counts["EXTRA"] += 1
        print("EXTRA    ", key)
    print("corpus:", counts)
    return 0 if counts["MATCH"] == len(rel) and not counts["EXTRA"] else 1


def items(released: Path, rebuilt: Path) -> int:
    rel, reb = _load(released), _load(rebuilt)
    bad = 0
    for iid, r in rel.items():
        b = reb.get(iid)
        if b is None:
            print("MISSING item", iid)
            bad += 1
            continue
        want = [(n["kind"], n.get("value_sha256") or _sha(n.get("value", ""))) for n in r["gold_nuggets"]]
        got = [(n["kind"], n.get("value_sha256") or _sha(n.get("value", ""))) for n in b["gold_nuggets"]]
        if r["gold_state"] != b["gold_state"] or want != got:
            print("DIFFERENT item", iid)
            bad += 1
    extra = reb.keys() - rel.keys()
    for iid in sorted(extra):
        print("EXTRA item", iid)
    print(f"items: {len(rel) - bad} of {len(rel)} match, {len(extra)} extra")
    return 0 if not bad and not extra else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--released", type=Path)
    ap.add_argument("--rebuilt", type=Path)
    ap.add_argument("--released-items", type=Path)
    ap.add_argument("--rebuilt-items", type=Path)
    a = ap.parse_args()
    rc = 0
    if a.released and a.rebuilt:
        rc |= corpus(a.released, a.rebuilt)
    if a.released_items and a.rebuilt_items:
        rc |= items(a.released_items, a.rebuilt_items)
    return rc


if __name__ == "__main__":
    sys.exit(main())
