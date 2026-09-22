import json

import pytest

from ai_insights import (
    extract_supported_claims,
    generate_insights,
    get_groq_client,
    get_groq_model,
    get_groq_models,
    parse_ai_response,
    validate_ai_output,
)


ANALYSIS_PACKAGE = {"kpis": {"row_count": 2, "numeric_columns": {"Revenue": {"sum": 300}}}}


def valid_output():
    return {
        "executive_summary": "Revenue totals 300.",
        "key_findings": [{"finding": "Revenue is concentrated.", "evidence": "300 total."}],
        "risks": [],
        "opportunities": [],
        "recommendations": ["Review the two records."],
        "report_sections": ["Summary"],
    }


def test_parse_json_and_code_fence():
    assert parse_ai_response("```json\n{\"ok\": true}\n```") == {"ok": True}


def test_validate_accepts_supported_claims():
    result = validate_ai_output(valid_output(), ANALYSIS_PACKAGE)

    assert result["valid"] is True
    assert "300" in result["supported_claims"]


def test_validate_rejects_missing_field():
    output = valid_output()
    del output["risks"]

    result = validate_ai_output(output, ANALYSIS_PACKAGE)

    assert result["valid"] is False
    assert "Missing required field: risks" in result["errors"]


def test_validate_rejects_unsupported_numeric_claim():
    output = valid_output()
    output["executive_summary"] = "Revenue totals 999."

    result = validate_ai_output(output, ANALYSIS_PACKAGE)

    assert result["valid"] is False
    assert "Unsupported numerical claim: 999" in result["errors"]


def test_validate_ignores_leading_zero_identifier():
    output = valid_output()
    output["executive_summary"] = "The strongest customer reference is 01163."

    result = validate_ai_output(output, ANALYSIS_PACKAGE)

    assert result["valid"] is True


def test_configured_fallback_model_is_used(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "primary-model")
    monkeypatch.setenv("GROQ_FALLBACK_MODEL", "fallback-model")

    assert get_groq_models() == ["primary-model", "fallback-model"]


def test_malformed_json_is_rejected():
    with pytest.raises(ValueError, match="valid JSON"):
        parse_ai_response("not json")


def test_missing_api_key_is_reported(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        get_groq_client()


def test_model_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")

    assert get_groq_model() == "openai/gpt-oss-120b"


def test_missing_model_is_reported(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_MODEL is not configured"):
        get_groq_model()


def test_generate_insights_returns_business_fallback_when_groq_fails(monkeypatch):
    monkeypatch.setattr("ai_insights.get_groq_client", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    result = generate_insights(ANALYSIS_PACKAGE, "Find the main business issue")

    assert result["source"] == "deterministic_fallback"
    assert result["recommendations"]
    assert "AI service unavailable" not in result["executive_summary"]