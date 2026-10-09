#!/usr/bin/env bash
# Reproduce every NEPVERSA number in the paper with one command.
#
#   bash reproduce.sh                  # quick check, ~1 minute, offline, no API key
#   bash reproduce.sh --from-source    # full rebuild from nepallaws.com, ~1 hour,
#                                      # needs the Firecrawl CLI (see REPRODUCE.md)
#   bash reproduce.sh --from-source --cache DIR   # full rebuild from saved pages
#
# Quick check: runs the tests, confirms the data files are the v2.0.0 release,
# and recounts every corpus and benchmark number from those files.
# Full rebuild: re-harvests the five Acts, re-derives every amendment and
# benchmark item, and compares the result with the release by SHA-256.
#
# Nothing in this folder is modified: every rebuild runs in a temporary copy.
# Exit status is 0 only when every number matches the paper.
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
export PYTHONUTF8=1
TAG="v2.0.0"

FROM_SOURCE=0
CACHE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-source) FROM_SOURCE=1 ;;
    --cache) CACHE="$(cd "$2" && pwd)"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# Two layouts share this script. The public release has corpus/*.jsonl with
# the statutory text replaced by hashes; the author's working copy has
# corpus/raw/*.jsonl with the text and corpus/cache/ with the fetched pages.
if [[ -d corpus/raw ]]; then
  LAYOUT=working; CORPUS=corpus/raw; BENCH=benchmark/candidates
  [[ -z "$CACHE" && -d corpus/cache ]] && { CACHE="$HERE/corpus/cache"; FROM_SOURCE=1; }
else
  LAYOUT=release; CORPUS=corpus; BENCH=benchmark
fi

PY="${PY:-}"
if [[ -z "$PY" ]]; then
  for cand in /c/ProgramData/anaconda3/python.exe python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import pytest" >/dev/null 2>&1; then
      PY="$cand"; break
    fi
  done
fi
[[ -n "$PY" ]] || { echo "no Python with pytest found: pip install pytest matplotlib defusedxml" >&2; exit 1; }

step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }

step "1/5  Environment"
"$PY" --version
echo "layout: $LAYOUT   mode: $([[ $FROM_SOURCE == 1 ]] && echo "full rebuild${CACHE:+ (cached pages)}" || echo "quick check")"

step "2/5  Unit tests"
PYTHONPATH=src "$PY" -m pytest tests -q -p no:cacheprovider 2>&1 | tail -1

step "3/5  Data is the $TAG release"
if [[ $LAYOUT == release ]]; then
  git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || git fetch -q --tags || true
  if git diff --quiet "$TAG" -- corpus benchmark AUDIT/audit_log.json paper/shared/numbers.json; then
    echo "  corpus/, benchmark/, AUDIT/audit_log.json, numbers.json: identical to tag $TAG"
  else
    echo "  data files differ from tag $TAG; run: git checkout $TAG -- corpus benchmark AUDIT paper/shared/numbers.json" >&2
    exit 1
  fi
else
  echo "  working copy: VERSION=$(cat VERSION); compared with the paper's numbers.json below"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [[ $FROM_SOURCE == 1 ]]; then
  step "4/5  Rebuild corpus -> benchmark -> numbers"
  [[ -n "$CACHE" ]] || echo "  fetching from nepallaws.com (7 s between pages; about an hour)"
  cp -r src analysis AUDIT configs "$WORK"/
  mkdir -p "$WORK/corpus/raw" "$WORK/benchmark/candidates" "$WORK/paper/shared" "$WORK/logs"
  [[ -n "$CACHE" ]] && cp -r "$CACHE" "$WORK/corpus/cache"
  ACTS=(
    "banking-offence-and-punishment-act-2064|banking-offences-en|banking-en"
    "bonus-act-2030|bonus-act-2030|bonus-act-2030"
    "foreign-exchange-regulation-act-2019|foreign-exchange-regulation-act-2019|foreign-exchange-regulation-act-2019"
    "income-tax-act-2058-2002|income-tax-act-2058|income-tax-act-2058-2002"
    "companies-act-2063-2006|companies-act-2063|companies-act-2063-2006"
  )
  (
    cd "$WORK"
    export PYTHONPATH=src
    for row in "${ACTS[@]}"; do
      IFS='|' read -r slug out cache <<<"$row"
      report="$("$PY" -m nepversa.harvest "https://nepallaws.com/Laws/$slug" \
          --out "corpus/raw/$out.jsonl" --cache "corpus/cache/$cache" | head -1)"
      echo "  harvest $out: ${report##*-> }"
      [[ "$report" == *"-> VALID"* ]] || { echo "  harvest not VALID; stopping" >&2; exit 1; }
      "$PY" -m nepversa.build_benchmark "corpus/raw/$out.jsonl" \
          --out "benchmark/candidates/$out.jsonl" >/dev/null
    done
    echo "  audit: $("$PY" analysis/audit_sheet.py reapply | tail -1)"
    echo "  validator: $("$PY" -m nepversa.validate corpus/raw/*.jsonl | tail -1)"
    "$PY" analysis/audit_items.py | tail -1 | sed 's/^/  item check: /'
    "$PY" analysis/make_tables.py >/dev/null
  )
  REBUILT="$WORK"
