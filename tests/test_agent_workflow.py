import agent_workflow


PACKAGE = {
    "metadata": {"rows": 2},
    "kpis": {"numeric_columns": {"Revenue": {"sum": 300}}},
    "trends": {},
    "segments": {},
}


def test_workflow_runs_through_validator(monkeypatch):
    output = {
        "executive_summary": "Revenue totals 300.",
        "key_findings": [],
        "risks": [],
        "opportunities": [],
        "recommendations": [],
        "report_sections": ["Summary"],
    }
    monkeypatch.setattr(agent_workflow.ai_insights, "generate_insights", lambda *_: output)

    state = agent_workflow.run_agent_workflow(PACKAGE, "Review revenue", "Sales")

    assert state["plan"]["analysis_type"] == "Sales"
    assert state["report_plan"]["sections"][:3] == [
        "Executive Summary",
        "Dataset Overview",
        "KPI Summary",
    ]
    assert state["validation"]["valid"] is True


def test_workflow_validator_rejects_failed_insight_call(monkeypatch):
    def fail(*_args):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(agent_workflow.ai_insights, "generate_insights", fail)

    state = agent_workflow.run_agent_workflow(PACKAGE, "Review revenue", "Sales")

    assert state["validation"]["valid"] is False
    assert "API unavailable" in state["validation"]["errors"]