"""Small inline charts for the dashboard and report topics."""

from html import escape

TONES = {
    "HIGH": "#9b2c2c",
    "MEDIUM": "#9a6b12",
    "LOW": "#1b4f8a",
    "INFO": "#8aa0bd",
}
BLUES = ("#0c2344", "#1b4f8a", "#3d74b8", "#7ea4d6", "#b9d0ec")
TOPIC_KINDS = {
    "housekeeping": {"housekeeping"},
    "governance": {"governance"},
    "cost": {"cost", "cost-inventory"},
}


def when(value):
    return str(value or "").replace("T", " ")[:16]


def present_scans(rows):
    presented = []
    for row in rows:
        summary = row.get("summary") or {}
        counts = summary.get("counts") or {}
        presented.append(
            {
                **row,
                "when": when(row.get("created_at")),
                "high": int(counts.get("HIGH") or 0),
                "medium": int(counts.get("MEDIUM") or 0),
                "total": int(summary.get("total") or 0),
                "saving": summary.get("monthly_saving"),
            }
        )
    return presented


def topic_visual(domain, scans):
    matching = [row for row in scans if row.get("kind") in TOPIC_KINDS.get(domain, set())]
    latest = matching[0] if matching else None
    series = _series(latest.get("summary") if latest else None)
    caption = "No scan has been stored for this topic yet."
    if latest:
        caption = (
            f"Latest {latest.get('kind', '').replace('-', ' ')} read for "
            f"{latest.get('account_name') or 'the account'} in {latest.get('region') or 'the selected region'}."
        )
    return {
        "chart": bar_svg(series),
        "caption": caption,
        "rows": matching[:6],
        "empty": not series,
    }


def factual_points(scans, kinds):
    """Stored breakdown only. Empty when no scan recorded counts."""
    for row in scans:
        if row.get("kind") not in kinds:
            continue
        series = _series(row.get("summary"))
        if not series:
            continue
        caption = (
            f"{row.get('account_name') or 'Account'} · {row.get('region') or 'region'} · {row.get('when')}. "
            "Figures are the counts saved with that scan."
        )
        return series, caption
    return [], ""


def factual_mix(scans, kinds):
    """Chart only a stored scan that actually recorded a breakdown."""
    series, caption = factual_points(scans, kinds)
    if not series:
        return "", ""
    return bar_svg(series), caption


def bar_svg(items):
    if not items:
        return ""
    row_height = 36
    height = len(items) * row_height
    peak = max(item["value"] for item in items) or 1
    parts = [
        f'<svg class="chart" viewBox="0 0 420 {height}" role="img" aria-label="Breakdown chart">'
    ]
    for index, item in enumerate(items):
        y = index * row_height + 8
        width = 220 * (item["value"] / peak)
        tone = item.get("tone") or BLUES[index % len(BLUES)]
        parts.append(
            f'<text x="0" y="{y + 12}" font-size="12" '
            f'style="fill:var(--muted);font-family:Plus Jakarta Sans,sans-serif">{escape(item["label"])}</text>'
            f'<rect x="118" y="{y}" width="220" height="14" rx="7" style="fill:var(--soft)"/>'
            f'<rect x="118" y="{y}" width="{width:.1f}" height="14" rx="7" fill="{tone}"/>'
            f'<text x="348" y="{y + 12}" font-size="12" font-weight="600" '
            f'style="fill:var(--ink);font-family:Plus Jakarta Sans,sans-serif">{int(item["value"])}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _series(summary):
    summary = summary or {}
    pillars = summary.get("pillars") or {}
    if any(pillars.values()):
        return [
            {"label": name, "value": int(value or 0), "tone": BLUES[index % len(BLUES)]}
            for index, (name, value) in enumerate(pillars.items())
            if value
        ]
    counts = summary.get("counts") or {}
    items = []
    for name in ("HIGH", "MEDIUM", "LOW", "INFO"):
        value = int(counts.get(name) or 0)
        if value:
            items.append({"label": name.title(), "value": value, "tone": TONES[name]})
    return items
