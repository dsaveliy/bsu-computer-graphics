"""Сборка отчёта: один текст -> отчёт.docx (python-docx) и отчёт.pdf (reportlab).

Запуск: python report/build.py  (сначала python experiments.py и python report/figures.py).
Текст и таблицы — в body.py, здесь только вёрстка (та же, что в отчёте к лабораторной 2).
Если рядом лежит screenshot.png, он вставляется как рисунок окна приложения.
"""
import re
from pathlib import Path

from body import BODY, TITLE

HERE = Path(__file__).parent
FIG = HERE / "figures"
SCREENSHOT = HERE / "screenshot.png"


# --- разбор разметки -------------------------------------------------------------------------

TAG = re.compile(r"</?(b|i|sub|sup)>")


def runs(text):
    """Строка с разметкой -> [(фрагмент, {"b", "i", "sub", "sup"})]."""
    out, active, pos = [], set(), 0
    for m in TAG.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], frozenset(active)))
        (active.discard if m.group(0).startswith("</") else active.add)(m.group(1))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], frozenset(active)))
    return out


def numbered(body):
    """Подставить сквозные номера рисунков и таблиц: ("fig", …) -> (…, номер)."""
    fig = table = 0
    for block in body:
        kind = block[0]
        if kind in ("fig", "screenshot"):
            fig += 1
            yield (kind, fig, *block[1:])
        elif kind == "table":
            table += 1
            yield (kind, table, *block[1:])
        else:
            yield block


# --- DOCX ------------------------------------------------------------------------------------

def build_docx(path):
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21)
    sec.left_margin, sec.right_margin = Cm(3), Cm(1.5)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    sec.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Times New Roman", Pt(14)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    pf = normal.paragraph_format
    pf.line_spacing, pf.space_after, pf.space_before = 1.5, Pt(0), Pt(0)

    def para(text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, indent=1.25, size=None, bold=False, **fmt):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.first_line_indent = Cm(indent)
        for key, value in fmt.items():
            setattr(p.paragraph_format, key, value)
        for chunk, style in runs(text):
            r = p.add_run(chunk)
            r.bold = bold or "b" in style
            r.italic = "i" in style
            r.font.subscript = "sub" in style
            r.font.superscript = "sup" in style
            if size:
                r.font.size = Pt(size)
        return p

    # титульный лист
    center = WD_ALIGN_PARAGRAPH.CENTER
    for line in TITLE["top"]:
        para(line, center, 0, line_spacing=1.0)
    for _ in range(7):
        para("", center, 0)
    for k, line in enumerate(TITLE["name"]):
        para(line, center, 0, bold=k == 0, size=16 if k == 0 else None)
    for _ in range(6):
        para("", center, 0)
    for line in TITLE["who"]:
        para(line, WD_ALIGN_PARAGRAPH.LEFT, 0, left_indent=Cm(10), line_spacing=1.0)
    for _ in range(6):
        para("", center, 0)
    para(TITLE["city"], center, 0).runs[0].add_break(WD_BREAK.PAGE)

    # номер страницы внизу по центру, кроме титульного
    footer = sec.footer.paragraphs[0]
    footer.alignment = center
    run = footer.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)

    text_width = 16.5
    for block in numbered(BODY):
        kind = block[0]
        if kind == "h":
            para(block[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, space_before=Pt(12), space_after=Pt(6),
                 keep_with_next=True)
        elif kind == "h2":
            para(block[1], WD_ALIGN_PARAGRAPH.LEFT, bold=True, space_before=Pt(6), space_after=Pt(3),
                 keep_with_next=True)
        elif kind == "p":
            para(block[1])
        elif kind == "list":
            for item in block[1]:
                para(item)
        elif kind == "f":
            p = para("\t" + block[1] + f"\t({block[2]})", WD_ALIGN_PARAGRAPH.LEFT, 0,
                     space_before=Pt(3), space_after=Pt(3))
            p.paragraph_format.tab_stops.add_tab_stop(Cm(text_width / 2), WD_TAB_ALIGNMENT.CENTER)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(text_width), WD_TAB_ALIGNMENT.RIGHT)
        elif kind in ("fig", "screenshot"):
            if kind == "fig":
                _, n, file, caption, width = block
                image = FIG / file
            else:
                _, n, caption = block
                image, width = SCREENSHOT, text_width
            p = para("", center, 0, keep_with_next=True, space_before=Pt(6))
            if image.exists():
                p.add_run().add_picture(str(image), width=Cm(width))
            else:
                p.add_run("[сюда вставить скриншот окна приложения]").italic = True
            para(f"Рисунок {n} – {caption}", center, 0, space_after=Pt(6))
        elif kind == "table":
            _, n, caption, rows, widths = block
            para(f"Таблица {n} – {caption}", WD_ALIGN_PARAGRAPH.LEFT, 0, space_before=Pt(6),
                 keep_with_next=True)
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False
            for column, width in zip(table.columns, widths):
                column.width = Cm(width)
            for i, row in enumerate(rows):
                props = table.rows[i]._tr.get_or_add_trPr()
                props.append(OxmlElement("w:cantSplit"))
                if i == 0:
                    props.append(OxmlElement("w:tblHeader"))
                for j, value in enumerate(row):
                    cell = table.cell(i, j)
                    cell.width = Cm(widths[j])
                    p = cell.paragraphs[0]
                    p.paragraph_format.line_spacing = 1.0
                    p.paragraph_format.first_line_indent = Cm(0)
                    # Таблицы короткие: держим строки вместе, чтобы заголовок и данные
                    # не разъезжались по страницам при открытии в Word.
                    p.paragraph_format.keep_with_next = i < len(rows) - 1
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 or i == 0 else center
                    r = p.add_run(value)
                    r.font.size = Pt(12)
                    r.bold = i == 0
            para("", line_spacing=1.0)
    doc.save(path)


