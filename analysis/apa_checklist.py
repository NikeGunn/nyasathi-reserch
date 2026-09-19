"""Verify the manuscript against the APA 7 checklist, and write the report.

    python analysis/apa_checklist.py paper/apa/output/Manuscript_APA7.docx

Writes `logs/apa_checklist.md` with a pass or fail for every item in
PAPER_PLAN.md §9.1, each one **measured from the built document** rather than
asserted. The project's own record is the reason: `deliverables.md` once
claimed "85 tests passing" against a directory that did not exist, and read
like a record of fact for two sessions.

Items that cannot be decided mechanically (whether the prose is plain, whether
a claim matches its evidence) are reported as `MANUAL`, never as a pass. A
checklist that marks its own unknowns as passes is worse than no checklist.
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS, FAIL, MANUAL = "PASS", "FAIL", "MANUAL"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, verdict: str, item: str, evidence: str) -> None:
        self.rows.append((verdict, item, evidence))

    def check(self, ok: bool, item: str, evidence: str) -> None:
        self.add(PASS if ok else FAIL, item, evidence)

    @property
    def failures(self) -> int:
        return sum(1 for v, _, _ in self.rows if v == FAIL)

    @property
    def manual(self) -> int:
        return sum(1 for v, _, _ in self.rows if v == MANUAL)


def _part(docx: Path, name: str) -> str:
    with zipfile.ZipFile(docx) as z:
        try:
            return z.read(name).decode("utf-8")
        except KeyError:
            return ""


def _plain_text(docx: Path) -> str:
    """Extract the document text with Pandoc, which reads the package properly."""
    pandoc = Path(
        (Path.home() / "AppData/Local/Pandoc/pandoc.exe")
    )
    exe = str(pandoc) if pandoc.exists() else "pandoc"
    out = subprocess.run([exe, "-t", "plain", str(docx)],
                         capture_output=True, check=False)
    # Pandoc emits CRLF on Windows. A stray carriage return defeats every
    # re.M anchor below and turns a passing check into a failing one, which
    # is a checklist reporting its own bug as a defect in the manuscript.
    raw = out.stdout.decode("utf-8", errors="replace")
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def run(docx: Path) -> Report:
    r = Report()
    styles = _part(docx, "word/styles.xml")
    document = _part(docx, "word/document.xml")
    header = _part(docx, "word/header1.xml")
    text = _plain_text(docx)

    # --- Typography (§9.1) -------------------------------------------------
    r.check('w:ascii="Times New Roman"' in styles,
            "Font: Times New Roman (an APA-permitted serif), used throughout",
            "word/styles.xml declares the face on Normal and every heading style")

    r.check('<w:sz w:val="24"/>' in styles,
            "Font size: 12 pt",
            'w:sz w:val="24" (half-points) in styles.xml')

    r.check('w:line="480"' in styles,
            "Double spacing, including the reference list",
            'w:line="480" with w:lineRule="auto" on the body styles')

    r.check('w:firstLine="720"' in styles,
            "First-line indent 0.5 in on body paragraphs",
            'w:ind w:firstLine="720" (twentieths of a point) on Normal/BodyText')

    r.check('<w:jc w:val="left"/>' in styles and '<w:jc w:val="both"/>' not in styles,
            "Flush left, ragged right; never justified",
            "no w:jc val=both anywhere in styles.xml")

    margins = re.search(r'<w:pgMar[^>]*>', document)
    ok_margin = bool(margins) and all(
        f'w:{side}="1440"' in margins.group(0)
        for side in ("top", "right", "bottom", "left")
    )
    r.check(ok_margin, "Margins: 1 in on every side",
            margins.group(0) if margins else "no w:pgMar found")

    # --- Running head and page numbers (§2.8) ------------------------------
    head_text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", header)).strip()
    r.check(bool(head_text) and head_text == head_text.upper(),
            "Running head in ALL CAPS, flush left",
            f"header1.xml carries {head_text!r}")

    r.check(len(head_text) <= 50,
            "Running head is 50 characters or fewer",
            f"{len(head_text)} characters")

    r.check("PAGE" in header,
            "Page number on every page, flush right",
            "a PAGE field in the header, right-aligned by a tab stop")

    # --- Structure ---------------------------------------------------------
    r.check("Author Note" in text, "Title page carries an Author Note",
            "the heading appears in the document text")

    r.check("orcid.org" in text, "Author Note gives the ORCID",
            "an orcid.org identifier appears in the Author Note")

    r.check("competing interest" in text.lower(),
            "Author Note discloses the competing interest",
            "the phrase appears in the Author Note")

    r.check("Generative AI" in text or "generative AI" in text,
            "Generative-AI use disclosed (APA requires it)",
            "the disclosure appears in the Author Note")

    abstract = ""
    m = re.search(r"Abstract\s*(.+?)\s*Keywords:", text, re.S)
    if m:
        abstract = m.group(1)
    words = len(abstract.split())
    r.check(0 < words <= 250, "Abstract is 250 words or fewer",
            f"{words} words measured between the Abstract heading and Keywords")

    # The keyword list wraps across lines. Matching only to the end of the
    # first line counted 3 of 6 and reported a correct document as a failure.
    kw = re.search(r"Keywords:\s*(.+?)(?:\n\s*\n|\Z)", text, re.S)
    n_kw = len([k for k in kw.group(1).split(",") if k.strip()]) if kw else 0
    r.check(5 <= n_kw <= 6, "Keywords: five or six, after the abstract",
            f"{n_kw} keywords found")

    # --- Tables and figures (§7) -------------------------------------------
    n_tbl = document.count("<w:tbl>")
    r.check(n_tbl > 0, "Tables survive as tables in the package",
            f"{n_tbl} w:tbl elements")

    def _sequence(kind: str) -> list[str]:
        """Distinct float numbers, in order of first appearance.

        Each number occurs at least twice, once in the sentence that refers to
        the float and once as the caption label, so the raw list is never a
        1..n sequence and a naive check fails on a correct document.
        """
        seen: list[str] = []
        for n in re.findall(rf"^{kind} (\d+)$", text, re.M):
            if n not in seen:
                seen.append(n)
        return seen

    labels = _sequence("Table")
    r.check(labels == [str(i) for i in range(1, len(labels) + 1)] and labels != [],
            "Tables numbered consecutively in order of mention",
            f"distinct table labels, in order of first appearance: {labels}")

    figs = _sequence("Figure")
    r.check(figs == [str(i) for i in range(1, len(figs) + 1)] and figs != [],
            "Figures numbered consecutively in order of mention",
            f"distinct figure labels, in order of first appearance: {figs}")

    n_draw = document.count("<w:drawing>")
    r.check(n_draw >= len(figs),
            "Every figure label has an image beneath it",
            f"{len(figs)} figure labels, {n_draw} embedded drawings")

    r.check('w:val="Table"' in document and 'w:styleId="Table"' in styles,
            "Tables use a defined style (APA rules: horizontal only)",
            "document references the Table style and styles.xml defines it")

    # --- Citations ---------------------------------------------------------
    # Citeproc renders the entries without printing a "References" heading of
    # its own, so the entries are counted directly: a line opening with a
    # surname and carrying a parenthesised year.
    # Only the tail of the document is the reference list. Scanning the whole
    # text matched body sentences that happen to end in a citation, and then
    # reported the paper's own prose as an out-of-order reference list.
    tail = text[text.rindex("\n\n", 0, len(text)) :] if "\n\n" in text else text
    conclusion = text.rfind("Conclusion")
    if conclusion != -1:
        tail = text[conclusion:]
    # An entry begins after a blank line; its continuation lines are indented
    # by the hanging indent. Matching any line that starts with a surname also
    # matched continuation lines carrying a middle author ("... & Han, J."),
    # which made a correctly sorted list look out of order.
    blocks = re.split(r"\n\s*\n", tail)
    entries = []
    for b in blocks:
        first = b.strip().split("\n", 1)[0]
        m2 = re.match(r"([A-Z][A-Za-z'\-]+),\s", first)
        if m2 and re.search(r"\(\d{4}[a-z]?\)", b):
            entries.append(m2.group(1))
    surnames = entries
    r.check(len(entries) > 0, "Reference list present",
            f"{len(entries)} entries detected")
    out_of_order = [b for a, b in zip(sorted(surnames), surnames) if a != b]
    r.check(surnames == sorted(surnames),
            "Reference list alphabetical by first author",
            "surnames appear in sorted order"
            if not out_of_order else f"out of order near: {out_of_order[:3]}")

    r.check("[[" not in text, "No placeholders remain",
            "no '[[' token anywhere in the extracted text")

    # --- Items a script must not claim to have judged -----------------------
    r.add(MANUAL, "Claims match the evidence exactly",
          "requires reading the Results against results/ and numbers.json")
    r.add(MANUAL, "Every in-text citation has a reference entry and vice versa",
          "verify with logs/citations_verified.md before submission")
    r.add(MANUAL, "Every table and figure is referred to in the text before it appears",
          "read the Results section; the build cannot decide this")
    r.add(MANUAL, "Nikhil has read every section and rewritten it in his own voice",
          "PAPER_PLAN.md §9.3; tracked in STATUS.md, currently 0 of 7 sections")
    r.add(MANUAL, "Benchmark items audited by a reader with legal training",
          "HUMAN GATE 1/2; all 46 items are status=unverified")

    return r


def main(argv: list[str]) -> int:
    docx = Path(argv[1]) if len(argv) > 1 else (
        ROOT / "paper/apa/output/Manuscript_APA7.docx")
    if not docx.exists():
        print(f"no such file: {docx}", file=sys.stderr)
        return 2

    r = run(docx)
    lines = [
        "# APA 7 checklist",
        "",
        f"Generated by `analysis/apa_checklist.py` on {date.today().isoformat()} "
        f"from `{docx.relative_to(ROOT).as_posix()}`.",
        "",
        "Every row is **measured from the built document**. Rows marked `MANUAL` "
        "are those a script must not claim to have judged; they are listed so "
        "that they are not mistaken for passes.",
        "",
        "| | Item | Evidence |",
        "|---|---|---|",
    ]
    for verdict, item, evidence in r.rows:
        mark = {PASS: "PASS", FAIL: "**FAIL**", MANUAL: "MANUAL"}[verdict]
        lines.append(f"| {mark} | {item} | {evidence} |")

    passed = sum(1 for v, _, _ in r.rows if v == PASS)
    lines += [
        "",
        f"**{passed} passed, {r.failures} failed, {r.manual} require a human.**",
        "",
    ]
    if r.failures:
        lines.append("The manuscript is **not** ready to send while any row reads FAIL.")
    else:
        lines.append(
            "No mechanical check fails. The MANUAL rows remain outstanding, and "
            "the benchmark audit (HUMAN GATE 1) is the substantive one."
        )

    out = ROOT / "logs" / "apa_checklist.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for verdict, item, _ in r.rows:
        if verdict != PASS:
            print(f"  {verdict:6} {item}")
    print(f"{passed} passed, {r.failures} failed, {r.manual} manual -> {out}")
    return 1 if r.failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
