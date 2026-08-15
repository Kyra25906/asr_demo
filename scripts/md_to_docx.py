"""把简单的 Markdown 转成 .docx（用标准库 zipfile 生成，不依赖第三方库）。

支持：标题 #/##/###、表格（含表头分隔行）、列表 -、引用块 >、行内 **加粗**、
行内 `代码`（等宽）、emoji（UTF-8 直写）。

用法：
    .venv\\Scripts\\python.exe scripts\\md_to_docx.py <输入.md> <输出.docx>
"""
import re
import sys
import zipfile
from pathlib import Path

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text: str, bold: bool = False, mono: bool = False) -> str:
    rpr_parts = []
    if bold:
        rpr_parts.append("<w:b/>")
    if mono:
        rpr_parts.append(
            '<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/>'
        )
    rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def inline(text: str) -> str:
    """处理行内 `code` 和 **bold**。"""
    out = []
    # 先按反引号拆 code 段
    for idx, seg in enumerate(text.split("`")):
        if idx % 2 == 1:  # code 段
            if seg:
                out.append(_run(seg, mono=True))
        else:
            # 在非 code 段里处理 **bold**
            for j, tok in enumerate(re.split(r"(\*\*.+?\*\*)", seg)):
                if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
                    out.append(_run(tok[2:-2], bold=True))
                elif tok:
                    out.append(_run(tok))
    return "".join(out)


def para(text: str, bold: bool = False, size: int | None = None,
         indent: int = 0) -> str:
    sz = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ""
    b = "<w:b/>" if bold else ""
    ind = f'<w:ind w:left="{indent}"/>' if indent else ""
    ppr = ""
    if sz or b or ind:
        ppr = f'<w:pPr>{ind}<w:rPr>{b}{sz}</w:rPr></w:pPr>'
    return f"<w:p>{ppr}{inline(text)}</w:p>"


def table(rows: list[list[str]]) -> str:
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/>'
        '<w:bottom w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/>'
        '<w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/>'
        "</w:tblBorders>"
    )
    xml = [f"<w:tbl><w:tblPr>{borders}</w:tblPr><w:tblGrid/>"]
    for i, row in enumerate(rows):
        xml.append("<w:tr>")
        for cell in row:
            xml.append(
                '<w:tc><w:tcPr><w:tcW w:w="2200" w:type="dxa"/></w:tcPr>'
                f"{para(cell, bold=(i == 0))}</w:tc>"
            )
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def convert(md_text: str) -> str:
    lines = md_text.split("\n")
    body: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if line.startswith("|"):
            raw: list[str] = []
            while i < len(lines) and lines[i].startswith("|"):
                raw.append(lines[i])
                i += 1
            parsed: list[list[str]] = []
            for r in raw:
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                # 跳过纯 --- | --- 分隔行
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                parsed.append(cells)
            if parsed:
                body.append(table(parsed))
            continue
        if line.startswith("### "):
            body.append(para(line[4:], bold=True, size=24)); i += 1; continue
        if line.startswith("## "):
            body.append(para(line[3:], bold=True, size=28)); i += 1; continue
        if line.startswith("# "):
            body.append(para(line[2:], bold=True, size=32)); i += 1; continue
        if line.startswith("> "):
            body.append(para(line[2:], indent=360)); i += 1; continue
        if line.startswith("- "):
            body.append(para(line, indent=360)); i += 1; continue
        if stripped == "":
            body.append("<w:p/>"); i += 1; continue
        body.append(para(line)); i += 1
    return "".join(body)


def build_docx(body_xml: str) -> bytes:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f"<w:document {W}><w:body>"
        f"{body_xml}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
        "</w:sectPr></w:body></w:document>"
    )
    buf = __import__("io").BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    md_text = src.read_text(encoding="utf-8")
    body_xml = convert(md_text)
    data = build_docx(body_xml)
    dst.write_bytes(data)
    print(f"OK: {dst} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
