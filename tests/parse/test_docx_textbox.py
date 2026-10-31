"""Text boxes must contribute to the text ``DOCXParser`` extracts.

``Paragraph.text`` concatenates only the ``w:t`` children of each direct
``w:r``. Text box content sits one level deeper, inside ``w:txbxContent``, so a
document whose callout text lives in a text box parses as if that text did not
exist: no exception, no warning, just missing content.

Word writes a text box twice -- DrawingML under ``mc:Choice`` and the VML
rendering under ``mc:Fallback`` -- so a reader that simply walks every ``w:t``
under the paragraph would return the same callout twice.
"""

import pytest

from semantica.parse.docx_parser import DOCXParser

docx = pytest.importorskip(
    "docx", reason="python-docx comes from the 'documents' extra"
)
oxml = pytest.importorskip("docx.oxml")

_NSDECLS = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
    'wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml"'
)

_WPS_GRAPHIC = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"


def _vml_textbox(text: str) -> str:
    """A paragraph whose only content is a VML text box."""
    return f"""
<w:p {_NSDECLS}>
  <w:r>
    <w:pict>
      <v:shape id="_x0000_s1026" type="#_x0000_t202"
               style="width:180pt;height:60pt">
        <v:textbox>
          <w:txbxContent>
            <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
          </w:txbxContent>
        </v:textbox>
      </v:shape>
    </w:pict>
  </w:r>
</w:p>
"""


def _alternate_content_textbox(text: str) -> str:
    """The same callout as Word writes it: DrawingML plus a VML fallback."""
    return f"""
<w:p {_NSDECLS}>
  <w:r>
    <mc:AlternateContent>
      <mc:Choice Requires="wps">
        <w:drawing>
          <wp:inline>
            <wp:extent cx="1828800" cy="457200"/>
            <a:graphic>
              <a:graphicData uri="{_WPS_GRAPHIC}">
                <wps:wsp>
                  <wps:txbx>
                    <w:txbxContent>
                      <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
                    </w:txbxContent>
                  </wps:txbx>
                </wps:wsp>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </mc:Choice>
      <mc:Fallback>
        <w:pict>
          <v:shape id="_x0000_s1027" type="#_x0000_t202">
            <v:textbox>
              <w:txbxContent>
                <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
              </w:txbxContent>
            </v:textbox>
          </v:shape>
        </w:pict>
      </mc:Fallback>
    </mc:AlternateContent>
  </w:r>
</w:p>
"""


def _insert_after(paragraph, xml: str) -> None:
    """Insert a raw ``w:p`` right after ``paragraph``.

    Going through ``add_paragraph`` keeps the insert point legal: appending to
    ``document.element.body`` directly puts the paragraph after ``w:sectPr``,
    which is not the position Word writes.
    """
    paragraph._p.addnext(oxml.parse_xml(xml))


def _parse(document, tmp_path) -> dict:
    path = tmp_path / "textbox.docx"
    document.save(str(path))
    return DOCXParser().parse(str(path))


def test_body_text_box_text_is_extracted(tmp_path):
    document = docx.Document()
    document.add_paragraph("BODY_TEXT")
    _insert_after(document.paragraphs[-1], _vml_textbox("CALLOUT_TEXT"))

    result = _parse(document, tmp_path)

    assert "BODY_TEXT" in result["full_text"]
    assert "CALLOUT_TEXT" in result["full_text"]


def test_alternate_content_text_box_is_extracted_once(tmp_path):
    document = docx.Document()
    document.add_paragraph("BODY_TEXT")
    _insert_after(document.paragraphs[-1], _alternate_content_textbox("CALLOUT_TEXT"))

    result = _parse(document, tmp_path)

    assert result["full_text"].count("CALLOUT_TEXT") == 1


def test_text_box_in_table_cell_is_extracted(tmp_path):
    document = docx.Document()
    table = document.add_table(rows=1, cols=1)
    _insert_after(table.cell(0, 0).paragraphs[0], _vml_textbox("CELL_CALLOUT"))

    result = _parse(document, tmp_path)

    assert "CELL_CALLOUT" in result["tables"][0]["rows"][0][0]


