"""Report library for housekeeping, governance, and cost."""

DOMAINS = (
    {
        "id": "housekeeping",
        "label": "Housekeeping",
        "headline": "Hygiene and exposure",
        "blurb": "What is idle, exposed, or drifting in the selected account, with the action each finding needs.",
    },
    {
        "id": "governance",
        "label": "Governance",
        "headline": "Well-Architected posture",
        "blurb": "The same evidence arranged by pillar, plus Trusted Advisor when the support plan allows it.",
    },
    {
        "id": "cost",
        "label": "Cost optimization",
        "headline": "Savings and inventory",
        "blurb": "Hub and Compute Optimizer savings when AWS returns them. Inventory estimates stay labeled as list price.",
    },
)

CATALOG = (
    {
        "id": "hk-executive",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-01",
        "title": "Executive briefing",
        "audience": "Leadership",
        "reads": "Housekeeping scan",
        "summary": "Severity totals and the findings most worth discussing in a readout.",
    },
    {
        "id": "hk-register",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-02",
        "title": "Findings register",
        "audience": "Operators",
        "reads": "Housekeeping scan",
        "summary": "Every finding from the scan, grouped by severity, with evidence and the recommended action.",
    },
    {
        "id": "hk-critical",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-03",
        "title": "High and medium issues",
        "audience": "Leadership",
        "reads": "Housekeeping scan",
        "summary": "Drops informational noise and keeps the issues that should be scheduled.",
    },
    {
        "id": "hk-security",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-04",
        "title": "Identity and data exposure",
        "audience": "Security",
        "reads": "Housekeeping scan",
        "summary": "IAM, S3, encryption, and public-access findings for a security review.",
    },
    {
        "id": "hk-network",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-05",
        "title": "Network perimeter",
        "audience": "Security",
        "reads": "Housekeeping scan",
        "summary": "Security groups, flow logs, and default-VPC findings that describe the perimeter.",
    },
    {
        "id": "hk-waste",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-06",
        "title": "Idle and unattached resources",
        "audience": "FinOps",
        "reads": "Housekeeping scan",
        "summary": "Stopped instances, unattached volumes, unused addresses, and idle gateways.",
    },
    {
        "id": "hk-actions",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-07",
        "title": "Remediation workbook",
        "audience": "Operators",
        "reads": "Housekeeping scan",
        "summary": "Findings grouped by the action to take, so a working session can move through them in batches.",
    },
    {
        "id": "hk-service",
        "domain": "housekeeping",
        "source": "checks",
        "code": "HK-08",
        "title": "Findings by service",
        "audience": "Operators",
        "reads": "Housekeeping scan",
        "summary": "The same scan split by service, for owners who only cover one part of the account.",
    },
    {
        "id": "gov-scorecard",
        "domain": "governance",
        "source": "checks",
        "code": "GV-01",
        "title": "Well-Architected scorecard",
        "audience": "Leadership",
        "reads": "Governance scan",
        "summary": "Finding counts for each pillar, a short sample from each, and Trusted Advisor when it is available.",
    },
    {
        "id": "gov-security",
        "domain": "governance",
        "source": "checks",
        "code": "GV-02",
        "title": "Security pillar",
        "audience": "Security",
        "reads": "Governance scan",
        "summary": "Posture findings mapped to the Security pillar, with documentation for each action.",
    },
    {
        "id": "gov-reliability",
        "domain": "governance",
        "source": "checks",
        "code": "GV-03",
        "title": "Reliability pillar",
        "audience": "Operations",
        "reads": "Governance scan",
        "summary": "Findings that affect recovery and visibility, including flow logs and related gaps.",
    },
    {
        "id": "gov-excellence",
        "domain": "governance",
        "source": "checks",
        "code": "GV-04",
        "title": "Operational excellence",
        "audience": "Operations",
        "reads": "Governance scan",
        "summary": "Alarm, runbook, and operational findings grouped under operational excellence.",
    },
    {
        "id": "gov-performance",
        "domain": "governance",
        "source": "checks",
        "code": "GV-05",
        "title": "Performance pillar",
        "audience": "Engineering",
        "reads": "Governance scan",
        "summary": "Lambda, EKS, and ECS findings that point at performance or sizing.",
    },
    {
        "id": "gov-cost",
        "domain": "governance",
        "source": "checks",
        "code": "GV-06",
        "title": "Cost pillar exceptions",
        "audience": "FinOps",
        "reads": "Governance scan",
        "summary": "Posture findings that land in the cost-optimization pillar, separate from the savings register.",
    },
    {
        "id": "gov-exceptions",
        "domain": "governance",
        "source": "checks",
        "code": "GV-07",
        "title": "High-severity exceptions",
        "audience": "Audit",
        "reads": "Governance scan",
        "summary": "Only high-severity findings, listed with pillar, resource, and evidence for an exception review.",
    },
    {
        "id": "gov-advisor",
        "domain": "governance",
        "source": "advisor",
        "code": "GV-08",
        "title": "Trusted Advisor digest",
        "audience": "Leadership",
        "reads": "Trusted Advisor",
        "summary": "Recommendation summaries from Trusted Advisor. Business Support or higher is required for this API.",
    },
    {
        "id": "cost-summary",
        "domain": "cost",
        "source": "native",
        "code": "CO-01",
        "title": "Savings briefing",
        "audience": "Leadership",
        "reads": "Cost Optimization Hub",
        "summary": "Monthly savings total, priority mix, and the ten largest opportunities from AWS recommendations.",
    },
    {
        "id": "cost-register",
        "domain": "cost",
        "source": "native",
        "code": "CO-02",
        "title": "Recommendation register",
        "audience": "FinOps",
        "reads": "Cost Optimization Hub",
        "summary": "The full recommendation list, including source, estimated saving, and the reasoning AWS supplied.",
    },
    {
        "id": "cost-priority",
        "domain": "cost",
        "source": "native",
        "code": "CO-03",
        "title": "High-value opportunities",
        "audience": "Leadership",
        "reads": "Cost Optimization Hub",
        "summary": "Recommendations estimated at $50 or more per month. Smaller items stay in the full register.",
    },
    {
        "id": "cost-rightsizing",
        "domain": "cost",
        "source": "native",
        "code": "CO-04",
        "title": "Rightsizing plan",
        "audience": "Engineering",
        "reads": "Cost Optimization Hub",
        "summary": "Scale, resize, and memory changes, without idle-resource deletions mixed in.",
    },
    {
        "id": "cost-idle",
        "domain": "cost",
        "source": "native",
        "code": "CO-05",
        "title": "Idle and removable spend",
        "audience": "FinOps",
        "reads": "Cost Optimization Hub",
        "summary": "Stop, terminate, release, and delete recommendations that remove spend rather than resize it.",
    },
    {
        "id": "cost-storage",
        "domain": "cost",
        "source": "native",
        "code": "CO-06",
        "title": "Storage optimization",
        "audience": "Engineering",
        "reads": "Cost Optimization Hub",
        "summary": "Volume, tier, and snapshot recommendations that change how data is stored.",
    },
    {
        "id": "cost-service",
        "domain": "cost",
        "source": "native",
        "code": "CO-07",
        "title": "Savings by service",
        "audience": "FinOps",
        "reads": "Cost Optimization Hub",
        "summary": "Recommendations rolled up by service, with a monthly subtotal for each group.",
    },
    {
        "id": "cost-inventory",
        "domain": "cost",
        "source": "inventory",
        "code": "CO-08",
        "title": "On-demand inventory estimate",
        "audience": "Finance",
        "reads": "Inventory estimate",
        "summary": "List-price inventory and documented rules. These figures are estimates, not the discounted bill.",
    },
)

