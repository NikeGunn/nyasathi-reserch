"""Apply the APA 7 layout rules Pandoc cannot express from Markdown.

    python analysis/fix_apa_docx.py paper/apa/output/Manuscript_APA7.docx

Pandoc writes correct *structure* — headings, paragraphs, a reference list — but
takes typography from the reference document, and the official APA
professional-paper template does not carry it:

* `docDefaults` names **theme fonts** (`minorHAnsi`), which resolve to the
  theme's sans-serif face, so body text renders in Aptos/Calibri rather than a
  serif;
* `Normal` sets no first-line indent, so paragraphs run flush left;
* the shipped running head is the sample paper's own — **FAKE NEWS, FAST AND
  SLOW** — and its header uses two literal tabs sized for that short title, so a
  longer running head pushes the page number onto its own line;
* a trailing empty paragraph in the header adds a blank line under it.

None of this is visible in extracted text. `pandoc -t plain` reads identically
whether the document is correct or not, and the header part is never read at
all. It was caught by rendering pages to images and looking at them, which is
why that step is in the build checklist.

APA 7 requirements implemented here (Publication Manual, 7th ed., §2.19-2.24):

* Times New Roman 12 pt throughout, including headings and the header
* double spacing everywhere, no extra space between paragraphs
* first-line indent 0.5 in on body paragraphs, flush left (not justified)
* running head in ALL CAPS flush left, page number flush right, same line
* Level 1 headings centred bold; Level 2 flush left bold; Level 3 flush left
  bold italic
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

RUNNING_HEAD = "A VERSION-AWARE NEPALI STATUTORY BENCHMARK"
MAX_RUNNING_HEAD = 50

FONT = "Times New Roman"

DEVANAGARI_FONT = "Nirmala UI"
"""The font Word uses for Devanagari runs.

Times New Roman has no Devanagari glyphs. Declaring it as the complex-script
font (`w:cs`) makes Word render every Nepali word as tofu boxes, which is what
the first build did: `मिति` printed as four empty rectangles in a paper about
Nepali statutory text. The PDF looked typeset and said nothing.

