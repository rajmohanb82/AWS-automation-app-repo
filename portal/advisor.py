"""Cost advice from AWS recommendation APIs, with a documented-rule fallback."""

import botocore.exceptions

from findings import SERVICE_DOCS, finding_id

HUB_DOC = "https://docs.aws.amazon.com/cost-management/latest/userguide/cost-optimization-hub.html"
COMPUTE_DOC = "https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html"


def _money(value):
    if isinstance(value, dict):
        for key in ("value", "amount"):
            if value.get(key) is not None:
                return round(float(value[key]), 2)
        return 0.0
    if value in (None, ""):
        return 0.0
    return round(float(value), 2)


def _priority(saving):
    if saving >= 50:
        return "HIGH"
    if saving >= 15:
        return "MEDIUM"
    return "LOW"


def _error_text(exc):
    if isinstance(exc, botocore.exceptions.ClientError):
        err = exc.response.get("Error", {})
        code = err.get("Code") or "Error"
        message = err.get("Message") or str(exc)
        if code in {"OptInRequiredException", "AccessDeniedException", "AccessDenied"}:
            return f"{code}: {message}"
        return f"{code}: {message}"
    return str(exc)


def _hub_recommendations(session, region):
    client = session.client("cost-optimization-hub", region_name="us-east-1")
    items = []
    token = None
    for _ in range(5):
        kwargs = {"maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        response = client.list_recommendations(**kwargs)
        items.extend(response.get("items") or [])
        token = response.get("nextToken")
        if not token:
            break
    recommendations = []
    for item in items:
        item_region = item.get("region") or ""
        if item_region and item_region != region:
            continue
        saving = _money(item.get("estimatedMonthlySavings"))
        current = _money(item.get("estimatedMonthlyCost"))
        resource = item.get("resourceId") or item.get("resourceArn") or item.get("recommendationId")
        action = item.get("actionType") or "Review"
        summary = item.get("recommendedResourceSummary") or item.get("currentResourceSummary") or ""
        recommendations.append(
            {
                "finding_id": finding_id(item.get("accountId"), region, "Cost", action, resource),
                "resource_id": resource or "account",
                "resource_name": item.get("currentResourceSummary") or resource or "Account recommendation",
                "service": item.get("currentResourceType") or item.get("source") or "AWS",
                "action": action.replace("_", " ").title() if action.isupper() else action,
                "reasoning": (
                    f"{summary} Estimated monthly saving ${saving:.2f}. "
                    "This figure comes from Cost Optimization Hub and includes the account's pricing agreements."
                ).strip(),
                "current_monthly_cost": current,
                "projected_monthly_cost": round(max(0, current - saving), 2) if current else None,
                "monthly_saving": saving,
                "priority": _priority(saving),
                "source": "Cost Optimization Hub",
                "documentation_url": HUB_DOC,
                "evidence": f"Look-back {item.get('recommendationLookbackPeriodInDays') or 'standard'} days",
            }
        )
    recommendations.sort(key=lambda row: row["monthly_saving"], reverse=True)
    return recommendations


def _option_saving(option):
    if not isinstance(option, dict):
        return 0.0
    for key in ("savingsOpportunityAfterDiscounts", "savingsOpportunity"):
        block = option.get(key) or {}
        amount = _money(block.get("estimatedMonthlySavings"))
        if amount:
            return amount
    return 0.0


def _first_option(recommendation):
    options = recommendation.get("recommendationOptions") or []
    return options[0] if options else {}


def _compute_rows(session, region):
    client = session.client("compute-optimizer", region_name=region)
    rows = []
    notes = []

    def add(resource_id, name, service, action, reasoning, saving, evidence):
        rows.append(
            {
                "finding_id": finding_id("", region, "Compute Optimizer", action, resource_id),
                "resource_id": resource_id,
                "resource_name": name or resource_id,
                "service": service,
                "action": action,
                "reasoning": reasoning,
                "current_monthly_cost": None,
                "projected_monthly_cost": None,
                "monthly_saving": saving,
                "priority": "HIGH" if "under-provisioned" in action.lower() else _priority(saving),
                "source": "Compute Optimizer",
                "documentation_url": COMPUTE_DOC,
                "evidence": evidence,
            }
        )

    try:
        ec2 = client.get_ec2_instance_recommendations().get("instanceRecommendations") or []
    except Exception as exc:
        notes.append(f"EC2 recommendations: {_error_text(exc)}")
        ec2 = []
    for item in ec2:
        finding = item.get("finding") or ""
        if finding == "OPTIMIZED":
            continue
        option = _first_option(item)
        current = item.get("currentInstanceType") or "current type"
        proposed = option.get("instanceType") or "the recommended type"
        saving = _option_saving(option)
        if finding == "UNDER_PROVISIONED":
            action = f"Scale up from {current} to {proposed}"
        elif finding == "IDLE":
            action = f"Stop or terminate idle {current}"
        else:
            action = f"Rightsize {current} to {proposed}"
        add(
            item.get("instanceArn") or item.get("instanceName") or current,
            item.get("instanceName") or current,
            "EC2",
            action,
            f"Compute Optimizer classified this instance as {finding.replace('_', ' ').lower()} from CloudWatch history in {region}.",
            saving,
            finding.replace("_", " ").title(),
        )

    try:
        volumes = client.get_ebs_volume_recommendations().get("volumeRecommendations") or []
    except Exception as exc:
        notes.append(f"EBS recommendations: {_error_text(exc)}")
        volumes = []
    for item in volumes:
        finding = item.get("finding") or ""
        if finding in {"Optimized", "OPTIMIZED"}:
            continue
        option = _first_option(item)
        config = (option.get("configuration") or {}) if option else {}
        proposed = config.get("volumeType") or "the recommended volume type"
        saving = _option_saving(option)
        add(
            item.get("volumeArn") or "volume",
            item.get("volumeArn") or "EBS volume",
            "EBS",
            f"Move volume to {proposed}",
            f"Compute Optimizer classified this volume as {finding}.",
            saving,
            finding,
        )

    try:
        functions = client.get_lambda_function_recommendations().get("lambdaFunctionRecommendations") or []
    except Exception as exc:
        notes.append(f"Lambda recommendations: {_error_text(exc)}")
        functions = []
    for item in functions:
        finding = item.get("finding") or ""
        if finding in {"Optimized", "OPTIMIZED"}:
            continue
        option = _first_option(item)
        saving = _option_saving(option)
        memory = option.get("memorySize")
        action = f"Set memory to {memory} MB" if memory else "Review function configuration"
        add(
            item.get("functionArn") or item.get("functionName") or "function",
            item.get("functionName") or "Lambda function",
            "Lambda",
            action,
            f"Compute Optimizer classified this function as {finding}.",
            saving,
            finding,
        )
    return rows, notes


def native_recommendations(session, region):
    notes = []
    try:
        hub_rows = _hub_recommendations(session, region)
        if hub_rows:
            notes.append(
                "Savings come from Cost Optimization Hub and include this account's Reserved Instances and Savings Plans."
            )
        else:
            notes.append("Cost Optimization Hub returned no recommendations in this region.")
        return {"recommendations": hub_rows, "notes": notes, "source": "Cost Optimization Hub"}
    except Exception as exc:
        notes.append(f"Cost Optimization Hub is unavailable. {_error_text(exc)}")

    try:
        rows, extra_notes = _compute_rows(session, region)
        notes.extend(extra_notes)
        rows.sort(key=lambda row: row["monthly_saving"], reverse=True)
        if rows:
            notes.append("Savings come from Compute Optimizer for this region.")
        else:
            notes.append("Compute Optimizer returned no change recommendations in this region.")
        return {"recommendations": rows, "notes": notes, "source": "Compute Optimizer"}
    except Exception as exc:
        notes.append(f"Compute Optimizer is unavailable. {_error_text(exc)}")
        notes.append("Run an inventory estimate to apply documented thresholds to a live resource list.")
        return {"recommendations": [], "notes": notes, "source": "Unavailable"}


def rules_from_scan(scan_data, account_id, region):
    recommendations = []
    for resource in scan_data.get("resources") or []:
        suggestion = resource.get("suggestion")
        saving = resource.get("potential_saving") or 0
        if not suggestion or saving <= 0:
            continue
        service = resource.get("service") or "AWS"
        state = resource.get("state") or ""
        cpu = resource.get("cpu_avg_pct")
        cost = resource.get("monthly_cost") or 0
        if cpu is not None:
            reasoning = (
                f"Average CPU was {cpu}% over the look-back window. "
                f"{suggestion}. The estimated saving of ${saving:.2f} per month uses published on-demand prices, "
                "so it can differ from the bill."
            )
            evidence = f"CPU average {cpu}%"
        elif state in {"available", "stopped", "unassociated"}:
            reasoning = (
                f"The resource is {state} and still estimated at ${cost:.2f} per month on published prices. "
                f"{suggestion}."
            )
            evidence = f"State {state}"
        else:
            reasoning = (
                f"{suggestion}. Estimated saving ${saving:.2f} per month from published on-demand prices."
            )
            evidence = state or "Configuration"
        text = suggestion.lower()
        if any(word in text for word in ("terminate", "delete", "release")):
            category = "Deletion"
        elif any(word in text for word in ("downsize", "resize", "rightsize")):
            category = "Rightsizing"
        elif any(word in text for word in ("gp3", "storage", "tier")):
            category = "Storage"
        else:
            category = "Architecture"
        resource_id = resource.get("resource_id") or ""
        recommendations.append(
            {
                "finding_id": finding_id(account_id, region, category, suggestion, resource_id),
                "resource_id": resource_id,
                "resource_name": resource.get("name") or resource_id,
                "service": service,
                "action": suggestion,
                "reasoning": reasoning,
                "current_monthly_cost": round(float(cost), 2),
                "projected_monthly_cost": round(max(0, float(cost) - float(saving)), 2),
                "monthly_saving": round(float(saving), 2),
                "priority": _priority(float(saving)),
                "source": "Documented rules",
                "documentation_url": SERVICE_DOCS.get(service, HUB_DOC),
                "evidence": evidence,
                "category": category,
            }
        )
    recommendations.sort(key=lambda row: row["monthly_saving"], reverse=True)
    return recommendations


def trusted_advisor(session):
    try:
        client = session.client("trustedadvisor", region_name="us-east-1")
        response = client.list_recommendations(maxResults=50)
    except botocore.exceptions.ClientError as exc:
        err = exc.response.get("Error", {})
        code = err.get("Code") or "Error"
        if code in {"AccessDeniedException", "SubscriptionRequiredException", "AccessDenied"}:
            return {
                "available": False,
                "reason": (
                    "Trusted Advisor API checks require Business Support+ on this account "
                    "(minimum $29 per month, or a percentage of the AWS bill when that is higher). "
                    "Core posture checks on this page still run with the account's read permissions."
                ),
            }
        return {"available": False, "reason": f"Trusted Advisor could not be read ({code})."}
    except Exception as exc:
        return {"available": False, "reason": f"Trusted Advisor could not be read. {exc}"}

    summaries = response.get("recommendationSummaries") or response.get("recommendations") or []
    items = []
    for summary in summaries[:50]:
        items.append(
            {
                "name": summary.get("name") or summary.get("id") or "Recommendation",
                "status": summary.get("status") or summary.get("lifecycleStage") or "",
                "pillars": summary.get("pillars") or [],
                "source": summary.get("source") or "Trusted Advisor",
                "id": summary.get("id") or summary.get("arn") or "",
            }
        )
    return {"available": True, "recommendations": items}
