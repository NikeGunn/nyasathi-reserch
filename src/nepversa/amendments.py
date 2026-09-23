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
from html import unescape
from dataclasses import dataclass, replace
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
    # The Income Tax Act 2058 prints "Extreted from the Financial Act,
    # 2080(2023)" against a clause whose body is a row of dots. The misspelling
    # is the source's, kept verbatim so the legend still resolves; "extracted"
    # is the translation of झिकिएको ("taken out") that it misspells.
    "extracted": Operation.REPEAL,
    "extreted": Operation.REPEAL,
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
# governs. Four published forms, across four Acts:
#
#   1(d1)  — footnote 1, lettered clause (d1)          [Banking §7]
#   1 (b)  — the same, with a space                    [Companies §13]
#   11)    — footnote 1, numbered sub-section 1)       [Banking §9, §15, §19]
#   2c)    — footnote 2, lettered clause c)            [Income Tax; also 1h1),
#            34a) = footnote 3, clause 4a), 1av1) = footnote 1, clause av1)]
#
# The last two are why this is not simply `(\d+)\(`. `11)` is not
# "sub-section eleven" and `34a)` is not footnote 34: the leading digit is the
# footnote marker and the rest is the unit. The unbracketed forms take exactly
# ONE leading digit — footnote markers in these editions are single-digit, and
# consuming more would silently renumber the unit it governs. (`34a)` sits
# under a legend numbered 1, 2, 3: footnote 3, inserted clause 4a.)
#
# Missing the space form and the lettered form cost the Companies Act its only
# amended section (§13, six units repealed) and the Income Tax Act its clauses
# c), h1), 4a), av1): the rows parsed cleanly and read as un-amended.
#
# `(?<![\w])` keeps this from matching inside an ordinary cross-reference such
# as "clause (d1) of Section 5".
_INLINE_RE = re.compile(
    r"(?<![\w])(?:"
    r"(\d+)\s?\(([^()\s]{1,10})\)"                   # 1(d1) / 1 (b) / २(ङ)
    r"|"
    r"(\d)(\d{1,2}[a-z]?\d?|[a-z]{1,2}\d{0,2})\)"     # 11) / 2c) / 1h1) / 34a)
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

    event: str = ""
    """The amendment event, as the legend names it: `First Amendment`, or the
    amending instrument (`Financial Act, 2075`) when the legend names an Act
    instead of an ordinal. Empty when the legend names neither."""


_INSTRUMENT_RE = re.compile(r"\b(?:by|from)\s+the\s+(.+?)\s*\.?\s*$", re.IGNORECASE)


def _event_label(sentence: str, ordinal: int | None) -> str:
    """Name the amendment event a legend records.

    An ordinal gives `First Amendment`. Without one, the legend's own words for
    the instrument are kept verbatim (`Act to Amend Certain Nepal Acts, 2074`),
    because the ordinal cannot be recovered: an Act amended by the Financial
    Act, 2075 has no "Nth Amendment" position this source states.
    """
    if ordinal is not None:
        return f"{_ORDINAL_WORDS.get(ordinal, f'{ordinal}th')} Amendment"
    m = _INSTRUMENT_RE.search(sentence)
    return normalize(m.group(1)) if m else ""


_ORDINAL_WORDS = {n: w.capitalize() for w, n in _ORDINALS_EN.items()}


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

    amendment_event: str = ""
    """The footnote's `event`: what to call the amendment in a question."""

    parent: str = ""
    """The nearest numbered unit above this one (`4` for clause `c` printed
    under sub-section `4)`), or empty. Clause labels repeat within a provision:
    Income Tax §4 has a repealed clause `c` under sub-section 3 and another
    under sub-section 4, and keyed on the label alone the two collided."""

    @property
    def path(self) -> str:
        """`4(c)` when a parent is known, else the bare label."""
        return f"{self.parent}({self.unit})" if self.parent and self.parent != self.unit else self.unit

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
    r"\bby\s+(?:the\s+)?\S*\s*amendment\b|संशोधनद्वारा|संशोधनबाट"
    # A named amending instrument with its year, at the END of the sentence:
    # "... by the Financial Act, 2075.", "... from the Financial Act,
    # 2080(2023)". End-anchored because body prose also cites Acts by name
    # ("registered under the Companies Act, 2063, shall ...") and continues.
    r"|\b(?:by|from)\s+the\s+[^.]*?\bact,?\s*\d{4}\s*(?:\(\d{4}\))?\s*(?:bs)?\.?\s*$",
    re.IGNORECASE,
)
"""Footnote grammar: "**by** the First Amendment", `संशोधन` + instrumental case,
or a named amending Act closing the sentence.

Deliberately narrower than the word "amendment". Statutes contain ordinary
numbered clauses *about* amendment — "Amendment of bylaws requires a general
meeting", and the site's own "Section 53: Amendment to Procurement Contract".
Matching the bare word made those raise `UnknownAmendmentVerbError`, which
would reject valid provisions and lose real text.

The agentive "by ... Amendment" is what distinguishes a footnote recording who
changed the provision from prose that merely discusses amendment. The
instrument alternative was added when "2 Extreted from the Financial Act,
2080(2023)" was skipped as an ordinary list item: no known verb, no "by ...
Amendment", so the guard stayed silent and the clause read as original.
"""