def test_section_content_includes_text_box_text(tmp_path):
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    _insert_after(document.paragraphs[-1], _vml_textbox("CALLOUT_TEXT"))

    result = _parse(document, tmp_path)

    assert "CALLOUT_TEXT" in result["sections"][0]["content"]


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
def test_text_box_preserves_tabs_breaks_and_carriage_returns(tmp_path, textbox):
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    xml = textbox("LEFT").replace(
        "<w:t>LEFT</w:t>",
        "<w:t>LEFT</w:t><w:tab/><w:t>MID</w:t>"
        "</w:r><w:r><w:br/><w:t>END</w:t><w:cr/><w:t>CR_TEXT</w:t>",
    )
    _insert_after(document.paragraphs[-1], xml)

    result = _parse(document, tmp_path)

    expected = "LEFT\tMID\nEND\nCR_TEXT"
    assert result["paragraphs"][-1] == expected
    assert result["full_text"].count(expected) == 1
    assert result["sections"][0]["content"] == expected + "\n\n"


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
@pytest.mark.parametrize(
    ("replacement", "expected"),
    [
        ("<w:tab/><w:t>EDGE</w:t><w:br/>", "\tEDGE\n"),
        ("<w:tab/>", "\t"),
        ("<w:cr/>", "\n"),
    ],
)
def test_text_box_keeps_edge_and_separator_only_content(
    tmp_path, textbox, replacement, expected
):
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    xml = textbox("EDGE").replace("<w:t>EDGE</w:t>", replacement)
    _insert_after(document.paragraphs[-1], xml)

    result = _parse(document, tmp_path)

    assert result["paragraphs"][-1] == expected
    assert result["full_text"].endswith(expected)
    assert result["sections"][0]["content"] == expected + "\n\n"


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
def test_text_box_in_table_preserves_edge_separators(tmp_path, textbox):
    document = docx.Document()
    cell = document.add_table(rows=1, cols=1).cell(0, 0)
    xml = textbox("EDGE").replace("<w:t>EDGE</w:t>", "<w:tab/><w:t>EDGE</w:t><w:br/>")
    _insert_after(cell.paragraphs[0], xml)

    result = _parse(document, tmp_path)

    assert result["tables"][0]["rows"][0][0] == "\tEDGE\n"


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
def test_text_box_ignores_space_only_content(tmp_path, textbox):
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    _insert_after(document.paragraphs[-1], textbox("   "))

    result = _parse(document, tmp_path)

    assert result["paragraphs"] == ["Heading One"]
    assert result["sections"][0]["content"] == ""


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
@pytest.mark.parametrize("box_text", ["", "   ", "BOX"])
def test_text_box_preserves_surrounding_cell_whitespace(tmp_path, textbox, box_text):
    document = docx.Document()
    cell = document.add_table(rows=1, cols=1).cell(0, 0)
    cell.paragraphs[0].text = "  FIRST  "
    _insert_after(cell.paragraphs[0], textbox(box_text))
    cell.add_paragraph("  LAST  ")

    result = _parse(document, tmp_path)

    assert result["tables"][0]["rows"][0][0] == (
        "FIRST  \n" + box_text.strip() + "\n  LAST"
    )


@pytest.mark.parametrize("textbox", [_vml_textbox, _alternate_content_textbox])
def test_text_box_preserves_anchor_paragraph_normalization(tmp_path, textbox):
    document = docx.Document()
    document.add_heading("Heading One", level=1)
    paragraph = document.add_paragraph("  HOST  ")
    paragraph._p.append(oxml.parse_xml(textbox("BOX"))[0])

    result = _parse(document, tmp_path)

    assert result["paragraphs"][-1] == "HOST  \nBOX"
    assert result["full_text"] == "Heading One\n\nHOST  \nBOX"
    assert result["sections"][0]["content"] == "HOST  \nBOX\n\n"
