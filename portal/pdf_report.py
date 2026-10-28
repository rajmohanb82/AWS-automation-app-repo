"""PDF exports for housekeeping, cost, and the report library."""

import struct
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

STATIC = Path(__file__).resolve().parent / "static"
VAYU_LOGO = STATIC / "vayu-logo.png"
CLOUDSYNC_LOGO = STATIC / "cloudsync-logo.png"

INK = (12, 35, 68)
MUTED = (92, 109, 128)
BODY = (16, 24, 40)
LINE = (213, 224, 235)
PAPER = (243, 247, 251)
ORANGE = (255, 153, 0)
WHITE = (255, 255, 255)

NAMED_TONES = {
    "HIGH": (155, 44, 44),
    "MEDIUM": (154, 107, 18),
    "LOW": (27, 79, 138),
    "INFO": (138, 160, 189),
    "SECURITY": (155, 44, 44),
    "RELIABILITY": (27, 79, 138),
    "PERFORMANCE": (61, 116, 184),
}
PALETTE = (
    (255, 153, 0),
    (27, 79, 138),
    (12, 35, 68),
    (61, 116, 184),
    (154, 107, 18),
    (29, 107, 69),
    (138, 160, 189),
)

FINDING_COLUMNS = ("Severity", "Category", "Resource", "Finding", "Action")
FINDING_WIDTHS = (22, 28, 36, 46, 54)
COST_COLUMNS = ("Priority", "Service", "Resource", "Saving / month", "Action")
COST_WIDTHS = (22, 24, 38, 28, 74)


def _ascii(value):
    return str(value or "").encode("ascii", "replace").decode("ascii")


def _clip(value, limit):
    text = " ".join(str(value or "").split())
    if not text:
        return "-"
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _png_size(path):
    with open(path, "rb") as handle:
        handle.seek(16)
        return struct.unpack(">II", handle.read(8))


def _tone(label, index):
    key = str(label or "").upper().split(" ")[0]
    if key in NAMED_TONES:
        return NAMED_TONES[key]
    return PALETTE[index % len(PALETTE)]


def _number(value, money=False):
    number = float(value or 0)
    if money:
        if abs(number) >= 100:
            return f"${number:,.0f}"
        return f"${number:,.2f}"
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.1f}"


class ReportPDF(FPDF):
    def __init__(self, org, domain, code):
        super().__init__(format="A4", unit="mm")
        self.c_margin = 0.8
        self.org_label = _clip(org, 42)
        self.domain_label = _clip(domain, 28)
        self.code_label = _clip(code, 16) if code else ""

    def header(self):
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, self.w, 2.2, "F")
        x = 12
        if VAYU_LOGO.is_file():
            width, height = _png_size(VAYU_LOGO)
            logo_h = 13.5
            self.image(str(VAYU_LOGO), x=x, y=5.2, h=logo_h)
            x += logo_h * (width / height) + 4.5
        if CLOUDSYNC_LOGO.is_file():
            self.image(str(CLOUDSYNC_LOGO), x=x, y=7.6, h=8.6)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 8)
        self.set_xy(self.w - 74, 6.2)
        self.cell(62, 4, self.domain_label, align="R")
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 7.5)
        self.set_xy(self.w - 74, 11)
        right = self.code_label or "Operations report"
        self.cell(62, 4, right, align="R")
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.line(12, 21.4, self.w - 12, 21.4)
        self.set_text_color(*BODY)
        self.set_xy(self.l_margin, 26)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)
        self.line(12, self.get_y(), self.w - 12, self.get_y())
        self.set_y(-10.5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(90, 6, "Vayu Technologies")
        self.cell(0, 6, f"Page {self.page_no()}", align="R")


def render_document(document, org="Operations"):
    pdf = ReportPDF(org, document.get("domain") or "Report", document.get("code") or "")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(12, 26, 12)
    pdf.add_page()
    _title_block(pdf, document)
    _kpis(pdf, document.get("kpis") or [])
    _chart(
        pdf,
        document.get("chart_title") or "",
        document.get("chart") or [],
        money=bool(document.get("money")),
    )
    for section in document.get("sections") or []:
        _section(pdf, section, money=bool(section.get("money", document.get("money"))))
    _notes(pdf, document.get("notes") or [])
    return bytes(pdf.output())


def _title_block(pdf, document):
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 7.2, _ascii(document.get("title") or "Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.6)
    meta = "   |   ".join(
        part
        for part in (
            document.get("audience") or "",
            document.get("subtitle") or "",
        )
        if part
    )
    if meta:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 4.6, _ascii(meta), new_x="LMARGIN", new_y="NEXT")
    summary = document.get("summary") or ""
    if summary:
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*BODY)
        pdf.multi_cell(0, 4.8, _ascii(summary), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _kpis(pdf, kpis):
    items = [item for item in kpis if item.get("label")][:4]
    if not items:
        return
    gap = 2.4
    width = (pdf.epw - gap * (len(items) - 1)) / len(items)
    y = _ensure(pdf, 18)
    for index, item in enumerate(items):
        x = pdf.l_margin + index * (width + gap)
        pdf.set_fill_color(*PAPER)
        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.2)
        pdf.rect(x, y, width, 16, "DF")
        pdf.set_fill_color(*ORANGE)
        pdf.rect(x, y, 1.3, 16, "F")
        pdf.set_xy(x + 3.2, y + 2.2)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(width - 5, 4, _ascii(_clip(item["label"], 26)))
        pdf.set_xy(x + 3.2, y + 7.4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*INK)
        pdf.cell(width - 5, 6, _ascii(_clip(item.get("value"), 18)))
    pdf.set_y(y + 20)


