"""Tests for the APA .docx post-processor's caption/figure binding.

APA 7 places the figure label and title above the image. Word breaks pages
between paragraphs, so without `w:keepNext` the caption is stranded at the foot
of one page and the figure appears unlabelled on the next. That is what the
first build of this manuscript did for all four figures.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from fix_apa_docx import (  # noqa: E402
    DEVANAGARI_FONT,
    FONT,
    TABLE_STYLE_ID,
    TEXT_WIDTH_DXA,
    ensure_table_style,
    fix_styles,
    fit_tables_to_page,
    font_devanagari_runs,
    keep_figures_with_captions,
)

DRAWING = "<w:p><w:pPr><w:pStyle w:val=\"BodyText\"/></w:pPr><w:r><w:drawing>x</w:drawing></w:r></w:p>"


def _para(text: str, *, props: bool = True) -> str:
    pr = '<w:pPr><w:pStyle w:val="BodyText"/></w:pPr>' if props else ""
    return f"<w:p>{pr}<w:r><w:t>{text}</w:t></w:r></w:p>"


def _doc(*paras: str) -> str:
    return "<w:document><w:body>" + "".join(paras) + "</w:body></w:document>"


class TestKeepNext:
    def test_caption_paragraphs_are_bound_to_the_figure(self):
        xml = _doc(_para("intro"), _para("Figure 1"), _para("A Title"), DRAWING)
        out, changes = keep_figures_with_captions(xml)
        assert out.count("<w:keepNext/>") == 2
        assert changes and "2 caption/figure" in changes[0]

    def test_the_unrelated_paragraph_is_untouched(self):
        xml = _doc(_para("intro"), _para("Figure 1"), _para("A Title"), DRAWING)
        out, _ = keep_figures_with_captions(xml)
        intro = out.split("</w:p>")[0]
        assert "keepNext" not in intro

    def test_the_image_paragraph_itself_is_not_bound(self):
        """The Note below a figure may legitimately flow to the next page."""
        xml = _doc(_para("Figure 1"), _para("A Title"), DRAWING, _para("Note."))
        out, _ = keep_figures_with_captions(xml)
        drawing_para = [p for p in out.split("</w:p>") if "w:drawing" in p][0]
        assert "keepNext" not in drawing_para

    def test_a_paragraph_without_properties_gets_them_created(self):
        xml = _doc(_para("Figure 1", props=False), _para("A Title", props=False),
                   DRAWING)
        out, _ = keep_figures_with_captions(xml)
        assert out.count("<w:keepNext/>") == 2
        # w:pPr must be the first child of w:p (ECMA-376 content model).
        assert "<w:p><w:pPr><w:keepNext/></w:pPr><w:r>" in out

    def test_document_with_no_figures_is_returned_unchanged(self):
        xml = _doc(_para("a"), _para("b"))
        out, changes = keep_figures_with_captions(xml)
        assert out == xml and changes == []

    def test_every_figure_in_the_document_is_handled(self):
        xml = _doc(_para("Figure 1"), _para("T1"), DRAWING,
                   _para("text"),
                   _para("Figure 2"), _para("T2"), DRAWING)
        out, _ = keep_figures_with_captions(xml)
        assert out.count("<w:keepNext/>") == 4

    def test_running_it_twice_does_not_double_the_element(self):
        xml = _doc(_para("Figure 1"), _para("A Title"), DRAWING)
        once, _ = keep_figures_with_captions(xml)
        twice, changes = keep_figures_with_captions(once)
        assert twice.count("<w:keepNext/>") == 2
        assert changes == [] or twice == once

    def test_keepnext_follows_pstyle_per_the_ecma_content_model(self):
        """`w:pStyle` must precede `w:keepNext` inside `w:pPr`.

        The reverse order is well-formed XML that Word rejects with one opaque
        message naming nothing. The first version of this function produced
        exactly that, and the structural checker caught it.
        """
        xml = _doc(_para("Figure 1"), _para("A Title"), DRAWING)
        out, _ = keep_figures_with_captions(xml)
        assert '<w:pStyle w:val="BodyText"/><w:keepNext/>' in out
        assert "<w:pPr><w:keepNext/><w:pStyle" not in out

    def test_back_to_back_figures_do_not_bind_one_image_to_another(self):
        xml = _doc(DRAWING, DRAWING)
        out, _ = keep_figures_with_captions(xml)
        assert "<w:keepNext/>" not in out


class TestDevanagariFont:
    """Times New Roman has no Devanagari glyphs.

    Word selects the *complex script* face (`w:cs`) for a Devanagari run. With
    `w:cs="Times New Roman"` the Nepali in this paper printed as empty boxes,
    in a PDF that otherwise looked correctly typeset.
    """

    def test_complex_script_face_is_not_the_latin_serif(self):
        """Every `w:cs` in the package, not only the styles we rewrite.

        The first version of this test used `Normal`, whose run properties
        `fix_styles` rebuilds wholesale, so it passed with the sweep deleted:
        the rebuild happened to produce the right answer and the line under
        test did nothing. `ListParagraph` here is a style the rewriter never
        touches, so only the sweep can fix it.
        """
        styles = (
            '<w:styles><w:style w:styleId="ListParagraph">'
            f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/>'
            "</w:rPr></w:style></w:styles>"
        )
        out = fix_styles(styles)
        assert f'w:cs="{DEVANAGARI_FONT}"' in out
        assert f'w:cs="{FONT}"' not in out

    def test_the_latin_face_is_still_times_new_roman(self):
        """The fix must not change the body face APA requires."""
        styles = (
            '<w:styles><w:style w:styleId="Normal"><w:name w:val="Normal"/>'
            f'<w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/>'
            "</w:rPr></w:style></w:styles>"
        )
        out = fix_styles(styles)
        assert f'w:ascii="{FONT}"' in out
        assert f'w:hAnsi="{FONT}"' in out

    def test_the_chosen_face_is_one_windows_ships(self):
        """A downloaded face renders here and substitutes on the reviewer's PC."""
        assert DEVANAGARI_FONT == "Nirmala UI"


