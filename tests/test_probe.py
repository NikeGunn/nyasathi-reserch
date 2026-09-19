"""Tests for the amendment-density probe.

The probe exists to spend API quota on a *decision*, so the thing worth testing
is not that it counts, but that it never reports an unread signal as a measured
zero. `UNKNOWN` and `REJECT` are different claims about the world, and a probe
that collapses them would silently narrow the corpus scope.
"""

from __future__ import annotations

import pytest

from nepversa.probe import ProbeResult, _lettered_sections, probe_act

ACT = "https://nepallaws.com/Laws/demo-act-2064"


def _urls(*tails: str) -> list[str]:
    return [f"{ACT}/chapter-1/{t}" for t in tails]


class TestLetteredSections:
    def test_plain_sections_are_not_lettered(self):
        assert _lettered_sections(_urls("section-1", "section-2", "section-12")) == []

    def test_letter_suffix_is_amendment_provenance(self):
        assert _lettered_sections(_urls("section-12a", "section-14b")) == ["12A", "14B"]

    def test_numeric_order_not_string_order(self):
        # "12A" < "9A" as strings; as sections, 9A comes first.
        assert _lettered_sections(_urls("section-12a", "section-9a")) == ["9A", "12A"]

    def test_duplicates_collapse(self):
        # The same section reachable from two chapter pages is one section.
        dup = _urls("section-12a") + [f"{ACT}/chapter-2/section-12a"]
        assert _lettered_sections(dup) == ["12A"]

    def test_multiple_letters_on_one_number(self):
        assert _lettered_sections(_urls("section-14a", "section-14b")) == ["14A", "14B"]

    @pytest.mark.parametrize("kind", ["section", "rule", "article", "dafa"])
    def test_every_provision_word_the_site_uses(self, kind):
        assert _lettered_sections(_urls(f"{kind}-3a")) == ["3A"]

    def test_case_is_normalised_upward(self):
        assert _lettered_sections(_urls("SECTION-5A")) == ["5A"]

    def test_act_slug_digits_are_not_mistaken_for_a_section(self):
        # The Act's own year (2064) must not read as section 2064.
        assert _lettered_sections([ACT]) == []


class TestVerdict:
    def test_lettered_section_decides_keep_without_a_harvest(self, monkeypatch):
        monkeypatch.setattr(
            "nepversa.probe._cached_discover",
            lambda url, cache: _urls("section-1", "section-12a"),
        )
        r = probe_act(ACT)
        assert r.verdict == "KEEP"
        assert r.lettered_sections == ["12A"]

    def test_no_lettered_section_is_unknown_never_reject(self, monkeypatch):
        """The footnote signal is unfetched, so density is unread, not zero.

        Mutating this to REJECT would drop the Bonus Act 2030, which has one
        lettered section and three amended units that only a harvest reveals.
        """
        monkeypatch.setattr(
            "nepversa.probe._cached_discover",
            lambda url, cache: _urls("section-1", "section-2"),
        )
        r = probe_act(ACT)
        assert r.verdict == "UNKNOWN"
        assert r.verdict != "REJECT"
        assert "not zero" in r.reason

    def test_transport_failure_is_not_a_density_of_zero(self, monkeypatch):
        from nepversa.harvest import HarvestError

        def boom(url, cache):
            raise HarvestError("firecrawl exit 1: rate limited")

        monkeypatch.setattr("nepversa.probe._cached_discover", boom)
        r = probe_act(ACT)
        assert r.verdict == "ERROR"
        assert r.discovered == 0
        assert "rate limited" in r.error
        assert "not a density of zero" in r.reason

    def test_empty_discovery_is_an_error_not_an_empty_act(self, monkeypatch):
        monkeypatch.setattr("nepversa.probe._cached_discover", lambda url, cache: [])
        r = probe_act(ACT)
        assert r.verdict == "ERROR"
        assert "not a short Act" in r.reason

    def test_discovered_counts_provisions_only(self, monkeypatch):
        # A chapter index sits at the same depth as a section but names no number.
        monkeypatch.setattr(
            "nepversa.probe._cached_discover",
            lambda url, cache: _urls("section-1", "section-2") + [f"{ACT}/chapter-1"],
        )
        assert probe_act(ACT).discovered == 2


class TestReportLine:
    def test_line_states_the_verdict(self):
        r = ProbeResult(
            act_slug="demo", act_url=ACT, discovered=34, lettered=2,
            lettered_sections=["12A", "14B"], verdict="KEEP", reason="",
            probed_at="2026-09-19T00:00:00+00:00",
        )
        line = r.line()
        assert "provisions=34" in line and "lettered=2" in line and "KEEP" in line

    def test_long_lists_are_truncated_with_a_count(self):
        many = [f"{n}A" for n in range(1, 13)]
        r = ProbeResult(
            act_slug="demo", act_url=ACT, discovered=50, lettered=len(many),
            lettered_sections=many, verdict="KEEP", reason="",
            probed_at="2026-09-19T00:00:00+00:00",
        )
        assert "+4 more" in r.line()

    def test_error_line_shows_the_error(self):
        r = ProbeResult(
            act_slug="demo", act_url=ACT, discovered=0, lettered=0,
            lettered_sections=[], verdict="ERROR", reason="",
            probed_at="2026-09-19T00:00:00+00:00", error="timeout",
        )
        assert "ERROR" in r.line() and "timeout" in r.line()
