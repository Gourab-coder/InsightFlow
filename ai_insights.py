"""Groq-powered interpretation of verified deterministic analysis."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from prompts import SYSTEM_PROMPT, build_insight_prompt

load_dotenv()


REQUIRED_FIELDS = (
    "executive_summary",
    "key_findings",
    "risks",
    "opportunities",
    "recommendations",
    "report_sections",
)
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:%?)"
)


def get_groq_client() -> Groq:
    """Create a Groq client from the environment without exposing credentials."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=api_key)


def get_groq_model() -> str:
    """Return the single Groq model configured in the environment."""
    model = os.getenv("GROQ_MODEL", "").strip()
    if not model:
        raise RuntimeError("GROQ_MODEL is not configured in .env.")
    return model


def get_groq_models() -> list[str]:
    """Return the configured primary model followed by an optional fallback."""
    models = [get_groq_model()]
    fallback = os.getenv("GROQ_FALLBACK_MODEL", "").strip()
    if fallback and fallback not in models:
        models.append(fallback)
    return models


def build_ai_input(analysis_package: dict[str, Any], objective: str) -> str:
    """Return the prompt sent to Groq, containing aggregate evidence only."""
    return build_insight_prompt(analysis_package, objective)


def parse_ai_response(response: Any) -> dict[str, Any]:
    """Parse a JSON response, tolerating a single markdown code fence."""
    content = response
    if hasattr(response, "choices"):
        content = response.choices[0].message.content
    if not isinstance(content, str):
        raise ValueError("AI response content must be a JSON string.")
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object.")
    return parsed


def _evidence_numbers(value: Any) -> set[float]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, (int, float)):
        return {float(value)}
    if isinstance(value, dict):
        numbers: set[float] = set()
        for item in value.values():
            numbers.update(_evidence_numbers(item))
        return numbers
    if isinstance(value, list):
        numbers: set[float] = set()
        for item in value:
            numbers.update(_evidence_numbers(item))
        return numbers
    return set()


def extract_supported_claims(
    ai_output: dict[str, Any], analysis_package: dict[str, Any]
) -> list[str]:
    """Return numeric claims that are present in verified evidence."""
    supported_numbers = _evidence_numbers(analysis_package)
    claims: list[str] = []
    for field in ("executive_summary", "key_findings", "risks", "opportunities", "recommendations"):
        text = json.dumps(ai_output.get(field, ""), ensure_ascii=True)
        for token in NUMBER_PATTERN.findall(text):
            numeric_token = token.rstrip("%").replace(",", "")
            # Leading-zero values are identifiers, not business metrics.
            if len(numeric_token.lstrip("+-")) > 1 and numeric_token.lstrip("+-").startswith("0"):
                continue
            number = float(numeric_token)
            # Four-digit years in narrative dates are context, not KPI claims.
            if number.is_integer() and 1900 <= number <= 2100:
                continue
            if not any(abs(number - evidence) <= max(0.01, abs(evidence) * 0.001) for evidence in supported_numbers):
                raise ValueError(f"Unsupported numerical claim: {token}")
            claims.append(token)
    return claims


def validate_ai_output(
    ai_output: dict[str, Any], analysis_package: dict[str, Any]
) -> dict[str, Any]:
    """Validate shape and numerical evidence before reports consume AI output."""
    missing = [field for field in REQUIRED_FIELDS if field not in ai_output]
    errors: list[str] = [f"Missing required field: {field}" for field in missing]
    if not isinstance(ai_output.get("executive_summary"), str):
        errors.append("executive_summary must be a string")
    for field in REQUIRED_FIELDS[1:]:
        if not isinstance(ai_output.get(field), list):
            errors.append(f"{field} must be a list")
    if not errors:
        try:
            supported_claims = extract_supported_claims(ai_output, analysis_package)
        except ValueError as exc:
            errors.append(str(exc))
            supported_claims = []
    else:
        supported_claims = []
    return {"valid": not errors, "errors": errors, "supported_claims": supported_claims}


def build_fallback_insights(analysis_package: dict[str, Any], reason: str) -> dict[str, Any]:
    """Create transparent deterministic insights when Groq is unavailable."""
    business = analysis_package.get("business_insights", {})
    financial_metrics = business.get("financial_metrics", {})
    key_findings = []
    for name, values in list(financial_metrics.items())[:3]:
        key_findings.append(
            {
                "finding": f"Average {name} is {values.get('average')} with a range of {values.get('minimum')} to {values.get('maximum')}.",
                "evidence": f"Deterministic distribution analysis for {name}.",
            }
        )
    for relationship in business.get("relationships", []):
        key_findings.append(
            {
                "finding": f"{relationship['type'].replace('_', ' ').title()} averages {relationship['average_ratio']}.",
                "evidence": "Calculated relationship between verified financial columns.",
            }
        )
    if not key_findings:
        key_findings.append({"finding": "No business measures were detected.", "evidence": "The uploaded dataset has no usable financial measures."})
    primary = business.get("primary_metrics", [])
    top_metric = primary[0] if primary else "the dataset"
    comparisons = business.get("segment_comparisons", [])
    segments = comparisons[0].get("groups", []) if comparisons else []
    segment_note = (
        f"The leading {comparisons[0]['group_column']} is "
        f"{segments[0]['name']}."
        if segments
        else "No segment comparison was available."
    )
    return {
        "executive_summary": f"{top_metric} is the primary verified business measure. {segment_note}",
        "key_findings": key_findings,
        "risks": ["Data quality and business context should be reviewed before making decisions."],
        "opportunities": ["Compare the strongest and weakest segments and investigate the gap."],
        "recommendations": [
            "Prioritize the strongest segment and identify what can be replicated.",
            "Review outliers and missing values before operational action.",
            "Track the same KPIs in the next reporting period.",
        ],
        "report_sections": ["Executive Summary", "KPI Summary", "Methodology"],
        "source": "deterministic_fallback",
        "fallback_reason": reason,
    }


def generate_insights(analysis_package: dict[str, Any], objective: str) -> dict[str, Any]:
    """Request and validate evidence-backed insights from Groq."""
    try:
        client = get_groq_client()
        last_error: Exception | None = None
        for model in get_groq_models():
            try:
                response = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_ai_input(analysis_package, objective)},
                    ],
                    response_format={"type": "json_object"},
                )
                ai_output = parse_ai_response(response)
                validation = validate_ai_output(ai_output, analysis_package)
                if not validation["valid"]:
                    raise ValueError("Invalid AI output: " + "; ".join(validation["errors"]))
                return ai_output
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
    except Exception as exc:
        return build_fallback_insights(analysis_package, str(exc))