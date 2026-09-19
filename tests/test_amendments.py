"""Tests for amendment-provenance extraction.

Every safety check here is **mutation-tested**: a comment records what breaks
the code so the test fails. Earlier work found two tests that
passed against a deliberately broken implementation, so "it passes" is not
evidence until removing the guarantee has been shown to fail it.

Nepali fixtures enumerate **inflected forms**, not example sentences. The
project has been broken three times by word-list matching of Nepali; the
`-दैन` rule reappeared four sessions after it was written down.
"""

from __future__ import annotations

import pytest

from nepversa.amendments import (
    Operation,
    UnknownAmendmentVerbError,
    extract_amended_units,
    inserted_by_numbering,
    parse_footnotes,
)
from nepversa.amendments import _INLINE_RE  # private: pinned by a mutation test


class TestFootnoteLegend:
    def test_english_insert_and_substitute(self) -> None:
        notes, lines = parse_footnotes(
            ["1 Added by the First Amendment.", "2 Amended by the First Amendment."]
        )
        assert notes["1"].operation is Operation.INSERT
        assert notes["2"].operation is Operation.SUBSTITUTE
        assert notes["1"].amendment_ordinal == 1
        assert lines == {0, 1}

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("1 पहिलो संशोधनद्वारा थप।", Operation.INSERT),
            ("1 पहिलो संशोधनद्वारा थप गरिएको।", Operation.INSERT),
            ("2 पहिलो संशोधनद्वारा संशोधित।", Operation.SUBSTITUTE),
            ("2 दोस्रो संशोधनद्वारा प्रतिस्थापित।", Operation.SUBSTITUTE),
            ("1 पहिलो संशोधनद्वारा झिकिएको।", Operation.REPEAL),
            ("3 तेस्रो संशोधनद्वारा हटाइएको।", Operation.REPEAL),
        ],
    )
    def test_nepali_operations_by_ending(self, line: str, expected: Operation) -> None:
        """Nepali verbs are matched by ENDING, not as whole words.

        `थप` and `थप गरिएको` are the same operation; a word list matching only
        the bare form passes the first and drops the second. That exact shape
        has broken this project three times.
        """
        notes, _ = parse_footnotes([line])
        assert next(iter(notes.values())).operation is expected

    @pytest.mark.parametrize(
        ("line", "ordinal"),
        [
            ("1 Added by the First Amendment.", 1),
            ("1 Amended by the Second Amendment.", 2),
            ("1 पहिलो संशोधनद्वारा थप।", 1),
            ("1 दोश्रो संशोधनद्वारा संशोधित।", 2),  # spelling variant
            ("1 तेस्रो संशोधनद्वारा थप।", 3),
        ],
    )
    def test_amendment_ordinal(self, line: str, ordinal: int) -> None:
        notes, _ = parse_footnotes([line])
        assert next(iter(notes.values())).amendment_ordinal == ordinal

    def test_devanagari_footnote_marker_is_folded(self) -> None:
        """`२ पहिलो संशोधनद्वारा संशोधित।` keys as "2", matching `२(ङ)`."""
        notes, _ = parse_footnotes(["२ पहिलो संशोधनद्वारा संशोधित।"])
        assert "2" in notes

    def test_numbered_list_item_is_not_a_footnote(self) -> None:
        """MUTATION: drop the `_classify` vocabulary check and this fails.

        Without it every numbered sub-clause becomes a phantom amendment, and
        the corpus fills with operations nobody published.
        """
        notes, lines = parse_footnotes(
            ["1) The Bank shall maintain records of all transactions.",
             "2. A person who contravenes this section commits an offence."]
        )
        assert notes == {}
        assert lines == set()

    @pytest.mark.parametrize(
        "line",
        [
            "1 Taken out by the First Amendment.",
            "1 Omitted by the Second Amendment.",
            "1 Struck out by the First Amendment.",
        ],
    )
    def test_repeal_phrasing_variants(self, line: str) -> None:
        """Published editions vary: "Taken out", not only "Deleted".

        REGRESSION. The first full harvest of the Banking Offences Act read
        2 of 4 amended provisions, because §3 and §5 write
        `Taken out by the First Amendment.` The inline markers `1(b)`, `1(d)`
        were present and correct; only the legend verb was unknown, so the
        provisions entered the corpus looking un-amended.
        """
        notes, _ = parse_footnotes([line])
        assert next(iter(notes.values())).operation is Operation.REPEAL

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("1Amended by the First Amendment.", Operation.SUBSTITUTE),
            ("1 Amended by the First Amendment.", Operation.SUBSTITUTE),
            ("१पहिलो संशोधनद्वारा थप।", Operation.INSERT),
        ],
    )
    def test_marker_separator_is_optional(self, line: str, expected: Operation) -> None:
        """REGRESSION: the space after the footnote number is not guaranteed.

        §3 of the Banking Offences Act prints `1Amended by the First
        Amendment.` with no space; §5 and §7 print `1 Taken out by ...` with
        one. Requiring `\\s+` swallowed §3's legend into the body text and left
        a genuinely amended provision looking original — and it did not even
        raise, because the line never matched the legend shape at all.
        """
        notes, _ = parse_footnotes([line])
        assert next(iter(notes.values())).operation is expected

    def test_unknown_amendment_verb_raises_rather_than_vanishing(self) -> None:
        """MUTATION: swap the raise for `continue` and this fails.

        The defect this guards is not a crash, it is silence: a footnote that
        names an amendment but uses an unknown verb would be dropped, and the
        provision would be indistinguishable from one never amended. Failing
        loudly puts the sentence in the harvest report so the vocabulary is
        extended against real text.
        """
        with pytest.raises(UnknownAmendmentVerbError, match="Reconstituted"):
            parse_footnotes(["1 Reconstituted by the Third Amendment."])

    def test_a_non_amendment_numbered_line_still_does_not_raise(self) -> None:
        """The loud failure must not fire on ordinary numbered prose."""
        notes, _ = parse_footnotes(["1) The Bank shall maintain records."])
        assert notes == {}

    @pytest.mark.parametrize(
        "line",
        [
            "1) This section applies to any amendment of the contract.",
            "2. Amendment of bylaws requires a general meeting.",
            "1) Section 53: Amendment to Procurement Contract",
        ],
    )
    def test_prose_about_amendment_is_not_a_footnote(self, line: str) -> None:
        """MUTATION: widen `_LOOKS_LIKE_AMENDMENT` to the bare word and this fails.

        Statutes contain numbered clauses *about* amendment — the site's own
        table of contents lists "Section 53: Amendment to Procurement
        Contract". Raising on the bare word would reject valid provisions and
        lose real statutory text, trading a silent miss for a loud one.

        Footnote grammar is agentive: "**by** the First Amendment",
        `संशोधनद्वारा`. That is what the matcher keys on.
        """
        notes, _ = parse_footnotes([line])
        assert notes == {}

    def test_ordinal_absent_is_none_not_guessed(self) -> None:
        """An undated/unnumbered amendment must not be assigned an ordinal."""
        notes, _ = parse_footnotes(["1 Added by amendment."])
        assert next(iter(notes.values())).amendment_ordinal is None