# --- PDF -------------------------------------------------------------------------------------

def build_pdf(path):
    from PIL import Image as PILImage
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    fonts = Path("/System/Library/Fonts/Supplemental")
    for name, file in [("TNR", "Times New Roman"), ("TNR-B", "Times New Roman Bold"),
                       ("TNR-I", "Times New Roman Italic"), ("TNR-BI", "Times New Roman Bold Italic")]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / f"{file}.ttf")))
    pdfmetrics.registerFontFamily("TNR", normal="TNR", bold="TNR-B", italic="TNR-I", boldItalic="TNR-BI")

    def style(name, **kw):
        base = dict(fontName="TNR", fontSize=14, leading=21, alignment=TA_JUSTIFY, firstLineIndent=1.25 * cm)
        base.update(kw)
        return ParagraphStyle(name, **base)

    body = style("body")
    center = style("center", alignment=TA_CENTER, firstLineIndent=0)
    left = style("left", alignment=TA_LEFT, firstLineIndent=0)
    h1 = style("h1", alignment=TA_LEFT, spaceBefore=12, spaceAfter=6, keepWithNext=1)
    h2 = style("h2", alignment=TA_LEFT, spaceBefore=6, spaceAfter=3, keepWithNext=1)
    cell = style("cell", fontSize=12, leading=14, alignment=TA_LEFT, firstLineIndent=0)
    cell_c = style("cell_c", fontSize=12, leading=14, alignment=TA_CENTER, firstLineIndent=0)
    number = style("number", alignment=TA_RIGHT, firstLineIndent=0)

    def bold(text):
        return f"<b>{text}</b>"

    story = []
    for line in TITLE["top"]:
        story.append(Paragraph(line, style("t", alignment=TA_CENTER, firstLineIndent=0, leading=17)))
    story.append(Spacer(1, 6 * cm))
    for k, line in enumerate(TITLE["name"]):
        story.append(Paragraph(bold(line) if k == 0 else line, style("n", alignment=TA_CENTER, firstLineIndent=0,
                                                                     fontSize=16 if k == 0 else 14)))
    story.append(Spacer(1, 4 * cm))
    for line in TITLE["who"]:
        story.append(Paragraph(line or "&nbsp;", style("w", alignment=TA_LEFT, firstLineIndent=0,
                                                       leftIndent=10 * cm, leading=17)))
    story.append(Spacer(1, 5 * cm))
    story += [Paragraph(TITLE["city"], center), PageBreak()]

    text_width = 16.5 * cm
    for block in numbered(BODY):
        kind = block[0]
        if kind == "h":
            story.append(Paragraph(bold(block[1]), h1))
        elif kind == "h2":
            story.append(Paragraph(bold(block[1]), h2))
        elif kind == "p":
            story.append(Paragraph(block[1], body))
        elif kind == "list":
            story += [Paragraph(item, body) for item in block[1]]
        elif kind == "f":
            t = Table([["", Paragraph(block[1], center), Paragraph(f"({block[2]})", number)]],
                      colWidths=[1.5 * cm, text_width - 3 * cm, 1.5 * cm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            story.append(t)
        elif kind in ("fig", "screenshot"):
            if kind == "fig":
                _, n, file, caption, width = block
                image = FIG / file
            else:
                _, n, caption = block
                image, width = SCREENSHOT, 16.5
            if image.exists():
                w, h = PILImage.open(image).size
                picture = Image(str(image), width=width * cm, height=width * cm * h / w)
            else:
                picture = Paragraph("<i>[сюда вставить скриншот окна приложения]</i>", center)
            story.append(KeepTogether([Spacer(1, 6), picture,
                                       Paragraph(f"Рисунок {n} – {caption}", center), Spacer(1, 6)]))
        elif kind == "table":
            _, n, caption, rows, widths = block
            data = [[Paragraph(bold(v) if i == 0 else v, cell if j == 0 or i == 0 else cell_c)
                     for j, v in enumerate(row)] for i, row in enumerate(rows)]
            t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"),
                                   ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            story.append(KeepTogether([Spacer(1, 6), Paragraph(f"Таблица {n} – {caption}", left), t]))
            story.append(Spacer(1, 10))

    def page_number(canvas, doc):
        canvas.setFont("TNR", 12)
        canvas.drawCentredString(A4[0] / 2 + 0.75 * cm, 1.2 * cm, str(doc.page))

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=3 * cm, rightMargin=1.5 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title="Лабораторная работа 3",
                            author="Давыдович Савелий")
    doc.build(story, onLaterPages=page_number)


if __name__ == "__main__":
    build_docx(HERE / "отчёт.docx")
    build_pdf(HERE / "отчёт.pdf")
    print("Готово:", HERE / "отчёт.docx", HERE / "отчёт.pdf")