PILLARS = (
    "Security",
    "Reliability",
    "Cost optimization",
    "Operational excellence",
    "Performance",
)

SECURITY_CATEGORIES = {"IAM", "S3", "KDS", "KFH"}
NETWORK_CATEGORIES = {"VPC", "Security Groups"}
SEVERITY_ORDER = ("HIGH", "MEDIUM", "LOW", "INFO")

METHODS = {
    ("housekeeping", "checks"): (
        "Produced from the console's read-only housekeeping checks for the selected account and region. "
        "No resource was changed."
    ),
    ("governance", "checks"): (
        "Produced from the same read-only checks, grouped with Well-Architected pillars. "
        "Trusted Advisor is included only on the scorecard, and only when the account's support plan allows the API."
    ),
    ("governance", "advisor"): (
        "Produced from the Trusted Advisor list-recommendations API in us-east-1. "
        "The API requires Business Support or a higher plan. Core posture checks are a separate report."
    ),
    ("cost", "native"): (
        "Savings come from Cost Optimization Hub when that API returns rows for this region, "
        "and include the account's pricing agreements. If the hub is unavailable, the console uses Compute Optimizer. "
        "A blank high-value or rightsizing section means this response had no rows in that cut, not that the account has no spend."
    ),
    ("cost", "inventory"): (
        "Inventory estimates use published on-demand prices and CloudWatch. "
        "They are not the discounted figure from Cost Optimization Hub."
    ),
}