def _chart(pdf, title, series, money=False):
    points = [item for item in series if float(item.get("value") or 0) > 0][:8]
    if not points:
        return
    row_h = 7.2
    block = 8 + row_h * len(points) + 3
    y = _ensure(pdf, min(block, 36))
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(0, 6, _ascii(title or "Breakdown"), new_x="LMARGIN", new_y="NEXT")
    peak = max(float(item["value"]) for item in points) or 1
    label_w = 46
    value_w = 22
    bar_max = pdf.epw - label_w - value_w
    for index, item in enumerate(points):
        row_y = pdf.get_y()
        if row_y + row_h > pdf.h - 16:
            pdf.add_page()
            row_y = pdf.get_y()
        pdf.set_xy(pdf.l_margin, row_y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(label_w, row_h, _ascii(_clip(item.get("label"), 26)))
        span = max(bar_max * (float(item["value"]) / peak), 1.2)
        pdf.set_fill_color(*_tone(item.get("label"), index))
        pdf.rect(pdf.l_margin + label_w, row_y + 2.1, span, 3.1, "F")
        pdf.set_xy(pdf.l_margin + label_w + bar_max, row_y)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*BODY)
        pdf.cell(value_w, row_h, _number(item["value"], money), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def _section(pdf, section, money=False):
    _ensure(pdf, 28)
    y = pdf.get_y()
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, y + 1.2, 2.2, 5.6, "F")
    pdf.set_xy(pdf.l_margin + 4.5, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, _ascii(_clip(section.get("title") or "Category", 80)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)
    _chart(pdf, section.get("chart_title") or "In this category", section.get("chart") or [], money=money)
    columns = list(section.get("columns") or [])
    rows = list(section.get("rows") or [])
    if columns and rows:
        _table(pdf, columns, rows, section.get("widths"), set(section.get("numeric") or []))
    omitted = int(section.get("omitted") or 0)
    if omitted:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(
            0,
            4.4,
            f"{omitted} additional rows were omitted from this category.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.ln(2.5)


def _table(pdf, columns, rows, weights, numeric):
    weights = list(weights or [1] * len(columns))
    if len(weights) != len(columns):
        weights = [1] * len(columns)
    total = sum(weights) or 1
    widths = [pdf.epw * weight / total for weight in weights]
    _table_header(pdf, columns, widths)
    for index, row in enumerate(rows):
        cells = [_ascii(_clip(cell, 180)) for cell in list(row)[: len(columns)]]
        while len(cells) < len(columns):
            cells.append("-")
        height = _row_height(pdf, widths, cells)
        if pdf.get_y() + height > pdf.h - 16:
            pdf.add_page()
            _table_header(pdf, columns, widths)
        fill = WHITE if index % 2 == 0 else PAPER
        _paint_row(pdf, pdf.get_y(), widths, cells, height, fill, numeric, bold=False)


def _table_header(pdf, columns, widths):
    pdf.set_font("Helvetica", "B", 8)
    height = 7.2
    if pdf.get_y() + height > pdf.h - 16:
        pdf.add_page()
    y = pdf.get_y()
    pdf.set_fill_color(*INK)
    pdf.rect(pdf.l_margin, y, pdf.epw, height, "F")
    x = pdf.l_margin
    pdf.set_text_color(*WHITE)
    for width, label in zip(widths, columns):
        pdf.set_xy(x, y + 1.6)
        pdf.cell(width, 4, _ascii(label))
        x += width
    pdf.set_y(y + height)
    pdf.set_text_color(*BODY)


def _row_height(pdf, widths, cells):
    pdf.set_font("Helvetica", "", 8)
    height = 7.4
    anchor = pdf.get_y()
    for width, text in zip(widths, cells):
        pdf.set_xy(pdf.l_margin, anchor)
        measured = pdf.multi_cell(
            max(width, 8),
            3.7,
            text or "-",
            dry_run=True,
            output="HEIGHT",
            align="LEFT",
        )
        height = max(height, float(measured) + 2.4)
    return min(height, 28)


def _paint_row(pdf, y, widths, cells, height, fill, numeric, bold):
    pdf.set_fill_color(*fill)
    pdf.rect(pdf.l_margin, y, pdf.epw, height, "F")
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.15)
    pdf.line(pdf.l_margin, y + height, pdf.l_margin + pdf.epw, y + height)
    pdf.set_font("Helvetica", "B" if bold else "", 8)
    pdf.set_text_color(*BODY)
    x = pdf.l_margin
    for index, (width, text) in enumerate(zip(widths, cells)):
        pdf.set_xy(x, y + 1.2)
        pdf.multi_cell(
            max(width, 8),
            3.7,
            text or "-",
            align="R" if index in numeric else "L",
            new_x="RIGHT",
            new_y="TOP",
        )
        x += width
    pdf.set_y(y + height)


def _notes(pdf, notes):
    lines = [_ascii(item).strip() for item in notes if str(item).strip()]
    if not lines:
        return
    _ensure(pdf, 24)
    y = pdf.get_y()
    pdf.set_fill_color(*ORANGE)
    pdf.rect(pdf.l_margin, y + 1.2, 2.2, 5.6, "F")
    pdf.set_xy(pdf.l_margin + 4.5, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, "How to read this report", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.4)
    for line in lines:
        pdf.set_fill_color(*PAPER)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*BODY)
        pdf.multi_cell(0, 4.4, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.4)


