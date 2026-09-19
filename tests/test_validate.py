"""Tests for the corpus cross-check.

Each case reconstructs one of the three silent-miss bugs found by hand in the
Banking Offences Act. The validator exists so the next one is found by a script
instead.
"""

from __future__ import annotations

from nepversa.validate import check_row

URL = "https://nepallaws.com/Laws/banking-offence-and-punishment-act-2064/chapter-2-banking-offences/section-5"


def _row(**over) -> dict:
    base = {
        "citation_key": "act:banking-offence-and-punishment-act-2064#5",
        "number": "5",
        "text": "(a) withdraw money in an unauthorised manner from another account,",
        "amended_units": [],
        "footnotes": [],
        "repealed_in_full": False,
        "source_url": URL,
    }
    return {**base, **over}


def test_inline_markers_without_parsed_units_is_reported() -> None:
    """BUG 1 and 2: the exact signature of both vocabulary/regex misses.

    §5 carried `1(b)` and `1(d)` in its text while `amended_units` was empty,
    and nothing in the output disagreed with itself.
    """
    row = _row(text="(a) withdraw money, 1(b) ……… (c) transfer fund, 1(d) ………")
    kinds = [f.kind for f in check_row(row)]
    assert "MARKERS_WITHOUT_UNITS" in kinds


def test_elision_without_a_recorded_repeal_is_reported() -> None:
    """BUG 3: a row of dots is deleted text; something must explain it."""
    row = _row(text="1………………………….")
    kinds = [f.kind for f in check_row(row)]
    assert "ELISION_WITHOUT_REPEAL" in kinds


def test_lettered_section_without_provenance_is_reported() -> None:
    """A section numbered 12A exists only because an amendment inserted it."""
    row = _row(number="12A", citation_key="act:x#12A")
    kinds = [f.kind for f in check_row(row)]
    assert "LETTERED_WITHOUT_PROVENANCE" in kinds


def test_orphan_footnote_is_reported() -> None:
    """A parsed footnote that matched no inline marker attached to nothing."""
    row = _row(
        footnotes=[{"marker": "9", "operation": "repeal", "text": "Taken out."}]
    )
    kinds = [f.kind for f in check_row(row)]
    assert "ORPHAN_FOOTNOTE" in kinds


def test_a_correctly_parsed_provision_is_clean() -> None:
    """No false positives on a well-formed record."""
    row = _row(
        text="(a) ordinary clause, 1(b) inserted clause text here,",
        amended_units=[
            {"unit": "b", "operation": "insert", "amendment_ordinal": 1,
             "footnote_marker": "1", "text": "inserted clause text here,"}
        ],
        footnotes=[{"marker": "1", "operation": "insert", "amendment_ordinal": 1,
                    "text": "Added by the First Amendment."}],
    )
    assert check_row(row) == []


def test_repealed_in_full_is_not_flagged_for_elision() -> None:
    """Once the repeal is recorded, the dots are explained."""
    row = _row(
        text="1………………………….",
        repealed_in_full=True,
        footnotes=[{"marker": "1", "operation": "repeal", "amendment_ordinal": 1,
                    "text": "Taken out by the First Amendment."}],
    )
    kinds = [f.kind for f in check_row(row)]
    assert "ELISION_WITHOUT_REPEAL" not in kinds
