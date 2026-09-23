"""Amendment events named by instrument, unit paths, and benchmark self-consistency.

v1.0.0 shipped contradictory items: Foreign Exchange §2(g4), inserted by "the
Act to Amend Certain Nepal Acts Relating to ...", produced one item saying the
clause was absent "before any amendment" and another quoting its text for the
same point. Each item was well-formed; only the pair was impossible. Every test
here names the mutation that makes it fail.
"""

from __future__ import annotations

import dataclasses

import pytest

from nepversa.amendments import (
    AmendedUnit,
    Operation,
    extract_amended_units,
    parse_footnotes,
)
from nepversa.build_benchmark import ContradictoryGoldError, check_consistency, items_from_row
from nepversa.versions import VersionState

KEY = "act:foreign-exchange-regulation-act-2019#2"


def _row(units: list[AmendedUnit]) -> dict:
    return {
        "citation_key": KEY,
        "source_url": "",
        "repealed_in_full": False,
        "amended_units": [
            {**dataclasses.asdict(u), "operation": u.operation.value} for u in units
        ],
    }


class TestEventLabels:
    @pytest.mark.parametrize(
        ("legend", "event"),
        [
            ("1 Inserted by the Financial Act, 2075.", "Financial Act, 2075"),
            ("1 Inserted by the Financial Act, 2080(2023)", "Financial Act, 2080(2023)"),
            ("1 Amended by the Act to Amend Certain Nepal Acts, 2074.",
             "Act to Amend Certain Nepal Acts, 2074"),
            ("1 Added by the First Amendment.", "First Amendment"),
        ],
    )
    def test_legend_names_its_event(self, legend: str, event: str) -> None:
        notes, _ = parse_footnotes([legend])
        assert notes["1"].event == event

    def test_instrument_named_insert_is_not_contradictory(self) -> None:
        """MUTATION: make `_anchor_phrase` ignore `event_label` and the two
        questions read "before any amendment" / "after the 1th Amendment"."""
        unit = AmendedUnit(
            unit="g4", operation=Operation.INSERT, amendment_ordinal=None,
            footnote_marker="1", text="Import of gold by a licensed dealer.",
            amendment_event="Act to Amend Certain Nepal Acts, 2074",
        )
        items = items_from_row(_row([unit]))
        check_consistency(items)
        by_state = {i.gold_state: i for i in items}
        assert "before the Act to Amend Certain Nepal Acts, 2074" in by_state[VersionState.ABSENT].question
        assert "after the Act to Amend Certain Nepal Acts, 2074" in by_state[VersionState.PRESENT_TEXT_KNOWN].question
        assert all(i.as_of_amendment is None for i in items)
        assert "any amendment" not in " ".join(i.question for i in items)

    def test_substitution_by_instrument_never_quotes_new_text_as_old(self) -> None:
        """FX §10A(1) in v1.0.0 answered "before any amendment" with the
        substituted (post-amendment) text."""
        unit = AmendedUnit(
            unit="1", operation=Operation.SUBSTITUTE, amendment_ordinal=None,
            footnote_marker="1", text="The new wording.",
            amendment_event="Act to Amend Certain Nepal Acts, 2075",
        )
        items = items_from_row(_row([unit]))
        assert len(items) == 1
        assert "after the Act to Amend" in items[0].question


class TestPaperFormulasMatchTheScorer:
    """The Method section's MC and TC equations, checked against the code."""

    def _items(self):
        u = AmendedUnit(unit="g4", operation=Operation.INSERT, amendment_ordinal=1,
                        footnote_marker="1", text="Import of gold by a licensed dealer is permitted.")
        items = items_from_row(_row([u]))
        absent = next(i for i in items if i.gold_state is VersionState.ABSENT)
        present = next(i for i in items if i.gold_state is VersionState.PRESENT_TEXT_KNOWN)
        return absent, present

    def test_tc_is_one_whenever_a_version_governs(self) -> None:
        """TC = 1 for g(q) != empty, whatever the answer says."""
        _, present = self._items()
        assert present.score("I cannot answer.")["time_correct"] is True

    def test_tc_is_the_abstention_indicator_when_nothing_governs(self) -> None:
        absent, _ = self._items()
        assert absent.score("It did not exist at that point.")["time_correct"] is True
        assert absent.score(f"{KEY} provides: import of gold ...")["time_correct"] is False

    def test_mc_is_a_product_and_exact_is_case_sensitive(self) -> None:
        """MC = prod over nuggets; mu_exact is n in r without casefold."""
        _, present = self._items()
        exact = next(n.value for n in present.gold_nuggets if n.kind == "exact")
        assert present.score(f"{KEY.upper()} says {exact}")["meaning_correct"] is True
        assert present.score(f"{KEY} says {exact.upper()}")["meaning_correct"] is False
        assert present.score(exact)["meaning_correct"] is False  # citation nugget missing