Nirmala UI ships with Windows 8 and later and is Microsoft's Devanagari UI
face, so a reviewer opening the .docx has it already. A downloaded face such as
Noto Sans Devanagari would render here and substitute on their machine, which
is the same failure moved somewhere we cannot see it.
"""

SIZE_HALF_POINTS = "24"   # 12 pt
LINE_DOUBLE = "480"       # 240 twentieths = single; 480 = double
INDENT_FIRST = "720"      # 0.5 in in DXA
RIGHT_TAB = "9360"        # 6.5 in content width: page number lands flush right

def _run_props(*, bold: bool = False, italic: bool = False) -> str:
    """Build a <w:rPr> body in schema order.

    ECMA-376 EG_RPrBase fixes the order as rStyle, rFonts, b, bCs, i, iCs,
    ..., sz, szCs. Emitting <w:sz> before <w:b> is well-formed XML that Word
    refuses to open, while LibreOffice renders it without complaint, so bold
    and italic are built here rather than appended by callers.
    """
    parts = [
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" '
        f'w:cs="{DEVANAGARI_FONT}" w:eastAsia="{FONT}"/>'
    ]
    if bold:
        parts.append("<w:b/><w:bCs/>")
    if italic:
        parts.append("<w:i/><w:iCs/>")
    parts.append(f'<w:sz w:val="{SIZE_HALF_POINTS}"/><w:szCs w:val="{SIZE_HALF_POINTS}"/>')
    return "".join(parts)


def fix_styles(xml: str) -> str:
    """Force Times New Roman 12 pt, double spacing, and APA heading formats."""
    # 1. Replace theme fonts in docDefaults with an explicit serif face.
    xml = re.sub(
        r'<w:rFonts[^/]*?w:asciiTheme="minorHAnsi"[^/]*?/>',
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" '
        f'w:cs="{DEVANAGARI_FONT}" w:eastAsia="{FONT}"/>',
        xml,
    )

    # 1b. Every complex-script declaration inherited from the template still
    # says Times New Roman, which has no Devanagari glyphs. Word picks the
    # w:cs face for Devanagari runs, so these must be rewritten or the Nepali
    # in this paper prints as empty boxes.
    xml = xml.replace(f'w:cs="{FONT}"', f'w:cs="{DEVANAGARI_FONT}"')
    xml = xml.replace('<w:sz w:val="22"/>', f'<w:sz w:val="{SIZE_HALF_POINTS}"/>')
    xml = xml.replace('<w:szCs w:val="22"/>', f'<w:szCs w:val="{SIZE_HALF_POINTS}"/>')

    # 2. Double spacing, no inter-paragraph space, in the paragraph defaults.
    xml = re.sub(
        r'<w:spacing w:after="160" w:line="259" w:lineRule="auto"\s*/>',
        f'<w:spacing w:after="0" w:before="0" w:line="{LINE_DOUBLE}" w:lineRule="auto"/>',
        xml,
    )

    def _style(style_id: str, body: str) -> tuple[re.Pattern[str], object]:
        """Rewrite one style's pPr/rPr, leaving its identity intact."""
        pattern = re.compile(
            r'(<w:style [^>]*w:styleId="%s"[^>]*>)(.*?)(</w:style>)' % style_id, re.S
        )

        def _sub(m: re.Match[str]) -> str:
            inner = m.group(2)
            # Keep <w:name>, <w:basedOn>, <w:next>, drop old formatting.
            keep = "".join(
                re.findall(
                    r'<w:(?:name|aliases|basedOn|next|link|autoRedefine|hidden|uiPriority'
                    r'|semiHidden|unhideWhenUsed|qFormat|locked|personal|rsid)[^>]*/>',
                    inner,
                )
            )
            return m.group(1) + keep + body + m.group(3)

        return pattern, _sub

    # CRITICAL: inside <w:pPr> the schema fixes the element order as
    # pStyle, numPr, tabs, spacing, ind, jc, outlineLvl, rPr. Emitting <w:jc>
    # before <w:ind> parses as well-formed XML but violates the schema, and
    # Word reports "we found a problem with some content" while LibreOffice
    # renders it without complaint. Keep these fragments in schema order.
    SPACING = (
        f'<w:spacing w:after="0" w:before="0" w:line="{LINE_DOUBLE}" w:lineRule="auto"/>'
    )
    body_p = f'{SPACING}<w:ind w:firstLine="{INDENT_FIRST}"/><w:jc w:val="left"/>' 

    targets = {
        # Body: double spaced, first line indented, flush left.
        "Normal": f'<w:pPr>{body_p}</w:pPr><w:rPr>{_run_props()}</w:rPr>',
        "BodyText": f'<w:pPr>{body_p}</w:pPr><w:rPr>{_run_props()}</w:rPr>',
        # APA Level 1: centred, bold, no indent.
        "Heading1": f'<w:pPr>{SPACING}<w:jc w:val="center"/><w:outlineLvl w:val="0"/></w:pPr>'
                    f'<w:rPr>{_run_props(bold=True)}</w:rPr>',
        # Level 2: flush left, bold.
        "Heading2": f'<w:pPr>{SPACING}<w:jc w:val="left"/><w:outlineLvl w:val="1"/></w:pPr>'
                    f'<w:rPr>{_run_props(bold=True)}</w:rPr>',
        # Level 3: flush left, bold italic.
        "Heading3": f'<w:pPr>{SPACING}<w:jc w:val="left"/><w:outlineLvl w:val="2"/></w:pPr>'
                    f'<w:rPr>{_run_props(bold=True, italic=True)}</w:rPr>',
        # Title block on page 1: centred bold, no indent.
        "Title": f'<w:pPr>{SPACING}<w:jc w:val="center"/></w:pPr>'
                 f'<w:rPr>{_run_props(bold=True)}</w:rPr>',
        # Header: serif, single spaced, right tab for the page number.
        "Header": f'<w:pPr><w:tabs><w:tab w:val="right" w:pos="{RIGHT_TAB}"/></w:tabs>'
                  f'<w:spacing w:after="0" w:before="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                  f'<w:rPr>{_run_props()}</w:rPr>',
    }

    for style_id, body in targets.items():
        pattern, sub = _style(style_id, body)
        xml, n = pattern.subn(sub, xml)
        if n == 0:
            print(f"  warning: style {style_id!r} not found", file=sys.stderr)

    xml = ensure_table_style(xml)
    xml = ensure_header_style(xml)
    return xml


