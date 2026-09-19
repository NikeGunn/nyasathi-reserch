# PROVENANCE.md

Every number that reaches either manuscript gets a line here
(PAPER_PLAN.md §1 rule 4):

`paper location | value | source file | script + commit hash | date`

Phase 0 entries are **re-derivations of product measurements**, recorded as
evidence. None is a paper result, and none may be written into a manuscript
until `RELEASE_OK.md` D4 approves it.

Commit for all Phase 0 rows: `10b5f741c3cb71f83593a6abd516f160d20d16e3`

| Paper location | Value | Source | Script | Date |
|---|---|---|---|---|
| (not yet cited) | 1711 passed, 3 skipped (120.09s) | test suite | `python -m pytest -q` | 2026-09-19 |
| (not yet cited) | P@1 0.871; recall@5 0.968; MRR 0.925; n=31+2; gap 2/2; false gap 0/31 | `evals/retrieval/nkp_v1.jsonl` over `var/snapshot/nkp.jsonl.gz` | `python -m engine.cli eval retrieval` | 2026-09-19 |
| (not yet cited) | recall@1 0.833; recall@5 0.833; MRR 0.833; n=12 | workspace fixtures | `python scripts/bench_workspace_retrieval.py` | 2026-09-19 |
| (not yet cited) | combined: 333 docs / 5683 nodes; nkp: 330 docs / 4102 nodes | `var/snapshot/*.jsonl.gz` | Python, UTF-8, in-session | 2026-09-19 |
| (not yet cited) | 3 statutes: constitution 2072, देवानी संहिता 2074, बैङ्किङ्ग कसूर ऐन 2064 | `var/snapshot/combined.jsonl.gz` | Python, UTF-8, in-session | 2026-09-19 |
| (not yet cited) | node kinds: paragraph 4102, upadafa 751, khanda 447, dafa 251, article 103, upakhanda 29 | `var/snapshot/combined.jsonl.gz` | Python, UTF-8, in-session | 2026-09-19 |
| (not yet cited) | eval rows: nkp_v1 33; generated_v1 394 (gold=1 for all 394); entailment 39/37/14 | `evals/**` | Python, UTF-8, in-session | 2026-09-19 |
| (not yet cited) | placeholders: Version A 81; Version B 118 | the two .docx drafts | docx XML extraction, in-session | 2026-09-19 |

## Phase 1 — literature and novelty (verified 2026-09-19)

| Paper location | Value | Source | Method | Date |
|---|---|---|---|---|
| Related Work | TIDE: 3,050 QA pairs, 644 instruments, 1969–2025; best macro 68.5%; version-from-implicit-date 59.7%; **reject-wrong-version 26.7%** | arXiv:2608.08512 abstract | arXiv API | 2026-09-19 |
| Related Work | FiscalQA Pro: 32,436 article-versions, 1938–2031; static RAG retrieves date-applicable version **0%**; their retriever 98.3% | arXiv:2608.09393 abstract | arXiv API | 2026-09-19 |
| Related Work | Prior et al.: 312 expert-validated German statutory QA pairs | arXiv:2605.23497 abstract | arXiv API | 2026-09-19 |
| Related Work | LegalSearch-R1: +57.7–80.3% on temporal consistency | arXiv:2605.25920 abstract | arXiv API | 2026-09-19 |
| Intro / Related Work | **Wagle et al.: BM25 P@1 0.91 > multilingual-E5-large 0.75** (Nepali legal RAG, case law only) | arXiv:2606.07523 abstract | arXiv API | 2026-09-19 |
| Related Work | NepKANUN: BERTScore F1 0.82/0.77/0.71; assistant, **no temporal dimension** | arXiv:2609.15999 abstract | arXiv API | 2026-09-19 |
| **Novelty claim** | arXiv `Nepali AND amendment AND statute` → **0 hits**; `"Bikram Sambat"` → **0**; `Nepali AND statutory AND corpus` → **0** | export.arxiv.org/api/query | arXiv API, non-urllib UA | 2026-09-19 |