class TestNoQuotingDots:
    def test_substitution_printed_as_dots_yields_no_quote_item(self) -> None:
        """Income Tax §10 (3): "Amended by the Financial Act, 2075" over `……`.
        MUTATION: drop the `can_be_quoted` check in `generate_point_in_time`."""
        u = AmendedUnit(unit="3", operation=Operation.SUBSTITUTE, amendment_ordinal=None,
                        footnote_marker="1", text="……………………………………",
                        amendment_event="Financial Act, 2075")
        items = items_from_row(_row([u]))
        assert not any(n.kind == "exact" for i in items for n in i.gold_nuggets)


class TestUnitPaths:
    def test_same_clause_letter_under_two_sub_sections_is_two_units(self) -> None:
        """Income Tax §4: a repealed clause `c` under sub-section 3 and another
        under sub-section 4. MUTATION: drop the parent update and both are `c`."""
        body = [
            "3) Notwithstanding anything contained in Sub-section (2),",
            "a) Only the income of any employment.",
            "2c)…………………………",
            "4) Notwithstanding anything contained in Sub-section (2),",
            "a) That person has only income earned from business.",
            "2c)…………………",
        ]
        notes, _ = parse_footnotes(["2 Removed by the Financial Act, 2079."])
        units = extract_amended_units(body, notes)
        assert [u.path for u in units] == ["3(c)", "4(c)"]

    def test_a_unique_label_is_not_given_a_guessed_parent(self) -> None:
        """Income Tax §2 (definitions): numbered items nest UNDER lettered
        clauses, so "nearest numbered unit above" would report top-level clause
        av1 as `3(av1)`. MUTATION: keep the parent for unique labels too."""
        body = [
            "n) “Tax” means the tax chargeable under this Act,",
            "3) The amount payable to the Department in respect of tax,",
            "1av1) “Electronic means” means a computer, fax, email,",
        ]
        notes, _ = parse_footnotes(["1 Inserted by the Financial Act, 2075 (2018)."])
        assert [u.path for u in extract_amended_units(body, notes)] == ["av1"]

    def test_colliding_units_are_refused(self) -> None:
        """MUTATION: remove the duplicate-id check in `check_consistency`."""
        u = AmendedUnit(unit="c", operation=Operation.REPEAL, amendment_ordinal=1,
                        footnote_marker="1", text="………")
        items = items_from_row(_row([u])) + items_from_row(_row([u]))
        with pytest.raises(ContradictoryGoldError, match="duplicate item id"):
            check_consistency(items)


class TestBuildRefusesToWrite:
    def test_contradictory_set_writes_no_file(self, tmp_path, monkeypatch) -> None:
        """MUTATION: remove the `check_consistency` call from `main()`.

        The check existing is not enough; the build has to run it before the
        output file is opened, or a contradictory release is still written."""
        import json

        from nepversa import build_benchmark

        u = AmendedUnit(unit="g4", operation=Operation.INSERT, amendment_ordinal=1,
                        footnote_marker="1", text="Some clause text.")
        good = items_from_row(_row([u]))
        absent = next(i for i in good if i.gold_state is VersionState.ABSENT)
        forged = dataclasses.replace(absent, item_id="forged",
                                     gold_state=VersionState.PRESENT_TEXT_KNOWN)
        monkeypatch.setattr(build_benchmark, "items_from_row", lambda row: [absent, forged])
        src = tmp_path / "in.jsonl"
        src.write_text(json.dumps(_row([u])) + "\n", encoding="utf-8")
        out = tmp_path / "out.jsonl"
        with pytest.raises(ContradictoryGoldError):
            build_benchmark.main([str(src), "--out", str(out)])
        assert not out.exists()


class TestConsistencyGuard:
    def test_same_anchor_with_two_gold_states_is_refused(self) -> None:
        """MUTATION: remove the gold-state comparison and this fails."""
        u = AmendedUnit(unit="g4", operation=Operation.INSERT, amendment_ordinal=1,
                        footnote_marker="1", text="Some clause text.")
        items = items_from_row(_row([u]))
        absent = next(i for i in items if i.gold_state is VersionState.ABSENT)
        forged = dataclasses.replace(absent, item_id="forged", gold_state=VersionState.PRESENT_TEXT_KNOWN)
        with pytest.raises(ContradictoryGoldError, match="both absent and present"):
            check_consistency([absent, forged])