def ensure_header_style(xml: str) -> str:
    """Define the `Header` style if the reference document has none.

    Pandoc's default reference document defines no `Header` style, because it
    emits no header part. This build synthesises one, so the style it points at
    has to exist or the running head inherits body formatting (double spaced,
    first-line indented) and pushes the page number onto a second line.
    """
    if 'w:styleId="Header"' in xml:
        return xml
    style = (
        '<w:style w:type="paragraph" w:styleId="Header">'
        '<w:name w:val="header"/><w:basedOn w:val="Normal"/>'
        f'<w:pPr><w:tabs><w:tab w:val="right" w:pos="{RIGHT_TAB}"/></w:tabs>'
        '<w:spacing w:after="0" w:before="0" w:line="240" w:lineRule="auto"/>'
        '<w:ind w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
        f'<w:rPr>{_run_props()}</w:rPr></w:style>'
    )
    return xml.replace("</w:styles>", style + "</w:styles>")


TABLE_STYLE_ID = "Table"
"""The table style Pandoc references on every table it emits.

The APA template defines only `TableNormal` and never `Table`, so each table
arrived pointing at a style that did not exist. Word then honoured no column
widths and stacked every cell into a single column: Table 1 rendered as a
vertical list of its own header labels, with the italic title broken
mid-word down the right margin. The table markup was correct throughout; only
the style it named was missing, and nothing in the package disagreed with
itself.
"""


_TBLPR_RE = re.compile(r"<w:tblPr>.*?</w:tblPr>", re.DOTALL)
_TBLW_RE = re.compile(r'<w:tblW [^>]*/>')

TEXT_WIDTH_DXA = 9360
"""The APA text column: 8.5in page less 1in margins, in twentieths of a point."""


def fit_tables_to_page(xml: str) -> tuple[str, list[str]]:
    """Give every table a width the page can actually hold.

    Pandoc emitted the nine-column dataset table with
    `<w:tblW w:w="9999999" w:type="pct">`, a preferred width Word cannot
    satisfy inside a 6.5-inch text column. Word's response is not to shrink the
    table but to abandon the layout: every cell is placed on its own line, so
    Table 1 printed as a vertical list of its own header labels with the italic
    title broken mid-word down the margin.

    Each table is pinned to the text width and allowed to autofit its columns,
    which is what a reader expects and what APA 7 shows in every sample table.
    """
    count = 0

    def _fix(m: re.Match[str]) -> str:
        nonlocal count
        pr = m.group(0)
        count += 1
        # w:tblW must follow w:tblStyle in the CT_TblPrBase sequence.
        fixed = _TBLW_RE.sub("", pr)
        width = f'<w:tblW w:w="{TEXT_WIDTH_DXA}" w:type="dxa"/><w:tblLayout w:type="autofit"/>'
        fixed = re.sub(r'<w:tblLayout [^>]*/>', "", fixed)
        if "<w:tblStyle " in fixed:
            return re.sub(r"(<w:tblStyle [^>]*/>)", r"\1" + width, fixed, count=1)
        return fixed.replace("<w:tblPr>", f"<w:tblPr>{width}", 1)

    out = _TBLPR_RE.sub(_fix, xml)
    out = _widen_first_column(out)
    out = _format_table_paragraphs(out)
    return out, ([f"fitted {count} table(s) to the text width"] if count else [])


_TBL_RE = re.compile(r"<w:tbl>.*?</w:tbl>", re.DOTALL)


def _widen_first_column(xml: str) -> str:
    """Give the label column the room its text needs.

    Pandoc divides the width equally, so a nine-column table gets 1040 twips
    (0.72in) per column. "Provisions" does not fit in 0.72in and Word breaks it
    mid-word down the column: `Pr / ovisions`, `L / ettered`, `NS / UB / EP`.
    A statistical table is read across its rows, and a header split over three
    lines is not readable.

    The first column holds the row labels (Act names) and the rest hold short
    numbers, so the label column takes 40% and the remainder is shared. Cell
    widths (`w:tcW`) are rewritten to match the grid, because Word honours the
    cell width over the grid column when the two disagree.
    """

    def _fix_table(m: re.Match[str]) -> str:
        tbl = m.group(0)
        cols = re.findall(r"<w:gridCol [^>]*/>", tbl)
        if len(cols) < 4:
            return tbl  # narrow tables already fit

        label = int(TEXT_WIDTH_DXA * 0.40)
        rest = (TEXT_WIDTH_DXA - label) // (len(cols) - 1)
        widths = [label] + [rest] * (len(cols) - 1)
        widths[-1] += TEXT_WIDTH_DXA - sum(widths)  # absorb the rounding

        grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
        tbl = re.sub(r"<w:tblGrid>.*?</w:tblGrid>",
                     f"<w:tblGrid>{grid}</w:tblGrid>", tbl, count=1, flags=re.DOTALL)

        # Rewrite each row's cell widths in column order.
        def _fix_row(rm: re.Match[str]) -> str:
            row = rm.group(0)
            i = [0]

            def _fix_cell(cm: re.Match[str]) -> str:
                w = widths[i[0]] if i[0] < len(widths) else rest
                i[0] += 1
                return f'<w:tcW w:w="{w}" w:type="dxa"/>'

            return re.sub(r"<w:tcW [^>]*/>", _fix_cell, row)

        return re.sub(r"<w:tr(?: [^>]*)?>.*?</w:tr>", _fix_row, tbl, flags=re.DOTALL)

    return _TBL_RE.sub(_fix_table, xml)