class TestTableStyle:
    """Pandoc names a table style the APA template never defines.

    Every table pointed at `Table`, which did not exist, so Word honoured no
    column widths and stacked each table into a single column: Table 1 rendered
    as a vertical list of its own header labels.
    """

    def test_the_missing_style_is_defined(self):
        out = ensure_table_style("<w:styles></w:styles>")
        assert f'w:styleId="{TABLE_STYLE_ID}"' in out
        assert 'w:type="table"' in out

    def test_apa_rules_are_horizontal_only(self):
        out = ensure_table_style("<w:styles></w:styles>")
        assert "<w:top " in out and "<w:bottom " in out
        # APA 7 forbids vertical rules in tables.
        assert "<w:left w:val=" not in out
        assert "<w:right w:val=" not in out
        assert "<w:insideV" not in out

    def test_no_interior_horizontal_rules_between_data_rows(self):
        assert "<w:insideH" not in ensure_table_style("<w:styles></w:styles>")

    def test_table_text_uses_the_devanagari_capable_cs_face(self):
        out = ensure_table_style("<w:styles></w:styles>")
        assert f'w:cs="{DEVANAGARI_FONT}"' in out

    def test_an_existing_definition_is_left_alone(self):
        existing = f'<w:styles><w:style w:styleId="{TABLE_STYLE_ID}"/></w:styles>'
        assert ensure_table_style(existing) == existing

    def test_the_style_lands_inside_the_styles_element(self):
        out = ensure_table_style("<w:styles></w:styles>")
        assert out.endswith("</w:styles>")
        assert out.count("</w:styles>") == 1