def catalog_groups():
    grouped = {domain["id"]: [] for domain in DOMAINS}
    for report in CATALOG:
        grouped[report["domain"]].append(report)
    return [{**domain, "reports": grouped[domain["id"]]} for domain in DOMAINS]


def get_report(report_id):
    for report in CATALOG:
        if report["id"] == report_id:
            return report
    return None


def build_document(report, ctx):
    """Structured report: summary figures, one chart, then a chart and table per category."""
    import pdf_report

    findings = list(ctx.get("findings") or [])
    recommendations = list(ctx.get("recommendations") or [])
    notes = [str(item) for item in (ctx.get("notes") or []) if str(item).strip()]
    method = METHODS.get((report["domain"], report["source"]))
    if method:
        notes.append(method)
    domain = next((item["label"] for item in DOMAINS if item["id"] == report["domain"]), "Report")
    document = {
        "code": report.get("code") or "",
        "domain": domain,
        "title": report["title"],
        "audience": report.get("audience") or "",
        "summary": report.get("summary") or "",
        "kpis": [],
        "chart_title": "",
        "chart": [],
        "money": False,
        "notes": notes,
        "sections": [],
    }
    report_id = report["id"]
    if report_id in {"hk-executive", "hk-register", "hk-critical"}:
        chosen = findings
        order = SEVERITY_ORDER
        limit = 50
        if report_id == "hk-critical":
            chosen = [item for item in findings if item.get("severity") in {"HIGH", "MEDIUM"}]
            order = ("HIGH", "MEDIUM")
        if report_id == "hk-executive":
            limit = 12
        _finding_overview(document, chosen)
        for name in order:
            rows = [item for item in chosen if (item.get("severity") or "INFO") == name]
            if rows:
                document["sections"].append(pdf_report._finding_section(name.title(), rows, limit=limit))
    elif report_id == "hk-security":
        _grouped_findings(
            document,
            [item for item in findings if _is_security(item)],
            lambda item: item.get("category") or "Security",
        )
    elif report_id == "hk-network":
        _grouped_findings(
            document,
            [item for item in findings if (item.get("category") or "") in NETWORK_CATEGORIES],
            lambda item: item.get("category") or "Network",
        )
    elif report_id == "hk-waste":
        _grouped_findings(
            document,
            [item for item in findings if _is_waste(item)],
            lambda item: item.get("category") or "Waste",
        )
    elif report_id == "hk-actions":
        _grouped_findings(document, findings, lambda item: item.get("action") or "Review the resource")
    elif report_id == "hk-service":
        _grouped_findings(document, findings, lambda item: item.get("category") or "Other")
    elif report_id == "gov-scorecard":
        _scorecard_document(document, findings, ctx.get("pillars") or {}, ctx.get("trusted"))
    elif report_id in {"gov-security", "gov-reliability", "gov-excellence", "gov-performance", "gov-cost"}:
        pillar = {
            "gov-security": "Security",
            "gov-reliability": "Reliability",
            "gov-excellence": "Operational excellence",
            "gov-performance": "Performance",
            "gov-cost": "Cost optimization",
        }[report_id]
        chosen = [item for item in findings if item.get("pillar") == pillar]
        _finding_overview(document, chosen, chart_title="Findings by category")
        document["chart"] = pdf_report._count_series(chosen, lambda item: item.get("category") or "Other")
        if chosen:
            document["sections"].append(
                pdf_report._finding_section(
                    pillar,
                    chosen,
                    chart_title="By severity",
                    keyfn=lambda item: (item.get("severity") or "INFO").title(),
                )
            )
    elif report_id == "gov-exceptions":
        chosen = [item for item in findings if item.get("severity") == "HIGH"]
        _grouped_findings(document, chosen, lambda item: item.get("pillar") or "Unmapped")
    elif report_id == "gov-advisor":
        document["sections"].append(_advisor_section(ctx.get("trusted")))
        _advisor_overview(document, ctx.get("trusted"))
    elif report_id == "cost-priority":
        chosen = [item for item in recommendations if item.get("priority") == "HIGH"]
        _cost_overview(document, chosen)
        if chosen:
            document["sections"].append(
                pdf_report._cost_section(
                    "At least $50 per month",
                    chosen,
                    chart_title="Largest resources",
                    keyfn=lambda item: item.get("resource_name") or item.get("resource_id") or "resource",
                )
            )
    elif report_id in {"cost-rightsizing", "cost-idle", "cost-storage"}:
        bucket, title = {
            "cost-rightsizing": ("rightsizing", "Rightsizing"),
            "cost-idle": ("idle", "Idle and removable"),
            "cost-storage": ("storage", "Storage"),
        }[report_id]
        chosen = [item for item in recommendations if _bucket(item) == bucket]
        _cost_overview(document, chosen)
        if chosen:
            document["sections"].append(
                pdf_report._cost_section(
                    title,
                    chosen,
                    chart_title="Largest resources",
                    keyfn=lambda item: item.get("resource_name") or item.get("resource_id") or "resource",
                )
            )
    elif report_id in {"cost-summary", "cost-register"}:
        _cost_overview(document, recommendations)
        for name in ("HIGH", "MEDIUM", "LOW"):
            rows = [item for item in recommendations if (item.get("priority") or "LOW") == name]
            if rows:
                document["sections"].append(pdf_report._cost_section(name.title(), rows))
    elif report_id in {"cost-service", "cost-inventory"}:
        if report_id == "cost-inventory":
            _inventory_kpis(document, recommendations, ctx.get("meta") or {})
        else:
            _cost_overview(document, recommendations)
        _grouped_cost(document, recommendations, lambda item: item.get("service") or "AWS")
    else:
        document["sections"].append(
            pdf_report._empty_section("Report", pdf_report.FINDING_COLUMNS, pdf_report.FINDING_WIDTHS, "This report has no layout.")
        )
    if not document["sections"]:
        columns, widths, message = _empty_for(report)
        document["sections"].append(pdf_report._empty_section(document["title"], columns, widths, message))
    return document


