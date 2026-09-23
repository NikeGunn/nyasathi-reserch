#!/usr/bin/env bash
# Regenerate every NEPVERSA artefact from the cached pages (or fetch them).
#
#   bash scripts_regenerate.sh            # from corpus/cache (no network if cached)
#
# Order matters: corpus -> validation -> benchmark items -> numbers/tables ->
# figures. Each step reads only what the previous one wrote. A harvest whose
# report is not VALID stops the script: an INVALID run is never counted.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-python}"
export PYTHONUTF8=1 PYTHONPATH=src

# act slug served by the site | output name | cache dir
ACTS=(
  "banking-offence-and-punishment-act-2064|banking-offences-en|banking-en"
  "bonus-act-2030|bonus-act-2030|bonus-act-2030"
  "foreign-exchange-regulation-act-2019|foreign-exchange-regulation-act-2019|foreign-exchange-regulation-act-2019"
  "income-tax-act-2058-2002|income-tax-act-2058|income-tax-act-2058-2002"
  "companies-act-2063-2006|companies-act-2063|companies-act-2063-2006"
)

mkdir -p logs/regenerate benchmark/candidates
for row in "${ACTS[@]}"; do
  IFS='|' read -r slug out cache <<<"$row"
  "$PY" -m nepversa.harvest "https://nepallaws.com/Laws/$slug" \
      --out "corpus/raw/$out.jsonl" --cache "corpus/cache/$cache" \
      | tee "logs/regenerate/$out.log"
  head -1 "logs/regenerate/$out.log" | grep -q -- "-> VALID" \
      || { echo "harvest for $slug is not VALID; stopping" >&2; exit 1; }
  "$PY" -m nepversa.build_benchmark "corpus/raw/$out.jsonl" \
      --out "benchmark/candidates/$out.jsonl" | tee -a "logs/regenerate/$out.log"
done

# build_benchmark writes every item as unverified; restore the recorded audit.
"$PY" analysis/audit_sheet.py reapply | tee logs/regenerate/audit_reapply.log
"$PY" -m nepversa.validate corpus/raw/*.jsonl | tee logs/regenerate/validate.log
"$PY" analysis/audit_items.py | tee logs/regenerate/audit.log
"$PY" analysis/make_tables.py > logs/regenerate/numbers.log
"$PY" analysis/make_figures.py > logs/regenerate/figures.log
echo "regenerated: corpus/raw, benchmark/candidates, paper/shared/{numbers.json,tables,figures}"
