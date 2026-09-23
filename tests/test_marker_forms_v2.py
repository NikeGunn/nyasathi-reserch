"""Marker and legend forms met when the corpus grew from three Acts to five.

Every case here was a **silent miss** on real pages of the Companies Act 2063
or the Income Tax Act 2058: the provision parsed cleanly and read as never
amended. Each test names the mutation that makes it fail; each was run against
the code before the fix and failed there.

Fixtures are cut from the scraped pages, shortened, with the marker lines kept
exactly as printed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nepversa.amendments import (
    Operation,
    UnknownAmendmentVerbError,
    extract_amended_units,
    parse_footnotes,
    sup_markers,
)
from nepversa.harvest import HarvestError, _cached_discover
from nepversa.provision import parse_provision

URL = "https://nepallaws.com/Laws/companies-act-2063-2006/chapter-2/section-13"


class TestEndOfProvisionMarker:
    UNTAGGED = """
# Section 91 : Tax withholding certificate

Estimated reading: 1 minute
120 views

1) A withholding agent shall provide a certificate to the withholdee.

[Share this Law](https://nepallaws.com/Laws/x/#)

Ask NepalLaws AI
"""

    def test_a_page_without_a_tag_list_ends_at_share_this_law(self) -> None:
        """MUTATION: drop `_SHARE_RE` from `_END_MARKERS` and this fails.

        Rejected 96 of 96 pages across two Acts before the fix.
        """
        p = parse_provision(self.UNTAGGED, URL)
        assert p.number == "91"
        assert "Ask NepalLaws AI" not in p.text
        assert p.text.endswith("to the withholdee.")


class TestInlineMarkerForms:
    def test_bracketed_marker_with_a_space(self) -> None:
        """MUTATION: remove `\\s?` from the bracketed alternative and this fails.

        Companies Act §13 prints `1 (b) ………` — six units repealed, read as none.
        """
        notes, _ = parse_footnotes(["1 Omitted by the First Amendment."])
        units = extract_amended_units(["1 (b) ………………….", "1 (4) ………"], notes)
        assert [u.unit for u in units] == ["b", "4"]

    @pytest.mark.parametrize(
        ("line", "marker", "unit"),
        [
            ("2c)…………………………", "2", "c"),
            ("1h1) “Windfall gain” means a gain", "1", "h1"),
            ("1av1) “Electronic means” means", "1", "av1"),
            # Not footnote 34: the legend on this page is numbered 1, 2, 3.
            ("34a) Notwithstanding anything contained", "3", "4a"),
        ],
    )
    def test_unbracketed_lettered_unit(self, line: str, marker: str, unit: str) -> None:
        """MUTATION: drop the `[a-z]` alternatives from `_INLINE_RE` and this fails."""
        notes, _ = parse_footnotes([f"{marker} Inserted by the Financial Act, 2075."])
        units = extract_amended_units([line], notes)
        assert [(u.footnote_marker, u.unit) for u in units] == [(marker, unit)]


class TestLegendForms:
    def test_verbless_legend_over_elided_units_is_a_repeal(self) -> None:
        """MUTATION: delete the `_VERBLESS_RE` branch and this fails (no footnote)."""
        lines = ["(a) If the general meeting ...", "1 (b) ………………….",
                 "1 (c)…………………..", "1 The first amendment."]
        notes, legend = parse_footnotes(lines)
        assert notes["1"].operation is Operation.REPEAL
        assert notes["1"].amendment_ordinal == 1
        assert legend == {3}

    def test_verbless_legend_over_live_text_raises(self) -> None:
        """An inserted and a substituted clause look alike; the page cannot say which.

        MUTATION: return REPEAL unconditionally in `_resolve_verbless` and this fails.
        """
        lines = ["1 (b) The company shall notify the Office.", "1 The first amendment."]
        with pytest.raises(UnknownAmendmentVerbError, match="not all elided"):
            parse_footnotes(lines)

    @pytest.mark.parametrize("line", [
        "1 (1A) Notwithstanding anything contained in sub-section (1), ...",
        "1(1A) The documents relating to application shall be valid ...",
        "1u1) “Electronic record” means all the documents submitted ...",
    ])
    def test_verbless_legend_over_an_insertion_label_is_an_insert(self, line: str) -> None:
        """Companies Act §9, the registration section and the definitions, verbatim.

        MUTATION: delete the `_INSERTED_LABEL_RE` branch and all three raise,
        rejecting three real provisions.
        """
        notes, _ = parse_footnotes([line, "1The first amendment."])
        assert notes["1"].operation is Operation.INSERT

    def test_verbless_legend_marking_nothing_raises(self) -> None:
        with pytest.raises(UnknownAmendmentVerbError):
            parse_footnotes(["1 The first amendment."])

    def test_source_misspelling_of_extracted_is_a_repeal(self) -> None:
        """`2 Extreted from the Financial Act, 2080(2023)` — verbatim from Income Tax §4."""
        notes, _ = parse_footnotes(["2 Extreted from the Financial Act, 2080(2023)"])
        assert notes["2"].operation is Operation.REPEAL
        assert notes["2"].amendment_ordinal is None
        assert "Financial Act, 2080" in notes["2"].text

    def test_unknown_verb_naming_an_amending_act_raises(self) -> None:
        """MUTATION: drop the instrument alternative from `_LOOKS_LIKE_AMENDMENT`.

        Before it, a legend citing an Act instead of "the N-th Amendment" and
        using an unknown verb was skipped as an ordinary list item.
        """
        with pytest.raises(UnknownAmendmentVerbError, match="Reworded"):
            parse_footnotes(["3 Reworded by the Financial Act, 2080(2023)"])

    def test_body_prose_citing_an_act_mid_sentence_does_not_raise(self) -> None:
        notes, _ = parse_footnotes(
            ["5) A company registered by the Companies Act, 2063 shall file returns."]
        )
        assert notes == {}


class TestLegendIsTheTrailingBlock:
    PAGE = """
# Section 22 : Amendment of prospectus

Estimated reading: 1 minute
120 views

1) If any amendment is made to the memorandum, the particulars removed shall be notified.