def _finding_overview(document, findings, chart_title="Findings by severity"):
    import pdf_report

    counts = pdf_report._count(findings, "severity")
    document["kpis"] = [
        {"label": "Findings", "value": str(len(findings))},
        {"label": "High", "value": str(counts.get("HIGH", 0))},
        {"label": "Medium", "value": str(counts.get("MEDIUM", 0))},
        {"label": "Low", "value": str(counts.get("LOW", 0))},
    ]
    document["chart_title"] = chart_title
    document["chart"] = [
        {"label": name.title(), "value": counts.get(name, 0)}
        for name in SEVERITY_ORDER
        if counts.get(name, 0)
    ]


def _grouped_findings(document, findings, keyfn):
    import pdf_report

    _finding_overview(document, findings, chart_title="Findings by category")
    order, grouped = _group(findings, keyfn)
    document["chart"] = _sized_chart(order, grouped)
    if not order:
        return
    for name in order[:12]:
        document["sections"].append(
            pdf_report._finding_section(
                name,
                grouped[name],
                chart_title="By severity",
                keyfn=lambda item: (item.get("severity") or "INFO").title(),
            )
        )
    if len(order) > 12:
        document["notes"].insert(0, f"{len(order) - 12} additional categories were omitted from this export.")


def _scorecard_document(document, findings, pillars, trusted):
    import pdf_report

    document["kpis"] = [
        {"label": "Findings", "value": str(len(findings))},
        {"label": "Security", "value": str(int(pillars.get("Security") or 0))},
        {"label": "Reliability", "value": str(int(pillars.get("Reliability") or 0))},
        {"label": "Cost", "value": str(int(pillars.get("Cost optimization") or 0))},
    ]
    document["chart_title"] = "Findings by pillar"
    document["chart"] = [
        {"label": name, "value": int(pillars.get(name) or 0)}
        for name in PILLARS
        if int(pillars.get(name) or 0)
    ]
    for name in PILLARS:
        rows = [item for item in findings if item.get("pillar") == name]
        if rows:
            document["sections"].append(pdf_report._finding_section(name, rows))
    document["sections"].append(_advisor_section(trusted))


