# Changelog

All notable changes to NEPVERSA are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the version scheme is
defined in `VERSIONING.md`, where MAJOR means **a published number may change**.

Three classes of change appear here regardless of version bump: any item whose
gold or status changed, any correction to a number that has appeared in a paper
or preprint, and any extraction defect found after release.

---

## [2.0.0] — 2026-09-23

MAJOR: every published number changes (3 → 5 Acts; 46 → 181 items), and four
v1.0.0 items were wrong (erratum below).

### Contents

- 5 Acts, 455 provisions, 35 amended provisions, 99 amendment units
  (47 insert, 24 substitute, 28 repeal), 43 lettered sections, 8 repealed in full.
- 181 benchmark items: 145 T2 point-in-time, 36 T3 supersession;
  111 (61.3%) abstention-expected. 98 T2 items anchored to a named instrument.
- Added: Income Tax Act 2058 (156 provisions), Companies Act 2063 (190).

### Verification status

All 181 items were checked against their source footnotes by **one auditor,
the author** (BCA, Tribhuvan University; **not legally trained**; not
independent of the pipeline). Verdicts: 181 correct, 0 incorrect, 0 unsure.
Recorded in `AUDIT/audit_log.json` by `analysis/audit_sheet.py`. There is no
inter-annotator agreement (single auditor). An independent audit by a reader
with legal training is still the most valuable contribution; see
`AUDIT_human_verification_required.md`.

### Erratum for v1.0.0 — 4 of 46 items were wrong

`nepversa-9aab78d4285b`, `nepversa-842d44ed6b18`, `nepversa-b0f333e1b2a2`,
`nepversa-02fce90c2f44` (Foreign Exchange Act §2(g4) contradictory pair;
§10A(1) post-substitution text given as the pre-amendment answer; §11(1)
"absent before any amendment" for a later-repealed clause). Cause: amendments
named by instrument ("Financial Act, 2075") had both window bounds open. Fixed;
`build_benchmark` now refuses contradictory item sets and
`analysis/audit_items.py` flags all four on v1.0.0 and passes 181/181 on v2.0.0.
Do not use v1.0.0 numbers.

### Fixed (extraction defects, each with a mutation-tested test)

Untagged pages rejected by a page-chrome terminator; `1 (b)` space form;
`2c)` / `1h1)` / `34a)` lettered forms; label-first markers; verbless legends
("The first amendment."); misspelt verbs ("Extreted"); instrument-named legends
now carry an event label; Markdown `10)` misread as marker + `0)` (markers now
read from HTML `<sup>`); `&#8230;` split in the sup window (lost 9 Income Tax
repeals); duplicate clause labels; partial repeals no longer recorded as unit
repeals; empty cached `_urls.json` no longer trusted.

### Added

- `REPRODUCE.md` and `scripts_regenerate.sh`: one command from cache to every
  number and figure.
- `analysis/audit_sheet.py` (export / apply / reapply), `analysis/audit_items.py`,
  `analysis/verify_rebuild.py` (hash-compare a rebuild against this release),
  `analysis/preflight_arxiv.py`, `analysis/render_numbers.py`.
- `NEPVERSA_preprint.pdf`: the manuscript (ACM format) matching this release.

---

## [1.0.0] — 2026-09-20

First versioned release. The extraction method, item schema and scoring rule
are settled; the human verification status is not, and is recorded in
`RELEASE_MANIFEST.json` rather than implied by the version.

### Contents

- 3 Acts, 109 provisions, 46 benchmark items (36 T2 point-in-time,
  10 T3 supersession; 22 abstention-expected).
- 28 amendment operations: 16 substitutions, 8 insertions, 4 repeals.
- Statutory text redacted to SHA-256 plus length; the harvester rebuilds the
  full corpus and a hash comparison verifies the rebuild byte-for-byte.

### Verification status

**No human legal audit has been performed.** All 46 items are
`status=unverified`. No error rate and no inter-annotator agreement exist,
because no audit took place. `AUDIT_human_verification_required.md` specifies
what closing that gap requires.

This was previously stated incorrectly: the manuscript described an audit in
the present tense ("We report the audited sample and its error rate") against a
release where none had occurred. Corrected before this release.

### Added

- `VERSIONING.md`, `CONTRIBUTING.md`, this changelog.
- `src/nepversa/probe.py` — amendment-density probe that buys the act-selection
  decision at the price of a table of contents rather than a full harvest.
- `analysis/make_figures.py` — four figures generated from `numbers.json`,
  colour-blind-safe and hatched so they survive greyscale.
- `analysis/apa_checklist.py` — 23 APA items measured from the built document,
  five reported as MANUAL rather than claimed.
- `analysis/originality_check.py` — flags runs of 8+ words shared with a cited
  source; verified by planting copied text (0 → 14 hits → 0).
- Version stamping: `VERSION` is the single source of truth, written into
  `RELEASE_MANIFEST.json` and `CITATION.cff` by the release build.

### Fixed

- **Act-slug resolution in the harvester.** The source site appends the
  Gregorian year to some slugs (`income-tax-act-2058` →
  `income-tax-act-2058-2002`). The requested slug is a *prefix* of the served
  one, so the old substring filter kept the chapter links while losing every
  provision beneath them. Two Acts were measured as having zero provisions and
  the wrong answer was written to the cache. Discovery now reads the slug back
  from the links the site served, and **refuses to cache a discovery that found
  no provisions**.
- **Manuscript build.** The official APA template cannot be copied by Pandoc
  without producing a package Word refuses to open; the LibreOffice re-save
  used to work around it returned a document with zero table elements, whose
  cells survived only as loose paragraphs. Both removed.
- **Devanagari rendering.** `w:cs` alone does not reach an unmarked Devanagari
  run, so Nepali printed as empty boxes in a document whose styles all named a
  Devanagari font correctly.
- **`make_release.py` cleared its own output directory with `rmtree`**,
  deleting the LICENSE, README and CITATION.cff it does not regenerate, and on
  Windows failing partway through on a packed git object. It now clears
  contents while preserving `.git` and the metadata files.

### Known limitations

- Validity windows are **ordinal-valued** ("First Amendment"), not
  date-anchored. Footnotes name no dates and no date is interpolated.
- The prior text of a substituted or repealed unit is **not in the source**;
  those periods are marked `PRESENT_TEXT_UNKNOWN` and generate no item.
- Single source (`nepallaws.com`), not reconciled against the Nepal Law
  Commission's own texts, whose PDFs extract to corrupted Nepali.
- Corpus is 3 Acts. Amendment density varies roughly fivefold between them, so
  the sample is small relative to that variation.

---

## Template for the next entry

```markdown
## [X.Y.Z] — YYYY-MM-DD

### Items changed
<!-- Required if any item's gold or status changed. List by item id. -->

### Numbers corrected
<!-- Required if a number that appeared in a paper or preprint changed.
     Give both the old and the new value. -->

### Added / Changed / Fixed / Removed

### Verification status
<!-- The verified proportion, or a plain statement that none has occurred. -->
```

[1.0.0]: https://github.com/NikeGunn/nyasathi-reserch/releases/tag/v1.0.0