_VERBLESS_RE = re.compile(r"^the\s+(\w+)\s+amendment\.?$", re.IGNORECASE)
"""A legend naming the amendment and nothing else: "1 The first amendment."

The Companies Act 2063 uses this for §13, where every unit it marks is a row
of dots. The legend states no operation, so the operation is read from what
the text shows: see `_resolve_verbless`.
"""

_ELIDED_UNIT_RE = re.compile(r"^[\s\.…।]*$")

_INSERTED_LABEL_RE = re.compile(r"^(?:\d{1,3}[A-Z]|[a-z]{1,2}\d{1,2})$")
"""A unit label that exists only because it was inserted: `1A`, `u1`, `d1`."""


def _resolve_verbless(marker: str, lines: list[str]) -> Operation:
    """The operation of a verbless legend, from the units it marks.

    REPEAL when every unit it governs is elided (the printed text shows that
    nothing remains); INSERT when every unit it governs carries an
    insertion-form label. Anything else, a substituted clause above all, is not
    readable from this source, and raises rather than guessing.
    """
    governed: list[tuple[str, str]] = []
    for raw in lines:
        m = _INLINE_RE.match(_fold_digits(raw.strip()))
        if not m:
            continue
        found = m.group(1) or m.group(3)
        label = m.group(2) or m.group(4)
        if found == marker:
            governed.append((raw.strip()[m.end():], label))
    if governed and all(_ELIDED_UNIT_RE.match(t) for t, _ in governed):
        return Operation.REPEAL
    # An inserted unit is numbered to fit between existing ones: sub-section
    # `1A` between (1) and (2), clause `u1` after (u). That is the same
    # numbering signal `inserted_by_numbering` reads at section level, and it
    # resolved all three verbless legends over live text in the Companies Act
    # (§9 (1A), the registration section's (1A), the definitions' (u1)).
    if governed and all(_INSERTED_LABEL_RE.match(label) for _, label in governed):
        return Operation.INSERT
    raise UnknownAmendmentVerbError(
        f"footnote {marker} states no operation and marks "
        f"{len(governed)} unit(s) that are not all elided"
    )


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
    # The legend is the TRAILING block of the provision: walk up from the foot
    # and stop at the first line that is not a legend. Accepting a legend-shaped
    # line anywhere let an ordinary sub-section that happens to contain a verb
    # ("2) If any amendment is made ... removed ...") be read as a footnote, and
    # the caller then deleted it from the quotable text: twelve provisions of
    # the Companies Act lost a sub-section this way, silently.
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped or _SEPARATOR_RE.match(stripped):
            continue
        m = _LEGEND_RE.match(_fold_digits(stripped))
        if not m:
            break
        marker, sentence = m.group(1), normalize(m.group(2))
        try:
            operation, ordinal = _classify(sentence)
            if not _LEGEND_GRAMMAR.search(sentence):
                break  # a body sentence that happens to contain a verb
        except FootnoteParseError:
            verbless = _VERBLESS_RE.match(sentence)
            if verbless:
                operation = _resolve_verbless(marker, lines)
                ordinal = _ORDINALS_EN.get(verbless.group(1).lower())
            elif _LOOKS_LIKE_AMENDMENT.search(sentence):
                raise UnknownAmendmentVerbError(sentence)
            else:
                break  # an ordinary numbered list item: the legend (if any) ended
        found[marker] = Footnote(
            marker=marker,
            operation=operation,
            amendment_ordinal=ordinal,
            text=sentence,
            event=_event_label(sentence, ordinal),
        )
        legend_lines.add(i)
    return found, legend_lines