def _format_table_paragraphs(xml: str) -> str:
    """Single-space table cells and remove the body first-line indent.

    A cell inherits `Normal`, which APA sets to double spacing with a 0.5in
    first-line indent. In a table that indent pushes every value away from its
    column edge and the double spacing makes a five-row table two pages long.
    APA 7 permits single spacing inside a table where it aids readability, and
    every sample table in the Publication Manual is set that way.
    """

    def _fix_table(m: re.Match[str]) -> str:
        tbl = m.group(0)
        fmt = ('<w:spacing w:after="0" w:before="0" w:line="240" '
               'w:lineRule="auto"/><w:ind w:firstLine="0" w:left="0"/>')

        def _fix_para(pm: re.Match[str]) -> str:
            para = pm.group(0)
            if "<w:pPr>" in para:
                body = re.sub(r"<w:spacing [^>]*/>", "", para, count=1)
                body = re.sub(r"<w:ind [^>]*/>", "", body, count=1)
                # w:spacing and w:ind follow w:pStyle in EG_PPrBase order.
                if "<w:pStyle " in body:
                    return re.sub(r"(<w:pStyle [^>]*/>)", r"\1" + fmt, body, count=1)
                return body.replace("<w:pPr>", f"<w:pPr>{fmt}", 1)
            return para.replace("<w:p>", f"<w:p><w:pPr>{fmt}</w:pPr>", 1)

        return _PARA_RE.sub(_fix_para, tbl)

    return _TBL_RE.sub(_fix_table, xml)


def ensure_table_style(xml: str) -> str:
    """Define the APA 7 table style if the template does not.

    APA 7 (§7.8, Table Setup): horizontal borders only, above and below the
    header row and at the foot of the table. No vertical rules, no interior
    horizontal rules between data rows. Table text is the body font, and APA
    permits single spacing inside a table where it aids readability.
    """
    if f'w:styleId="{TABLE_STYLE_ID}"' in xml:
        return xml

    def _rule(edge: str) -> str:
        """One APA horizontal rule: half-point, black, on the named edge."""
        return f'<w:{edge} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'

    style = (
        f'<w:style w:type="table" w:styleId="{TABLE_STYLE_ID}">'
        f'<w:name w:val="Table"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="59"/>'
        f'<w:pPr><w:spacing w:after="0" w:before="0" w:line="240" w:lineRule="auto"/>'
        f'<w:ind w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
        f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" '
        f'w:cs="{DEVANAGARI_FONT}" w:eastAsia="{FONT}"/>'
        f'<w:sz w:val="{SIZE_HALF_POINTS}"/><w:szCs w:val="{SIZE_HALF_POINTS}"/></w:rPr>'
        # Table-level borders: top and bottom of the table only.
        f'<w:tblPr><w:tblBorders>'
        f'{_rule("top")}{_rule("bottom")}'
        f'</w:tblBorders>'
        f'<w:tblCellMar><w:top w:w="43" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
        f'<w:bottom w:w="43" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
        f'</w:tblPr>'
        # The header row carries the rule beneath it, and repeats across pages.
        f'<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr>'
        f'<w:tblPr/><w:tcPr><w:tcBorders>'
        f'{_rule("bottom")}'
        f'</w:tcBorders></w:tcPr></w:tblStylePr>'
        f"</w:style>"
    )
    return xml.replace("</w:styles>", style + "</w:styles>")


HEADER_PART = "word/header1.xml"

_W_NS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
)


