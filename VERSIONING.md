# Versioning policy

NEPVERSA is a **dataset plus the code that derives it**, and those two things
fail differently. Code that changes behaviour breaks a caller; a dataset that
changes content breaks a *published number*. A paper reporting "P@1 0.871 on
NEPVERSA" is only checkable if a reader can obtain the exact corpus that was
measured, so the version is part of the scientific claim, not packaging.

The release is versioned `MAJOR.MINOR.PATCH`, read as follows.

## What each part means here

| Change | Bump | Why |
|---|---|---|
| An item is added, removed, or its gold changes | **MAJOR** | Any previously published number computed on this set stops being reproducible. This is the case that matters most. |
| An item's `status` changes (`unverified` → `verified`/`rejected`) | **MAJOR** | The evaluable set changes, so scores change even though no text did. |
| The scoring rule or nugget semantics change | **MAJOR** | The same answers now score differently. |
| An Act is added, leaving existing items untouched | **MINOR** | Old numbers remain reproducible on the old subset, which the manifest's per-act counts let you recover. |
| New fields, scripts, figures, or documentation | **MINOR** | Additive; nothing previously measured moves. |
| A typo in prose, a comment, a test, a build fix | **PATCH** | No artefact a number depends on is touched. |

**The rule behind the table:** if a published number could change, the MAJOR
version changes. Convenience to downstream users never outranks that.

A pre-1.0 `0.x` line would have signalled "unstable, expect breakage". This
release is `1.0.0` because the extraction method, the item schema and the
scoring rule are settled and documented. What is *not* settled is the human
verification status, and that is recorded in the manifest and the item records
rather than hidden in a version number.

## The version is not a quality claim

`1.0.0` does **not** mean the benchmark is validated. Every item currently
carries `status=unverified` and no human legal audit has been performed
(`AUDIT_human_verification_required.md`). When that audit happens the version
becomes `2.0.0`, because the evaluable set changes, and the manifest will carry
the verified proportion.

A reader must never infer verification status from the version. Read
`RELEASE_MANIFEST.json`, whose `items_verified_by_human` field is the answer,
and which CI checks against the item records on every push.

## Where the version lives

`VERSION` in the research tree is the single source of truth. Every other
appearance is generated from it by `analysis/make_release.py`:

- `RELEASE_MANIFEST.json` → `version`, `released`
- `CITATION.cff` → `version`, `date-released`

Never edit those by hand; they are overwritten on the next release build, and a
hand-edited version that disagrees with its tag is how a dataset becomes
uncitable. CI fails the build if the manifest and the citation disagree.

## Releasing

```bash
# 1. Decide the bump from the table above and record why in CHANGELOG.md.
echo "1.1.0" > ../VERSION

# 2. Rebuild. The manifest and the citation are stamped from VERSION.
python ../analysis/make_release.py

# 3. Confirm the counts changed the way you expected, and that no statutory
#    text leaked into the release.
cat RELEASE_MANIFEST.json

# 4. Commit, tag, push. The tag is what makes a version citable.
git add -A && git commit -m "Release 1.1.0: <what changed and why>"
git tag -a v1.1.0 -m "NEPVERSA 1.1.0 — <one line>"
git push origin main --follow-tags
```

`--follow-tags` pushes annotated tags with the commit. A tag left on a laptop
is a version nobody else can obtain.

## Citing a specific version

Cite the tag, never `main`. `main` moves; a reader who follows it a year later
gets a different corpus and cannot reproduce the number they are checking.

```
Bhagat, N. (2026). NEPVERSA: A version-aware Nepali statutory retrieval
benchmark (Version 1.0.0) [Data set]. GitHub.
https://github.com/NikeGunn/nyasathi-reserch/releases/tag/v1.0.0
```

If the repository is later archived to Zenodo, the DOI supersedes the URL and
each tag receives its own DOI, which is what a journal will prefer.

## Changes that are never silent

Three classes of change must always appear in `CHANGELOG.md` with the reason,
whatever the version bump:

1. **Any item whose gold or status changed**, listed by item id.
2. **Any correction to a number that has appeared in a paper or preprint**,
   with both the old and the new value. Correcting a published number quietly
   is worse than the original error.
3. **Any extraction defect found after release**, including ones that turned
   out to be corpus facts rather than bugs. The project's own record is that
   automated cross-checking found defects hand-reading had missed; that history
   is useful to anyone building on the method.
