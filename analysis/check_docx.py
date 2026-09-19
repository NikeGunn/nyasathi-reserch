"""Structural checks a .docx must pass before anyone is asked to open it.

    python analysis/check_docx.py paper/apa/output/Manuscript_APA7.docx

Word refuses a package that violates the OOXML content model with a single
opaque message, "We're sorry. We can't open <file> because we found a problem
with its contents", and names nothing. LibreOffice opens the same file without
complaint and exports a correct-looking PDF, so a PDF-only check passes files
Word will not open. Both failures this build hit were of that shape:

1. `<w:jc>` emitted before `<w:ind>` inside `<w:pPr>`. The order is fixed by the
   schema; the XML is still well-formed.
2. The trailing `<w:p/>` removed from `<w:hdr>`. A header part must end with a
   block-level element, and that paragraph was the only one.

These checks run in the build so the next one is caught here rather than by a
person double-clicking the file.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

# Child order inside <w:pPr>, per ECMA-376. Only the elements we emit.
_PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "numPr", "pBdr",
    "shd", "tabs", "suppressAutoHyphens", "spacing", "ind", "jc", "outlineLvl",
    "rPr", "sectPr",
]

# Child order inside <w:rPr>, per ECMA-376 EG_RPrBase. Emitting <w:sz> before
# <w:b> is well-formed XML that Word refuses to open.
_RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
    "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern",
    "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd",
    "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
    "specVanish", "oMath",
]

# Child order inside <w:style>.
_STYLE_ORDER = [
    "name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden",
    "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "locked",
    "personal", "personalCompose", "personalReply", "rsid", "pPr", "rPr",
    "tblPr", "trPr", "tcPr", "tblStylePr",
]


def _ordered(names: list[str], order: list[str]) -> bool:
    idx = [order.index(n) for n in names if n in order]
    return idx == sorted(idx)


def check(path: Path) -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            problems.append("zip archive is corrupt")

        for name in z.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            try:
                ET.fromstring(z.read(name))
            except ET.ParseError as exc:
                problems.append(f"{name}: not well-formed XML ({exc})")

        # 1. Every header and footer must end with a block-level element.
        for name in z.namelist():
            if not re.match(r"word/(header|footer)\d*\.xml$", name):
                continue
            xml = z.read(name).decode("utf-8")
            if not re.search(r"</w:(p|tbl|sdt)>\s*</w:(hdr|ftr)>\s*$", xml):
                problems.append(
                    f"{name}: must end with a block-level element; Word refuses "
                    f"a header whose last child is not <w:p>, <w:tbl> or <w:sdt>"
                )

        # 2. Child order inside every <w:pPr> and <w:style> we may have touched.
        for name in ("word/styles.xml", "word/document.xml"):
            if name not in z.namelist():
                continue
            xml = z.read(name).decode("utf-8")
            for m in re.finditer(r"<w:pPr>(.*?)</w:pPr>", xml, re.S):
                kids = re.findall(r"<w:([a-zA-Z]+)[ />]", m.group(1))
                top = [k for k in kids if k in _PPR_ORDER]
                if not _ordered(top, _PPR_ORDER):
                    problems.append(f"{name}: <w:pPr> children out of order: {top}")
                    break
            for m in re.finditer(r"<w:rPr>(.*?)</w:rPr>", xml, re.S):
                kids = re.findall(r"<w:([a-zA-Z]+)[ />]", m.group(1))
                top = [k for k in kids if k in _RPR_ORDER]
                if not _ordered(top, _RPR_ORDER):
                    problems.append(f"{name}: <w:rPr> children out of order: {top}")
                    break

        if "word/styles.xml" in z.namelist():
            xml = z.read("word/styles.xml").decode("utf-8")
            for m in re.finditer(r"<w:style [^>]*>(.*?)</w:style>", xml, re.S):
                kids, depth = [], 0
                for tok in re.finditer(r"<(/?)w:([a-zA-Z]+)([^>]*?)(/?)>", m.group(1)):
                    close, nm, _, selfc = tok.groups()
                    if depth == 0 and not close:
                        kids.append(nm)
                    if not close and not selfc:
                        depth += 1
                    elif close:
                        depth -= 1
                if not _ordered(kids, _STYLE_ORDER):
                    problems.append(f"styles.xml: <w:style> children out of order: {kids}")
                    break

        # 3. Every media part must have a declared content type.
        ct = z.read("[Content_Types].xml").decode("utf-8")
        for name in z.namelist():
            if not name.startswith("word/media/") or "." not in name:
                continue
            ext = name.rsplit(".", 1)[-1].lower()
            if f'Extension="{ext}"' not in ct and f'PartName="/{name}"' not in ct:
                problems.append(f"{name}: content type not declared")

    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    problems = check(path)
    if problems:
        print(f"FAIL: {path.name} has {len(problems)} structural problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"structure: {path.name} passes all OOXML checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
