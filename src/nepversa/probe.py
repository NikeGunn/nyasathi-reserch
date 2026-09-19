"""Probe an Act's amendment density before paying to harvest it.

    python -m nepversa.probe <act-url> [...] --cache corpus/cache --out results/density.json

A full harvest costs one API call per provision (30-50 for a typical Act). The
quota is finite and was mis-recorded as ~340 when it was 115, so the scope was
planned against a number that did not exist. This module buys the *selection*
decision at the price of the table of contents alone: discovery is two levels
of link-walking (~2-7 calls), and the section numbering it returns already
carries one of the two amendment signals the corpus depends on.

**What a probe can and cannot see.** `configs/acts_scope.yaml` keeps an Act when
it has >= 3 amended units OR >= 1 lettered section. Only the second of those is
visible from a table of contents: a lettered section (12A, 14B) is one that an
amendment *inserted*, and the site records that fact in the section number
itself. Amended *units* live in per-provision footnotes, which a probe never
fetches. So a probe reports one signal of two, and this module says so in its
output rather than letting a `lettered=0` read as `density=0`:

* `lettered >= 1`            -> `KEEP`, decided, no harvest needed to know it.
* `lettered == 0`            -> `UNKNOWN`, never `REJECT`. The footnote signal
  is unread. The Bonus Act 2030 is the standing proof: 1 lettered section and 3
  amended units, of which a probe sees only the first.

Reporting every probed Act including the zeros is the config's rule, and the
reason is reproducibility: a scope narrowed by an unreported filter is a scope
nobody can check. The zeros are also a finding in their own right, because
amendment density is what decides whether a version-aware corpus is buildable
from this source at all.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .harvest import HarvestError, _cached_discover

_LETTERED_RE = re.compile(r"/(?:section|rule|article|dafa)-(\d+)([a-z])(?:-|$)", re.IGNORECASE)
"""A provision slug whose number carries a letter suffix: `section-12a`.

Nepali consolidated Acts number an amendment-inserted section by suffixing a
letter to the section it follows (12 -> 12A -> 12B), mirroring the Devanagari
`१२क`. The letter is therefore provenance, not decoration: it states that the
section did not exist when the Act was enacted.
"""

_NUMBERED_RE = re.compile(r"/(?:section|rule|article|dafa)-(\d+)", re.IGNORECASE)


@dataclass(slots=True)
class ProbeResult:
    """One Act's probe. Carries its own verdict and the reason for it."""

    act_slug: str
    act_url: str
    discovered: int
    lettered: int
    lettered_sections: list[str]
    verdict: str
    reason: str
    probed_at: str
    error: str = ""

    def line(self) -> str:
        if self.error:
            return f"[{self.act_slug}] ERROR {self.error}"
        shown = ", ".join(self.lettered_sections[:8])
        if len(self.lettered_sections) > 8:
            shown += f", +{len(self.lettered_sections) - 8} more"
        return (
            f"[{self.act_slug}] provisions={self.discovered} "
            f"lettered={self.lettered} -> {self.verdict}"
            + (f"  ({shown})" if shown else "")
        )


def _lettered_sections(urls: list[str]) -> list[str]:
    """Amendment-inserted sections, by numbering, deduplicated and ordered.

    Ordered by (number, letter) rather than by string, so 9A sorts before 12A
    instead of after it.
    """
    found: dict[str, tuple[int, str]] = {}
    for url in urls:
        m = _LETTERED_RE.search(url)
        if m:
            found[f"{m.group(1)}{m.group(2).upper()}"] = (int(m.group(1)), m.group(2).lower())
    return sorted(found, key=lambda k: found[k])


def probe_act(act_url: str, cache_dir: Path | None = None) -> ProbeResult:
    """Probe one Act. Never raises: a transport failure is a reported outcome.

    A probe that crashes mid-sweep loses the Acts already probed, and the quota
    spent on them is not refunded. A failure is recorded with `verdict=ERROR`
    and an empty count, which is deliberately not the same value as a real zero.
    """
    act_slug = act_url.rstrip("/").split("/Laws/")[-1].split("/")[0]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    act_cache = (cache_dir / act_slug) if cache_dir else None
    try:
        urls = _cached_discover(act_url, act_cache)
    except HarvestError as exc:
        return ProbeResult(
            act_slug=act_slug, act_url=act_url, discovered=0, lettered=0,
            lettered_sections=[], verdict="ERROR",
            reason="discovery failed; this is not a density of zero",
            probed_at=now, error=str(exc)[:300],
        )

    provisions = [u for u in urls if _NUMBERED_RE.search(u)]
    lettered = _lettered_sections(urls)

    if not urls:
        verdict = "ERROR"
        reason = "discovery returned no URLs; a short list is not a short Act"
    elif lettered:
        verdict = "KEEP"
        reason = (
            f"{len(lettered)} amendment-inserted section(s) by numbering; "
            "meets the acts_scope.yaml rule (>= 1 lettered section)"
        )
    else:
        verdict = "UNKNOWN"
        reason = (
            "no lettered sections; the footnote signal (amended units) is not "
            "visible from the table of contents, so density is unread, not zero"
        )

    return ProbeResult(
        act_slug=act_slug, act_url=act_url, discovered=len(provisions),
        lettered=len(lettered), lettered_sections=lettered,
        verdict=verdict, reason=reason, probed_at=now,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Probe Acts for amendment density")
    ap.add_argument("act_urls", nargs="+")
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    results = [probe_act(u, args.cache) for u in args.act_urls]
    for r in results:
        print(r.line())

    keep = [r for r in results if r.verdict == "KEEP"]
    unknown = [r for r in results if r.verdict == "UNKNOWN"]
    errors = [r for r in results if r.verdict == "ERROR"]
    print(
        f"\nprobed={len(results)} keep={len(keep)} unknown={len(unknown)} "
        f"error={len(errors)}"
    )
    print("every probed Act is listed above, including the zeros "
          "(configs/acts_scope.yaml selection_rule)")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps([asdict(r) for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