class TestDevanagariRuns:
    """`w:cs` alone leaves Devanagari to the Latin face.

    Word consults the complex-script font only for runs it treats as complex
    script. An unmarked Devanagari run is drawn with `w:ascii`, so a document
    whose styles all name a Devanagari font correctly still printed every
    Nepali word as boxes.
    """

    NEP = "\u092e\u093f\u0924\u093f"          # मिति, "date"
    VERB = "\u0917\u0930\u094d\u0928\u0941"   # गर्नु, with a virama

    def _run(self, text: str) -> str:
        """A run with no properties at all, which is what Pandoc emits here."""
        return f"<w:r><w:t>{text}</w:t></w:r>"

    def test_a_devanagari_run_gets_a_devanagari_face(self):
        out, changes = font_devanagari_runs(f"<w:p>{self._run(self.NEP)}</w:p>")
        assert f'w:ascii="{DEVANAGARI_FONT}"' in out
        assert changes and "1 run" in changes[0]

    def test_virama_bearing_text_is_matched_too(self):
        """Nepali morphology has broken this project before; match the script."""
        out, _ = font_devanagari_runs(f"<w:p>{self._run(self.VERB)}</w:p>")
        assert DEVANAGARI_FONT in out

    def test_a_latin_run_keeps_times_new_roman(self):
        xml = f"<w:p>{self._run('date')}</w:p>"
        out, changes = font_devanagari_runs(xml)
        assert out == xml and changes == []

    def test_existing_run_properties_are_preserved(self):
        xml = f"<w:p><w:r><w:rPr><w:i/></w:rPr><w:t>{self.NEP}</w:t></w:r></w:p>"
        out, _ = font_devanagari_runs(xml)
        assert "<w:i/>" in out
        assert DEVANAGARI_FONT in out

    def test_rfonts_is_the_first_child_of_rpr(self):
        """EG_RPrBase fixes the order; w:rFonts precedes w:i."""
        xml = f"<w:p><w:r><w:rPr><w:i/></w:rPr><w:t>{self.NEP}</w:t></w:r></w:p>"
        out, _ = font_devanagari_runs(xml)
        assert "<w:rPr><w:rFonts" in out
        assert out.index("<w:rFonts") < out.index("<w:i/>")

    def test_a_stale_latin_rfonts_is_replaced_not_duplicated(self):
        xml = (f'<w:p><w:r><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}"/>'
               f"</w:rPr><w:t>{self.NEP}</w:t></w:r></w:p>")
        out, _ = font_devanagari_runs(xml)
        assert out.count("<w:rFonts") == 1
        assert f'w:ascii="{FONT}"' not in out

    def test_running_it_twice_changes_nothing_further(self):
        once, _ = font_devanagari_runs(f"<w:p>{self._run(self.NEP)}</w:p>")
        twice, changes = font_devanagari_runs(once)
        assert twice == once and changes == []

    def test_a_mixed_script_run_is_fixed_once(self):
        out, changes = font_devanagari_runs(
            f"<w:p>{self._run('date (' + self.NEP + ')')}</w:p>")
        assert out.count("<w:rFonts") == 1
        assert changes and "1 run" in changes[0]

    def test_rfonts_follows_rstyle_per_the_ecma_content_model(self):
        """EG_RPrBase order: rStyle, then rFonts.

        Putting rFonts first is well-formed XML that violates the content
        model. Word reports one opaque message naming nothing; the structural
        checker named it.
        """
        nep = "\u092e\u093f\u0924\u093f"
        xml = ('<w:p><w:r><w:rPr><w:rStyle w:val="VerbatimChar"/></w:rPr>'
               f"<w:t>{nep}</w:t></w:r></w:p>")
        out, _ = font_devanagari_runs(xml)
        assert out.index("<w:rStyle") < out.index("<w:rFonts")
        assert "<w:rPr><w:rFonts" not in out

    def test_a_mixed_run_keeps_its_latin_in_the_serif(self):
        """Only the Devanagari changes face, not the English around it.

        Pandoc emits "The Nepal Gazette (राजपत्र) publishes ..." as ONE run.
        Refacing the whole run fixed the tofu and switched an entire line of
        English out of Times New Roman, which breaks APA's body-font rule.
        """
        nep = "\u0930\u093e\u091c\u092a\u0924\u094d\u0930"   # राजपत्र
        xml = f"<w:p><w:r><w:t>The Nepal Gazette ({nep}) publishes</w:t></w:r></w:p>"
        out, _ = font_devanagari_runs(xml)
        # The Devanagari piece is refaced ...
        assert f'w:ascii="{DEVANAGARI_FONT}"' in out
        # ... and the Latin pieces are separate runs with no Devanagari face.
        latin = [r for r in out.split("</w:r>") if "The Nepal Gazette" in r]
        assert latin and DEVANAGARI_FONT not in latin[0]

    def test_splitting_preserves_all_the_text(self):
        nep = "\u0930\u093e\u091c\u092a\u0924\u094d\u0930"
        xml = f"<w:p><w:r><w:t>Gazette ({nep}) publishes</w:t></w:r></w:p>"
        out, _ = font_devanagari_runs(xml)
        import re as _re
        joined = "".join(_re.findall(r"<w:t[^>]*>(.*?)</w:t>", out))
        assert joined == f"Gazette ({nep}) publishes"

    def test_a_pure_devanagari_run_is_not_split(self):
        nep = "\u092e\u093f\u0924\u093f"
        xml = f"<w:p><w:r><w:t>{nep}</w:t></w:r></w:p>"
        out, _ = font_devanagari_runs(xml)
        assert out.count("<w:r>") == 1


