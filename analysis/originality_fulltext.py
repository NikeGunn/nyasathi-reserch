"""Full-text overlap check of the manuscript against every cited work we can fetch.

    python analysis/originality_fulltext.py

Extends `originality_check.py` (abstracts only) to the FULL TEXT of cited papers
that are openly available: arXiv PDFs via export.arxiv.org and ACL Anthology
PDFs. Downloads are cached in `logs/originality_sources/` (git-ignored: the
texts are other authors' copyright and are used here only for comparison).

Reports every run of >= WINDOW identical consecutive words shared between the
rendered manuscript (numbers substituted, as submitted) and a source, excluding
text inside quotation marks or code spans in the manuscript, which is quoted on
purpose. Writes `logs/originality_fulltext_report.md`.

What it cannot do, stated plainly: it does not search the web or the private
databases Turnitin and iThenticate use. A clean result here means no
long verbatim overlap with the works this paper cites, which is where
accidental copying is most likely; it does not certify originality.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "logs" / "originality_sources"
REPORT = ROOT / "logs" / "originality_fulltext_report.md"
WINDOW = 8

ARXIV = [
    "2608.08512", "2608.09393", "2605.23497", "2605.25920", "2606.07523",
    "2609.15999", "2005.11401", "2212.10509", "2305.06983", "2403.14403",
    "2210.03629", "2503.09516", "2410.13013", "2108.11792", "2109.06157",
    "2108.06314", "2106.15110", "2205.11388", "1806.03822", "2308.11462",
    "2408.10343", "2406.17186", "2311.09356", "2411.09607", "2609.16010",
]
ACL = ["2022.aacl-short.34"]


def _fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 10_000:
        return True
    curl = shutil.which("curl")
    if curl is None:
        raise SystemExit("curl not on PATH")
    time.sleep(3.5)  # arXiv asks for >= 3 s between requests
    done = subprocess.run([curl, "-sSL", "--fail", "-A",
                           "NEPVERSA-originality-check/1.0 (+https://github.com/NikeGunn/nyasathi-reserch)",
                           "-o", str(dest), url], capture_output=True, timeout=180)
    return done.returncode == 0 and dest.exists() and dest.stat().st_size > 10_000


def _pdf_text(pdf: Path) -> str:
    import fitz  # PyMuPDF

    with fitz.open(pdf) as doc:
        return "\n".join(page.get_text() for page in doc)


def _words(text: str) -> list[str]:
    text = re.sub(r"-\n", "", text)  # re-join hyphenated line breaks
    return re.findall(r"[a-z0-9]+", text.lower())


def _manuscript() -> str:
    sys.path.insert(0, str(ROOT / "analysis"))
    from render_numbers import render_dir

    out = CACHE / "_rendered"
    files = render_dir(ROOT / "paper" / "apa" / "sections", out)
    text = "\n".join(f.read_text(encoding="utf-8") for f in files)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)      # code blocks
    text = re.sub(r"`[^`]*`", " ", text)                     # code spans
    text = re.sub(r"\"[^\"]{0,400}\"|“[^”]{0,400}”", " ", text)  # quotations
    text = re.sub(r"\$\$.*?\$\$|\$[^$]*\$", " ", text, flags=re.S)  # maths
    text = re.sub(r"\[@[^\]]*\]|@\w+", " ", text)            # citation keys
    return text


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    sources: dict[str, str] = {}
    missing = []
    for aid in ARXIV:
        pdf = CACHE / f"arxiv_{aid}.pdf"
        if _fetch(f"https://export.arxiv.org/pdf/{aid}", pdf):
            sources[f"arXiv:{aid}"] = _pdf_text(pdf)
        else:
            missing.append(f"arXiv:{aid}")
    for aid in ACL:
        pdf = CACHE / f"acl_{aid}.pdf"
        if _fetch(f"https://aclanthology.org/{aid}.pdf", pdf):
            sources[f"ACL:{aid}"] = _pdf_text(pdf)
        else:
            missing.append(f"ACL:{aid}")

    ms = _words(_manuscript())
    ms_grams = {tuple(ms[i:i + WINDOW]): i for i in range(len(ms) - WINDOW + 1)}
    hits: list[tuple[str, str]] = []
    for name, text in sources.items():
        src = _words(text)
        shared = {tuple(src[i:i + WINDOW]) for i in range(len(src) - WINDOW + 1)} & ms_grams.keys()
        # merge overlapping shingles into runs, reported once each
        starts = sorted(ms_grams[g] for g in shared)
        run_start = prev = None
        for s in starts + [None]:
            if s is not None and prev is not None and s <= prev + 1:
                prev = s
                continue
            if run_start is not None:
                hits.append((name, " ".join(ms[run_start:prev + WINDOW])))
            run_start = prev = s

    lines = [
        f"# Full-text originality report ({date.today().isoformat()})",
        "",
        f"Manuscript: {len(ms):,} words (rendered, quotations/code/maths/citation keys excluded).",
        f"Sources compared in full text: {len(sources)}; unavailable: {len(missing)} {missing}.",
        f"Window: {WINDOW} consecutive identical words.",
        "",
        f"**Shared runs found: {len(hits)}**",
        "",
    ]
    lines += [f"- `{name}`: \"{run}\"" for name, run in hits]
    lines += ["", "Not covered: web pages, unpublished work, and the private databases used",
              "by Turnitin/iThenticate. This is a self-check, not a certification."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    for name, run in hits:
        print(f"  {name}: {run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
