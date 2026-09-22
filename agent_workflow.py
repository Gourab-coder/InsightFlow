"""Small LangGraph workflow that orchestrates InsightFlow's analysis layers."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

import ai_insights


class WorkflowState(TypedDict, total=False):
	analysis_type: str
	business_objective: str
	analysis_package: dict[str, Any]
	plan: dict[str, Any]
	ai_insights: dict[str, Any]
	report_plan: dict[str, Any]
	validation: dict[str, Any]
	errors: list[str]


def create_initial_state(
	analysis_package: dict[str, Any], objective: str, analysis_type: str
) -> WorkflowState:
	"""Create explicit state for one workflow run."""
	return {
		"analysis_type": analysis_type,
		"business_objective": objective,
		"analysis_package": analysis_package,
		"errors": [],
	}


def planner_node(state: WorkflowState) -> dict[str, Any]:
	"""Choose the report scope from user-provided settings."""
	return {
		"plan": {
			"analysis_type": state["analysis_type"],
			"objective": state.get("business_objective", ""),
			"include_trends": bool(state["analysis_package"].get("trends")),
			"include_segments": bool(state["analysis_package"].get("segments")),
		}
	}


def analyst_node(state: WorkflowState) -> dict[str, Any]:
	"""Expose deterministic evidence to downstream nodes unchanged."""
	return {"analysis_package": state["analysis_package"]}


def insight_node(state: WorkflowState) -> dict[str, Any]:
	"""Generate validated AI interpretation from the evidence package."""
	try:
		insights = ai_insights.generate_insights(
			state["analysis_package"], state.get("business_objective", "")
		)
		return {"ai_insights": insights}
	except (RuntimeError, ValueError, OSError) as exc:
		return {"ai_insights": {}, "errors": [str(exc)]}


def report_planner_node(state: WorkflowState) -> dict[str, Any]:
	"""Create a deterministic report outline from available workflow state."""
	sections = ["Executive Summary", "Dataset Overview", "KPI Summary"]
	if state["analysis_package"].get("trends"):
		sections.append("Performance Trend")
	if state["analysis_package"].get("segments"):
		sections.append("Segment Analysis")
	sections.extend(["Key Findings", "Recommendations", "Methodology"])
	return {"report_plan": {"sections": sections}}


def validator_node(state: WorkflowState) -> dict[str, Any]:
	"""Gate report generation on validated AI output and accumulated errors."""
	if state.get("errors"):
		return {"validation": {"valid": False, "errors": state["errors"]}}
	validation = ai_insights.validate_ai_output(
		state.get("ai_insights", {}), state["analysis_package"]
	)
	return {"validation": validation}


def build_workflow():
	"""Build and compile the InsightFlow workflow graph."""
	graph = StateGraph(WorkflowState)
	graph.add_node("planner", planner_node)
	graph.add_node("analyst", analyst_node)
	graph.add_node("insight", insight_node)
	graph.add_node("report_planner", report_planner_node)
	graph.add_node("validator", validator_node)
	graph.add_edge(START, "planner")
	graph.add_edge("planner", "analyst")
	graph.add_edge("analyst", "insight")
	graph.add_edge("insight", "report_planner")
	graph.add_edge("report_planner", "validator")
	graph.add_edge("validator", END)
	return graph.compile()


def run_agent_workflow(
	analysis_package: dict[str, Any], objective: str, analysis_type: str
) -> WorkflowState:
	"""Run one complete workflow and return its inspectable final state."""
	return build_workflow().invoke(
		create_initial_state(analysis_package, objective, analysis_type)
	)