_LEGEND_GRAMMAR = re.compile(
    r"^[A-Za-z]+(?:\s+out)?\s+(?:by|from)\s+(?:the\s+)?.*\b(?:acts?|amendment)\b"
    r"|संशोधन",
    re.IGNORECASE,
)
"""What a legend sentence looks like: it OPENS with the verb, then "by/from the"
and an instrument (`Taken out by the First Amendment`, `Added by the Act to
Amend Certain Nepal Acts ...`, `Extreted from the Financial Act, 2080`).

Audited against every legend-shaped trailing line in the five cached Acts
(2026-09-23): all 61 real legends match, and none of the body sentences that
merely contain a verb ("The Office shall register the amended prospectus",
"No auditor ... shall be removed pending ...") does, because a statute's
sentence does not begin with a bare participle followed by "by the"."""

_SEPARATOR_RE = re.compile(r"^(?:[*\-_]\s*){3,}$")
"""`* * *` / `---`: the rule some pages print between body and legend."""


# The follow text is captured to the next tag and only THEN unescaped and cut:
# a fixed 60-character window split `&#8230;` mid-entity, left a stray `&`, and
# lost Companies §13 (5), (6), (7).
_SUP_RE = re.compile(r"<sup[^>]*>\s*([0-9०-९]+)\s*</sup>([^<]{0,2000})", re.IGNORECASE)
"""An inline superscript marker and the text that follows it, up to the next tag.

Legend superscripts (`<sup>1 Inserted by ...</sup>`) carry prose, not a bare
number, and do not match.
"""

_UNIT_RE = re.compile(r"^\(?([^()\s]{1,10})\)")

_PLAIN_NUMBERED_RE = re.compile(r"^\(?(\d{1,3}[A-Z]?)\)\s")
"""An unmarked numbered unit, `4) ...` or `(4) ...`: a candidate parent."""

_SUP_MATCH_CHARS = 12
"""How much of the text after a superscript must agree with the Markdown line."""


def _squash(text: str) -> str:
    """Drop whitespace and elision characters, for alignment only (never stored)."""
    return re.sub(r"[\s\.…।]+", "", text)


def sup_markers(html: str) -> list[tuple[str, str]]:
    """Every inline footnote marker on the page, read from `<sup>` in the HTML.

    Returns `(marker, following_text)` pairs in page order. This is the ground
    truth that Markdown destroys: `<sup>2</sup>8)` and a plain `28)` flatten to
    the same characters, and so do `<sup>1</sup>0)` (which does not exist) and
    sub-section `10)` (which does). §88 and §95A of the Income Tax Act 2058 have
    both kinds in one provision, and sequence heuristics would have to guess.
    """
    return [
        (_fold_digits(m.group(1)), normalize(unescape(m.group(2))))
        for m in _SUP_RE.finditer(html)
    ]


