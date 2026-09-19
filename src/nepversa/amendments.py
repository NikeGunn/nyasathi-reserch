"""Amendment-provenance extraction from Nepali consolidated Acts.

Nepali consolidated Acts publish amendment provenance *inside* the statutory
text: a numbered footnote marker sits immediately before the clause it governs,
and a legend at the foot of the provision says what the amendment did.

    1(d1) Avail credit or advance facilities by the Chief Executive Officer ...
    2(e)  Re-avail or re-provide loans from or by another Bank ...

    1 Added by the First Amendment.
    2 Amended by the First Amendment.

This module turns that into structured records. Every field is read from the
source; nothing is inferred (the project rule that no datum is invented).

Why this exists at all: the usual route to a validity window is the Gazette
commencement notice, and Nepal's are 50-of-53 `NO_TEXT` scans
(documented in an earlier corpus survey). Footnotes are the route that works — see
the project README.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class Operation(Enum):
    """What an amendment did to a provision unit.

    A closed set. An unrecognised footnote raises rather than defaulting:
    a silent `UNKNOWN` would enter the corpus as data and be indistinguishable
    from a real reading.
    """

    INSERT = "insert"
    SUBSTITUTE = "substitute"
    REPEAL = "repeal"


# Ordinals as they appear in the published footnotes, both editions.
# Matched by *ending* on the Nepali side, never as whole words: the root
# Three separate defects in earlier work came from word-list matching of
# Nepali (`-दैन`, `गर्नुपर्नेछ`/`तिर्नुपर्नेछ`, the greeting matcher).
_ORDINALS_EN = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
_ORDINALS_NE = {
    "पहिलो": 1, "दोस्रो": 2, "दोश्रो": 2, "तेस्रो": 3, "तेश्रो": 3,
    "चौथो": 4, "पाँचौं": 5, "पाँचौ": 5, "छैटौं": 6, "छैटौ": 6,
    "सातौं": 7, "सातौ": 7, "आठौं": 8, "आठौ": 8, "नवौं": 9, "नवौ": 9,
    "दशौं": 10, "दशौ": 10,
}

# Footnote verb -> operation. Nepali entries are matched as endings.
#
# The English side is a PHRASE list, not a word list, because the published
# editions vary: the Banking Offences Act writes "Taken out by the First
# Amendment." where others write "Deleted by ...". That variant was missed on
# the first full harvest and silently cost two provisions their provenance —
# the same failure shape seen three times for Nepali in earlier work.
# `UnknownAmendmentVerbError` exists so the next variant is reported, not lost.
_OPS_EN = {
    "added": Operation.INSERT,
    "inserted": Operation.INSERT,
    "amended": Operation.SUBSTITUTE,
    "substituted": Operation.SUBSTITUTE,
    "replaced": Operation.SUBSTITUTE,
    "deleted": Operation.REPEAL,
    "removed": Operation.REPEAL,
    "repealed": Operation.REPEAL,
    "omitted": Operation.REPEAL,
    "taken out": Operation.REPEAL,
    "struck out": Operation.REPEAL,
}
_OPS_NE = {
    "थप": Operation.INSERT,          # थप / थप गरिएको
    "संशोधित": Operation.SUBSTITUTE,  # संशोधित / संशोधन गरिएको
    "प्रतिस्थापित": Operation.SUBSTITUTE,
    "राखिएको": Operation.SUBSTITUTE,
    "झिकिएको": Operation.REPEAL,
    "हटाइएको": Operation.REPEAL,
    "खारेज": Operation.REPEAL,
}

# Devanagari digits, for footnote markers written in Nepali numerals.
_DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# A footnote legend line: a marker number, then the sentence describing it.
# Both scripts' digits are allowed; `\d` is Unicode-aware in Python, so
# Devanagari numerals already match .
#
# The separator is OPTIONAL. §3 of the Banking Offences Act prints
# `1Amended by the First Amendment.` with no space, while §5 and §7 print
# `1 Taken out by ...` with one. Requiring `\s+` silently swallowed the legend
# into the body and left the provision looking un-amended — the same silent
# class of failure as the unknown-verb bug, from a different direction.
# The following `[A-Za-zऀ-ॿ]` stops this matching an ordinary
# numbered clause like `1) The Bank shall ...`.
_LEGEND_RE = re.compile(r"^\s*(\d+)[\.\)]?\s*([A-Za-zऀ-ॿ]\S*.*)$")

# An inline marker: a footnote digit immediately followed by the unit it
# governs. Two published forms, both seen in the same Act:
#
#   1(d1)  — footnote 1, lettered clause (d1)          [§7]
#   11)    — footnote 1, numbered sub-section 1)       [§9, §15, §19]
#
# The second form is why this is not simply `(\d+)\(`. `11)` is not
# "sub-section eleven": the leading digit is the footnote marker and the rest
# is the unit. The alternation is ordered so the bracketed form wins, and the
# numbered form takes exactly ONE leading digit — footnote markers in these
# editions are single-digit, and consuming more would silently renumber the
# sub-section it governs.
#
# `(?<![\w])` keeps this from matching inside an ordinary cross-reference such
# as "clause (d1) of Section 5".
_INLINE_RE = re.compile(
    r"(?<![\w])(?:"
    r"(\d+)\(([^()\s]{1,10})\)"      # 1(d1) / २(ङ)
    r"|"
    r"(\d)(\d{1,2})\)"               # 11)  -> footnote 1, unit 1)
    r")"
)


def _fold_digits(text: str) -> str:
    """Devanagari numerals to ASCII. `१२क` -> `12क`."""
    return text.translate(_DEVA_DIGITS)


def normalize(text: str) -> str:
    """NFC-normalize and collapse whitespace.

    NFC because the corpus quotes character-exactly downstream and Devanagari
    has decomposable forms; a span that differs only by composition would fail
    an exact match for no semantic reason.
    """
    return " ".join(unicodedata.normalize("NFC", text).split())


@dataclass(frozen=True, slots=True)
class Footnote:
    """One legend entry: `1 Added by the First Amendment.`"""

    marker: str
    """The footnote number as printed, ASCII-folded."""

    operation: Operation
    amendment_ordinal: int | None
    """1 for "First Amendment". `None` when the footnote names no ordinal."""

    text: str
    """The legend sentence verbatim, for audit."""


@dataclass(frozen=True, slots=True)
class AmendedUnit:
    """One clause that an amendment touched, with its provenance."""

    unit: str
    """The unit label as printed: `d1`, `ङ`, `घ१`."""

    operation: Operation
    amendment_ordinal: int | None
    footnote_marker: str
    text: str
    """The unit's current text, after the amendment."""

    @property
    def text_before_available(self) -> bool:
        """Whether the pre-amendment text can be recovered from this source.

        `False` for SUBSTITUTE: the consolidated edition prints only the text as
        amended, so the superseded wording is not in the document. Benchmark
        items built from a SUBSTITUTE must therefore ask which version *governs*,
        never ask the model to reproduce superseded text we do not hold
        (see README).
        """
        return self.operation in (Operation.INSERT, Operation.REPEAL)


