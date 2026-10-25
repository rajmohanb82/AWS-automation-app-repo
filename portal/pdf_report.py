"""Plain PDF exports for housekeeping and cost results."""

from datetime import datetime, timezone

from fpdf import FPDF


def _ascii(value):
    return str(value or "").encode("ascii", "replace").decode("ascii")


def _pdf(title, subtitle, sections):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    def write(text, height, style="", size=10):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(0, height, _ascii(text), new_x="LMARGIN", new_y="NEXT")

    write(title, 9, "B", 16)
    write(subtitle, 6, "", 10)
    pdf.ln(2)
    for heading, lines in sections:
        write(heading, 7, "B", 12)
        if not lines:
            write("None.", 5, "", 9)
        for line in lines:
            write(line, 5, "", 9)
        pdf.ln(1)
    return bytes(pdf.output())


def housekeeping_pdf(account_name, region, findings):
    lines = []
    for finding in findings:
        lines.append(
            f"[{finding.get('severity', 'INFO')}] {finding.get('title', '')} | "
            f"{finding.get('resource_id', '')} | {finding.get('details', '')} | "
            f"Action: {finding.get('action', '')}"
        )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return _pdf(
        f"Housekeeping report: {account_name}",
        f"Region {region}. Generated {stamp}.",
        [("Findings", lines)],
    )


def cost_pdf(account_name, region, recommendations, notes):
    lines = []
    for row in recommendations:
        lines.append(
            f"[{row.get('priority', '')}] {row.get('service', '')} {row.get('resource_id', '')} | "
            f"{row.get('action', '')} | Saving ${row.get('monthly_saving', 0)} / month | "
            f"{row.get('source', '')} | {row.get('reasoning', '')}"
        )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return _pdf(
        f"Cost report: {account_name}",
        f"Region {region}. Generated {stamp}.",
        [("How to read this", notes or []), ("Recommendations", lines)],
    )