class TestInlineMarkers:
    def test_attaches_clause_to_footnote(self) -> None:
        notes, _ = parse_footnotes(
            ["1 Added by the First Amendment.", "2 Amended by the First Amendment."]
        )
        units = extract_amended_units(
            [
                "(d) Avail or provide credit beyond the authority obtained.",
                "1(d1) Avail credit by the Chief Executive Officer.",
                "2(e) Re-avail loans from another Bank.",
            ],
            notes,
        )
        assert [(u.unit, u.operation) for u in units] == [
            ("d1", Operation.INSERT),
            ("e", Operation.SUBSTITUTE),
        ]

    def test_unmarked_clause_is_not_reported(self) -> None:
        """An unamended clause reported as amended is invented provenance."""
        notes, _ = parse_footnotes(["1 Added by the First Amendment."])
        units = extract_amended_units(["(d) An ordinary unamended clause."], notes)
        assert units == []

    @pytest.mark.parametrize("line", ["(d) An ordinary clause.", "(क) साधारण खण्ड ।"])
    def test_inline_regex_itself_requires_a_marker_digit(self, line: str) -> None:
        """MUTATION: weaken `(\\d+)` to `(\\d*)` in `_INLINE_RE` and this fails.

        Isolates the regex, because `test_unmarked_clause_is_not_reported`
        cannot see this mutation on its own: with `\\d*` an unmarked clause
        still matches, with an EMPTY marker, and is then dropped by the
        missing-legend rule further down. Two independent guards were covering
        one input, so the weaker one could rot undetected — exactly the
        "a test that has never failed has not been shown to test anything"
        case in the root CLAUDE.md.
        """
        assert _INLINE_RE.match(line) is None

    def test_numbered_subsection_marker_form(self) -> None:
        """REGRESSION: `11)` is footnote 1 + sub-section 1), not "clause 11".

        §9, §15 and §19 of the Banking Offences Act mark amended *numbered
        sub-sections* this way, while §7 uses the bracketed `1(d1)` form. Only
        handling the bracketed form left three amended provisions with parsed
        footnotes attached to nothing — visible only as ORPHAN_FOOTNOTE
        findings from the validator.
        """
        notes, _ = parse_footnotes(["1 Amended by the First Amendment."])
        units = extract_amended_units(
            ["11) The founder, director or shareholder shall not misuse...",
             "12) If any person commits any act as per clauses (d), (d1)..."],
            notes,
        )
        assert [u.unit for u in units] == ["1", "2"]
        assert all(u.operation is Operation.SUBSTITUTE for u in units)

    def test_cross_reference_is_not_read_as_a_marker(self) -> None:
        """MUTATION: drop `(?<![\\w])` from `_INLINE_RE` and this fails.

        Statutes cross-reference their own clauses constantly — "clauses (d),
        (d1), (d2) of Section 5". Reading one as an amendment marker would
        invent provenance for a clause nobody amended.
        """
        notes, _ = parse_footnotes(["1 Amended by the First Amendment."])
        assert extract_amended_units(
            ["clause (d1) of Section 5 shall apply."], notes
        ) == []

    def test_marker_without_legend_is_dropped_not_guessed(self) -> None:
        """MUTATION: default the operation instead of dropping, and this fails.

        An amendment we cannot describe is not evidence. Under-reporting is
        safe; inventing an operation is not.
        """
        notes, _ = parse_footnotes(["1 Added by the First Amendment."])
        units = extract_amended_units(["7(z) A clause citing a missing footnote."], notes)
        assert units == []

    def test_devanagari_clause_label_and_marker(self) -> None:
        notes, _ = parse_footnotes(["1 पहिलो संशोधनद्वारा थप।"])
        units = extract_amended_units(
            ["1(घ१) बैङ्क वा वित्तीय संस्थाको प्रमुख कार्यकारी अधिकृतले कर्जा लिन,"], notes
        )
        assert len(units) == 1
        assert units[0].operation is Operation.INSERT

    def test_substitute_has_no_recoverable_prior_text(self) -> None:
        """The consolidated edition prints only the amended wording.

        A benchmark item built on a SUBSTITUTE must therefore ask which version
        *governs*, never ask a model to reproduce text we do not hold.
        """
        notes, _ = parse_footnotes(
            ["1 Added by the First Amendment.", "2 Amended by the First Amendment."]
        )
        units = extract_amended_units(["1(a) Inserted.", "2(b) Substituted."], notes)
        by_op = {u.operation: u for u in units}
        assert by_op[Operation.INSERT].text_before_available is True
        assert by_op[Operation.SUBSTITUTE].text_before_available is False


class TestSectionNumbering:
    @pytest.mark.parametrize("number", ["12A", "14B", "19B", "१२क", "१४ख", "१९क"])
    def test_lettered_sections_were_inserted(self, number: str) -> None:
        """A letter suffix means the section was squeezed in by an amendment."""
        assert inserted_by_numbering(number) is True

    @pytest.mark.parametrize("number", ["1", "7", "34", "१", "७", "३४"])
    def test_plain_numbers_were_not(self, number: str) -> None:
        assert inserted_by_numbering(number) is False
