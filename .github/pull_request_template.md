<!-- One concern per PR. A harvest fix and a scoring change do not belong
     together, because they need different version bumps. -->

## What this changes

## Version bump this requires

<!-- See VERSIONING.md. If it changes any item's gold or status, it is MAJOR:
     any published number computed on the old set stops being reproducible. -->

- [ ] PATCH — prose, comments, tests, build; no artefact a number depends on
- [ ] MINOR — additive (a new Act, new scripts, new fields); old numbers still reproducible
- [ ] MAJOR — an item, its gold, its status, or the scoring rule changed

**Why that bump:**

## Checks

- [ ] `PYTHONUTF8=1 PYTHONPATH=src python -m pytest tests -q` passes
- [ ] If this adds a safety check, I broke the code on purpose and confirmed my
      test fails (a test that has never failed has not been shown to test anything)
- [ ] No number is typed by hand; if a reported number changed, I name the
      script that re-derives it
- [ ] No statutory text is added to the release bundle
- [ ] No item is marked `verified` without a qualified human having verified it

## If this changes data

**Items affected (by id):**

**Numbers that change, old → new:**

<!-- Required if a number has appeared in a paper or preprint. Correcting a
     published number quietly is worse than the original error. -->

**CHANGELOG.md updated:** yes / no