2) The Office shall register the amended prospectus.

- Tagged:
"""

    def test_a_body_line_containing_a_verb_is_not_a_footnote(self) -> None:
        """Twelve Companies Act provisions lost a sub-section this way: the line
        was read as a legend ("removed") and then deleted from the text.
        MUTATION: accept legend-shaped lines anywhere (`continue` for `break`)."""
        p = parse_provision(self.PAGE, URL)
        assert p.footnotes == {}
        assert "particulars removed shall be notified" in p.text


    def test_a_legend_shaped_sentence_mid_body_is_still_body(self) -> None:
        """Discriminates the trailing-block rule from the grammar rule: this
        sentence opens like a legend ("Removed by the ... Act") but body text
        follows it. MUTATION: accept legend lines anywhere, and it is eaten."""
        page = self.PAGE.replace(
            "1) If any amendment",
            "1) Removed by the Registrar under this Act, a company shall cease to exist.\n\n"
            "3) If any amendment",
        )
        p = parse_provision(page, URL)
        assert p.footnotes == {}
        assert "Removed by the Registrar under this Act" in p.text


class TestLabelBeforeMarker:
    def test_repealed_subsection_printed_label_first(self) -> None:
        """Bonus Act §5: `4) <sup>1</sup>……` under "Omitted by the Fourth
        Amendment". MUTATION: delete the label-first loop and (4) is missed."""
        html = "<p>3C) Except for the matters</p><p>4) <sup>1</sup>&#8230;&#8230;&#8230;</p>"
        notes, _ = parse_footnotes(["4) 1……………….", "1 Omitted by the Fourth Amendment."])
        units = extract_amended_units(
            ["3C) Except for the matters", "4) 1………………."], notes, sup_markers(html)
        )
        assert [(u.unit, u.operation) for u in units] == [("4", Operation.REPEAL)]


    def test_words_omitted_inside_a_surviving_clause_are_not_a_repeal(self) -> None:
        """Bonus Act §8 (a): the clause survives with words removed.
        MUTATION: drop the elided-text requirement for REPEAL units."""
        html = "<p>a) <sup>1</sup>&#8230;&#8230; theft of the enterprise&#8217;s property</p>"
        notes, _ = parse_footnotes(["1 Omitted by the Fourth Amendment."])
        units = extract_amended_units(
            ["a) 1…… theft of the enterprise’s property"], notes, sup_markers(html)
        )
        assert units == []


