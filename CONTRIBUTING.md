# Contributing to NEPVERSA

Contributions are welcome, particularly from people who can do the one thing
the maintainer cannot: **read Nepali statutory law with legal training**.

This is a research dataset, so a contribution changes what published numbers
mean. Read `VERSIONING.md` before proposing anything that touches an item.

---

## The contribution this project needs most

**Legal audit of benchmark items.** All 46 items are `status=unverified`. The
extraction is mechanically faithful to published footnotes; what is unverified
is whether each item asks a well-formed legal question about the provision that
actually governs.

If you hold a law degree recognised in Nepal, or are a final-year law student
supervised by an advocate, and can read statutory Devanagari, the protocol is
in `AUDIT_human_verification_required.md`. It specifies the decision fields,
the enumeration, and the statistics. Please open an issue before starting so
work is not duplicated.

You will be credited as you choose: named, pseudonymous, or not at all.
Co-authorship on a resulting paper is a separate conversation, decided on
substantial intellectual contribution, and never assumed.

## Other valuable contributions

| Contribution | Why it matters |
|---|---|
| **Another Act harvested** | The corpus is 3 Acts. Amendment density varies fivefold between them, so more Acts change what the method demonstrates. |
| **A failing extraction case** | An Act whose footnotes the parser misreads is worth more than one it handles. Open an issue with the URL and the provision. |
| **Commencement dates from an authoritative source** | Validity windows are ordinal ("First Amendment") because footnotes name no dates. Verified dates, with provenance, would materially strengthen the resource. |
| **The Nepali edition of a harvested Act** | Both editions should agree on operations and ordinals. Disagreement is an informative finding, not a bug to hide. |
| **Reproduction of a reported number** | Especially a failure to reproduce. Open an issue with what you ran and what you got. |

## Ground rules

These are not negotiable, and a pull request that breaks one will be declined
however good the code is.

1. **Never mark an item verified without a qualified human having verified it.**
   Not by a model, not by a second parser, not because it looks right. A
   fabricated audit in a legal dataset is worse than no dataset.
2. **Never invent a legal fact.** No dates, no commencement provisions, no
   citations, no amendment ordinals that are not in the source. If it cannot be
   verified, mark it unverified and say why.
3. **Never let statutory text into the release.** The licence status is
   unresolved (`corpus/SOURCES.md`). The bundle carries hashes, offsets and
   annotations; `analysis/make_release.py` enforces the redaction.
4. **A new safety check must be mutation-tested.** Break the code on purpose
   and confirm your test fails. The project has shipped tests that passed
   against a deliberately broken implementation; a test that has never failed
   has not been shown to test anything.
5. **Count from the artefact before writing a number anywhere.** No number is
   typed by hand into a document. `analysis/make_tables.py` produces them.

## Practical setup

```bash
git clone https://github.com/NikeGunn/nyasathi-reserch.git
cd nyasathi-reserch
python -m pip install -r requirements.txt   # if present; otherwise stdlib + firecrawl

# The tests need src/ on the path and UTF-8 on Windows.
PYTHONUTF8=1 PYTHONPATH=src python -m pytest tests -q     # expect 153 passed
```

**On Windows, always set `PYTHONUTF8=1`.** Without it Devanagari is mangled to
`????` before it reaches the code, and the silence that follows reads as a
finding rather than a broken pipe. Never send Nepali through a shell argument
to test something; write a Python script.

Rebuilding the corpus needs a Firecrawl API key and costs roughly one call per
provision:

```bash
python -m nepversa.harvest "<act-url>" --out corpus/raw/<act>.jsonl \
    --cache corpus/cache/<act>
python -m nepversa.validate corpus/raw/*.jsonl
```

Harvest with `--cache`. A re-parse after a parser fix then costs nothing, which
matters: three parser bugs each forced a full re-scrape before caching existed.

## Pull requests

- One concern per PR. A harvest fix and a scoring change do not belong together.
- Say which version bump you believe your change requires, and why
  (`VERSIONING.md`). If it changes any item, it is MAJOR.
- Include the test that fails without your change.
- If you changed a number, say which script re-derives it.
- Run the suite before opening. A PR that has not been run is a draft.

## Reporting a problem with the data

Open an issue titled with the item or provision id. Include:

- the item id or `citation_key`
- the source URL and the date you retrieved it
- what the source says
- what the release says
- why you believe they differ

A discrepancy that turns out to be a property of the source rather than a bug
is still worth reporting, and will be recorded as a corpus fact. Several
already have been.

## Code of conduct

Be straightforward and assume competence. Disagreement about a legal reading is
expected and useful; record it rather than resolving it silently. If you think
a number in the paper is wrong, say so plainly — that is the most valuable
thing anyone can contribute.
