"""Mechanical audit of every benchmark item against the corpus it was built from.

    python analysis/audit_items.py            # exits 1 on any violation

This is NOT the human legal audit (AUDIT/human_verification_required.md). It
checks the invariants a machine can check, over the whole set, so that a
reviewer rebuilding the release can confirm them in one command:

  1. every `exact` nugget occurs verbatim (character-exact) in the provision
     text it cites — the property the benchmark's quotation scoring relies on;
  2. every `citation` nugget equals the item's own citation key;
  3. `should_abstain` holds exactly when the gold state is `absent`, and every
     abstaining item carries the `absent` label nugget;
  4. item ids are unique, and one (key, unit, type, anchor) has one gold state;
  5. every item cites a provision that exists in the corpus, and its unit is an
     amended unit of that provision (or the whole section, for a full repeal);
  6. no item asks for text of a period the source does not print
     (`present_text_unknown` never appears as gold);
  7. no question says "before any amendment" for a unit whose amendment is
     named by instrument rather than ordinal (the v1.0.0 defect);
  8. each T2 gold state follows from the unit's operation and the side of the
     amendment the question asks about.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    corpus: dict[str, dict] = {}
    for f in sorted((ROOT / "corpus" / "raw").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                corpus[row["citation_key"]] = row

    items = []
    for f in sorted((ROOT / "benchmark" / "candidates").glob("*.jsonl")):
        items += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]

    problems: list[str] = []
    seen: set[str] = set()
    gold: dict[tuple, set[str]] = defaultdict(set)
    for it in items:
        iid, key = it["item_id"], it["citation_key"]
        row = corpus.get(key)
        if row is None:
            problems.append(f"{iid}: cites {key}, which is not in the corpus")
            continue
        if iid in seen:
            problems.append(f"{iid}: duplicate id")
        seen.add(iid)
        gold[(key, it["unit"], it["question_type"], it.get("as_of_amendment"), it.get("as_of_event"))].add(it["gold_state"])

        units = {u.get("parent") and f'{u["parent"]}({u["unit"]})' or u["unit"]: u
                 for u in row.get("amended_units", [])}
        if it["unit"] and it["unit"] not in units:
            problems.append(f"{iid}: unit ({it['unit']}) is not an amended unit of {key}")
        if not it["unit"] and not row.get("repealed_in_full"):
            problems.append(f"{iid}: whole-section item but {key} is not repealed in full")

        for n in it["gold_nuggets"]:
            if n["kind"] == "exact" and n["value"] not in row["text"]:
                problems.append(f"{iid}: exact nugget not found verbatim in {key}: {n['value'][:40]!r}")
            if n["kind"] == "citation" and n["value"] != key:
                problems.append(f"{iid}: citation nugget {n['value']} != {key}")

        absent = it["gold_state"] == "absent"
        if it["should_abstain"] != absent:
            problems.append(f"{iid}: should_abstain={it['should_abstain']} but gold_state={it['gold_state']}")
        if absent and not any(n["kind"] == "label" and n["value"] == "absent" for n in it["gold_nuggets"]):
            problems.append(f"{iid}: absent gold without an 'absent' label nugget")
        if it["gold_state"] == "present_text_unknown":
            problems.append(f"{iid}: gold is a period whose text the source does not print")
        unit = units.get(it["unit"])
        if unit is not None and it["question_type"] == "T2_point_in_time":
            if "any amendment" in it["question"] and unit.get("amendment_ordinal") is None:
                problems.append(f"{iid}: 'before any amendment' on a unit amended by "
                                f"a named instrument ({unit.get('amendment_event') or '?'})")
            # 8. Gold must follow from the unit's operation and the side of the
            #    amendment the question is anchored to.
            before = " before " in f" {it['question']} "
            op = unit["operation"]
            expected = {
                ("insert", True): "absent", ("insert", False): "present_text_known",
                ("repeal", False): "absent", ("substitute", False): "present_text_known",
            }.get((op, before))
            if expected is None or it["gold_state"] != expected:
                problems.append(f"{iid}: {op} unit, question anchored "
                                f"{'before' if before else 'after'} the amendment, "
                                f"gold {it['gold_state']} (expected {expected})")

    for k, states in gold.items():
        if len(states) > 1:
            problems.append(f"{k}: contradictory gold {sorted(states)}")

    print(f"items audited: {len(items)} against {len(corpus)} provisions")
    for p in problems:
        print("  FAIL", p)
    print("audit: PASS" if not problems else f"audit: {len(problems)} violation(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