class TestTableWidth:
    """Pandoc asked for a width no page can hold.

    The nine-column dataset table carried `w:tblW w:w="9999999"`. Word does not
    shrink such a table; it abandons the layout and puts every cell on its own
    line, which is how Table 1 shipped as a vertical list of its own headers.
    """

    WIDE = ('<w:tbl><w:tblPr><w:tblStyle w:val="Table"/>'
            '<w:tblW w:w="9999999" w:type="pct"/>'
            '<w:tblLayout w:type="fixed"/></w:tblPr></w:tbl>')

    def test_an_impossible_width_is_replaced(self):
        out, changes = fit_tables_to_page(self.WIDE)
        assert "9999999" not in out
        assert 'w:type="dxa"' in out
        assert changes and "1 table" in changes[0]

    def test_the_width_is_the_apa_text_column(self):
        out, _ = fit_tables_to_page(self.WIDE)
        assert f'w:w="{TEXT_WIDTH_DXA}"' in out
        assert TEXT_WIDTH_DXA == 9360  # 6.5in at 1440 twentieths per inch

    def test_columns_may_autofit(self):
        out, _ = fit_tables_to_page(self.WIDE)
        assert 'w:tblLayout w:type="autofit"' in out
        assert 'w:type="fixed"' not in out

    def test_only_one_width_element_remains(self):
        out, _ = fit_tables_to_page(self.WIDE)
        assert out.count("<w:tblW") == 1
        assert out.count("<w:tblLayout") == 1

    def test_tblw_follows_tblstyle_per_the_ecma_sequence(self):
        out, _ = fit_tables_to_page(self.WIDE)
        assert out.index("<w:tblStyle") < out.index("<w:tblW")

    def test_every_table_in_the_document_is_fitted(self):
        out, changes = fit_tables_to_page(self.WIDE + self.WIDE)
        assert out.count(f'w:w="{TEXT_WIDTH_DXA}"') == 2
        assert "2 table" in changes[0]

    def test_a_document_with_no_tables_is_unchanged(self):
        xml = "<w:document><w:body><w:p/></w:body></w:document>"
        out, changes = fit_tables_to_page(xml)
        assert out == xml and changes == []