def _advisor_overview(document, trusted):
    rows = (trusted or {}).get("recommendations") or []
    if not trusted or not trusted.get("available"):
        document["kpis"] = [{"label": "Trusted Advisor", "value": "Unavailable"}]
        document["chart"] = []
        return
    document["kpis"] = [
        {"label": "Recommendations", "value": str(len(rows))},
        {"label": "Open", "value": str(sum(1 for item in rows if (item.get("status") or "open") == "open"))},
    ]
    document["chart_title"] = "Trusted Advisor by status"
    document["chart"] = _count_pairs((item.get("status") or "open") for item in rows)


def _advisor_section(trusted):
    import pdf_report

    columns = ("Recommendation", "Status", "Pillars")
    widths = (108, 28, 50)
    items = []
    if trusted and trusted.get("available"):
        items = list(trusted.get("recommendations") or [])
    shown = items[:40]
    if not trusted:
        rows = [["-", "-", "Trusted Advisor was not queried for this report."]]
    elif not trusted.get("available"):
        rows = [["-", "-", trusted.get("reason") or "Trusted Advisor could not be read."]]
    elif not shown:
        rows = [["-", "-", "Trusted Advisor returned no recommendation summaries."]]
    else:
        rows = [
            [
                item.get("name") or "Recommendation",
                item.get("status") or "open",
                ", ".join(item.get("pillars") or []) or "-",
            ]
            for item in shown
        ]
    return {
        "title": "Trusted Advisor" if not items else f"Trusted Advisor ({len(items)})",
        "chart_title": "By status",
        "chart": pdf_report._count_series(
            [{"status": item.get("status") or "open"} for item in shown],
            lambda item: (item.get("status") or "open").title(),
        ),
        "columns": columns,
        "widths": widths,
        "numeric": [],
        "rows": rows,
        "omitted": max(0, len(items) - 40),
        "money": False,
    }


def _cost_overview(document, recommendations):
    import pdf_report

    counts = pdf_report._count(recommendations, "priority")
    total = round(sum(float(item.get("monthly_saving") or 0) for item in recommendations), 2)
    document["money"] = True
    document["kpis"] = [
        {"label": "Recommendations", "value": str(len(recommendations))},
        {"label": "Monthly saving", "value": pdf_report._number(total, money=True)},
        {"label": "High", "value": str(counts.get("HIGH", 0))},
        {"label": "Medium", "value": str(counts.get("MEDIUM", 0))},
    ]
    document["chart_title"] = "Estimated monthly saving by service"
    document["chart"] = pdf_report._money_series(recommendations, lambda item: item.get("service") or "AWS")
    if not document["chart"]:
        document["chart_title"] = "Recommendations by priority"
        document["money"] = False
        document["chart"] = [
            {"label": name.title(), "value": counts.get(name, 0)}
            for name in ("HIGH", "MEDIUM", "LOW")
            if counts.get(name, 0)
        ]


def _inventory_kpis(document, recommendations, meta):
    import pdf_report

    document["money"] = True
    kpis = []
    if meta.get("actual_30d_ce_cost") is not None:
        kpis.append({"label": "Cost Explorer 30 days", "value": pdf_report._number(meta["actual_30d_ce_cost"], money=True)})
    if meta.get("total_cost") is not None:
        kpis.append({"label": "List-price inventory", "value": pdf_report._number(meta["total_cost"], money=True)})
    if meta.get("total_saving") is not None:
        kpis.append({"label": "Rule-based saving", "value": pdf_report._number(meta["total_saving"], money=True)})
    kpis.append({"label": "Rows", "value": str(len(recommendations))})
    document["kpis"] = kpis[:4]
    document["chart_title"] = "List-price estimate by service"
    document["chart"] = pdf_report._money_series(recommendations, lambda item: item.get("service") or "AWS")


def _grouped_cost(document, recommendations, keyfn):
    import pdf_report

    if not document["chart"]:
        document["chart_title"] = "Estimated monthly saving by service"
        document["chart"] = pdf_report._money_series(recommendations, keyfn)
        document["money"] = True
    order, grouped = _group(recommendations, keyfn)
    order.sort(key=lambda name: (-_money(grouped[name]), name.lower()))
    if not order:
        return
    for name in order[:12]:
        rows = grouped[name]
        section = pdf_report._cost_section(
            f"{name} (${_money(rows):,.2f} / month)",
            rows,
            chart_title="Saving by priority",
            keyfn=lambda item: (item.get("priority") or "LOW").title(),
        )
        if not section["chart"]:
            section["chart"] = pdf_report._count_series(rows, lambda item: (item.get("priority") or "LOW").title())
            section["money"] = False
        document["sections"].append(section)
    if len(order) > 12:
        document["notes"].insert(0, f"{len(order) - 12} additional services were omitted from this export.")


