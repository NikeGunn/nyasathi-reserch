"""Harvest one Act from nepallaws.com into provision records.

Two steps, one scrape each:

1. **Discover** — scrape the act index with `--format links` and keep the
   provision URLs. The act's own table of contents is authoritative;
   `firecrawl map` returned 20 of 34 sections for one act and 0 for another,
   so it is not used.
2. **Fetch** — scrape each provision and parse it.

Rules this file follows, each paid for elsewhere in the project:

* **Never send Nepali through a shell.** URLs and text are handled in Python
  with explicit UTF-8. A Windows shell mangles Devanagari to `????` and the
  silence that follows reads as a finding (recorded in earlier engineering notes).
* **Pace before the call, not after a 429.** Reacting to a rate limit means the
  request was already refused and the run pays the latency without getting the
  bytes. Every run reports its failure counter; a run with discarded calls is
  not a valid run.
* **Establish which layer refused.** A transport failure that looks like an
  empty corpus has cost this project two wrong conclusions.
* **Record retrieval date per provision.** The site's URL slugs changed between
  2026-09-04 and 2026-09-19 and the old ones now 404, so a URL is not an
  identity and a harvest is not timeless.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .provision import Provision, ProvisionParseError, parse_provision

_FIRECRAWL_TIMEOUT_S = 240

_PACE_S = 7.0
"""Delay between scrapes.

The API meters **requests per minute** and refused at 11 req/min on the first
real run, costing one section of 34. 7s holds the rate under ~8.5/min with
headroom. Paced *before* the call, never as a reaction to a 429: by the time a
429 arrives the request has already been refused, so the run pays the latency
without getting the bytes (earlier engineering notes — the Groq run that spent
147 of 159 calls collecting 429s and still wrote its output).
"""

_RETRY_AFTER_S = 65.0
"""One retry per URL after a rate-limit refusal, past the 1-minute window."""

_RATE_LIMIT_MARKERS = ("rate limit", "429", "too many requests")

_SECTION_SLUG_RE = re.compile(
    r"/(?:section|rule|article|dafa|preamble)[-0-9]", re.IGNORECASE
)
"""A URL segment that names a provision rather than a chapter index.

