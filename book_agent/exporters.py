from __future__ import annotations

import base64
import html
import io
import textwrap
import zipfile


def make_docx(title: str, chapters: list[tuple[str, str]]) -> bytes:
    body = [
        "<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>"
        + html.escape(title)
        + "</w:t></w:r></w:p>"
    ]
    for chapter_title, text in chapters:
        body.append("<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>" + html.escape(chapter_title) + "</w:t></w:r></w:p>")
        for para in text.splitlines():
            if para.strip():
                body.append("<w:p><w:r><w:t>" + html.escape(para) + "</w:t></w:r></w:p>")
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + "<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
    return buffer.getvalue()


def make_pdf(title: str, chapters: list[tuple[str, str]]) -> bytes:
    # Minimal single-font PDF. Built-in Helvetica is ASCII-oriented, so non-ASCII
    # characters are replaced for broad reader compatibility in the no-dependency MVP.
    text = title + "\n\n" + "\n\n".join(f"{chapter_title}\n{text}" for chapter_title, text in chapters)
    safe_lines = [
        line.encode("latin-1", "replace").decode("latin-1")
        for line in textwrap.wrap(text.replace("\r", ""), width=88, replace_whitespace=False)
    ][:60]
    commands = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    for line in safe_lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({escaped}) Tj")
        commands.append("T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{idx} 0 obj\n".encode("ascii"))
        output.write(obj)
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return output.getvalue()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