def _group(items, keyfn):
    grouped = {}
    order = []
    for item in items:
        key = keyfn(item) or "Other"
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append(item)
    order.sort(key=lambda name: (-len(grouped[name]), str(name).lower()))
    return order, grouped


def _sized_chart(order, grouped):
    chart = [{"label": name, "value": len(grouped[name])} for name in order[:8]]
    rest = sum(len(grouped[name]) for name in order[8:])
    if rest:
        chart.append({"label": "Other", "value": rest})
    return chart


def _count_pairs(names):
    counts = {}
    order = []
    for name in names:
        label = str(name or "Other")
        if label not in counts:
            order.append(label)
            counts[label] = 0
        counts[label] += 1
    return [{"label": name.title(), "value": counts[name]} for name in order]


def _empty_for(report):
    import pdf_report

    if report.get("domain") == "cost":
        return (
            pdf_report.COST_COLUMNS,
            pdf_report.COST_WIDTHS,
            "AWS returned no recommendations for this account and region.",
        )
    return (
        pdf_report.FINDING_COLUMNS,
        pdf_report.FINDING_WIDTHS,
        "No findings matched this report.",
    )


def compose(report, ctx):
    findings = ctx.get("findings") or []
    recommendations = ctx.get("recommendations") or []
    report_id = report["id"]
    if report_id == "hk-executive":
        sections = _executive(findings)
    elif report_id == "hk-register":
        sections = _by_severity(findings, SEVERITY_ORDER)
    elif report_id == "hk-critical":
        sections = _by_severity(
            [item for item in findings if item.get("severity") in {"HIGH", "MEDIUM"}],
            ("HIGH", "MEDIUM"),
        )
    elif report_id == "hk-security":
        chosen = [item for item in findings if _is_security(item)]
        sections = _by_key(chosen, lambda item: item.get("category") or "Security")
    elif report_id == "hk-network":
        chosen = [item for item in findings if (item.get("category") or "") in NETWORK_CATEGORIES]
        sections = _by_key(chosen, lambda item: item.get("category") or "Network")
    elif report_id == "hk-waste":
        chosen = [item for item in findings if _is_waste(item)]
        sections = _by_key(chosen, lambda item: item.get("category") or "Waste")
    elif report_id == "hk-actions":
        sections = _by_key(findings, lambda item: item.get("action") or "Review the resource")
    elif report_id == "hk-service":
        sections = _by_key(findings, lambda item: item.get("category") or "Other")
    elif report_id == "gov-scorecard":
        sections = _scorecard(findings, ctx.get("pillars") or {}, ctx.get("trusted"))
    elif report_id == "gov-security":
        sections = _pillar(findings, "Security")
    elif report_id == "gov-reliability":
        sections = _pillar(findings, "Reliability")
    elif report_id == "gov-excellence":
        sections = _pillar(findings, "Operational excellence")
    elif report_id == "gov-performance":
        sections = _pillar(findings, "Performance")
    elif report_id == "gov-cost":
        sections = _pillar(findings, "Cost optimization")
    elif report_id == "gov-exceptions":
        chosen = [item for item in findings if item.get("severity") == "HIGH"]
        sections = _by_key(chosen, lambda item: item.get("pillar") or "Unmapped")
    elif report_id == "gov-advisor":
        sections = [("Trusted Advisor", _advisor_lines(ctx.get("trusted")))]
    elif report_id == "cost-summary":
        sections = _cost_summary(recommendations, ctx.get("notes") or [])
    elif report_id == "cost-register":
        sections = _cost_groups(recommendations, lambda item: item.get("priority") or "LOW")
    elif report_id == "cost-priority":
        chosen = [item for item in recommendations if item.get("priority") == "HIGH"]
        sections = [(
            "At least $50 per month",
            _cap([_cost_line(item) for item in chosen]) or [
                "No recommendation in this response is estimated at $50 or more per month."
            ],
        )]
    elif report_id == "cost-rightsizing":
        sections = _cost_cut(recommendations, "rightsizing", "Rightsizing")
    elif report_id == "cost-idle":
        sections = _cost_cut(recommendations, "idle", "Idle and removable")
    elif report_id == "cost-storage":
        sections = _cost_cut(recommendations, "storage", "Storage")
    elif report_id == "cost-service":
        sections = _cost_groups(recommendations, lambda item: item.get("service") or "AWS", with_total=True)
    elif report_id == "cost-inventory":
        sections = _inventory(recommendations, ctx.get("notes") or [], ctx.get("meta") or {})
    else:
        sections = [("Report", ["This report has no layout."])]

    if report_id != "cost-summary" and report.get("source") == "native":
        notes = ctx.get("notes") or []
        if notes:
            sections = [("How to read the figures", notes)] + sections
    method = METHODS.get((report["domain"], report["source"]))
    if method:
        sections.append(("How this report was produced", [method]))
    return sections


