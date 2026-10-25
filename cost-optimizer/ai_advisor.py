"""
AWS Cost Optimizer — AI Advisor
Uses OpenAI GPT-4o (via openai package) to generate natural-language insights.
Falls back gracefully to a built-in rules engine if OpenAI is unavailable or
no API key is configured.
"""

import os
import json
from datetime import datetime, timezone


# ─── OpenAI integration ───────────────────────────────────────────────────────

def _call_openai(resources_summary: str) -> list[dict]:
    """Call OpenAI GPT-4o with a structured cost analysis prompt."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        return []

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return []

    client = OpenAI(api_key=api_key)

    system_prompt = """You are an expert AWS cost optimization specialist with deep knowledge of 
AWS pricing, rightsizing, and architectural best practices. Analyze the provided AWS resource 
inventory and utilization data, then return ONLY a JSON array of recommendation objects.

Each object must have these exact fields:
{
  "resource_id": "string",
  "resource_name": "string",
  "service": "string",
  "current_monthly_cost": number,
  "projected_monthly_cost": number,
  "monthly_saving": number,
  "action": "string (short action name)",
  "reasoning": "string (2-3 sentence explanation)",
  "priority": "HIGH" | "MEDIUM" | "LOW",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "category": "Rightsizing" | "Deletion" | "Storage Optimization" | "Architecture" | "Reserved Instance" | "Network Optimization"
}

Focus on the highest-impact, lowest-risk recommendations. Be specific and actionable.
Return ONLY the JSON array, no other text."""

    user_prompt = f"""Analyze these AWS resources and provide cost optimization recommendations:

{resources_summary}

Return a JSON array of recommendations sorted by monthly_saving descending."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        # GPT sometimes wraps in an object key
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    return []


# ─── Rules-based fallback engine ─────────────────────────────────────────────

def _rules_engine(scan_data: dict) -> list[dict]:
    """
    Built-in rules engine — no external API needed.
    Produces structured recommendations from the scanner output.
    """
    recommendations = []
    resources = scan_data.get("resources", [])

    for r in resources:
        svc     = r.get("service", "")
        rid     = r.get("resource_id", "")
        name    = r.get("name", rid)
        cost    = r.get("monthly_cost", 0) or 0
        saving  = r.get("potential_saving", 0) or 0
        suggest = r.get("suggestion")

        if not suggest or saving <= 0:
            continue

        # Determine priority from saving magnitude
        if saving >= 50:
            priority = "HIGH"
        elif saving >= 15:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Categorise
        if "terminate" in suggest.lower() or "delete" in suggest.lower() or "release" in suggest.lower():
            category = "Deletion"
        elif "downsize" in suggest.lower() or "resize" in suggest.lower():
            category = "Rightsizing"
        elif "gp3" in suggest.lower() or "storage" in suggest.lower() or "tiering" in suggest.lower():
            category = "Storage Optimization"
        elif "vpc" in suggest.lower() or "nat" in suggest.lower() or "transit" in suggest.lower() or "peering" in suggest.lower() or "subnet" in suggest.lower():
            category = "Network Optimization"
        else:
            category = "Architecture"

        # Generate reasoning
        cpu = r.get("cpu_avg_pct")
        state = r.get("state", "")
        if cpu is not None:
            reasoning = (
                f"This {svc} resource shows an average CPU utilization of {cpu}% over the past "
                f"14 days, which is significantly below the efficient utilization threshold. "
                f"{suggest} is recommended to eliminate waste and reduce costs by ${saving:.2f}/month."
            )
        elif state in ("available", "stopped", "unassociated"):
            reasoning = (
                f"This {svc} resource is in '{state}' state, meaning it is not actively serving "
                f"workloads but still incurring charges of ${cost:.2f}/month. "
                f"{suggest} will eliminate this waste entirely."
            )
        else:
            reasoning = (
                f"Based on resource configuration and utilization patterns, {suggest} is recommended "
                f"for this {svc} resource to achieve a monthly saving of ${saving:.2f}."
            )

        recommendations.append({
            "resource_id":           rid,
            "resource_name":         name,
            "service":               svc,
            "current_monthly_cost":  round(cost, 2),
            "projected_monthly_cost": round(max(0, cost - saving), 2),
            "monthly_saving":        round(saving, 2),
            "action":                suggest,
            "reasoning":             reasoning,
            "priority":              priority,
            "confidence":            "HIGH" if state in ("available", "stopped", "unassociated") else "MEDIUM",
            "category":              category,
        })

    # Sort by saving desc
    recommendations.sort(key=lambda x: x["monthly_saving"], reverse=True)
    return recommendations


# ─── Public entry point ─────────────────────────────────────────────────────

def generate_recommendations(scan_data: dict) -> dict:
    """
    Generate AI recommendations from scan data.
    Tries OpenAI GPT-4o first; falls back to rules engine.
    Returns { recommendations, ai_powered, model_used, generated_at }
    """
    ai_powered = False
    model_used = "Rules Engine"
    recommendations = []

    # Attempt OpenAI if key available
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        try:
            # Build a compact summary for the LLM (avoid token blowout)
            resources = scan_data.get("resources", [])
            summary_lines = []
            for r in resources:
                cpu = r.get("cpu_avg_pct")
                cpu_str = f", CPU avg {cpu}%" if cpu is not None else ""
                summary_lines.append(
                    f"- {r['service']} | {r['resource_id']} ({r.get('name','')}) | "
                    f"Type: {r.get('type','N/A')} | State: {r.get('state','N/A')} | "
                    f"${r.get('monthly_cost',0):.2f}/mo{cpu_str}"
                )
            resources_summary = "\n".join(summary_lines)

            ai_recs = _call_openai(resources_summary)
            if ai_recs:
                recommendations = ai_recs
                ai_powered = True
                model_used = "OpenAI GPT-4o"
        except Exception:
            pass

    # Fall back if AI didn't produce results
    if not recommendations:
        recommendations = _rules_engine(scan_data)
        ai_powered = False
        model_used = "Built-in Rules Engine"

    return {
        "recommendations":  recommendations,
        "ai_powered":       ai_powered,
        "model_used":       model_used,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }
