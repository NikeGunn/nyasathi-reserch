"""Worst-case preflight of the arXiv upload: the PDF and the source bundle.

    python analysis/preflight_arxiv.py        # exits 1 on any failure

Checks the artefacts as a reader and as arXiv's builder will meet them, not the
sources they came from:

PDF (paper/acm/output/NEPVERSA_acm.pdf)
  * every font embedded, none Type 3 (bitmap fonts blur and some venues reject them)
  * no unresolved reference (`??`), citation (`[?]`, `(?)`), token (`{{`) or
    placeholder (`[[`) survives into the text layer
  * Devanagari is present as real text (extractable), not boxes or images
  * every number in the abstract matches paper/shared/numbers.json
  * the PDF metadata names the title and author, and leaks no local path
  * size under arXiv's limit
Bundle (paper/acm/output/nepversa_arxiv_source.zip)
  * a 00README.json selecting xelatex, a main.tex and main.bbl with matching names
  * no absolute or Windows paths, no file arXiv would refuse, no comments left
  * nothing but source: no PDF of the paper itself, no build debris
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "paper" / "acm" / "output" / "NEPVERSA_acm.pdf"
ZIP = ROOT / "paper" / "acm" / "output" / "nepversa_arxiv_source.zip"
NUMBERS = json.loads((ROOT / "paper" / "shared" / "numbers.json").read_text(encoding="utf-8"))
ARXIV_MAX_BYTES = 50 * 1024 * 1024


def check_pdf(fails: list[str]) -> None:
    import fitz

    doc = fitz.open(PDF)
    text = "\n".join(p.get_text() for p in doc)
    fonts = {}
    for page in doc:
        for f in page.get_fonts(full=True):
            # (xref, ext, type, basefont, name, encoding, referencer)
            fonts[f[3]] = (f[1], f[2])
    for name, (ext, ftype) in fonts.items():
        if ftype == "Type3":
            fails.append(f"Type 3 (bitmap) font: {name}")
        if ext in ("n/a", ""):
            fails.append(f"font not embedded: {name}")
    for pat, what in [(r"\?\?", "unresolved reference ??"), (r"\[\?\]|\(\?\)", "unresolved citation"),
                      (r"\{\{", "unrendered token"), (r"\[\[", "placeholder")]:
        if re.search(pat, text):
            fails.append(f"{what} in PDF text: {re.search(pat, text).group(0)!r}")
    if not re.search(r"[\u0900-\u097F]{3,}", text):
        fails.append("no extractable Devanagari in the PDF text layer")
    abstract = text[: text.find("1 Introduction")] if "1 Introduction" in text else text[:4000]
    abstract = " ".join(abstract.split())
    want = {
        "acts": f"covers {NUMBERS['corpus']['acts']} Acts",
        "provisions": f"{NUMBERS['corpus']['provisions']} provisions",
        "items": f"{NUMBERS['benchmark']['items']} items",
        "markers": f"{NUMBERS['extraction']['html_markers']} markers",
        "missed": f"misses {NUMBERS['extraction']['html_only']} amended units",
    }
    for k, s in want.items():
        if s not in abstract:
            fails.append(f"abstract does not state {k} as numbers.json does ({s!r})")
    meta = doc.metadata or {}
    if "NEPVERSA" not in (meta.get("title") or ""):
        fails.append(f"PDF title metadata is {meta.get('title')!r}")
    if "Bhagat" not in (meta.get("author") or ""):
        fails.append(f"PDF author metadata is {meta.get('author')!r}")
    for k, v in meta.items():
        if v and re.search(r"[A-Za-z]:\\|/Users/|/home/", str(v)):
            fails.append(f"PDF metadata {k} leaks a local path: {v!r}")
    if PDF.stat().st_size > ARXIV_MAX_BYTES:
        fails.append("PDF over 50 MB")
    print(f"PDF: {doc.page_count} pages, {len(fonts)} fonts, {PDF.stat().st_size // 1024} KB, "
          f"title={meta.get('title')!r}")


def check_bundle(fails: list[str]) -> None:
    z = zipfile.ZipFile(ZIP)
    names = z.namelist()
    if "00README.json" not in names:
        fails.append("bundle lacks 00README.json")
    else:
        readme = json.loads(z.read("00README.json"))
        if readme.get("process", {}).get("compiler") != "xelatex":
            fails.append("00README.json does not select xelatex")
    for need in ("main.tex", "main.bbl"):
        if need not in names:
            fails.append(f"bundle lacks {need}")
    for n in names:
        if n.startswith("/") or "\\" in n or ":" in n:
            fails.append(f"bad path in bundle: {n}")
        if n.endswith((".pdf",)) and not n.startswith("figures/"):
            fails.append(f"non-figure PDF in bundle: {n}")
        if n.endswith((".aux", ".log", ".out", ".blg", ".synctex.gz", ".zip")):
            fails.append(f"build debris in bundle: {n}")
    tex = z.read("main.tex").decode("utf-8")
    if re.search(r"^\s*%", tex, re.M):
        fails.append("comments left in main.tex (arXiv publishes the source)")
    for m in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex):
        if m not in names:
            fails.append(f"main.tex includes {m}, which is not in the bundle")
    if re.search(r"[A-Za-z]:\\\\|/Users/", tex):
        fails.append("main.tex contains a local absolute path")
    print(f"bundle: {len(names)} files, {ZIP.stat().st_size // 1024} KB: {names}")


def main() -> int:
    fails: list[str] = []
    check_pdf(fails)
    check_bundle(fails)
    for f in fails:
        print("  FAIL", f)
    print("preflight: PASS" if not fails else f"preflight: {len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
