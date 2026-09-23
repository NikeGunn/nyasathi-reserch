# NEPVERSA

**A version-aware Nepali statutory retrieval benchmark derived from amendment
footnotes.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22916911.svg)](https://doi.org/10.5281/zenodo.22916911)

Nikhil Bhagat · Independent Researcher, Nepal ·
[ORCID 0009-0008-9603-8746](https://orcid.org/0009-0008-9603-8746)

---

> **Reviewers: reproduce in three commands** (Python 3.12, ~2 minutes, no API key)
>
> ```bash
> git clone https://github.com/NikeGunn/nyasathi-reserch && cd nyasathi-reserch && git checkout v2.0.0
> pip install pytest matplotlib defusedxml
> PYTHONUTF8=1 PYTHONPATH=src python -m pytest tests -q     # expect: 216 passed
> ```
>
> Every number in the paper is in `paper/shared/numbers.json`, produced by
> `analysis/make_tables.py`. Rebuilding the corpus itself from the live source
> needs a Firecrawl key and about an hour: see [`REPRODUCE.md`](REPRODUCE.md),
> which lists every step and the expected value of every number.

## What this is

When a legislature amends an Act, the earlier text remains the correct law for
events that happened before the amendment. Retrieval systems assume the
opposite, that newer documents supersede older ones, so they return a real,
correctly-cited provision that does not govern the period in question.

Measuring that failure needs a corpus where every provision's versions and
validity windows are known. No such corpus existed for Nepali.

Building one looked blocked. Nepal Gazette commencement notices are published as
scanned images (50 of 53 we examined had no text layer), and the official Act
PDFs extract to corrupted text, `मिति` comes out as `मममि`, because the
typesetting pipeline writes wrong Unicode codepoints into real Unicode fonts.

**The amendment record turns out to be somewhere else: inside the consolidated
statutory text, as numbered footnotes attached to individual clauses.**

```
1(d1)  Avail credit or advance facilities by the Chief Executive Officer ...
2(e)   Re-avail or re-provide loans from or by another Bank ...

1 Added by the First Amendment.
2 Amended by the First Amendment.
```

Each marker names the amending instrument and its operation (insertion,
substitution, or repeal) at clause granularity. Gold answers are therefore
*derived from published statements* rather than authored, and every benchmark
item traces to a specific sentence in the law.

## Status

- **Preprint:** https://doi.org/10.5281/zenodo.22916911 (not peer reviewed)
- **Journal:** under review at ACM Transactions on Asian and Low-Resource
  Language Information Processing (TALLIP), submitted 2026-09-23
- **arXiv:** pending

## Contents

```
corpus/       provision records with amendment provenance (text redacted; see Licensing)
benchmark/    NEPVERSA items with deterministic nugget gold
src/nepversa/ the extraction pipeline
tests/        216 tests, every safety check mutation-tested
analysis/     numbers, tables, figures, audit, release and preflight scripts
AUDIT/        audit_log.json: who checked each item, qualification, verdict
REPRODUCE.md  exact steps to regenerate every number from scratch
```

## Current release — v2.0.0

Versioning is defined in [`VERSIONING.md`](VERSIONING.md). For a dataset,
**MAJOR means a published number may change**. Cite the tag, never `main`.
v1.0.0 contained 4 wrong items; see the erratum in [`CHANGELOG.md`](CHANGELOG.md).

| | |
|---|---|
| Acts | 5 |
| Provisions | 455 |
| Amended provisions (clause footnotes) | 35 (7.7%) |
| Amendment operations | 99 (47 insert, 24 substitute, 28 repeal) |
| Amendment-inserted (lettered) sections | 43 |
| Sections repealed in full | 8 |
| **Benchmark items** | **181** (145 T2 point-in-time, 36 T3 supersession) |
| Abstention-expected | 111 (61.3%) |

| Act | Provisions | Amended | Lettered | Repealed in full |
|---|---|---|---|---|
| Banking Offence and Punishment Act, 2064 | 34 | 6 | 5 | 1 |
| Bonus Act, 2030 | 29 | 3 | 1 | 5 |
| Companies Act, 2063 | 190 | 4 | 3 | 0 |
| Foreign Exchange (Regulation) Act, 2019 | 46 | 3 | 21 | 1 |
| Income Tax Act, 2058 | 156 | 19 | 13 | 1 |

**Verification.** All 181 items were checked against their source footnotes by
one auditor, the author (BCA; **not legally trained**; not independent of the
pipeline): 181 correct, 0 incorrect, 0 unsure (`AUDIT/audit_log.json`).
`status=verified` therefore means *checked against the published footnote by
the author*, not endorsement by a legal professional. There is no
inter-annotator agreement. An independent audit by a qualified legal reader is
the contribution this project needs most: see
[`AUDIT_human_verification_required.md`](AUDIT_human_verification_required.md)
and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Reproducing

Step-by-step instructions are in [`REPRODUCE.md`](REPRODUCE.md). In short:

```bash
pip install pytest matplotlib defusedxml
npm i -g @mendable/firecrawl-cli && firecrawl config    # scraping backend
bash scripts_regenerate.sh                              # corpus -> items -> numbers -> figures
python analysis/verify_rebuild.py --released corpus/ --rebuilt corpus/raw/
PYTHONUTF8=1 PYTHONPATH=src python -m pytest tests -q
```

Each provision record carries `source_url`, `retrieved_at` and `text_sha256`, so
a rebuild can be verified byte-for-byte against this release.

## Licensing and redaction

The licence status of Nepali statutory text is **unresolved**. Government legal
texts are typically freely reproducible, but "typically" is not a licence, and
the source aggregator publishes no terms.

**This release therefore omits the statutory text itself.** Each provision
carries `text_sha256` and `text_length` instead of `text`; verbatim gold spans
carry `value_sha256` and `value_length`. Everything needed to rebuild and verify
the corpus is present: run the harvester and hash the result.

The code is released under the MIT Licence. The annotations (amendment
operations, validity windows, benchmark items) are released under CC BY 4.0.
Neither covers the underlying statutory text, which remains the property of its
publisher.

## Known limitations

- **Windows are ordinal-valued, not dated.** Footnotes name "the First
  Amendment", not a date. Bikram Sambat and Gregorian bounds require each
  amending Act's commencement provision, which the gazette record does not
  supply in machine-readable form.
- **Superseded text is unavailable.** Consolidated editions print only current
  text, so for substituted and repealed units the prior wording is not in the
  document. Those periods are marked textually undetermined and generate no
  quotation questions.
- **Two question types populated.** T2 (point-in-time) and T3 (supersession).
  T1, T4 and T5 are defined but not yet built.
- **Small scale.** Five Acts. The constraint is scraping quota, not method.
- **Single source**, not independently reconciled against the Law Commission's
  own texts, those being the PDFs whose extraction failure motivated the source
  choice.

## A finding worth knowing before you build something similar

Seven distinct extraction defects were found while building this corpus. **None
produced a visible symptom.** A provision whose amendment footnote is missed
enters the corpus looking exactly like a provision that was never amended. There
is no malformed field and no exception, only a record that is quietly wrong
about the one property the benchmark exists to measure.

"34 of 34 provisions parsed, zero rejected" was true of this corpus at a point
when it was recovering fewer than a third of the amendments actually published
in it.

Three things made the failures visible, and they are built into this pipeline:

1. **Fail loudly on unrecognised vocabulary.** A footnote naming an amendment
   with an unknown verb raises rather than being skipped. A rejected provision
   is a visible gap; a skipped footnote is an invisible falsehood.
2. **Keep redundant signals.** Amendment-inserted sections are identifiable both
   from footnotes and from lettered numbering (`12A`, `१२क`). Neither signal is
   complete: the Foreign Exchange Act carries 21 lettered sections and only 3
   with clause footnotes.
3. **Cross-check automatically.** `nepversa/validate.py` compares the signals
   and reports disagreements. It found two defects that manual inspection had
   passed, one of them inside the fix for an earlier defect.

## Manuscript

[`NEPVERSA_preprint.pdf`](NEPVERSA_preprint.pdf) is the preprint matching this
release, archived at https://doi.org/10.5281/zenodo.22916911. It has not been peer reviewed; its findings concern extraction
correctness, not model capability.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). The most valuable contributions are a
legal audit of the benchmark items, an Act whose footnotes the parser misreads,
and a failure to reproduce a reported number.

Three rules are enforced by CI rather than trusted: no statutory text in the
release, a version consistent across the manifest and the citation, and **no
item marked `verified` beyond the number the manifest records as audited**.

## Citation

Cite the version you used — `main` moves.

Paper (preprint):

```
Bhagat, N. (2026). NEPVERSA: A version-aware Nepali statutory retrieval
benchmark derived from amendment footnotes (Version 2.0.0) [Preprint].
Zenodo. https://doi.org/10.5281/zenodo.22916911
```

Code and data:

```
Bhagat, N. (2026). NEPVERSA (Version 2.0.0) [Data set]. GitHub.
https://github.com/NikeGunn/nyasathi-reserch/releases/tag/v2.0.0
```

See `CITATION.cff`, whose version field is generated from `VERSION` so it
cannot drift from the tag.
