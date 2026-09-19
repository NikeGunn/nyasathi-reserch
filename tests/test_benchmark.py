"""Tests for benchmark generation and nugget scoring.

The invariant under test throughout: **no item may require gold the source does
not contain.** A benchmark that asks for superseded wording we never saw would
score every model wrong for a reason that is our fault, not theirs.
"""

from __future__ import annotations

import pytest

from nepversa.amendments import AmendedUnit, Operation
from nepversa.benchmark import (
    Nugget,
    QuestionType,
    generate_for_provision,
    generate_point_in_time,
    generate_supersession,
)
from nepversa.versions import VersionState, build_versions, versions_for_unit

KEY = "act:banking-offence-and-punishment-act-2064#7"
TEXT = "Avail credit or advance facilities by the Chief Executive Officer."


def _unit(op: Operation, ordinal: int | None = 1) -> AmendedUnit:
    return AmendedUnit(
        unit="d1", operation=op, amendment_ordinal=ordinal,
        footnote_marker="1", text=TEXT,
    )


class TestNoUnsupportedGold:
    def test_substitute_yields_no_point_in_time_item_for_old_text(self) -> None:
        """MUTATION: drop the PRESENT_TEXT_UNKNOWN guard and this fails.

        The consolidated edition prints only post-amendment wording. An item
        over the superseded period would demand text that exists nowhere in
        our corpus.
        """
        before, _ = versions_for_unit(KEY, _unit(Operation.SUBSTITUTE))
        assert before.state is VersionState.PRESENT_TEXT_UNKNOWN
        assert generate_point_in_time(before) is None

    def test_repealed_prior_text_yields_no_item(self) -> None:
        before, _ = versions_for_unit(KEY, _unit(Operation.REPEAL))
        assert generate_point_in_time(before) is None

    def test_every_generated_exact_nugget_has_real_text(self) -> None:
        """No item ever carries an empty verbatim nugget."""
        items = generate_for_provision(build_versions(KEY, [_unit(Operation.INSERT)]))
        for item in items:
            for nugget in item.gold_nuggets:
                assert nugget.value.strip(), f"empty nugget in {item.item_id}"


class TestPointInTime:
    def test_absent_period_expects_abstention(self) -> None:
        """Before an INSERT the clause did not exist: the honest answer is 'no'."""
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        item = generate_point_in_time(before)
        assert item is not None
        assert item.question_type is QuestionType.T2_POINT_IN_TIME
        assert item.should_abstain is True
        assert item.gold_state is VersionState.ABSENT

    def test_present_period_expects_the_text(self) -> None:
        _, after = versions_for_unit(KEY, _unit(Operation.INSERT))
        item = generate_point_in_time(after)
        assert item is not None
        assert item.should_abstain is False
        assert any(n.kind == "citation" and n.value == KEY for n in item.gold_nuggets)

    def test_provenance_is_always_recorded(self) -> None:
        items = generate_for_provision(build_versions(KEY, [_unit(Operation.INSERT)]))
        assert items
        for item in items:
            assert item.provenance.strip()
            assert item.status == "unverified"


class TestSupersession:
    def test_repeal_generates_a_t3_item(self) -> None:
        _, after = versions_for_unit(KEY, _unit(Operation.REPEAL))
        item = generate_supersession(after)
        assert item is not None
        assert item.question_type is QuestionType.T3_SUPERSESSION
        assert item.should_abstain is True

    def test_insert_does_not_generate_a_t3_item(self) -> None:
        """MUTATION: drop the `from_amendment is not None` check and this fails.

        The absent period *before* an insertion is not a supersession: nothing
        was superseded, the clause simply had not been written yet.
        """
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        assert generate_supersession(before) is None


class TestNuggetScoring:
    def test_label_nugget_is_case_insensitive(self) -> None:
        assert Nugget("label", "absent").matches("The clause was ABSENT.") is True

    def test_exact_nugget_is_case_sensitive(self) -> None:
        """MUTATION: casefold the `exact` branch and this fails.

        `exact` exists to pin verbatim statutory wording. Case-folding it here
        would make the benchmark's exact-quote check a different normal form
        from the product's character-exact gate — documented as how near-misses
        start passing silently.
        """
        n = Nugget("exact", "Chief Executive Officer")
        assert n.matches("...the Chief Executive Officer...") is True
        assert n.matches("...the chief executive officer...") is False

    def test_scores_are_reported_separately(self) -> None:
        """Meaning and time are never averaged into one number."""
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        item = generate_point_in_time(before)
        assert item is not None
        scored = item.score("That clause did not exist at the time.")
        assert set(scored) == {"meaning_correct", "time_correct"}
        assert scored["time_correct"] is True

    def test_confident_wrong_answer_fails_the_time_score(self) -> None:
        """The failure the benchmark exists to expose.

        A fluent answer quoting a real provision that did not govern then.
        """
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        item = generate_point_in_time(before)
        assert item is not None
        scored = item.score(f"Clause (d1) provided: {TEXT}")
        assert scored["time_correct"] is False

    @pytest.mark.parametrize(
        "answer", ["कुनै आधार भेटिएन", "That provision was not in force then."]
    )
    def test_abstention_recognised_in_both_scripts(self, answer: str) -> None:
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        item = generate_point_in_time(before)
        assert item is not None
        assert item.score(answer)["time_correct"] is True


class TestItemIdentity:
    def test_ids_are_deterministic(self) -> None:
        """Reproducibility: the same corpus must yield the same item ids."""
        a = generate_for_provision(build_versions(KEY, [_unit(Operation.INSERT)]))
        b = generate_for_provision(build_versions(KEY, [_unit(Operation.INSERT)]))
        assert [i.item_id for i in a] == [i.item_id for i in b]

    def test_different_units_get_different_ids(self) -> None:
        u2 = AmendedUnit("d2", Operation.INSERT, 1, "1", TEXT)
        ids = {
            i.item_id
            for i in generate_for_provision(
                build_versions(KEY, [_unit(Operation.INSERT), u2])
            )
        }
        assert len(ids) == 4


class TestWholeSectionRepeal:
    """§4 of the Banking Offences Act: repealed in full, no surviving clauses."""

    ROW = {
        "citation_key": "act:banking-offence-and-punishment-act-2064#4",
        "repealed_in_full": True,
        "footnotes": [
            {"marker": "1", "operation": "repeal", "amendment_ordinal": 1,
             "text": "Taken out by the First Amendment."}
        ],
        "amended_units": [],
    }

    def test_generates_a_t3_item(self) -> None:
        from nepversa.benchmark import whole_section_repeal_item

        item = whole_section_repeal_item(self.ROW)
        assert item is not None
        assert item.question_type is QuestionType.T3_SUPERSESSION
        assert item.should_abstain is True
        assert "Taken out by the First Amendment." in item.provenance

    def test_requires_a_repeal_footnote(self) -> None:
        """MUTATION: return an item without checking for the footnote and this fails.

        An empty page is not evidence of repeal. Only a published REPEAL
        statement is.
        """
        from nepversa.benchmark import whole_section_repeal_item

        assert whole_section_repeal_item({**self.ROW, "footnotes": []}) is None
