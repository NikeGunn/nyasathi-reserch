# Reproducing NEPVERSA v2.0.0

Every number in the paper is produced by a script in this repository and read
from `paper/shared/numbers.json`. This file lists the exact steps, in order.
Tested on Windows 10 (Git Bash) and Ubuntu with Python 3.12.

## 0. Requirements

```bash
python --version                         # 3.12
pip install pytest matplotlib defusedxml
npm i -g @mendable/firecrawl-cli         # only needed to re-fetch pages
firecrawl config                         # paste your Firecrawl API key
export PYTHONUTF8=1 PYTHONPATH=src       # always: Devanagari fixtures need UTF-8
```

## 1. Check the code before trusting it

```bash
python -m pytest tests -q                # expect: 216 passed
```

## 2. Rebuild the corpus and benchmark

The release omits statutory text (licence unresolved), so the corpus is rebuilt
from the live source. One command does every step in order and stops if any
harvest is not `VALID`:

```bash
bash scripts_regenerate.sh
```

What it runs, per Act (5 Acts, ~455 pages, ~1 Firecrawl credit per page, 7 s
pacing, so roughly one hour cold):

```bash
python -m nepversa.harvest "https://nepallaws.com/Laws/<slug>" \
    --out corpus/raw/<act>.jsonl --cache corpus/cache/<act>
python -m nepversa.build_benchmark corpus/raw/<act>.jsonl \
    --out benchmark/candidates/<act>.jsonl
```

then, once:

```bash
python analysis/audit_sheet.py reapply   # restore recorded audit verdicts (needs the sheet)
python -m nepversa.validate corpus/raw/*.jsonl
python analysis/audit_items.py           # expect: 181/181 pass
python analysis/make_tables.py           # -> paper/shared/numbers.json + tables
python analysis/make_figures.py          # -> paper/shared/figures
```

A harvest report ending `-> VALID` is required; a run with any transport
failure marks itself `INVALID` and must not be counted.

## 3. Verify your rebuild against this release

```bash
python analysis/verify_rebuild.py --released corpus/ --rebuilt corpus/raw/
python analysis/verify_rebuild.py --released-items benchmark/ \
                                  --rebuilt-items benchmark/candidates/
```

Each provision is reported `MATCH`, `DIFFERENT` (the site changed the text
after our retrieval date, or a parser differs), `MISSING` or `EXTRA`.
Retrieval dates are in each record's `retrieved_at`.

## 4. Expected numbers

| Quantity | v2.0.0 |
|---|---|
| Acts / provisions | 5 / 455 |
| Amended provisions | 35 (7.7%) |
| Amendment units (INS / SUB / REP) | 99 (47 / 24 / 28) |
| Items (T2 / T3) | 181 (145 / 36) |
| Abstention-expected | 111 (61.3%) |
| Nuggets (label / citation / exact) | 111 / 70 / 70 |

If the live site has changed since 2026-09-23, counts may differ; report it as
a data discrepancy issue with the `verify_rebuild.py` output attached.