def _executive(findings):
    counts = _counts(findings, "severity")
    glance = [
        f"Total findings: {len(findings)}",
        "    ".join(f"{name}: {counts.get(name, 0)}" for name in SEVERITY_ORDER),
    ]
    priority = [item for item in findings if item.get("severity") == "HIGH"][:12]
    label = "High-severity findings"
    if not priority:
        priority = [item for item in findings if item.get("severity") == "MEDIUM"][:12]
        label = "Medium-severity findings"
    lines = [_finding_line(item) for item in priority] or ["No high or medium findings in this scan."]
    return [("At a glance", glance), (label, lines)]


def _scorecard(findings, pillars, trusted):
    glance = [f"{name}: {int(pillars.get(name) or 0)}" for name in PILLARS]
    glance.insert(0, f"Total findings: {len(findings)}")
    sections = [("Pillar counts", glance)]
    for name in PILLARS:
        rows = [item for item in findings if item.get("pillar") == name][:6]
        sections.append((name, [_finding_line(item) for item in rows] or ["No findings in this pillar."]))
    sections.append(("Trusted Advisor", _advisor_lines(trusted)))
    return sections


def _pillar(findings, name):
    rows = [item for item in findings if item.get("pillar") == name]
    return [(
        name,
        _cap([_finding_line(item) for item in rows]) or [f"No findings mapped to {name}."],
    )]


def _by_severity(findings, order):
    if not findings:
        return [("Findings", ["No findings matched this report."])]
    sections = []
    for name in order:
        rows = [item for item in findings if (item.get("severity") or "INFO") == name]
        if rows:
            sections.append((name.title(), _cap([_finding_line(item) for item in rows])))
    return sections or [("Findings", ["No findings matched this report."])]


def _by_key(findings, keyfn):
    if not findings:
        return [("Findings", ["No findings matched this report."])]
    grouped = {}
    order = []
    for item in findings:
        key = keyfn(item) or "Other"
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append(item)
    order.sort(key=lambda name: (-len(grouped[name]), name.lower()))
    return [
        (f"{name} ({len(grouped[name])})", _cap([_finding_line(item) for item in grouped[name]]))
        for name in order
    ]


def _cost_summary(recommendations, notes):
    total = _money(recommendations)
    counts = _counts(recommendations, "priority")
    glance = [
        f"Recommendations: {len(recommendations)}",
        f"Estimated monthly saving: ${total:,.2f}",
        "    ".join(f"{name}: {counts.get(name, 0)}" for name in ("HIGH", "MEDIUM", "LOW")),
    ]
    top = sorted(recommendations, key=lambda item: float(item.get("monthly_saving") or 0), reverse=True)[:10]
    sections = []
    if notes:
        sections.append(("How to read the figures", list(notes)))
    sections.append(("At a glance", glance))
    sections.append((
        "Largest opportunities",
        [_cost_line(item) for item in top] or ["AWS returned no recommendations for this account and region."],
    ))
    return sections


def _cost_cut(recommendations, bucket, title):
    chosen = [item for item in recommendations if _bucket(item) == bucket]
    return [(
        title,
        _cap([_cost_line(item) for item in chosen]) or [
            f"No {title.lower()} rows were present in this recommendation set."
        ],
    )]


def _cost_groups(recommendations, keyfn, with_total=False):
    if not recommendations:
        return [("Recommendations", ["AWS returned no recommendations for this account and region."])]
    grouped = {}
    order = []
    for item in recommendations:
        key = keyfn(item) or "Other"
        if key not in grouped:
            order.append(key)
            grouped[key] = []
        grouped[key].append(item)
    order.sort(key=lambda name: (-_money(grouped[name]), name.lower()))
    sections = []
    for name in order:
        rows = grouped[name]
        heading = f"{name} ({len(rows)})"
        if with_total:
            heading = f"{name} - ${_money(rows):,.2f} / month ({len(rows)})"
        sections.append((heading, _cap([_cost_line(item) for item in rows])))
    return sections