class FootnoteParseError(ValueError):
    """A footnote legend line matched the shape but not the vocabulary."""


class UnknownAmendmentVerbError(FootnoteParseError):
    """A footnote names an amendment with a verb this module does not know.

    Raised rather than skipped. A real amendment whose operation we cannot read
    is worse than no data: it looks exactly like a provision that was never
    amended, so the benchmark would silently claim a clause is original when
    the law says it was inserted or removed. `"Taken out by the First
    Amendment."` did precisely this on the first full harvest.
    """


_LOOKS_LIKE_AMENDMENT = re.compile(
    r"\bby\s+(?:the\s+)?\S*\s*amendment\b|संशोधनद्वारा|संशोधनबाट",
    re.IGNORECASE,
)
"""Footnote grammar: "**by** the First Amendment", `संशोधन` + instrumental case.

Deliberately narrower than the word "amendment". Statutes contain ordinary
numbered clauses *about* amendment — "Amendment of bylaws requires a general
meeting", and the site's own "Section 53: Amendment to Procurement Contract".
Matching the bare word made those raise `UnknownAmendmentVerbError`, which
would reject valid provisions and lose real text.

The agentive "by ... Amendment" is what distinguishes a footnote recording who
changed the provision from prose that merely discusses amendment.
"""


def _classify(sentence: str) -> tuple[Operation, int | None]:
    """Read operation and amendment ordinal out of a legend sentence."""
    low = sentence.lower()

    operation: Operation | None = None
    for phrase, op in _OPS_EN.items():
        if re.search(rf"\b{re.escape(phrase)}\b", low):
            operation = op
            break
    if operation is None:
        # Nepali: match the ENDING, not the whole word. `संशोधनद्वारा थप।`
        # and `पहिलो संशोधनद्वारा थप गरिएको।` must both resolve.
        for stem, op in _OPS_NE.items():
            if re.search(rf"{stem}\S*", sentence):
                operation = op
                break
    if operation is None:
        raise FootnoteParseError(
            f"no known amendment operation in footnote: {sentence!r}"
        )

    ordinal: int | None = None
    for word, n in _ORDINALS_EN.items():
        if re.search(rf"\b{word}\b", low):
            ordinal = n
            break
    if ordinal is None:
        for word, n in _ORDINALS_NE.items():
            if word in sentence:
                ordinal = n
                break
    if ordinal is None:
        # Numeric form: "2nd Amendment", "२ संशोधन".
        m = re.search(r"(\d+)(?:st|nd|rd|th)?\s+(?:amendment|संशोधन)", _fold_digits(low))
        if m:
            ordinal = int(m.group(1))

    return operation, ordinal


