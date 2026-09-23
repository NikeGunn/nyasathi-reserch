"""Generate NEPVERSA benchmark items from provision versions.

Every item's gold answer is **derived from a published statement in the source**,
never authored. That is what makes the benchmark defensible and what makes it
buildable by one person: the amendment footnote *is* the ground truth.

## Scoring: nuggets, not a judge

Items are scored against deterministic **nuggets** — exact strings or a closed
set of labels — following Cymbler et al. (2026), who avoid an LLM judge for
temporal correctness because *a judge inherits the temporal bias it is meant to
measure*. A model that must output `absent` or a `citation_key` can be scored by
string comparison, with no second model in the loop.

Consequence for the annotation budget: humans **audit a sample** rather than
label every item, which keeps the rule that only humans confirm gold intact (no invented
annotations) while remaining finishable.

## Two scores, never averaged

Following TIDE (Sobhani et al., 2026), meaning-correct and time-correct are
separate. Averaging them hides the failure this benchmark exists to expose:
a model that retrieves a real provision that did not govern on the date.

## What is deliberately NOT generated

No item requires reproducing text the source does not print — the superseded
side of a SUBSTITUTE, or repealed wording. `ProvisionVersion.can_be_quoted`
gates this, and `generate_for_provision` refuses to build a quote item over a
version that fails it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from .versions import ProvisionVersion, VersionState


class QuestionType(Enum):
    """The five NEPVERSA question types."""

    T1_LOOKUP = "T1_lookup"
    """Plain retrieval of a provision. No temporal component."""

    T2_POINT_IN_TIME = "T2_point_in_time"
    """Which version governed at a given point. The core temporal task."""

    T3_SUPERSESSION = "T3_supersession"
    """Whether a version still governs — the honest answer may be refusal."""

    T4_STATUTE_TO_CASE = "T4_statute_to_case"
    """From a provision to the judgments interpreting it."""

    T5_CROSS_ACT = "T5_cross_act"
    """Requires combining provisions from more than one Act."""


class Script(Enum):
    DEVANAGARI = "devanagari"
    ROMANIZED = "romanized"
    CODE_MIXED = "code_mixed"


@dataclass(frozen=True, slots=True)
class Nugget:
    """One deterministically checkable fact the answer must contain."""

    kind: str
    """`label` (closed set), `citation` (exact key), or `exact` (verbatim span)."""

    value: str

    def matches(self, answer: str) -> bool:
        """Whether `answer` satisfies this nugget.

        Case-insensitive containment for labels and citations. **Never** the
        search normal form: the product's gate matches character-exactly and
        mixing the two normal forms is documented as how near-misses start
        passing silently (recorded in earlier engineering notes).
        """
        if self.kind == "exact":
            return self.value in answer
        return self.value.casefold() in answer.casefold()


@dataclass(frozen=True, slots=True)
class BenchmarkItem:
    """One question with mechanically derived gold."""

    item_id: str
    question_type: QuestionType
    question: str
    script: Script

    citation_key: str
    unit: str

    as_of_amendment: int | None
    """The amendment ordinal the question is anchored to. `None` when the
    amendment is named by instrument, not ordinal; see `as_of_event`."""

    gold_state: VersionState
    gold_nuggets: tuple[Nugget, ...]
    should_abstain: bool
    """True when the honest answer is a refusal (no governing text we hold)."""

    provenance: str
    """The published statement this item was derived from. Audit trail."""

    status: str = "unverified"
    """`unverified` until a human audits it (the rule that only humans confirm gold)."""

    source_url: str = ""

    as_of_event: str = ""
    """The amendment event the question is anchored to, as the legend names it."""

    def score(self, answer: str) -> dict[str, bool]:
        """Two independent scores. Deliberately not averaged."""
        return {
            "meaning_correct": all(n.matches(answer) for n in self.gold_nuggets),
            "time_correct": not self.should_abstain or _reads_as_abstention(answer),
        }


_ABSTENTION_MARKERS = (
    "no provision", "not in force", "does not exist", "did not exist",
    "cannot answer", "no basis", "आधार भेटिएन", "लागू छैन", "थिएन",
)


def _reads_as_abstention(answer: str) -> bool:
    low = answer.casefold()
    return any(m.casefold() in low for m in _ABSTENTION_MARKERS)


def _item_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"nepversa-{digest}"


def generate_point_in_time(
    version: ProvisionVersion, *, source_url: str = ""
) -> BenchmarkItem | None:
    """A T2 item: did this unit exist, and what did it say, at a point in time?

    Returns `None` when the source cannot support a checkable answer — the
    superseded side of a SUBSTITUTE, where we know a different text governed but
    not what it said. Generating that item would require gold we do not hold.
    """
    if version.state is VersionState.PRESENT_TEXT_UNKNOWN:
        return None

    anchor = version.from_amendment if version.from_amendment is not None else 0
    ordinal_phrase = _anchor_phrase(version)
    as_of = anchor if version.ordinal_known else None
    event = version.event_label
    # For an instrument-named amendment the anchor is the full phrase, so
    # "before the X" and "after the X" are distinct points in the
    # consistency check rather than one point with two gold states.
    as_of_event = ordinal_phrase if (event and not version.ordinal_known) else event
    unit_ref = f"{version.citation_key} ({version.unit})"

    if version.state is VersionState.ABSENT:
        # ABSENT is either the period before an INSERT or the period after a
        # REPEAL; the provenance must say which.
        if version.to_amendment is not None:
            provenance = f"clause ({version.unit}) inserted by the {event or version.to_amendment}"
        else:
            provenance = f"clause ({version.unit}) repealed by the {event or version.from_amendment}"
        question = (
            f"Under {unit_ref}, {ordinal_phrase}: was clause ({version.unit}) "
            f"in force, and if so what did it provide?"
        )
        return BenchmarkItem(
            item_id=_item_id(version.citation_key, version.unit, "T2", str(anchor)),
            question_type=QuestionType.T2_POINT_IN_TIME,
            question=question,
            script=Script.DEVANAGARI,
            citation_key=version.citation_key,
            unit=version.unit,
            as_of_amendment=as_of,
            gold_state=VersionState.ABSENT,
            gold_nuggets=(Nugget("label", "absent"),),
            should_abstain=True,
            provenance=provenance,
            source_url=source_url,
            as_of_event=as_of_event,
        )

    if not version.can_be_quoted:
        return None  # "text" that is only an elision run: nothing to quote
    question = (
        f"Under {unit_ref}, {ordinal_phrase}: what did clause "
        f"({version.unit}) provide?"
    )
    return BenchmarkItem(
        item_id=_item_id(version.citation_key, version.unit, "T2", str(anchor), "present"),
        question_type=QuestionType.T2_POINT_IN_TIME,
        question=question,
        script=Script.DEVANAGARI,
        citation_key=version.citation_key,
        unit=version.unit,
        as_of_amendment=as_of,
        gold_state=VersionState.PRESENT_TEXT_KNOWN,
        gold_nuggets=(
            Nugget("citation", version.citation_key),
            Nugget("exact", _salient_span(version.text or "")),
        ),
        should_abstain=False,
        provenance=f"clause ({version.unit}) text as printed after the {event or version.from_amendment}",
        source_url=source_url,
        as_of_event=as_of_event,
    )


def generate_supersession(
    version: ProvisionVersion, *, source_url: str = ""
) -> BenchmarkItem | None:
    """A T3 item: does this unit still govern?

    Only built over a REPEAL's post-state — the one case where the source says
    outright that the unit no longer exists. This is the item type TIDE found
    hardest (26.7% on rejecting a non-governing version).
    """
    if not (version.state is VersionState.ABSENT and version.from_amendment is not None):
        return None

    return BenchmarkItem(
        item_id=_item_id(version.citation_key, version.unit, "T3"),
        question_type=QuestionType.T3_SUPERSESSION,
        question=(
            f"Is clause ({version.unit}) of {version.citation_key} currently in "
            f"force? If not, state what happened to it."
        ),
        script=Script.DEVANAGARI,
        citation_key=version.citation_key,
        unit=version.unit,
        as_of_amendment=None,
        gold_state=VersionState.ABSENT,
        gold_nuggets=(Nugget("label", "absent"),),
        should_abstain=True,
        provenance=f"clause ({version.unit}) repealed by the {version.event_label or version.from_amendment}",
        source_url=source_url,
        as_of_event=version.event_label,
    )


def whole_section_repeal_item(row: dict, *, source_url: str = "") -> BenchmarkItem | None:
    """A T3 item for a section repealed in its entirety.

    The page prints only elided dots under a REPEAL footnote, so there are no
    surviving clauses for the clause-level path to expand — yet this is the
    least ambiguous supersession evidence the corpus holds: the law says the
    whole provision is gone.

    Returns `None` unless a REPEAL footnote is present, so the item is always
    backed by a published statement rather than by an empty page.
    """
    repeal = next(
        (f for f in row.get("footnotes", []) if f.get("operation") == "repeal"),
        None,
    )
    if repeal is None:
        return None

    key = row["citation_key"]
    ordinal = repeal.get("event") or repeal.get("amendment_ordinal")
    return BenchmarkItem(
        item_id=_item_id(key, "whole", "T3"),
        question_type=QuestionType.T3_SUPERSESSION,
        question=(
            f"Is {key} currently in force? If not, state what happened to it."
        ),
        script=Script.DEVANAGARI,
        citation_key=key,
        unit="",
        as_of_amendment=None,
        gold_state=VersionState.ABSENT,
        gold_nuggets=(Nugget("label", "absent"),),
        should_abstain=True,
        provenance=(
            f"whole section repealed by the {ordinal}: "
            f"{repeal.get('text', '').strip()}"
        ),
        source_url=source_url,
    )


def _anchor_phrase(version: ProvisionVersion) -> str:
    """How a question names its point in time.

    A version bounded by a named instrument is described by that instrument on
    both sides ("before the Financial Act, 2075"); "before any amendment" would
    be false for a clause whose Act had earlier, unrelated amendments.
    """
    if version.event_label and not version.ordinal_known:
        side = "before" if version.from_amendment is None else "after"
        return f"{side} the {version.event_label}"
    if version.from_amendment is None:
        return "before any amendment"
    return f"after the {_ordinal_word(version.from_amendment)} Amendment"


def _ordinal_word(n: int) -> str:
    words = {
        1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
        6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
    }
    return words.get(n, f"{n}th")


def _salient_span(text: str, *, words: int = 8) -> str:
    """A short verbatim span for exact-match scoring.

    Taken from the start of the clause rather than sampled, so the nugget is
    reproducible from the stored text alone.
    """
    return " ".join(text.split()[:words])


def generate_for_provision(
    versions: list[ProvisionVersion], *, source_url: str = ""
) -> list[BenchmarkItem]:
    """All deterministically-gradable items for one provision's versions."""
    items: list[BenchmarkItem] = []
    for v in versions:
        for maker in (generate_point_in_time, generate_supersession):
            item = maker(v, source_url=source_url)  # type: ignore[operator]
            if item is not None:
                items.append(item)
    return items