## Phase 2 — corpus and harvester (measured 2026-09-19)

| Paper location | Value | Source | Script | Date |
|---|---|---|---|---|
| Method / Corpus | nepallaws.com lists **59 act entries (29 Nepali + 30 English)** | https://nepallaws.com/laws/ | WebFetch | 2026-09-19 |
| Method / Corpus | Banking Offences Act 2064: **34 sections discovered, 34/34** | act TOC, 2-level discovery | `nepversa.harvest.discover_provisions` | 2026-09-19 |
| Method / Corpus | §7 carries **6 amended clauses**: 4 INSERT, 2 SUBSTITUTE, all First Amendment | live page footnotes | `nepversa.provision.parse_provision` | 2026-09-19 |
| Method / Benchmark | §7 alone yields **10 T2 items, 4 abstention-expected** | `corpus/probe/s7.jsonl` | `nepversa.build_benchmark` | 2026-09-19 |
| **Dataset table** | Banking Offences Act 2064 FINAL: **34 provisions, 6 amended, 1 repealed-in-full, 5 lettered**; ops **13 substitute / 6 insert / 2 repeal** | `corpus/raw/banking-offences-en.jsonl` | `nepversa.validate` | 2026-09-19 |
| **Dataset table** | **30 benchmark items** from one act: 27 T2 + 3 T3, **11 abstention-expected** | `benchmark/candidates/banking-offences-en.jsonl` | `nepversa.build_benchmark` | 2026-09-19 |
| Method / validation | §15 parser output (1,2,3,6 substitute; 7,8 insert) **matches the page HTML `<sup>` markers exactly** | live HTML scrape | manual cross-check vs `<sup>` tags | 2026-09-19 |
| Reproducibility | Research tests **87 passed**; product gate **1711 passed, 3 skipped** (re-run after all changes) | — | `pytest` | 2026-09-19 |
| ~~Method / Corpus~~ | ~~density 8 of 34 (24%)~~ **SUPERSEDED** by the FINAL row above (6 of 34 by footnote; the 8 came from a partial 2026-09-04 cache of a different harvest) | — | — | 2026-09-19 |
| Method / Corpus | Lettered (amendment-inserted) sections: **12A, 14A, 14B, 19A, 19B** (5 — an earlier note said 4, missing 19A) | `corpus/raw/banking-offences-en.jsonl` | `nepversa.validate` | 2026-09-19 |
| Limitations | Firecrawl API refused at **11 req/min**; first full run marked INVALID (33/34) | harvest report | `nepversa.harvest` | 2026-09-19 |
| ~~Reproducibility~~ | ~~63 passed~~ **SUPERSEDED** — final count is 87 (row above) | — | — | 2026-09-19 |

## NOT re-derived — must not be used until re-run

Quoted in product docs; evidence only (see `docs/CODEBASE_NOTES.md` §3):

| Value | Reproducing script |
|---|---|
| Dense P@1 0.389 vs BM25 0.722; hybrid RRF 0.500 (n=18) | `scripts/bench_embedding_semantics.py` |
| Nepali class margin +0.125 vs English +0.303 (R29) | `scripts/bench_embedding_semantics.py` |
| StemmedIndex P@1 0.944 → 0.722 | `scripts/bench_stemmed_index.py` |
| 4-char stem 8/8 → 3/8 inflection recovery | `scripts/bench_stem.py` |
| Devanagari ≈ 0.99 cl100k tokens/char (R30) | `scripts/bench_embedding_tokens.py` |
| Time to answer p90 17.2 s | `scripts/bench_time_to_answer.py` |
| Rarity floor recall@1 0.833 → 0.583; ubiquity ceiling → 0.500 | `scripts/bench_workspace_retrieval.py` variants |