def build_header(running_head: str) -> bytes:
    """The APA 7 running head: title ALL CAPS flush left, page number flush right.

    Written from scratch rather than inherited from the official APA template,
    because Pandoc cannot copy that template without producing a package Word
    refuses to open (it drops the template's chart, embedding and endnote parts
    while keeping the rest). The workaround for that was a LibreOffice re-save,
    which made Word accept the file and destroyed its tables: re-saving that
    already-broken package returned a document with zero `w:tbl` elements whose
    cells survived only as loose paragraphs, which is why the nine-column
    dataset table printed as a vertical list of its own header labels.

    Pandoc's own default reference document opens in Word, keeps its tables,
    and already defines every style APA needs. The only thing it lacks is a
    header, so this supplies one and the template is not used at all.

    The page number is a `PAGE` field, so it numbers every page rather than
    printing a literal digit.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:hdr {_W_NS}>"
        "<w:p><w:pPr><w:pStyle w:val=\"Header\"/>"
        f'<w:tabs><w:tab w:val="right" w:pos="{RIGHT_TAB}"/></w:tabs>'
        '<w:spacing w:after="0" w:before="0" w:line="240" w:lineRule="auto"/>'
        '<w:ind w:firstLine="0"/><w:jc w:val="left"/></w:pPr>'
        f"<w:r><w:rPr>{_run_props()}</w:rPr>"
        f'<w:t xml:space="preserve">{running_head}</w:t></w:r>'
        "<w:r><w:tab/></w:r>"
        f'<w:r><w:rPr>{_run_props()}</w:rPr>'
        '<w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:rPr>{_run_props()}</w:rPr>'
        '<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        f'<w:r><w:rPr>{_run_props()}</w:rPr>'
        '<w:fldChar w:fldCharType="end"/></w:r>'
        "</w:p></w:hdr>"
    ).encode("utf-8")


def fix_header(xml: str, running_head: str) -> tuple[str, list[str]]:
    """Set the running head and put the page number flush right on the same line."""
    changes: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        inner = m.group(2)
        stripped = inner.strip()
        if stripped and not stripped.isdigit() and stripped.upper() == stripped:
            changes.append(f"running head: {stripped!r} -> {running_head!r}")
            return f"{m.group(1)}{running_head}{m.group(3)}"
        return m.group(0)

    xml = re.sub(r"(<w:t[^>]*>)([^<]*)(</w:t>)", _sub, xml)

    # The template emits two literal tabs, sized for its own short running head.
    # With a longer one they overflow and push the page number to a new line.
    # One right-aligned tab stop (set on the Header style) does the job at any
    # title length.
    xml, n = re.subn(r"(<w:r[^>]*>\s*<w:tab\s*/>\s*</w:r>\s*){2,}",
                     '<w:r><w:tab/></w:r>', xml)
    if n:
        changes.append("collapsed 2 literal tabs to 1 (page number was wrapping)")

    # The template's trailing empty paragraph adds a blank line under the
    # header. It cannot simply be deleted: it is the last block-level element
    # in <w:hdr>, and the content model requires the part to end with one.
    # Removing it produced a file Word refuses to open ("we found a problem
    # with its contents") while LibreOffice rendered it happily. Collapse it
    # to zero height instead, which removes the blank line and keeps the
    # element the schema requires.
    # Keep the element, drop its height: turn the self-closing <w:p .../> into
    # <w:p ...><w:pPr>...</w:pPr></w:p> with an exact tiny line height.
    def _collapse(m: re.Match[str]) -> str:
        attrs = m.group(1)
        return (
            f'<w:p {attrs}><w:pPr><w:spacing w:after="0" w:before="0" '
            'w:line="20" w:lineRule="exact"/><w:rPr><w:sz w:val="2"/>'
            '<w:szCs w:val="2"/></w:rPr></w:pPr></w:p>'
        )

    xml, n = re.subn(
        r'<w:p ([^<>]*?w14:textId="77777777"[^<>]*?)\s*/>', _collapse, xml
    )
    if n:
        changes.append("collapsed trailing header paragraph (kept for schema)")

    return xml, changes


_CONTENT_TYPES = {
    "png": "image/png", "gif": "image/gif", "jpeg": "image/jpeg",
    "jpg": "image/jpeg", "bmp": "image/bmp", "svg": "image/svg+xml",
    "tiff": "image/tiff", "emf": "image/x-emf", "wmf": "image/x-wmf",
}


def fix_content_types(xml: str, extensions: set[str]) -> tuple[str, list[str]]:
    """Declare every media extension present in the package.

    The APA template carries images whose extensions it never declares in
    `[Content_Types].xml`. Word refuses such a package with "we found a problem
    with some content", while LibreOffice opens it without complaint, so a
    PDF-only check passes a file Word will not open.
    """
    changes: list[str] = []
    for ext in sorted(extensions):
        ctype = _CONTENT_TYPES.get(ext)
        if ctype is None or f'Extension="{ext}"' in xml:
            continue
        xml = xml.replace(
            "</Types>", f'<Default Extension="{ext}" ContentType="{ctype}"/></Types>'
        )
        changes.append(f"declared content type for .{ext}")
    return xml, changes


_PARA_RE = re.compile(r"<w:p(?: [^>]*)?>.*?</w:p>", re.DOTALL)

_DEVANAGARI = re.compile(r"[ऀ-ॿ꣠-ꣿ]")
"""Devanagari, plus the Vedic extensions block.