def _ensure(pdf, height):
    if pdf.get_y() + height > pdf.h - 16:
        pdf.add_page()
    return pdf.get_y()


def housekeeping_pdf(account_name, region, findings):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    document = _finding_document(
        "Housekeeping report",
        "Housekeeping",
        f"{account_name}   |   {region}   |   {stamp}",
        "Findings from the latest housekeeping scan, grouped by severity.",
        findings,
    )
    return render_document(document, org=account_name)


def cost_pdf(account_name, region, recommendations, notes):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    document = _cost_document(
        "Cost report",
        "Cost optimization",
        f"{account_name}   |   {region}   |   {stamp}",
        "Savings recommendations grouped by priority. Figures include the discounts returned by AWS.",
        recommendations,
        notes or [],
    )
    return render_document(document, org=account_name)


def _finding_document(title, domain, subtitle, summary, findings):
    counts = _count(findings, "severity")
    document = {
        "domain": domain,
        "title": title,
        "subtitle": subtitle,
        "summary": summary,
        "kpis": [
            {"label": "Findings", "value": str(len(findings))},
            {"label": "High", "value": str(counts.get("HIGH", 0))},
            {"label": "Medium", "value": str(counts.get("MEDIUM", 0))},
            {"label": "Low", "value": str(counts.get("LOW", 0))},
        ],
        "chart_title": "Findings by severity",
        "chart": [
            {"label": name.title(), "value": counts.get(name, 0)}
            for name in ("HIGH", "MEDIUM", "LOW", "INFO")
            if counts.get(name, 0)
        ],
        "money": False,
        "notes": [],
        "sections": [],
    }
    order = ("HIGH", "MEDIUM", "LOW", "INFO")
    for name in order:
        rows = [item for item in findings if (item.get("severity") or "INFO") == name]
        if rows:
            document["sections"].append(_finding_section(name.title(), rows))
    if not document["sections"]:
        document["sections"].append(_empty_section("Findings", FINDING_COLUMNS, FINDING_WIDTHS, "No findings matched this report."))
    return document