else
  step "4/5  Recount every number from the released files"
  mkdir -p "$WORK/corpus" "$WORK/benchmark" "$WORK/paper/shared"
  cp -r src analysis "$WORK"/
  cp -r "$CORPUS" "$WORK/corpus/raw"
  cp -r "$BENCH" "$WORK/benchmark/candidates"
  REBUILT="$WORK"
fi

step "5/5  Compare with the paper (paper/shared/numbers.json)"
"$PY" - "$HERE" "$REBUILT" "$FROM_SOURCE" "$LAYOUT" "$CORPUS" "$BENCH" <<'EOF'
import hashlib, json, sys
from pathlib import Path

here, work = Path(sys.argv[1]), Path(sys.argv[2])
full, layout, corpus_dir, bench_dir = sys.argv[3] == "1", sys.argv[4], sys.argv[5], sys.argv[6]
paper = json.loads((here / "paper/shared/numbers.json").read_text(encoding="utf-8"))

if full:
    built = json.loads((work / "paper/shared/numbers.json").read_text(encoding="utf-8"))
    checked = sorted(paper)
else:
    # Recount with the paper's own counting code, pointed at the released files.
    sys.path.insert(0, str(work / "analysis"))
    import make_tables as mt
    mt.CORPUS, mt.BENCH = work / "corpus/raw", work / "benchmark/candidates"
    agg, per_act = mt.corpus_stats()
    built = {"corpus": agg, "per_act": per_act, "benchmark": mt.benchmark_stats()}
    checked = ["corpus", "per_act", "benchmark"]

def diffs(a, b, path):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            yield from diffs(a.get(k), b.get(k), f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diffs(x, y, f"{path}[{i}]")
    elif a != b:
        yield f"{path}: paper={a!r} reproduced={b!r}"

bad = [d for k in checked for d in diffs(paper.get(k), built.get(k), k)]

c, b = built["corpus"], built["benchmark"]
rows = [
    ("Acts / provisions",            f'{c["acts"]} / {c["provisions"]}'),
    ("Amended provisions",           f'{c["amended_provisions"]} ({c["amended_pct"]}%)'),
    ("Amendment units INS/SUB/REP",  f'{c["amendment_units"]} ({c["op_insert"]}/{c["op_substitute"]}/{c["op_repeal"]})'),
    ("Items T2 / T3",                f'{b["items"]} ({b["t2_point_in_time"]}/{b["t3_supersession"]})'),
    ("Abstention-expected",          f'{b["abstention_expected"]} ({b["abstention_pct"]}%)'),
    ("Nuggets label/citation/exact", f'{b["nugget_label"]}/{b["nugget_citation"]}/{b["nugget_exact"]}'),
    ("Items verified by audit",      f'{b["status_verified"]}'),
]
if full:
    x = built["extraction"]
    rows += [("HTML markers", f'{x["html_markers"]}'),
             ("Markdown-only reading: missed/invented", f'{x["html_only"]} / {x["md_only"]}')]
w = max(len(k) for k, _ in rows)
for k, v in rows:
    print(f"  {k:<{w}}  {v}")

def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load(d, key):
    return {r[key]: r for f in sorted(Path(d).glob("*.jsonl"))
            for r in map(json.loads, f.read_text(encoding="utf-8").splitlines())}

if full:
    # Every rebuilt provision and item must hash to the released record.
    rel_c, reb_c = load(here / corpus_dir, "citation_key"), load(work / "corpus/raw", "citation_key")
    rel_i, reb_i = load(here / bench_dir, "item_id"), load(work / "benchmark/candidates", "item_id")
    def text_hash(r):
        return r.get("text_sha256") or sha(r.get("text", ""))
    def nugget_hashes(r):
        return [n.get("value_sha256") or sha(n["value"]) if n["kind"] == "exact" else n.get("value")
                for n in r["gold_nuggets"]]
    c_bad = sorted(k for k in rel_c.keys() | reb_c.keys()
                   if k not in rel_c or k not in reb_c or text_hash(rel_c[k]) != text_hash(reb_c[k]))
    i_bad = sorted(k for k in rel_i.keys() | reb_i.keys()
                   if k not in rel_i or k not in reb_i
                   or rel_i[k]["gold_state"] != reb_i[k]["gold_state"]
                   or nugget_hashes(rel_i[k]) != nugget_hashes(reb_i[k]))
    print(f'  {"Provisions matching release":<{w}}  {len(rel_c) - len(c_bad)} / {len(rel_c)} by SHA-256')
    print(f'  {"Items matching release":<{w}}  {len(rel_i) - len(i_bad)} / {len(rel_i)} by id, state, nugget hash')
    bad += [f"provision {k} differs from the release" for k in c_bad[:20]]
    bad += [f"item {k} differs from the release" for k in i_bad[:20]]
else:
    print("\n  (The extraction numbers - 119 HTML markers, 26 missed / 6 invented by a")
    print("   Markdown-only reading - need the source pages: run with --from-source.)")

print()
if bad:
    print("MISMATCH:")
    for line in bad:
        print("  ", line)
    print("\nA mismatch after --from-source can mean nepallaws.com edited a page after")
    print("2026-09-23 (each record carries retrieved_at). Report it with this output.")
    sys.exit(1)
print("REPRODUCED: every number checked matches the paper.")
EOF
