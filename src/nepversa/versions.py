"""Turn amendment provenance into provision *versions* with validity windows.

This is the object the paper is about. A provision is not one text; it is a
sequence of versions, each authoritative for a period. A point-in-time question
(T2) asks which version governs a date; a supersession question (T3) asks
whether a version still governs at all.

## What the source supports, and what it does not

nepallaws.com publishes the **consolidated** text with footnotes naming the
amendment that changed each unit. From that we can derive, per unit:

* **INSERT** — the unit did not exist before amendment *n*. Both the pre-state
  (absent) and the post-state (the printed text) are known.
* **REPEAL** — the unit existed before amendment *n* and does not now. The
  post-state (absent) is known; the pre-state text is NOT printed.
* **SUBSTITUTE** — the unit existed and was reworded by amendment *n*. Only the
  post-state is printed; **the superseded wording is not in the document.**

`VersionBound.UNKNOWN_TEXT` marks the cases where the source does not carry the
text. That marker is the whole honesty mechanism of this module: a benchmark
item is generated only over bounds whose text we actually hold, so no question
can ever require a model to reproduce wording we never saw
(the project README §7).

## Dates

A footnote names an **ordinal** ("First Amendment"), not a date. Windows are
therefore ordinal-valued by default, and a BS/AD date is attached only when the
amending act's commencement is independently verified and recorded in
a dated-amendment table (not yet populated). An unverified date is left `None` — never
interpolated. The product has already been bitten once by a date that was
defaulted rather than resolved, and every downstream check was *correct about
the wrong year* (recorded in earlier engineering notes).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .amendments import AmendedUnit, Operation


class VersionState(Enum):
    """Whether a unit exists in a given period, and whether we hold its text."""

    ABSENT = "absent"
    """The unit does not exist in this period. Deterministically known."""

    PRESENT_TEXT_KNOWN = "present_text_known"
    """The unit exists and the source prints its text for this period."""

    PRESENT_TEXT_UNKNOWN = "present_text_unknown"
    """The unit exists but the source does not print this period's wording.

    The superseded side of a SUBSTITUTE. Usable for questions about *which
    version governs*; never for questions that require quoting the text.
    """


@dataclass(frozen=True, slots=True)
class ProvisionVersion:
    """One unit of one provision, over one period bounded by amendment events."""

    citation_key: str
    unit: str
    state: VersionState
    text: str | None

    from_amendment: int | None
    """Opening bound. `None` = since original enactment."""

    to_amendment: int | None
    """Closing bound, exclusive. `None` = still in force."""

    from_date_bs: str | None = None
    to_date_bs: str | None = None
    """Set only from an independently verified commencement date."""

    event_label: str = ""
    """The amendment event that bounds this version, as the legend names it.

    When the legend names an instrument rather than an ordinal (`Financial Act,
    2075`), the bounds are **unit-local**: `0` is before that event and `1`
    after it, and nothing here orders it against another unit's amendments.
    Before this field existed such a unit got `None` on both bounds, which
    `None`-means-enactment read as "in force since enactment and still in
    force", on both sides of the amendment at once."""

    ordinal_known: bool = True

    @property
    def is_current(self) -> bool:
        return self.to_amendment is None

    @property
    def can_be_quoted(self) -> bool:
        """Whether a benchmark item may require this version's exact wording.

        Wording means words: Income Tax §10 prints sub-section 3) as a row of
        dots under an "Amended by the Financial Act, 2075" legend, and the
        generator produced an item whose verbatim gold was `……………`. The
        source contradicts itself there (a substitution with nothing
        substituted), so no quotation item is defensible.
        """
        substance = "".join(ch for ch in (self.text or "") if ch not in " .…।\t\n")
        return self.state is VersionState.PRESENT_TEXT_KNOWN and len(substance) >= 3

    def governs_at(self, amendment_ordinal: int) -> bool:
        """Whether this version is in force *after* `amendment_ordinal` applied.

        Bounds are half-open `[from, to)` on amendment ordinals, so exactly one
        version of a unit governs any point. Closed bounds would make the
        amendment event itself ambiguous, which is the single thing a
        point-in-time benchmark must never be.
        """
        lo = self.from_amendment if self.from_amendment is not None else 0
        if amendment_ordinal < lo:
            return False
        return self.to_amendment is None or amendment_ordinal < self.to_amendment


