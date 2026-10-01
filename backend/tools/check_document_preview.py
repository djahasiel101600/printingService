"""Standalone checks for apps.orders.services.document_preview.

Run with:  python -m tools.check_document_preview   (from the backend folder)
Builds synthetic OOXML containers in-memory so the readers can be exercised
without committing binary fixtures to the repo.
"""
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.orders.services import document_preview as dp  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def zipped(parts: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def check_docx():
    document = f"""<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Quarterly Report</w:t></w:r></w:p>
<w:p><w:r><w:t>Revenue grew by 12 percent.</w:t></w:r></w:p>
<w:tbl>
  <w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Cost</w:t></w:r></w:p></w:tc></w:tr>
  <w:tr><w:tc><w:p><w:r><w:t>Ink</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>450</w:t></w:r></w:p></w:tc></w:tr>
</w:tbl></w:body></w:document>"""
    preview = dp.build_preview("report.docx", zipped({"word/document.xml": document}))
    assert preview.kind == "document", preview.kind
    texts = [b["text"] for b in preview.blocks]
    assert texts[0] == "Quarterly Report", texts
    assert preview.blocks[0]["type"] == "heading", preview.blocks[0]
    assert "Revenue grew by 12 percent." in texts, texts
    assert "Item | Cost" in texts, texts            # table row, joined once
    assert "Ink | 450" in texts, texts
    print("  docx  ->", preview.kind, texts)


def check_xlsx():
    strings = f'<?xml version="1.0"?><sst xmlns="{S}"><si><t>Paper</t></si><si><t>A4</t></si></sst>'
    sheet = f"""<?xml version="1.0"?><worksheet xmlns="{S}"><sheetData>
      <row r="1"><c t="s"><v>0</v></c><c t="s"><v>1</v></c></row>
      <row r="2"><c><v>250</v></c><c><v>75</v></c></row></sheetData></worksheet>"""
    preview = dp.build_preview("quote.xlsx", zipped({
        "xl/sharedStrings.xml": strings,
        "xl/worksheets/sheet1.xml": sheet,
    }))
    assert preview.kind == "spreadsheet", preview.kind
    rows = preview.blocks[0]["rows"]
    assert rows[0] == ["Paper", "A4"], rows      # shared strings resolved
    assert rows[1] == ["250", "75"], rows        # numeric cells kept
    print("  xlsx  ->", preview.kind, rows)


def check_pptx():
    slide = f"""<?xml version="1.0"?><p:sld xmlns:p="urn:p" xmlns:a="{A}">
      <a:p><a:r><a:t>Welcome Slide</a:t></a:r></a:p>
      <a:p><a:r><a:t>Bullet one</a:t></a:r></a:p></p:sld>"""
    preview = dp.build_preview("deck.pptx", zipped({"ppt/slides/slide1.xml": slide}))
    assert preview.kind == "slides", preview.kind
    block = preview.blocks[0]
    assert block["title"] == "Welcome Slide", block
    assert block["items"] == ["Welcome Slide", "Bullet one"], block
    print("  pptx  ->", preview.kind, block["items"])


def check_plain():
    text = dp.build_preview("notes.txt", b"Hello\n\nWorld")
    assert text.kind == "text"
    csv = dp.build_preview("rows.csv", b"name,qty\nink,3\n")
    assert csv.blocks[0]["rows"][0] == ["name", "qty"], csv.blocks
    print("  text  ->", [b["text"] for b in text.blocks])
    print("  csv   ->", csv.blocks[0]["rows"])


def check_errors():
    for name, payload in (("old.doc", b"\xd0\xcf\x11\xe0"), ("mystery.xyz", b"data")):
        try:
            dp.build_preview(name, payload)
        except dp.PreviewError as exc:
            print(f"  error -> {name}: {exc}")
        else:
            raise AssertionError(f"{name} should not be previewable")
    try:
        dp.build_preview("broken.docx", zipped({"word/document.xml": "<not xml"}))
    except dp.PreviewError as exc:
        print("  error -> broken.docx:", exc)
    else:
        raise AssertionError("corrupt docx should raise")


if __name__ == "__main__":
    check_docx()
    check_xlsx()
    check_pptx()
    check_plain()
    check_errors()
    print("document_preview: all checks passed")