def _unit_from_sup(
    line: str, sup_marks: list[tuple[str, str]]
) -> tuple[str, str, str] | None:
    """Match a Markdown line to an unused superscript, consuming it.

    Returns `(marker, unit, text)` when the line is the flattened form of
    `<sup>marker</sup>` + the recorded following text, else `None`.
    """
    folded = _fold_digits(line)
    for idx, (marker, follow) in enumerate(sup_marks):
        if not folded.startswith(marker):
            continue
        rest = normalize(folded[len(marker):])
        # Compare with elision runs and spaces squeezed out: the HTML prints a
        # repealed unit as `(5)&#8230;&#8230;...` and the Markdown as
        # `(5)………..`, different lengths of the same dots. A raw prefix
        # compare lost Companies §13 (5), (6), (7) this way.
        probe = _squash(follow)[:_SUP_MATCH_CHARS]
        if len(probe) < 2 or not _squash(rest).startswith(probe):
            continue
        unit = _UNIT_RE.match(rest)
        if unit is None:
            continue
        del sup_marks[idx]
        return marker, unit.group(1), normalize(rest[unit.end():])
    # Label FIRST, then the marker: Bonus Act §5 prints the repealed
    # sub-section 4 as `4) <sup>1</sup>……`. The follow text is then only
    # dots, so the prefix probe above has nothing to match on; require the
    # label shape, the marker right after it, and the same (squeezed) rest.
    for idx, (marker, follow) in enumerate(sup_marks):
        m = re.match(
            rf"^\(?(\d{{1,3}}[A-Z]?|[a-z]{{1,2}}\d{{0,2}})\)\s*{re.escape(marker)}(.*)$", folded
        )
        if m is None or _squash(m.group(2))[:_SUP_MATCH_CHARS] != _squash(follow)[:_SUP_MATCH_CHARS]:
            continue
        del sup_marks[idx]
        return marker, m.group(1), normalize(m.group(2))
    return None


def extract_amended_units(
    body_lines: list[str],
    footnotes: dict[str, Footnote],
    sup_marks: list[tuple[str, str]] | None = None,
) -> list[AmendedUnit]:
    """Attach each inline marker to its footnote.

    With `sup_marks` (from the page HTML) a line is marked **only** if a
    superscript says so. Without them the marker is inferred from the Markdown
    shape by `_INLINE_RE`, which cannot tell `28)` (footnote 2, sub-section 8)
    from sub-section 28; the provision records which source was used.

    A marker whose number has no legend entry is **dropped**, not guessed: an
    amendment we cannot describe is not evidence. Under-reporting is safe here;
    inventing an operation is not.
    """
    remaining = list(sup_marks) if sup_marks is not None else None
    units: list[AmendedUnit] = []
    parent = ""
    for raw in body_lines:
        line = raw.strip()
        if not line:
            continue
        plain = _PLAIN_NUMBERED_RE.match(line)
        if remaining is not None:
            hit = _unit_from_sup(line, remaining)
            if hit is None:
                if plain:
                    parent = plain.group(1)
                continue
            marker, unit, text = hit
        else:
            m = _INLINE_RE.match(_fold_digits(line))
            if not m:
                if plain:
                    parent = plain.group(1)
                continue
            # Groups 1-2 are the bracketed form `1(d1)`; groups 3-4 the
            # unbracketed form `11)` / `2c)`. Exactly one pair is populated.
            marker, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            text = normalize(line[m.end():])
        note = footnotes.get(marker)
        if note is None:
            if plain:
                parent = plain.group(1)
            continue
        if note.operation is Operation.REPEAL and not _ELIDED_UNIT_RE.match(text):
            # Words omitted INSIDE a unit that survives: Bonus Act §8 prints
            # `a) <sup>1</sup>…… theft of the enterprise's property ...` under
            # "Omitted by the Fourth Amendment". Recording "clause (a) repealed"
            # would make every item about (a) say it no longer exists. The
            # marker stays unattached and the validator reports it.
            continue
        unit = normalize(unit)
        units.append(
            AmendedUnit(
                unit=unit,
                operation=note.operation,
                amendment_ordinal=note.amendment_ordinal,
                footnote_marker=marker,
                text=text,
                amendment_event=note.event,
                parent=parent,
            )
        )
        if unit[:1].isdigit():
            parent = unit
    # Qualify a label with its parent ONLY where the label repeats. The
    # "nearest numbered unit above" is a heuristic about structure: it is right
    # for Income Tax §4 (clause c under sub-sections 3 and 4) and wrong for a
    # definitions section, where numbered items nest *under* lettered clauses
    # and a top-level clause `av1` would be reported as `3(av1)`. Applied
    # everywhere it asserted structure the page does not state; applied only to
    # collisions it does the one job it exists for.
    counts: dict[str, int] = {}
    for u in units:
        counts[u.unit] = counts.get(u.unit, 0) + 1
    return [u if counts[u.unit] > 1 else replace(u, parent="") for u in units]


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
