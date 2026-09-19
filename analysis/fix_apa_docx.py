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
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/>'
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
        f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/>',
        xml,
    )
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

    return xml


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

    with zipfile.ZipFile(docx) as src, zipfile.ZipFile(
        tmp, "w", zipfile.ZIP_DEFLATED
    ) as out:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text, ct_changes = fix_content_types(data.decode("utf-8"), media_ext)
                data = text.encode("utf-8")
                changes.extend(ct_changes)
            elif item.filename == "word/styles.xml":
                data = fix_styles(data.decode("utf-8")).encode("utf-8")
                changes.append("styles: Times New Roman 12pt, double spaced, APA headings")
            elif re.match(r"word/header\d*\.xml$", item.filename):
                text, hdr_changes = fix_header(data.decode("utf-8"), running_head)
                data = text.encode("utf-8")
                changes.extend(hdr_changes)
            out.writestr(item, data)

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
