"""Tests for act-slug resolution and the refusal to cache an empty discovery.

Both guard the same failure shape, which this project keeps meeting: a step
that finds nothing, reports success, and writes the nothing down. The site
renames slugs by appending the Gregorian year (`income-tax-act-2058` ->
`income-tax-act-2058-2002`), the requested slug is a prefix of the served one,
and a substring filter therefore keeps the chapter links while silently losing
every provision beneath them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nepversa.harvest import (
    HarvestError,
    _cached_discover,
    _canonical_slug,
    discover_provisions,
)

BASE = "https://nepallaws.com/Laws"


class TestCanonicalSlug:
    def test_exact_slug_is_kept(self):
        asked = f"{BASE}/bonus-act-2030"
        links = {f"{BASE}/bonus-act-2030/section-1"}
        assert _canonical_slug(asked, links) == "bonus-act-2030"

    def test_site_appended_gregorian_year_is_recovered(self):
        """The bug: the served slug is longer than the one we asked for."""
        asked = f"{BASE}/income-tax-act-2058"
        links = {f"{BASE}/income-tax-act-2058-2002/chapter-1-preliminary"}
        assert _canonical_slug(asked, links) == "income-tax-act-2058-2002"

    def test_longest_matching_slug_wins(self):
        asked = f"{BASE}/companies-act-2063"
        links = {
            f"{BASE}/companies-act-2063/x",
            f"{BASE}/companies-act-2063-2006/chapter-8-audit",
        }
        assert _canonical_slug(asked, links) == "companies-act-2063-2006"

    def test_unrelated_act_sharing_a_prefix_word_is_not_adopted(self):
        # "bonus-act-2030" must not absorb "bonus-act-2030x-other".
        asked = f"{BASE}/bonus-act-2030"
        links = {f"{BASE}/bonus-act-2030xother/section-1"}
        assert _canonical_slug(asked, links) == "bonus-act-2030"

    def test_no_links_falls_back_to_the_requested_slug(self):
        assert _canonical_slug(f"{BASE}/some-act-2064", set()) == "some-act-2064"


class TestDiscoveryUsesTheServedSlug:
    def test_provisions_under_a_renamed_slug_are_found(self, monkeypatch):
        """Before the fix this returned zero provisions and looked healthy."""
        real = "income-tax-act-2058-2002"
        index = {f"{BASE}/{real}/chapter-1-preliminary"}
        chapter = {
            f"{BASE}/{real}/chapter-1-preliminary",
            f"{BASE}/{real}/chapter-1-preliminary/section-1",
            f"{BASE}/{real}/chapter-1-preliminary/section-2a",
        }

        def fake_links(url: str):
            return index if url.endswith("income-tax-act-2058") else chapter

        monkeypatch.setattr("nepversa.harvest._links_on", fake_links)
        monkeypatch.setattr("nepversa.harvest.time.sleep", lambda s: None)

        found = discover_provisions(f"{BASE}/income-tax-act-2058")
        assert found == [
            f"{BASE}/{real}/chapter-1-preliminary/section-1",
            f"{BASE}/{real}/chapter-1-preliminary/section-2a",
        ]

    def test_a_prefix_sibling_act_is_not_harvested_into_this_one(self, monkeypatch):
        """`bonus-act-2030` must not pull in `bonus-act-2030-amendment`."""
        index = {
            f"{BASE}/bonus-act-2030/section-1",
            f"{BASE}/bonus-act-2030-amendment/section-9",
        }
        monkeypatch.setattr("nepversa.harvest._links_on", lambda url: index)
        monkeypatch.setattr("nepversa.harvest.time.sleep", lambda s: None)
        found = discover_provisions(f"{BASE}/bonus-act-2030-amendment")
        # The flat-Act shape means this Act's own section-9 is a provision; the
        # point is that the shorter sibling's section-1 is not pulled in with it.
        assert found == [f"{BASE}/bonus-act-2030-amendment/section-9"]
        assert all("/bonus-act-2030/" not in u for u in found)


class TestEmptyDiscoveryIsNeverCached:
    def test_zero_provisions_raises_instead_of_writing_the_cache(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr("nepversa.harvest.discover_provisions", lambda url: [])
        with pytest.raises(HarvestError, match="refusing to cache"):
            _cached_discover(f"{BASE}/ghost-act-2064", tmp_path)
        assert not (tmp_path / "_urls.json").exists()

    def test_a_real_discovery_is_cached(self, tmp_path: Path, monkeypatch):
        urls = [f"{BASE}/demo-act-2064/chapter-1/section-1"]
        monkeypatch.setattr("nepversa.harvest.discover_provisions", lambda url: urls)
        assert _cached_discover(f"{BASE}/demo-act-2064", tmp_path) == urls
        assert json.loads((tmp_path / "_urls.json").read_text(encoding="utf-8")) == urls

    def test_the_cache_is_reused_without_a_second_discovery(
        self, tmp_path: Path, monkeypatch
    ):
        urls = [f"{BASE}/demo-act-2064/chapter-1/section-1"]
        (tmp_path / "_urls.json").write_text(json.dumps(urls), encoding="utf-8")

        def boom(url):
            raise AssertionError("discovery ran despite a populated cache")

        monkeypatch.setattr("nepversa.harvest.discover_provisions", boom)
        assert _cached_discover(f"{BASE}/demo-act-2064", tmp_path) == urls
