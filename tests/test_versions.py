"""Tests for provision versioning and validity windows.

The property that matters most here is **exactly one version governs any
point**. A point-in-time benchmark whose own corpus is ambiguous at the
amendment boundary would score models on a question with two right answers.
"""

from __future__ import annotations

import pytest

from nepversa.amendments import AmendedUnit, Operation
from nepversa.versions import (
    ProvisionVersion,
    VersionState,
    build_versions,
    version_at,
    versions_for_unit,
)

KEY = "act:banking-offence-and-punishment-act-2064#7"


def _unit(op: Operation, ordinal: int | None = 1, text: str = "Some clause text.") -> AmendedUnit:
    return AmendedUnit(
        unit="d1", operation=op, amendment_ordinal=ordinal,
        footnote_marker="1", text=text,
    )


class TestInsert:
    def test_absent_then_present(self) -> None:
        before, after = versions_for_unit(KEY, _unit(Operation.INSERT))
        assert before.state is VersionState.ABSENT
        assert after.state is VersionState.PRESENT_TEXT_KNOWN
        assert after.text == "Some clause text."

    def test_inserted_text_is_quotable(self) -> None:
        """An INSERT gives us the real post-amendment wording."""
        _, after = versions_for_unit(KEY, _unit(Operation.INSERT))
        assert after.can_be_quoted is True

    def test_absent_version_is_never_quotable(self) -> None:
        before, _ = versions_for_unit(KEY, _unit(Operation.INSERT))
        assert before.can_be_quoted is False


class TestRepeal:
    def test_present_then_absent(self) -> None:
        before, after = versions_for_unit(KEY, _unit(Operation.REPEAL))
        assert before.state is VersionState.PRESENT_TEXT_UNKNOWN
        assert after.state is VersionState.ABSENT

    def test_repealed_wording_is_not_claimed(self) -> None:
        """MUTATION: set the pre-repeal state to PRESENT_TEXT_KNOWN and this fails.

        The consolidated edition does not print repealed text — it prints a row
        of dots. Claiming we hold it would let a benchmark item demand wording
        that exists nowhere in our corpus.
        """
        before, _ = versions_for_unit(KEY, _unit(Operation.REPEAL))
        assert before.text is None
        assert before.can_be_quoted is False


class TestSubstitute:
    def test_superseded_wording_is_not_claimed(self) -> None:
        """MUTATION: mark the pre-substitution version quotable and this fails."""
        before, after = versions_for_unit(KEY, _unit(Operation.SUBSTITUTE))
        assert before.state is VersionState.PRESENT_TEXT_UNKNOWN
        assert before.can_be_quoted is False
        assert after.can_be_quoted is True


class TestValidityWindows:
    def test_exactly_one_version_governs_each_point(self) -> None:
        """The core corpus invariant."""
        versions = build_versions(KEY, [_unit(Operation.SUBSTITUTE, ordinal=2)])
        for point in range(0, 6):
            hits = [v for v in versions if v.governs_at(point)]
            assert len(hits) == 1, f"{len(hits)} versions govern at amendment {point}"

    def test_bounds_are_half_open_at_the_amendment_event(self) -> None:
        """MUTATION: make `governs_at` use `<=` on `to_amendment` and this fails.

        At the amendment ordinal itself, the NEW version governs. A closed
        upper bound makes both versions match at exactly that point — the one
        place a point-in-time question is most likely to be asked.
        """
        before, after = versions_for_unit(KEY, _unit(Operation.INSERT, ordinal=1))
        assert before.governs_at(0) is True
        assert before.governs_at(1) is False
        assert after.governs_at(1) is True

    def test_version_at_picks_the_governing_one(self) -> None:
        versions = build_versions(KEY, [_unit(Operation.INSERT, ordinal=1)])
        assert version_at(versions, "d1", 0).state is VersionState.ABSENT
        assert version_at(versions, "d1", 1).state is VersionState.PRESENT_TEXT_KNOWN

    def test_overlapping_windows_raise_rather_than_pick_one(self) -> None:
        """A corpus defect must surface, not be answered plausibly."""
        overlapping = [
            ProvisionVersion(KEY, "d1", VersionState.PRESENT_TEXT_KNOWN, "a", None, None),
            ProvisionVersion(KEY, "d1", VersionState.PRESENT_TEXT_KNOWN, "b", None, None),
        ]
        with pytest.raises(ValueError, match="overlap"):
            version_at(overlapping, "d1", 1)

    def test_unknown_unit_returns_none(self) -> None:
        versions = build_versions(KEY, [_unit(Operation.INSERT)])
        assert version_at(versions, "zz", 1) is None


class TestDates:
    def test_dates_are_absent_until_independently_verified(self) -> None:
        """A footnote names an ordinal, never a date. Nothing is interpolated.

        The product was once answered as of 2083 for a session pinned to 2078,
        with every downstream check correct about the wrong year.
        """
        for v in versions_for_unit(KEY, _unit(Operation.INSERT)):
            assert v.from_date_bs is None
            assert v.to_date_bs is None

    def test_no_ordinal_and_no_named_event_yields_no_versions(self) -> None:
        """REGRESSION. This test used to assert `before.to_amendment is None and
        after.from_amendment is None` — i.e. that both versions are in force
        from enactment onward. That was the bug, pinned by its own test: v1.0.0
        shipped Foreign Exchange §2(g4) as both absent and present "before any
        amendment". An event we cannot name cannot anchor a question."""
        assert versions_for_unit(KEY, _unit(Operation.INSERT, ordinal=None)) == []

    def test_named_instrument_gives_unit_local_bounds(self) -> None:
        """MUTATION: drop the `n = 1` fallback and both bounds are `None` again."""
        unit = AmendedUnit(
            unit="g4", operation=Operation.INSERT, amendment_ordinal=None,
            footnote_marker="1", text="Some clause text.",
            amendment_event="Financial Act, 2075",
        )
        before, after = versions_for_unit(KEY, unit)
        assert (before.from_amendment, before.to_amendment) == (None, 1)
        assert (after.from_amendment, after.to_amendment) == (1, None)
        assert before.event_label == after.event_label == "Financial Act, 2075"
        assert not before.ordinal_known
        assert version_at([before, after], "g4", 0) is before
        assert version_at([before, after], "g4", 1) is after