Matching the script rather than a word list: the project's standing rule is
that a check against Nepali matches the writing system or the ending, never an
enumerated set of examples.
"""

_RUN_RE = re.compile(r"<w:r(?: [^>]*)?>.*?</w:r>", re.DOTALL)
_TEXT_RE = re.compile(r"<w:t(?: [^>]*)?>(.*?)</w:t>", re.DOTALL)


def font_devanagari_runs(xml: str) -> tuple[str, list[str]]:
    """Give every run containing Devanagari a font that can draw it.

    `w:cs` is **not** sufficient on its own. Word consults the complex-script
    face only for runs it has decided are complex script; a Devanagari run that
    carries no such marking is drawn with `w:ascii`, which is Times New Roman,
    which has no Devanagari glyphs. The result is a page of empty boxes in a
    document whose styles all name a Devanagari font correctly.

    Setting `w:ascii` and `w:hAnsi` on the affected runs removes the guess.
    Latin runs are untouched, so the body stays in Times New Roman as APA
    requires, and a run of mixed script gets the Devanagari face only if it
    actually contains Devanagari.
    """
    fonts = (
        f'<w:rFonts w:ascii="{DEVANAGARI_FONT}" w:hAnsi="{DEVANAGARI_FONT}" '
        f'w:cs="{DEVANAGARI_FONT}"/>'
    )
    count = 0

    def _split_mixed(run: str) -> str | None:
        """Split a mixed-script run so only the Devanagari changes face.

        Pandoc emits `The Nepal Gazette (राजपत्र) publishes ...` as one run.
        Applying the Devanagari face to the whole run switched an entire line
        of English out of Times New Roman, which breaks the APA body-font rule
        while fixing the tofu. The run is therefore cut into script-homogeneous
        pieces and only the Devanagari pieces are refaced.
        """
        texts = _TEXT_RE.findall(run)
        if len(texts) != 1:
            return None
        text = texts[0]
        pieces = [p for p in re.split(r"([ऀ-ॿ꣠-ꣿ]+)", text) if p]
        if len(pieces) < 2:
            return None

        prefix = run[: run.index("<w:t")]
        suffix = "</w:r>"
        # Preserve xml:space so leading and trailing spaces survive the split.
        opener = '<w:t xml:space="preserve">'
        out: list[str] = []
        for piece in pieces:
            escaped = piece.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if _DEVANAGARI.search(piece):
                body = prefix
                if "<w:rPr>" in body:
                    body = re.sub(r"<w:rFonts[^>]*/>", "", body, count=1)
                    if "<w:rStyle " in body:
                        body = re.sub(r"(<w:rStyle [^>]*/>)", r"\1" + fonts, body, count=1)
                    else:
                        body = body.replace("<w:rPr>", f"<w:rPr>{fonts}", 1)
                else:
                    body = re.sub(r"(<w:r(?: [^>]*)?>)", r"\1" + f"<w:rPr>{fonts}</w:rPr>",
                                  body, count=1)
                out.append(f"{body}{opener}{escaped}</w:t>{suffix}")
            else:
                out.append(f"{prefix}{opener}{escaped}</w:t>{suffix}")
        return "".join(out)

    def _fix(m: re.Match[str]) -> str:
        nonlocal count
        run = m.group(0)
        if not any(_DEVANAGARI.search(t) for t in _TEXT_RE.findall(run)):
            return run
        if DEVANAGARI_FONT in run:
            return run
        count += 1
        split = _split_mixed(run)
        if split is not None:
            return split
        if "<w:rPr>" in run:
            # EG_RPrBase order is rStyle, rFonts, b, bCs, i, iCs, ... so
            # w:rFonts goes after an existing w:rStyle and before everything
            # else. Inserting it at the head of w:rPr produces well-formed XML
            # that violates the content model, and the structural checker
            # caught exactly that on the first attempt.
            body = re.sub(r"<w:rFonts[^>]*/>", "", run, count=1)
            if "<w:rStyle " in body:
                return re.sub(r"(<w:rStyle [^>]*/>)", r"\1" + fonts, body, count=1)
            return body.replace("<w:rPr>", f"<w:rPr>{fonts}", 1)
        return re.sub(r"(<w:r(?: [^>]*)?>)", r"\1" + f"<w:rPr>{fonts}</w:rPr>",
                      run, count=1)

    out = _RUN_RE.sub(_fix, xml)
    return out, ([f"set a Devanagari face on {count} run(s)"] if count else [])


def keep_figures_with_captions(xml: str) -> tuple[str, list[str]]:
    """Stop a page break falling between a figure caption and its figure.

    APA 7 puts **Figure N** and the italic title *above* the image. Word breaks
    pages on paragraph boundaries and, left alone, stranded every caption at the
    foot of one page with its figure overleaf: the reader meets "Figure 1" and a
    title with nothing under it, and the figure arrives unlabelled.

    `w:keepNext` binds a paragraph to the one after it, so the pair moves
    together. It is applied to the two paragraphs preceding each drawing (the
    label and the italic title), which is the whole caption APA specifies.
    """
    paragraphs = list(_PARA_RE.finditer(xml))
    bind: set[int] = set()
    for i, para in enumerate(paragraphs):
        if "<w:drawing>" not in para.group(0):
            continue
        # The two caption paragraphs above the image: the bold "Figure N" label
        # and the italic title. Each is bound to the paragraph that follows it,
        # so label -> title -> image cannot be split across a page boundary.
        # The image paragraph itself is not bound, because the Note below it may
        # legitimately flow onto the next page.
        for j in (i - 2, i - 1):
            if j >= 0 and "<w:drawing>" not in paragraphs[j].group(0):
                bind.add(j)

    if not bind:
        return xml, []

    out: list[str] = []
    last = 0
    for i, para in enumerate(paragraphs):
        if i not in bind:
            continue
        text = para.group(0)
        if "<w:keepNext/>" in text:
            continue
        if "<w:pPr>" in text:
            # ECMA-376 fixes the order of w:pPr's children: w:pStyle first,
            # then w:keepNext. Inserting at the head of w:pPr produces
            # well-formed XML that violates the content model, and Word reports
            # it as one opaque "problem with the contents" naming nothing.
            # check_docx.py catches it; this places the element correctly.
            if "<w:pStyle " in text:
                fixed = re.sub(r"(<w:pStyle [^>]*/>)", r"\1<w:keepNext/>", text, count=1)
            else:
                fixed = text.replace("<w:pPr>", "<w:pPr><w:keepNext/>", 1)
        else:
            # A paragraph with no properties needs the element created, and
            # w:pPr must be the FIRST child of w:p per ECMA-376.
            fixed = re.sub(r"(<w:p(?: [^>]*)?>)", r"\1<w:pPr><w:keepNext/></w:pPr>",
                           text, count=1)
        out.append(xml[last:para.start()])
        out.append(fixed)
        last = para.end()
    out.append(xml[last:])
    return "".join(out), [f"kept {len(bind)} caption/figure paragraph(s) together"]


def fix(docx: Path, running_head: str = RUNNING_HEAD) -> list[str]:
    if len(running_head) > MAX_RUNNING_HEAD:
        raise ValueError(
            f"running head is {len(running_head)} characters; APA 7 allows "
            f"{MAX_RUNNING_HEAD} (§2.8)"
        )

    changes: list[str] = []
    tmp = docx.with_suffix(".tmp.docx")

    with zipfile.ZipFile(docx) as probe:
        media_ext = {
            n.rsplit(".", 1)[-1].lower()
            for n in probe.namelist()
            if n.startswith("word/media/") and "." in n
        }

    with zipfile.ZipFile(docx) as probe:
        has_header = any(
            re.match(r"word/header\d*\.xml$", n) for n in probe.namelist()
        )
        # One relationship id, shared by the three parts that must agree on it.
        if not has_header:
            rels_now = probe.read("word/_rels/document.xml.rels").decode("utf-8")
            used = set(re.findall(r'Id="(rId\d+)"', rels_now))
            i = 1
            while f"rId{i}" in used:
                i += 1
            header_rid = f"rId{i}"

    with zipfile.ZipFile(docx) as src, zipfile.ZipFile(
        tmp, "w", zipfile.ZIP_DEFLATED
    ) as out:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text, ct_changes = fix_content_types(data.decode("utf-8"), media_ext)
                if not has_header and f'PartName="/{HEADER_PART}"' not in text:
                    text = text.replace(
                        "</Types>",
                        f'<Override PartName="/{HEADER_PART}" ContentType='
                        '"application/vnd.openxmlformats-officedocument.'
                        'wordprocessingml.header+xml"/></Types>')
                data = text.encode("utf-8")
                changes.extend(ct_changes)
            elif item.filename == "word/styles.xml":
                data = fix_styles(data.decode("utf-8")).encode("utf-8")
                changes.append("styles: Times New Roman 12pt, double spaced, APA headings")
            elif re.match(r"word/header\d*\.xml$", item.filename):
                text, hdr_changes = fix_header(data.decode("utf-8"), running_head)
                data = text.encode("utf-8")
                changes.extend(hdr_changes)
            elif item.filename == "word/_rels/document.xml.rels" and not has_header:
                data = data.decode("utf-8").replace(
                    "</Relationships>",
                    f'<Relationship Id="{header_rid}" Type="http://schemas.'
                    'openxmlformats.org/officeDocument/2006/relationships/header"'
                    ' Target="header1.xml"/></Relationships>').encode("utf-8")
            elif item.filename == "word/document.xml":
                text, keep_changes = keep_figures_with_captions(data.decode("utf-8"))
                text, font_changes = font_devanagari_runs(text)
                text, tbl_changes = fit_tables_to_page(text)
                if not has_header and "<w:headerReference" not in text:
                    # w:headerReference is the FIRST child of w:sectPr in the
                    # CT_SectPr sequence, before w:pgSz and w:pgMar. Inserted
                    # by slicing rather than re.sub: an earlier version lost
                    # its group backreference in the replacement string, which
                    # ate the <w:sectPr> tag itself and left invalid XML.
                    ref = ('<w:headerReference w:type="default" '
                           f'r:id="{header_rid}"/>')
                    m = re.search(r"<w:sectPr(?: [^>]*)?>", text)
                    if m:
                        text = text[: m.end()] + ref + text[m.end():]
                # APA 7 requires 1-inch margins on every side. Pandoc emits a
                # w:sectPr carrying neither w:pgSz nor w:pgMar, so the geometry
                # is whatever the reader's Word defaults to: correct on a US
                # install, and A4 with different margins elsewhere. A layout
                # that depends on the reader's locale is not a layout.
                if "<w:pgMar" not in text:
                    geometry = (
                        '<w:pgSz w:w="12240" w:h="15840"/>'
                        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440"'
                        ' w:left="1440" w:header="720" w:footer="720"'
                        ' w:gutter="0"/>'
                    )
                    sm = re.search(r"<w:sectPr(?: [^>]*)?>", text)
                    if sm:
                        # w:pgSz and w:pgMar follow w:headerReference in the
                        # CT_SectPr sequence.
                        end = text.index("</w:sectPr>", sm.end())
                        text = text[:end] + geometry + text[end:]
                    changes.append("declared US Letter with 1in margins")
                data = text.encode("utf-8")
                changes.extend(keep_changes)
                changes.extend(font_changes)
                changes.extend(tbl_changes)
            out.writestr(item, data)

        if not has_header:
            out.writestr(HEADER_PART, build_header(running_head))
            changes.append(f"added a running-head part ({running_head!r})")

    shutil.move(str(tmp), str(docx))
    return changes


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    docx = Path(argv[1])
    if not docx.exists():
        print(f"no such file: {docx}", file=sys.stderr)
        return 1
    for c in fix(docx):
        print(f"  {c}")
    print(f"APA 7 layout applied ({len(RUNNING_HEAD)}/{MAX_RUNNING_HEAD} char running head)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