def _inventory(recommendations, notes, meta):
    glance = []
    if meta.get("actual_30d_ce_cost") is not None:
        glance.append(f"Cost Explorer, last 30 days: ${float(meta['actual_30d_ce_cost']):,.2f}")
    if meta.get("total_cost") is not None:
        glance.append(f"List-price inventory: ${float(meta['total_cost']):,.2f} / month")
    if meta.get("total_saving") is not None:
        glance.append(f"Estimated saving from documented rules: ${float(meta['total_saving']):,.2f} / month")
    sections = []
    if notes:
        sections.append(("How to read the figures", list(notes)))
    if glance:
        sections.append(("At a glance", glance))
    sections.extend(_cost_groups(recommendations, lambda item: item.get("service") or "AWS", with_total=True))
    return sections


def _advisor_lines(trusted):
    if not trusted:
        return ["Trusted Advisor was not queried for this report."]
    if not trusted.get("available"):
        return [trusted.get("reason") or "Trusted Advisor could not be read."]
    rows = trusted.get("recommendations") or []
    if not rows:
        return ["Trusted Advisor returned no recommendation summaries."]
    lines = []
    for item in rows[:40]:
        pillars = ", ".join(item.get("pillars") or []) or "pillar not stated"
        status = item.get("status") or "open"
        lines.append(f"{item.get('name') or 'Recommendation'}  |  {status}  |  {pillars}")
    return lines


def _finding_line(item):
    parts = [
        f"[{item.get('severity') or 'INFO'}] {item.get('title') or 'Finding'}  |  {item.get('resource_id') or 'n/a'}",
    ]
    if item.get("pillar"):
        parts[0] += f"  |  {item['pillar']}"
    if item.get("details"):
        parts.append(str(item["details"]))
    parts.append(f"Action: {item.get('action') or 'Review the resource.'}")
    if item.get("documentation_url"):
        parts.append(str(item["documentation_url"]))
    return "\n".join(parts)


def _cost_line(item):
    saving = float(item.get("monthly_saving") or 0)
    parts = [
        f"[{item.get('priority') or 'LOW'}] ${saving:,.2f} / month  |  {item.get('service') or 'AWS'}  |  {item.get('resource_name') or item.get('resource_id') or 'resource'}",
        item.get("action") or "Review the recommendation.",
    ]
    if item.get("reasoning"):
        parts.append(str(item["reasoning"]))
    if item.get("evidence"):
        parts.append(f"Evidence: {item['evidence']}")
    if item.get("source"):
        parts.append(f"Source: {item['source']}")
    return "\n".join(parts)


def _is_security(item):
    category = item.get("category") or ""
    title = item.get("title") or ""
    if category in SECURITY_CATEGORIES:
        return True
    return any(word in title for word in ("Public", "MFA", "Encryption", "Access Key"))


def _is_waste(item):
    title = item.get("title") or ""
    return any(word in title for word in ("Stopped", "Unattached", "Unused", "Idle", "NAT"))


def _bucket(item):
    explicit = (item.get("category") or "").lower()
    if explicit in {"rightsizing", "storage"}:
        return explicit
    if explicit == "deletion":
        return "idle"
    text = " ".join(
        str(item.get(key) or "")
        for key in ("action", "service", "reasoning", "evidence")
    ).lower()
    if any(word in text for word in ("rightsize", "resize", "downsize", "scale up", "scale down", "memory")):
        return "rightsizing"
    if any(word in text for word in ("gp3", "storage", "tier", "snapshot", "volume")):
        return "storage"
    if any(word in text for word in ("delete", "terminate", "release", "idle", "stop", "unused", "unattached")):
        return "idle"
    return "other"


def _counts(rows, key):
    counts = {}
    for item in rows:
        name = item.get(key) or "INFO"
        counts[name] = counts.get(name, 0) + 1
    return counts


def _money(rows):
    return round(sum(float(item.get("monthly_saving") or 0) for item in rows), 2)


def _cap(lines, limit=400):
    if len(lines) <= limit:
        return lines
    hidden = len(lines) - limit
    return lines[:limit] + [f"{hidden} additional items were omitted from this export."]
