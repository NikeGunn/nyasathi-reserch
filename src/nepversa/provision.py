"""Parse one scraped nepallaws.com provision page into a structured record.

The scraped Markdown is a whole web page: consent banner, nav, the provision,
then "Related Laws" listings of *other* acts. Only the slice between the
provision heading and the `- Tagged:` footer is the provision.

That boundary is load-bearing. The product's own harvester lost half an act to
a similar cut-order mistake (an earlier corpus survey), so this
module fails loudly rather than storing a partially-cleaned body: text that
still carries page chrome is not quotable, and a corpus of not-quite-right
quotes is worse than a smaller correct one.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .amendments import (
    AmendedUnit,
    Footnote,
    Operation,
    UnknownAmendmentVerbError,
    extract_amended_units,
    inserted_by_numbering,
    normalize,
    parse_footnotes,
)

# The provision heading, e.g. `# Section 7: Not to avail or provide loans ...`
# or `# दफा ७ः अनधिकृत रुपमा कर्जा लिन वा दिन नहुने`.
# The separator after the number may be a colon OR a Devanagari visarga
# `ः` (U+0903). Treating the visarga as part of the number silently dropped
# 8% of provisions in the product's harvest and halved one act
# (an earlier corpus survey, "the visarga bug").
_HEADING_RE = re.compile(
    r"^#{1,4}\s*(?:Section|दफा|धारा|Article|Rule|नियम)\s*"
    r"([0-9०-९]+\s*(?:[A-Za-z]|[क-ह])?)\s*[:ः\.\-–]?\s*(.*)$",
    re.IGNORECASE,
)

_TAGGED_RE = re.compile(r"^\s*[-*]?\s*Tagged\s*:", re.IGNORECASE)

# Page chrome that must never survive into a stored provision. Any hit makes
# the row invalid: the validation gate fails loudly instead of storing dirt.
_CHROME_MARKERS = (
    "Estimated reading",
    "Was this page helpful",
    "Related Laws",
    "Scrape ID:",
    "We value your privacy",
    "cookie",
    "Accept All",
    "Open accessibility menu",
    "](http",
)

_VIEWS_RE = re.compile(r"^\s*[\d,]+\s+views\s*$", re.IGNORECASE)
_READING_RE = re.compile(r"^\s*Estimated reading:", re.IGNORECASE)


class ProvisionParseError(ValueError):
    """The page did not yield a clean, quotable provision."""


# A wholly repealed section keeps its number and prints only a run of dots
# where its text stood: `1………………………….` under `1 Taken out by the First
# Amendment.` Both ASCII and Devanagari ellipsis runs occur.
_ELIDED_RE = re.compile(r"^[\s\.…।]*$")


def _is_wholly_repealed(text: str, footnotes: dict[str, Footnote]) -> bool:
    """Whether this is a repealed-in-full section rather than a parse failure.

    §4 of the Banking Offences Act is exactly this: heading, a row of dots, and
    `1 Taken out by the First Amendment.` The length floor rejected it as
    "body too short", losing **the single clearest T3 supersession item in the
    act** — a section the law states outright no longer exists.

    Requires a REPEAL footnote, so an empty body with no explanation is still
    rejected. A provision that is blank for an unknown reason is a parse
    failure; one the law says was taken out is data.
    """
    stripped = re.sub(r"[0-9०-९]", "", text)
    return bool(footnotes) and _ELIDED_RE.match(stripped) is not None and any(
        f.operation is Operation.REPEAL for f in footnotes.values()
    )


@dataclass(frozen=True, slots=True)
class Provision:
    """One provision, as published in the consolidated edition."""

    act_slug: str
    chapter_slug: str
    number: str
    heading: str
    text: str
    source_url: str
    retrieved_at: str
    sha256: str
    language: str
    """`ne` or `en` — nepallaws.com publishes both editions."""

    footnotes: dict[str, Footnote] = field(default_factory=dict)
    amended_units: tuple[AmendedUnit, ...] = ()

    repealed_in_full: bool = False
    """The whole section was repealed; the page prints only elided dots.

    A first-class T3 supersession item: the law states outright that this
    provision no longer exists.
    """

    @property
    def citation_key(self) -> str:
        """Stable ID: `act:<slug>#<number>`. Survives URL slug changes.

        The site's slugs changed between 2026-09-04 and 2026-09-19 and the old
        ones now 404, so a URL is not an identity.
        """
        return f"act:{self.act_slug}#{self.number}"

    @property
    def was_inserted_by_amendment(self) -> bool:
        """True when the section number itself shows amendment insertion."""
        return inserted_by_numbering(self.number)

    @property
    def is_amended(self) -> bool:
        return bool(self.amended_units) or self.was_inserted_by_amendment


def _slugs(url: str) -> tuple[str, str]:
    parts = [p for p in url.split("/Laws/", 1)[-1].split("/") if p]
    act = parts[0] if parts else ""
    chapter = parts[1] if len(parts) > 1 else ""
    return act, chapter


def _detect_language(text: str) -> str:
    """`ne` when Devanagari dominates, else `en`."""
    deva = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "ne" if deva > latin else "en"


def _body_slice(lines: list[str]) -> tuple[int, int, str, str]:
    """Locate the provision heading and the `- Tagged:` terminator.

    Cuts at the EARLIEST terminator at or after the heading, never the first in
    list order — the page repeats the section title further down under
    "Related Laws", and taking a later cut would swallow other acts' text.
    """
    head = next(
        (
            (i, m)
            for i, line in enumerate(lines)
            if (m := _HEADING_RE.match(line.strip()))
        ),
        None,
    )
    if head is None:
        raise ProvisionParseError("no provision heading found")
    head_idx, match = head

    end = next(
        (j for j in range(head_idx + 1, len(lines)) if _TAGGED_RE.match(lines[j])),
        None,
    )
    if end is None:
        raise ProvisionParseError("no '- Tagged:' terminator after the heading")

    return head_idx, end, normalize(match.group(1)), normalize(match.group(2))


def parse_provision(markdown: str, source_url: str, *, retrieved_at: str | None = None) -> Provision:
    """Parse a scraped page into a `Provision`, or raise.

    Raises `ProvisionParseError` when the body is empty or still carries page
    chrome. Dropping a row loses one provision; storing an unquotable one
    corrupts every benchmark item built from it.
    """
    lines = markdown.split("\n")
    head_idx, end_idx, number, heading = _body_slice(lines)

    block = [
        ln for ln in lines[head_idx + 1 : end_idx]
        if ln.strip() and not _VIEWS_RE.match(ln) and not _READING_RE.match(ln)
    ]

    try:
        footnotes, legend_lines = parse_footnotes(block)
    except UnknownAmendmentVerbError as exc:
        # Reject the row and name the sentence. A provision whose amendment we
        # cannot read must not enter the corpus looking un-amended.
        raise ProvisionParseError(f"unknown amendment verb: {exc}") from exc
    body_lines = [ln for i, ln in enumerate(block) if i not in legend_lines]

    amended = extract_amended_units(body_lines, footnotes)
    text = normalize("\n".join(body_lines).replace("\n", " "))

    if len(text) < 20 and not _is_wholly_repealed(text, footnotes):
        raise ProvisionParseError(f"provision body too short ({len(text)} chars)")
    for marker in _CHROME_MARKERS:
        if marker.lower() in text.lower():
            raise ProvisionParseError(f"page chrome survived into body: {marker!r}")

    return Provision(
        act_slug=_slugs(source_url)[0],
        chapter_slug=_slugs(source_url)[1],
        number=number,
        heading=heading,
        text=text,
        source_url=source_url,
        retrieved_at=retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        language=_detect_language(text),
        footnotes=footnotes,
        amended_units=tuple(amended),
        repealed_in_full=_is_wholly_repealed(text, footnotes),
    )