class TestSuperscriptMarkers:
    def test_elision_runs_of_different_length_still_align(self) -> None:
        """Companies §13: HTML `(5)&#8230;x6` vs Markdown `(5)………..`.
        MUTATION: compare raw prefixes (drop `_squash`) and (5) is lost."""
        # Long enough that a fixed 60-char capture window cuts an entity in half.
        html = "<p><sup>1 </sup>(5)" + "&#8230;" * 12 + "</p>"
        notes, _ = parse_footnotes(["1 The first amendment."] and ["1 (5)……….."] + ["1 The first amendment."])
        units = extract_amended_units(["1 (5)……….."], notes, sup_markers(html))
        assert [u.unit for u in units] == ["5"]

    # Income Tax §88, shape preserved: sub-section 10) is plain; 28) is
    # footnote 2 + sub-section 8); 39A) is footnote 3 + sub-section 9A).
    HTML = (
        "<p>9) In the payment of the interest</p>"
        "<p><sup>2</sup>8) &#8230;&#8230;&#8230;</p>"
        "<p><sup>3</sup>9A) At the rate of five percent</p>"
        "<p>10) Tax shall not be deducted</p>"
        "<p><sup>2 Removed by the Financial Act, 2078.</sup></p>"
    )
    MARKDOWN = [
        "9) In the payment of the interest",
        "28) ………",
        "39A) At the rate of five percent",
        "10) Tax shall not be deducted",
    ]
    LEGEND = ["1 Removed by the Financial Act, 2077.",
              "2 Removed by the Financial Act, 2078.",
              "3 Inserted by the Financial Act, 2080."]

    def test_sup_markers_skip_legend_superscripts(self) -> None:
        assert [m for m, _ in sup_markers(self.HTML)] == ["2", "3"]

    def test_html_markers_do_not_invent_sub_section_zero(self) -> None:
        """MUTATION: ignore `sup_marks` (fall back to Markdown) and this fails.

        The Markdown shape reads `10)` as footnote 1 + sub-section `0)`, which
        does not exist, and misses nothing it should catch only by luck.
        """
        notes, _ = parse_footnotes(self.LEGEND)
        units = extract_amended_units(self.MARKDOWN, notes, sup_markers(self.HTML))
        assert [(u.footnote_marker, u.unit, u.operation) for u in units] == [
            ("2", "8", Operation.REPEAL),
            ("3", "9A", Operation.INSERT),
        ]

    def test_markdown_inference_alone_gets_this_wrong(self) -> None:
        """Pins WHY the HTML is fetched: without it `10)` becomes footnote 1, unit 0.

        Uses an INSERT legend for footnote 1: under a REPEAL legend the invented
        unit is now also caught by the partial-repeal guard (its text is not an
        elision run), which would hide the Markdown flaw this test pins."""
        legend = ["1 Inserted by the Financial Act, 2077."] + self.LEGEND[1:]
        notes, _ = parse_footnotes(legend)
        units = extract_amended_units(self.MARKDOWN, notes)
        assert ("1", "0") in [(u.footnote_marker, u.unit) for u in units]

    def test_provision_records_its_marker_source(self) -> None:
        md = TestEndOfProvisionMarker.UNTAGGED
        assert parse_provision(md, URL).marker_source == "markdown"
        assert parse_provision(md, URL, html="<p>x</p>").marker_source == "html"


class TestCachedDiscoveryIndex:
    def test_an_empty_cached_index_is_refused_on_read(self, tmp_path: Path) -> None:
        """MUTATION: remove the empty check on the read path and this fails.

        The Bonus Act's `_urls.json` was `[]`, written before the write-side
        guard existed; a re-harvest would have replaced 29 rows with none.
        """
        (tmp_path / "_urls.json").write_text(json.dumps([]), encoding="utf-8")
        with pytest.raises(HarvestError, match="is empty"):
            _cached_discover("https://nepallaws.com/Laws/bonus-act-2030", tmp_path)
