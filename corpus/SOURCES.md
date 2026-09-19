# SOURCES.md — where every NEPVERSA document came from

PAPER_PLAN.md §3 and §6 item 1. One row per source, with URL, access date, and
terms. **Terms are recorded as found, not as hoped.**

---

## S1. nepallaws.com — consolidated statutes (primary source)

| Field | Value |
|---|---|
| Base URL | `https://nepallaws.com/Laws/` |
| First accessed | 2026-09-04 (product harvest) |
| Re-verified | **2026-09-19** (this project) |
| Format | Real HTML, one page per provision; citation hierarchy in the URL path |
| Editions | **Bilingual** — Nepali and English pages for the same provision |
| Coverage | **59 act entries: 29 Nepali + 30 English** |
| Retrieval | `firecrawl scrape --format markdown --only-main-content`, paced ≥7 s |

### Why this source and not the official one

lawcommission.gov.np publishes Acts as PDFs. **All 61 fail character-exact
extraction** — the typesetting pipeline writes wrong Unicode codepoints into
real Unicode fonts, lossily (`मिति` → `मममि`, `कार्यान्वयन` → `कायाान्वयि`).
`pypdf` and `PyMuPDF` fail identically; no repair table fixes it. The PDFs look
correct on screen and **cannot be quoted**, which disqualifies them for a
benchmark whose gold includes verbatim spans (`docs/CORPUS_ACQUISITION.md`).

nepallaws.com serves text that passes the citability bar.

### Changes observed since the product's 2026-09-04 harvest

Recorded because they contradict the product docs and because **a URL is not an
identity**:

1. **16 acts → 29 Nepali acts.** an earlier corpus survey is stale.
2. **मुलुकी अपराध संहिता (Penal Code) is now present**; the product docs record
   it as unavailable.
3. **URL slugs changed from percent-encoded Devanagari to ASCII.** The old
   cached URLs now **404**. Every provision therefore stores `retrieved_at`,
   and identity is `act:<slug>#<number>`, never the URL.
4. **English editions now exist** beside the Nepali.

### Terms — UNRESOLVED, and it gates redistribution

No explicit licence is published on the site. The underlying texts are Nepali
government legal texts, which `docs/research.md` R12-1 records as
**"typically freely reproducible, but 'typically' is not a licence."**

**Position adopted for NEPVERSA, pending written confirmation:**

- Local use for research: proceeding.
- **Release: IDs, offsets, amendment annotations, nugget gold, and a rebuild
  script — never the source text.** Anyone can reconstruct the corpus by
  running the harvester against the live site.

This is the standard fallback for unlicensed corpora and it does not block
publication. Recorded in `RELEASE_OK.md` D3.5.

### Rate limits (measured)

The first full harvest was refused at **11 requests/minute** with an explicit
`Rate limit exceeded ... Remaining (req/min): 0` from the Firecrawl API — **the
API's quota, not the site's**. The run correctly reported itself
`INVALID — do not use` rather than presenting 33 of 34 sections as a complete
act. Pacing is now 7 s between calls with one retry past the window.

---

## S2. Nepal Kanun Patrika (NKP) — court decisions

| Field | Value |
|---|---|
| Source | `nkp.gov.np`, via the the author's separate legal tool product snapshot |
| Content | **330 judgments, BS 2076–2082, 4,102 paragraphs** |
| Role | T4 (statute→case) items only |
| Terms | Same unresolved position as S1 |

Counted from `var/snapshot/nkp.jsonl.gz` on 2026-09-19. This is the
**product's** corpus; it is used as a source of linkage, not as the paper's
benchmark (`RELEASE_OK.md` D3.4).

---

## S3. Amendment commencement dates — NOT YET SOURCED

The single open dependency.

Footnotes name an **ordinal** ("First Amendment"), never a date. To attach BS/AD
validity windows we need each amending act's commencement date.

Attempted and rejected: the Nepal Gazette (राजपत्र) archive — **50 of 53
documents gathered are `NO_TEXT` scans**, mostly BS 2011–2013
(an earlier corpus survey).

**Until a date is independently verified, windows stay ordinal-valued and the
date fields stay `None`.** Nothing is interpolated: the product was once
answered as of 2083 for a session pinned to 2078, with the quote, the citation
and the entailment all correct about the wrong year (recorded in earlier engineering notes).

Verified dates, when found, go in a dated-amendment table (not yet populated) with their source.

---

## Reproduction

```bash
python -m nepversa.harvest "https://nepallaws.com/Laws/<act-slug>/" \
    --out corpus/raw/<act>.jsonl
python -m nepversa.build_benchmark corpus/raw/*.jsonl \
    --out benchmark/candidates/items.jsonl
```

Each harvested row carries `source_url`, `retrieved_at` and `sha256` of the
provision text, so any row can be re-verified against the live site.