def parse_footnotes(lines: list[str]) -> tuple[dict[str, Footnote], set[int]]:
    """Parse the legend block at the foot of a provision.

    Returns the footnotes **and the indices of the lines they occupied**, so
    the caller can drop exactly those lines from the body without re-matching
    text. Comparing rendered strings to decide what to remove is how a legend
    line and a body line that merely look alike get confused.

    A line is a legend entry only if it starts with a number AND names a known
    amendment operation, so ordinary numbered sub-clauses do not match.

    Raises `UnknownAmendmentVerbError` when a line names an amendment but uses
    a verb this module does not know. That is a **corpus-integrity error, not a
    parse miss**: the provision really was amended, and dropping it quietly
    makes it indistinguishable from one that never was. The harvester records
    the row as rejected and names the sentence, so the vocabulary can be
    extended against real text rather than guessed at.
    """
    found: dict[str, Footnote] = {}
    legend_lines: set[int] = set()
    for i, raw in enumerate(lines):
        m = _LEGEND_RE.match(_fold_digits(raw.strip()))
        if not m:
            continue
        marker, sentence = m.group(1), normalize(m.group(2))
        try:
            operation, ordinal = _classify(sentence)
        except FootnoteParseError:
            if _LOOKS_LIKE_AMENDMENT.search(sentence):
                raise UnknownAmendmentVerbError(sentence)
            continue  # an ordinary numbered list item
        found[marker] = Footnote(
            marker=marker,
            operation=operation,
            amendment_ordinal=ordinal,
            text=sentence,
        )
        legend_lines.add(i)
    return found, legend_lines


def extract_amended_units(
    body_lines: list[str], footnotes: dict[str, Footnote]
) -> list[AmendedUnit]:
    """Attach each inline marker to its footnote.

    A marker whose number has no legend entry is **dropped**, not guessed: an
    amendment we cannot describe is not evidence. Under-reporting is safe here;
    inventing an operation is not.
    """
    units: list[AmendedUnit] = []
    for raw in body_lines:
        line = raw.strip()
        if not line:
            continue
        m = _INLINE_RE.match(_fold_digits(line))
        if not m:
            continue
        # Groups 1-2 are the bracketed form `1(d1)`; groups 3-4 the numbered
        # form `11)`. Exactly one pair is populated.
        marker, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        note = footnotes.get(marker)
        if note is None:
            continue
        text = normalize(line[m.end():])
        units.append(
            AmendedUnit(
                unit=normalize(unit),
                operation=note.operation,
                amendment_ordinal=note.amendment_ordinal,
                footnote_marker=marker,
                text=text,
            )
        )
    return units


def inserted_by_numbering(section_number: str) -> bool:
    """Whether a section number shows it was inserted by amendment.

    An amendment-inserted section carries a letter suffix — `12A`, `14B`,
    `१२क`, `१९ख` — because it had to fit between existing numbers. Such a
    section did not exist before that amendment, which is a validity window
    with a known opening bound, derived independently of any footnote.

    This is a second signal that cross-checks the first
    (see README).
    """
    folded = _fold_digits(normalize(section_number))
    return bool(re.fullmatch(r"\d+\s*(?:[A-Za-z]|[क-ह])", folded))