def _cost_document(title, domain, subtitle, summary, recommendations, notes):
    counts = _count(recommendations, "priority")
    total = round(sum(float(item.get("monthly_saving") or 0) for item in recommendations), 2)
    document = {
        "domain": domain,
        "title": title,
        "subtitle": subtitle,
        "summary": summary,
        "kpis": [
            {"label": "Recommendations", "value": str(len(recommendations))},
            {"label": "Monthly saving", "value": _number(total, money=True)},
            {"label": "High", "value": str(counts.get("HIGH", 0))},
            {"label": "Medium", "value": str(counts.get("MEDIUM", 0))},
        ],
        "chart_title": "Estimated monthly saving by service",
        "chart": _money_series(recommendations, lambda item: item.get("service") or "AWS"),
        "money": True,
        "notes": [str(item) for item in notes if str(item).strip()],
        "sections": [],
    }
    for name in ("HIGH", "MEDIUM", "LOW"):
        rows = [item for item in recommendations if (item.get("priority") or "LOW") == name]
        if rows:
            document["sections"].append(_cost_section(name.title(), rows))
    if not document["sections"]:
        document["sections"].append(
            _empty_section("Recommendations", COST_COLUMNS, COST_WIDTHS, "AWS returned no recommendations for this account and region.")
        )
    return document


def _finding_section(title, rows, limit=50, chart_title="By category", keyfn=None):
    shown = rows[:limit]
    keyfn = keyfn or (lambda item: item.get("category") or "Other")
    return {
        "title": f"{title} ({len(rows)})",
        "chart_title": chart_title,
        "chart": _count_series(shown, keyfn),
        "columns": FINDING_COLUMNS,
        "widths": FINDING_WIDTHS,
        "numeric": [],
        "rows": [_finding_row(item) for item in shown],
        "omitted": max(0, len(rows) - limit),
        "money": False,
    }


def _cost_section(title, rows, limit=50, chart_title="Saving by service", keyfn=None):
    shown = rows[:limit]
    keyfn = keyfn or (lambda item: item.get("service") or "AWS")
    return {
        "title": f"{title} ({len(rows)})",
        "chart_title": chart_title,
        "chart": _money_series(shown, keyfn),
        "columns": COST_COLUMNS,
        "widths": COST_WIDTHS,
        "numeric": [3],
        "rows": [_cost_row(item) for item in shown],
        "omitted": max(0, len(rows) - limit),
        "money": True,
    }


def _empty_section(title, columns, widths, message):
    blank = ["-"] * len(columns)
    blank[-1] = message
    return {
        "title": title,
        "chart": [],
        "columns": columns,
        "widths": widths,
        "numeric": [],
        "rows": [blank],
        "omitted": 0,
    }


def _finding_row(item):
    return [
        item.get("severity") or "INFO",
        _clip(item.get("category") or "Other", 32),
        _clip(item.get("resource_id") or "n/a", 42),
        _clip(item.get("title") or "Finding", 90),
        _clip(item.get("action") or "Review the resource.", 160),
    ]


def _cost_row(item):
    saving = float(item.get("monthly_saving") or 0)
    return [
        item.get("priority") or "LOW",
        _clip(item.get("service") or "AWS", 28),
        _clip(item.get("resource_name") or item.get("resource_id") or "resource", 42),
        _number(saving, money=True),
        _clip(item.get("action") or "Review the recommendation.", 160),
    ]


def _count(rows, key):
    counts = {}
    for item in rows:
        name = item.get(key) or "INFO"
        counts[name] = counts.get(name, 0) + 1
    return counts


def _count_series(rows, keyfn, limit=8):
    totals = {}
    for item in rows:
        name = keyfn(item) or "Other"
        totals[name] = totals.get(name, 0) + 1
    return _top_series(totals, limit)


def _money_series(rows, keyfn, limit=8):
    totals = {}
    for item in rows:
        name = keyfn(item) or "Other"
        totals[name] = round(totals.get(name, 0) + float(item.get("monthly_saving") or 0), 2)
    return _top_series(totals, limit)


def _top_series(totals, limit):
    ordered = sorted(totals, key=lambda name: (-float(totals[name]), str(name).lower()))
    series = [{"label": name, "value": totals[name]} for name in ordered[:limit] if float(totals[name])]
    rest = round(sum(float(totals[name]) for name in ordered[limit:]), 2)
    if rest:
        series.append({"label": "Other", "value": rest})
    return series