def versions_for_unit(citation_key: str, amended: AmendedUnit) -> list[ProvisionVersion]:
    """Expand one amended unit into its before/after versions.

    Returns two versions — the period before the amendment and the period after
    — except where the source cannot support a claim about one of them.
    """
    n = amended.amendment_ordinal
    label = amended.amendment_event
    ordinal_known = n is not None
    if n is None:
        if not label:
            # Neither an ordinal nor a named instrument: the event cannot be
            # stated in a question, so no version is claimed at all.
            return []
        n = 1  # unit-local: before (0) / after (1) the named event

    unit = amended.path
    versions = _versions(citation_key, unit, amended, n)
    return [
        ProvisionVersion(
            x.citation_key, x.unit, x.state, x.text,
            from_amendment=x.from_amendment, to_amendment=x.to_amendment,
            event_label=label, ordinal_known=ordinal_known,
        )
        for x in versions
    ]


def _versions(
    citation_key: str, unit: str, amended: AmendedUnit, n: int
) -> list[ProvisionVersion]:
    if amended.operation is Operation.INSERT:
        return [
            ProvisionVersion(
                citation_key, unit, VersionState.ABSENT, None,
                from_amendment=None, to_amendment=n,
            ),
            ProvisionVersion(
                citation_key, unit, VersionState.PRESENT_TEXT_KNOWN, amended.text,
                from_amendment=n, to_amendment=None,
            ),
        ]

    if amended.operation is Operation.REPEAL:
        return [
            # The repealed wording is not printed, so the earlier period is
            # PRESENT_TEXT_UNKNOWN: we know it existed, not what it said.
            ProvisionVersion(
                citation_key, unit, VersionState.PRESENT_TEXT_UNKNOWN, None,
                from_amendment=None, to_amendment=n,
            ),
            ProvisionVersion(
                citation_key, unit, VersionState.ABSENT, None,
                from_amendment=n, to_amendment=None,
            ),
        ]

    # SUBSTITUTE
    return [
        ProvisionVersion(
            citation_key, unit, VersionState.PRESENT_TEXT_UNKNOWN, None,
            from_amendment=None, to_amendment=n,
        ),
        ProvisionVersion(
            citation_key, unit, VersionState.PRESENT_TEXT_KNOWN, amended.text,
            from_amendment=n, to_amendment=None,
        ),
    ]


def build_versions(citation_key: str, amended_units: list[AmendedUnit]) -> list[ProvisionVersion]:
    """All versions for one provision's amended units."""
    out: list[ProvisionVersion] = []
    for unit in amended_units:
        out.extend(versions_for_unit(citation_key, unit))
    return out


def version_at(
    versions: list[ProvisionVersion], unit: str, amendment_ordinal: int
) -> ProvisionVersion | None:
    """The single version of `unit` governing after `amendment_ordinal`.

    Raises if the windows overlap: two versions governing one point is a corpus
    defect, and returning the first would hide it behind a plausible answer.
    """
    hits = [
        v for v in versions
        if v.unit == unit and v.governs_at(amendment_ordinal)
    ]
    if len(hits) > 1:
        raise ValueError(
            f"{citation_for(hits)} — {len(hits)} versions govern at amendment "
            f"{amendment_ordinal}; validity windows overlap"
        )
    return hits[0] if hits else None


def citation_for(versions: list[ProvisionVersion]) -> str:
    v = versions[0]
    return f"{v.citation_key}({v.unit})"
