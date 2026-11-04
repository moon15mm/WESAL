"""Exports: CSV (UTF-8 BOM for Excel), XLSX (RTL sheets for Arabic/Urdu) and PDF (WeasyPrint,
embedded IBM Plex Sans Arabic / Noto Nastaliq Urdu / Noto Sans Devanagari / Inter)."""
from __future__ import annotations

import csv
import html
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.core.i18n import direction, t

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def to_csv(columns: list[tuple[str, str]], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow([_sanitize_cell(_fmt(r.get(k))) for k, _ in columns])
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _sanitize_cell(value: str) -> str:
    # prevent CSV/Excel formula injection
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") and not _is_number(value) else value


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def to_xlsx(title: str, columns: list[tuple[str, str]], rows: list[dict], locale: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.sheet_view.rightToLeft = direction(locale) == "rtl"
    ws.append([label for _, label in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="102B46")
        cell.alignment = Alignment(horizontal="center")
    for r in rows:
        values = []
        for k, _ in columns:
            v = r.get(k)
            if isinstance(v, Decimal):
                v = float(v)
            elif isinstance(v, datetime):
                v = v.replace(tzinfo=None)
            elif isinstance(v, str):
                v = _sanitize_cell(v)
            values.append(v)
        ws.append(values)
    for i, (k, label) in enumerate(columns, start=1):
        width = max([len(label)] + [len(_fmt(r.get(k))) for r in rows[:200]]) + 2
        ws.column_dimensions[ws.cell(1, i).column_letter].width = min(width, 50)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


ARABIC_RANGE = "U+0600-06FF, U+0750-077F, U+0870-088E, U+0890-0891, U+0898-08E1, U+08E3-08FF, U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, U+FE70-FE74, U+FE76-FEFC"
LATIN_RANGE = "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD"
DEVA_RANGE = "U+0900-097F, U+1CD0-1CF9, U+200C-200D, U+20A8, U+20B9, U+25CC, U+A830-A839, U+A8E0-A8FF"


def _font_css() -> str:
    faces = [
        ("WesalArabic", "ibm-plex-sans-arabic-arabic-400-normal.woff", 400, ARABIC_RANGE),
        ("WesalArabic", "ibm-plex-sans-arabic-arabic-700-normal.woff", 700, ARABIC_RANGE),
        ("WesalArabic", "ibm-plex-sans-arabic-latin-400-normal.woff", 400, LATIN_RANGE),
        ("WesalArabic", "ibm-plex-sans-arabic-latin-700-normal.woff", 700, LATIN_RANGE),
        ("WesalUrdu", "noto-nastaliq-urdu-arabic-400-normal.woff", 400, ARABIC_RANGE),
        ("WesalUrdu", "noto-nastaliq-urdu-arabic-700-normal.woff", 700, ARABIC_RANGE),
        ("WesalDeva", "noto-sans-devanagari-devanagari-400-normal.woff", 400, DEVA_RANGE),
        ("WesalDeva", "noto-sans-devanagari-devanagari-700-normal.woff", 700, DEVA_RANGE),
        ("WesalLatin", "inter-latin-400-normal.woff", 400, LATIN_RANGE),
        ("WesalLatin", "inter-latin-700-normal.woff", 700, LATIN_RANGE),
    ]
    return "\n".join(f"@font-face {{ font-family: '{f}'; src: url('{(FONTS / file).as_uri()}'); font-weight: {w}; unicode-range: {r}; }}"
                     for f, file, w, r in faces)


FAMILY = {"ar": "'WesalLatin', 'WesalArabic'", "ur": "'WesalUrdu', 'WesalArabic', 'WesalLatin'",
          "hi": "'WesalDeva', 'WesalLatin', 'WesalArabic'", "en": "'WesalLatin', 'WesalArabic', 'WesalDeva'"}

BASE_CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #718096; } }
body { font-size: 9.5pt; color: #172B3A; line-height: 1.55; }
.header { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #20B99A;
  padding-bottom: 8px; margin-bottom: 14px; }
.brand { font-size: 18pt; font-weight: 700; color: #102B46; }
.brand small { display: block; font-size: 8pt; color: #718096; font-weight: 400; }
h1 { font-size: 14pt; color: #102B46; margin: 0 0 4px; }
h2 { font-size: 11pt; color: #102B46; margin: 16px 0 6px; }
.meta { color: #718096; font-size: 8.5pt; }
table { width: 100%; border-collapse: collapse; margin-top: 6px; }
th { background: #102B46; color: #fff; font-weight: 700; padding: 6px; font-size: 8.5pt; text-align: start; }
td { border-bottom: 1px solid #E2E8F0; padding: 5px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #F5F8FA; }
.num { text-align: end; white-space: nowrap; font-variant-numeric: tabular-nums; }
.grid { display: flex; gap: 12px; }
.card { flex: 1; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 10px; }
.card b { display: block; color: #102B46; margin-bottom: 2px; }
.totals { width: 45%; margin-inline-start: auto; margin-top: 10px; }
.totals td { border: none; padding: 3px 6px; }
.totals tr.grand td { border-top: 2px solid #102B46; font-weight: 700; font-size: 11pt; }
.note { margin-top: 14px; padding: 8px 10px; background: #F5F8FA; border-inline-start: 3px solid #E5A13B; font-size: 8pt; color: #4A5568; }
.ltr { direction: ltr; unicode-bidi: embed; }
"""


def logo_svg() -> str:
    return ('<svg width="34" height="34" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="64" height="64" rx="16" fill="#102B46"/>'
            '<path d="M18 22 L32 44 L46 22" stroke="#20B99A" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            '<line x1="18" y1="22" x2="46" y2="22" stroke="#55D6B0" stroke-width="2.5" stroke-linecap="round" opacity=".7"/>'
            '<circle cx="18" cy="22" r="6" fill="#55D6B0"/><circle cx="46" cy="22" r="6" fill="#55D6B0"/>'
            '<circle cx="32" cy="44" r="6.5" fill="#20B99A"/></svg>')


def html_document(title: str, locale: str, body: str) -> str:
    d = direction(locale)
    return (f"<!doctype html><html lang='{locale}' dir='{d}'><head><meta charset='utf-8'><style>{_font_css()}{BASE_CSS}"
            f"body {{ font-family: {FAMILY.get(locale, FAMILY['en'])}; }}</style><title>{html.escape(title)}</title></head>"
            f"<body><div class='header'><div class='brand'>{logo_svg()} {html.escape(t('brand.name', locale))}"
            f"<small>{html.escape(t('brand.tagline', locale))}</small></div>"
            f"<div class='meta'>{html.escape(t('pdf.generated_at', locale))}: <span class='ltr'>{datetime.now().strftime('%Y-%m-%d %H:%M')}</span></div></div>"
            f"{body}</body></html>")


def table_html(columns: list[tuple[str, str]], rows: list[dict], numeric: set[str] = frozenset()) -> str:
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body = "".join("<tr>" + "".join(f"<td class='{'num' if k in numeric else ''}'>{html.escape(_fmt(r.get(k)))}</td>"
                                     for k, _ in columns) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def to_pdf_html(doc: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=doc, base_url=str(FONTS)).write_pdf()


def report_pdf(title: str, locale: str, sections: list[dict], subtitle: str = "") -> bytes:
    body = f"<h1>{html.escape(title)}</h1><div class='meta'>{html.escape(subtitle)}</div>"
    for s in sections:
        body += f"<h2>{html.escape(s['heading'])}</h2>" + table_html(s["columns"], s["rows"], set(s.get("numeric", [])))
    return to_pdf_html(html_document(title, locale, body))