Used to tell a flat Act's sections from a nested Act's chapter pages, which
sit at the same URL depth.
"""


class HarvestError(RuntimeError):
    """A harvest step failed in a way that must not be read as 'no data'."""


@dataclass(slots=True)
class HarvestReport:
    """What a run actually did. Printed in full; never summarised to a success."""

    act_slug: str
    discovered: int = 0
    fetched: int = 0
    parsed: int = 0
    rejected: int = 0
    transport_failures: int = 0
    from_cache: int = 0
    rejections: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.rejections is None:
            self.rejections = []

    @property
    def is_valid_run(self) -> bool:
        """A run with transport failures is not a valid measurement."""
        return self.transport_failures == 0 and self.discovered > 0

    def summary(self) -> str:
        verdict = "VALID" if self.is_valid_run else "INVALID — do not use"
        return (
            f"[{self.act_slug}] discovered={self.discovered} fetched={self.fetched} "
            f"parsed={self.parsed} rejected={self.rejected} "
            f"transport_failures={self.transport_failures} "
            f"from_cache={self.from_cache}  -> {verdict}"
        )


def _firecrawl_exe() -> str:
    """Resolve the firecrawl launcher.

    On Windows the npm shim is `firecrawl.cmd`, which `CreateProcess` will not
    run under the bare name. Resolving it here — rather than passing
    `shell=True` — keeps the URL out of a shell, which matters because these
    URLs are Nepali-derived and a shell round-trip is how this project has
    twice destroyed Devanagari before the request was sent.
    """
    import shutil

    found = shutil.which("firecrawl") or shutil.which("firecrawl.cmd")
    if not found:
        raise HarvestError(
            "firecrawl CLI not on PATH — install it, or the empty result will "
            "read as 'the site has no provisions'"
        )
    return found


def _firecrawl(url: str, fmt: str, *, main_only: bool = True, _retry: bool = True) -> str:
    """Run one firecrawl scrape, or raise `HarvestError` naming the layer.

    `main_only=False` for link discovery: `--only-main-content` strips the
    navigation tree, and the table of contents *is* navigation. It cut one act
    index from 6,980 bytes to 871 and yielded zero provisions — a silent empty
    result that would read as "this act has no sections".
    """
    cmd = [_firecrawl_exe(), "scrape", url, "--format", fmt]
    if main_only:
        cmd.append("--only-main-content")
    try:
        done = subprocess.run(
            cmd, capture_output=True, timeout=_FIRECRAWL_TIMEOUT_S, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise HarvestError(f"firecrawl timed out after {_FIRECRAWL_TIMEOUT_S}s: {url}") from exc
    out = done.stdout.decode("utf-8", errors="replace")
    if done.returncode != 0:
        err = done.stderr.decode("utf-8", errors="replace")[:300]
        low = (err + out).casefold()
        if any(m in low for m in _RATE_LIMIT_MARKERS) and _retry:
            # Establish WHICH layer refused before concluding anything: this is
            # the quota saying "later", not the site saying "no such page".
            time.sleep(_RETRY_AFTER_S)
            return _firecrawl(url, fmt, main_only=main_only, _retry=False)
        raise HarvestError(f"firecrawl exit {done.returncode} for {url}: {err}")
    if not out.strip():
        raise HarvestError(f"firecrawl returned empty output for {url}")
    return out


def _links_on(url: str) -> set[str]:
    raw = _firecrawl(url, "links", main_only=False)
    return {
        u.rstrip("/")
        for u in re.findall(r"https://nepallaws\.com/Laws/[A-Za-z0-9\-/]+", raw)
    }


def _depth(url: str, act_slug: str) -> int:
    tail = url.rstrip("/").split(f"/Laws/{act_slug}", 1)[-1]
    return len([p for p in tail.split("/") if p])


def _canonical_slug(act_url: str, links: set[str]) -> str:
    """The act slug the *site* uses, which is not always the one we asked for.

    The site appends the Gregorian year to some slugs: a request for
    `income-tax-act-2058` redirects to `income-tax-act-2058-2002`. The
    requested slug is a **prefix** of the real one, so a naive
    `f"/Laws/{slug}" in u` filter keeps the chapter links and the walk looks
    healthy right up until it returns zero provisions - reported, before this
    fix, as a clean `UNKNOWN` density for two Acts.

    So the slug is read back from the links the site actually served. The
    longest slug that the requested one is a prefix of wins; ties and misses
    fall back to the requested slug, which keeps single-edition Acts unchanged.
    """
    asked = act_url.rstrip("/").split("/Laws/")[-1].split("/")[0]
    served = {u.split("/Laws/")[-1].split("/")[0] for u in links if "/Laws/" in u}
    matches = sorted(
        (s for s in served if s == asked or s.startswith(f"{asked}-")),
        key=len,
    )
    return matches[-1] if matches else asked


def discover_provisions(act_url: str) -> list[str]:
    """Provision URLs for one act, via its own table of contents.

    Two levels, because the act index lists only chapters: act -> chapters ->
    provisions. `firecrawl map` is deliberately not used; it returned 20 of 34
    sections for this act and 0 for another, and a short list here is
    indistinguishable from an act that really is short.
    """
    top_links = _links_on(act_url)
    act_slug = _canonical_slug(act_url, top_links)
    top = {u for u in top_links if f"/Laws/{act_slug}/" in u + "/"}

    # Acts come in two shapes. Most nest provisions under chapters
    # (act/chapter-N/section-M, depth 2); older short Acts such as the Bonus
    # Act 2030 list sections directly (act/section-M, depth 1). Assuming the
    # nested shape returns zero provisions for a flat Act — silently, and
    # indistinguishably from an Act with no sections.
    depth1 = {u for u in top if _depth(u, act_slug) == 1}
    provisions = {u for u in top if _depth(u, act_slug) == 2}
    provisions |= {u for u in depth1 if _SECTION_SLUG_RE.search(u)}

    # Anything at depth 1 that is not itself a provision is a chapter index.
    for chapter in sorted(depth1 - provisions):
        time.sleep(_PACE_S)  # pace BEFORE the call
        provisions |= {
            u for u in _links_on(chapter)
            if f"/Laws/{act_slug}" in u and _depth(u, act_slug) == 2
        }

    return sorted(provisions)


def _cache_path(cache_dir: Path, url: str) -> Path:
    import hashlib

    return cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}.md"


def _cached_discover(act_url: str, cache_dir: Path | None) -> list[str]:
    """Discover provision URLs, caching the list.

    The act->chapter->provision link walk costs ~7 API calls per act. Those
    calls are pure waste on a re-parse after a parser fix, and the quota is
    finite. Delete `_urls.json` to force re-discovery when the site changes.
    """
    if cache_dir is None:
        return discover_provisions(act_url)
    index = cache_dir / "_urls.json"
    if index.exists():
        return json.loads(index.read_text(encoding="utf-8"))
    urls = discover_provisions(act_url)
    if not urls:
        # A zero-provision discovery is a failure, not a fact about the Act, and
        # caching it makes the failure permanent and free to repeat. Two Acts
        # were probed as empty this way (a slug the site had renamed) and the
        # wrong answer was written to disk, where a later run would have trusted
        # it without spending a call to notice.
        raise HarvestError(
            f"discovery found no provisions for {act_url}; refusing to cache "
            "an empty result - check the act slug the site actually serves"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps(urls, indent=1), encoding="utf-8")
    return urls


def harvest_act(
    act_url: str,
    out_path: Path,
    *,
    limit: int | None = None,
    cache_dir: Path | None = None,
) -> HarvestReport:
    """Harvest one act to JSONL. Returns a report that states its own validity.

    `cache_dir` stores the raw scraped markdown per URL. A re-parse after a
    parser fix then costs **zero** API calls — which matters: three parser
    bugs in this act each forced a full re-scrape, and the API quota is finite.
    The cache is keyed by URL and never expires on its own; delete it to
    re-fetch.
    """
    act_slug = act_url.rstrip("/").split("/Laws/")[-1].split("/")[0]
    report = HarvestReport(act_slug=act_slug)

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    urls = _cached_discover(act_url, cache_dir)
    report.discovered = len(urls)
    if limit is not None:
        urls = urls[:limit]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for url in urls:
            cached = _cache_path(cache_dir, url) if cache_dir else None
            if cached is not None and cached.exists():
                md = cached.read_text(encoding="utf-8")
                report.from_cache += 1
            else:
                time.sleep(_PACE_S)  # pace BEFORE the call, not after a 429
                try:
                    md = _firecrawl(url, "markdown")
                except HarvestError as exc:
                    report.transport_failures += 1
                    report.rejections.append(f"TRANSPORT {url}: {exc}")
                    continue
                if cached is not None:
                    cached.write_text(md, encoding="utf-8")
            report.fetched += 1
            try:
                prov = parse_provision(
                    md, url, retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
                )
            except ProvisionParseError as exc:
                report.rejected += 1
                report.rejections.append(f"PARSE {url}: {exc}")
                continue
            fh.write(json.dumps(_to_row(prov), ensure_ascii=False) + "\n")
            report.parsed += 1
    return report


def _to_row(p: Provision) -> dict:
    """JSONL row. Amendment provenance is stored alongside the text, never merged into it."""
    return {
        "citation_key": p.citation_key,
        "act_slug": p.act_slug,
        "chapter_slug": p.chapter_slug,
        "number": p.number,
        "heading": p.heading,
        "text": p.text,
        "language": p.language,
        "source_url": p.source_url,
        "retrieved_at": p.retrieved_at,
        "sha256": p.sha256,
        "inserted_by_amendment_numbering": p.was_inserted_by_amendment,
        "repealed_in_full": p.repealed_in_full,
        "footnotes": [asdict(f) | {"operation": f.operation.value} for f in p.footnotes.values()],
        "amended_units": [
            asdict(u) | {"operation": u.operation.value, "text_before_available": u.text_before_available}
            for u in p.amended_units
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Harvest one Act from nepallaws.com")
    ap.add_argument("act_url")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="directory for raw scraped markdown; re-parsing costs no API calls",
    )
    args = ap.parse_args(argv)

    report = harvest_act(
        args.act_url, args.out, limit=args.limit, cache_dir=args.cache
    )
    print(report.summary())
    for line in report.rejections:
        print("   ", line)
    return 0 if report.is_valid_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
