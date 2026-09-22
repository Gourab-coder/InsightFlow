"""InsightFlow Streamlit entry point."""

import streamlit as st
from dotenv import load_dotenv
from typing import Callable

from agent_workflow import run_agent_workflow
from analyzer import build_analysis_package, load_data
from ppt_generator import generate_powerpoint
from report_generator import generate_word_report
from utils import (
	PRESENTATIONS_DIR,
	REPORTS_DIR,
	create_output_filename,
	ensure_output_dirs,
	format_number,
)

load_dotenv()


ANALYSIS_TYPES = ("General Business", "Sales", "Finance", "Risk")
SUPPORTED_FILE_TYPES = ("csv", "xls", "xlsx")


def render_header() -> None:
	"""Render the application header."""
	st.set_page_config(
		page_title="InsightFlow",
		page_icon="IF",
		layout="centered",
	)
	st.title("InsightFlow")
	st.subheader("AI-powered business report generator")
	st.write(
		"Turn a business dataset into a clear analysis, executive insights, "
		"and downloadable reports."
	)


def main() -> None:
	"""Run the Streamlit application."""
	render_header()
def render_upload_section():
	"""Render the dataset uploader and return the selected file."""
	return st.file_uploader(
		"Upload a business dataset",
		type=list(SUPPORTED_FILE_TYPES),
		help="Supported formats: CSV, XLS, and XLSX.",
	)


def render_analysis_options() -> tuple[str, str]:
	"""Render analysis settings and return the selected values."""
	analysis_type = st.selectbox("Analysis type", ANALYSIS_TYPES)
	business_objective = st.text_area(
		"Business objective (optional)",
		placeholder="Example: Identify the strongest regions and products.",
	)
	return analysis_type, business_objective


def render_file_info(uploaded_file) -> None:
	"""Show basic metadata for the uploaded file."""
	extension = uploaded_file.name.rsplit(".", 1)[-1].lower()
	if extension not in SUPPORTED_FILE_TYPES:
		st.error("Unsupported file type. Please upload CSV, XLS, or XLSX.")
		return

	st.caption(f"Selected file: {uploaded_file.name} ({uploaded_file.size:,} bytes)")


def render_results(state: dict) -> None:
	"""Render verified KPIs and validated insights."""
	package = state["analysis_package"]
	if state.get("ai_insights", {}).get("source") == "deterministic_fallback":
		st.warning(
			"Groq was unavailable, so this report uses deterministic KPI insights. "
			"Configure GROQ_MODEL/GROQ_FALLBACK_MODEL and rerun for AI interpretation."
		)
		with st.expander("Why Groq was unavailable"):
			st.code(state["ai_insights"].get("fallback_reason", "Unknown Groq error"))
	st.subheader("KPI Preview")
	metric_names = package.get("business_insights", {}).get("primary_metrics", [])
	kpis = package["kpis"].get("numeric_columns", {})
	kpis = {name: kpis[name] for name in metric_names if name in kpis} or kpis
	if kpis:
		columns = st.columns(min(len(kpis), 3))
		for column, (name, values) in zip(columns, kpis.items()):
			column.metric(name, format_number(values.get("sum")))
	else:
		st.info("No numeric columns were found for KPI preview.")

	st.subheader("Key Findings")
	for finding in state["ai_insights"].get("key_findings", []):
		text = finding.get("finding", "") if isinstance(finding, dict) else str(finding)
		st.write(f"- {text}")


def render_download_buttons(state: dict) -> None:
	"""Render downloads for validated generated artifacts."""
	report_path = state.get("report_path")
	presentation_path = state.get("presentation_path")
	if report_path and presentation_path:
		report_col, presentation_col = st.columns(2)
		with report_col:
			st.download_button(
				"Download Word Report",
				data=report_path.read_bytes(),
				file_name=report_path.name,
				mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
				use_container_width=True,
			)
		with presentation_col:
			st.download_button(
				"Download PowerPoint",
				data=presentation_path.read_bytes(),
				file_name=presentation_path.name,
				mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
				use_container_width=True,
			)


def run_analysis(
	uploaded_file,
	analysis_type: str,
	business_objective: str,
	progress_callback: Callable[[int, str], None] | None = None,
) -> dict:
	"""Run analysis, validation, and report generation for one upload."""
	update = progress_callback or (lambda _value, _message: None)
	update(10, "Loading uploaded dataset...")
	dataframe = load_data(uploaded_file)
	update(30, "Validating and calculating deterministic metrics...")
	analysis_package = build_analysis_package(dataframe, analysis_type, business_objective)
	update(45, "Planning the analysis workflow...")
	state = run_agent_workflow(analysis_package, business_objective, analysis_type)
	update(75, "Validating evidence-backed insights...")
	if not state.get("validation", {}).get("valid"):
		errors = state.get("validation", {}).get("errors", ["Workflow validation failed."])
		raise ValueError("; ".join(errors))

	update(85, "Generating Word and PowerPoint reports...")
	ensure_output_dirs()
	report_path = REPORTS_DIR / create_output_filename("insightflow_report", ".docx")
	presentation_path = PRESENTATIONS_DIR / create_output_filename("insightflow_presentation", ".pptx")
	generate_word_report(analysis_package, state["ai_insights"], report_path)
	generate_powerpoint(analysis_package, state["ai_insights"], presentation_path)
	state["report_path"] = report_path
	state["presentation_path"] = presentation_path
	update(100, "Analysis complete.")
	return state


def main() -> None:
	"""Run the Streamlit application."""
	render_header()
	uploaded_file = render_upload_section()
	analysis_type, business_objective = render_analysis_options()

	if uploaded_file is not None:
		render_file_info(uploaded_file)

	if st.button("Generate Analysis", type="primary", use_container_width=True):
		if uploaded_file is None:
			st.warning("Upload a CSV or Excel file before generating an analysis.")
		else:
			progress = st.progress(0, text="Starting analysis...")

			def update_progress(value: int, message: str) -> None:
				progress.progress(value, text=f"{message} {value}%")

			try:
				state = run_analysis(
					uploaded_file,
					analysis_type,
					business_objective,
					progress_callback=update_progress,
				)
				st.session_state["analysis_state"] = state
				st.success("Analysis complete.")
			except (ValueError, RuntimeError, OSError, ImportError) as exc:
				progress.progress(100, text="Analysis stopped")
				st.error(str(exc))

	if "analysis_state" in st.session_state:
		render_results(st.session_state["analysis_state"])
		render_download_buttons(st.session_state["analysis_state"])


if __name__ == "__main__":
	main()
