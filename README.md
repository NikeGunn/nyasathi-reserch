# NEPVERSA

**A version-aware Nepali statutory retrieval benchmark derived from amendment
footnotes.**

Nikhil Bhagat · Independent Researcher, Nepal ·
[ORCID 0009-0008-9603-8746](https://orcid.org/0009-0008-9603-8746)

---

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

## Contents

```
corpus/       provision records with amendment provenance (see Licensing)
benchmark/    NEPVERSA items with deterministic gold
src/nepversa/ the extraction pipeline
tests/        153 tests, every safety check mutation-tested
analysis/     table generation, release building, APA post-processing
logs/         provenance, verified citations, literature notes
```

## Current release

| | |
|---|---|
| Acts | 3 |
| Provisions | 109 |
| Amended provisions (clause footnotes) | 10 |
| Amendment operations | 28 (8 insert, 16 substitute, 4 repeal) |
| Sections repealed in full | 7 |
| Amendment-inserted sections (lettered) | 27 |
| **Benchmark items** | **46** (36 T2 point-in-time, 10 T3 supersession) |
| Abstention-expected | 22 (47.8%) |

| Act | Provisions | Amended | Lettered | Repealed in full |
|---|---|---|---|---|
| Banking Offence and Punishment Act, 2064 | 34 | 6 | 5 | 1 |
| Bonus Act, 2030 | 29 | 1 | 1 | 5 |
| Foreign Exchange (Regulation) Act, 2019 | 46 | 3 | 21 | 1 |

Every item is `status=unverified` pending human audit. See
`benchmark/guidelines.md` for the audit protocol.

## Reproducing

```bash
npm i -g @mendable/firecrawl-cli && firecrawl config   # scraping backend

# rebuild the corpus from the live source
PYTHONPATH=src python -m nepversa.harvest \
    "https://nepallaws.com/Laws/<act-slug>/" \
    --out corpus/raw/<act>.jsonl --cache corpus/cache/<act>

# cross-check the signals against each other
PYTHONPATH=src python -m nepversa.validate corpus/raw/*.jsonl

# generate benchmark items
PYTHONPATH=src python -m nepversa.build_benchmark corpus/raw/*.jsonl \
    --out benchmark/candidates/items.jsonl

# regenerate every number reported in the paper
python analysis/make_tables.py

# tests
PYTHONPATH=src python -m pytest tests -q
```

Each provision record carries `source_url`, `retrieved_at` and `text_sha256`, so
a rebuild can be verified byte-for-byte against ours.

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
- **Small scale.** Three Acts. The constraint is scraping quota, not method.
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

`NEPVERSA_manuscript_draft.pdf` is the current working draft (APA 7). It has not
been peer reviewed and its findings concern extraction correctness, not model
capability.

## Citation

A manuscript describing this resource is in preparation. Until it appears,
please cite the repository (see `CITATION.cff`).

## Contact

Nikhil Bhagat, programmer@nikhilbhagat.com.np
