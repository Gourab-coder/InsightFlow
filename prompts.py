"""Version-controlled prompts for InsightFlow's insight layer."""

import json
from typing import Any


SYSTEM_PROMPT = (
	"You are a careful business analyst. Use only the verified evidence provided. "
	"Never invent metrics. Return valid JSON with no markdown fences."
)

INSIGHT_PROMPT = """Analyze the verified business evidence below.
Business objective: {objective}
Verified evidence:
{evidence}

Return JSON with these fields:
executive_summary (string), key_findings (list of objects with finding and evidence),
risks (list of strings), opportunities (list of strings), recommendations (list of strings),
report_sections (list of strings).
Do not calculate or invent new numbers.
Do not mention customer IDs, card numbers, transaction IDs, account numbers,
row numbers, dates as metrics, or other identifiers. Use only verified KPI and
aggregate values from the evidence.
"""

PLANNER_PROMPT = ""
REPORT_PLANNER_PROMPT = ""
VALIDATOR_PROMPT = ""


def build_insight_prompt(analysis_package: dict[str, Any], objective: str) -> str:
	"""Build an evidence-only prompt for the Groq request."""
	evidence = json.dumps(analysis_package, ensure_ascii=True, sort_keys=True)
	return INSIGHT_PROMPT.format(objective=objective or "Provide a general business overview.", evidence=evidence)
