"""Word report generation from verified analysis and validated insights."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document


def create_document() -> Document:
	"""Create a report document with consistent base metadata."""
	document = Document()
	document.core_properties.title = "InsightFlow Business Report"
	return document


def add_title_section(document: Document, analysis_package: dict[str, Any]) -> None:
	metadata = analysis_package["metadata"]
	document.add_heading("InsightFlow Business Report", level=0)
	document.add_paragraph(f"Analysis type: {metadata.get('analysis_type', 'General Business')}")
	objective = metadata.get("business_objective")
	if objective:
		document.add_paragraph(f"Business objective: {objective}")


def add_executive_summary(document: Document, ai_output: dict[str, Any]) -> None:
	document.add_heading("Executive Summary", level=1)
	document.add_paragraph(ai_output["executive_summary"])


def add_dataset_overview(document: Document, analysis_package: dict[str, Any]) -> None:
	document.add_heading("Dataset Overview", level=1)
	metadata = analysis_package["metadata"]
	document.add_paragraph(
		f"The dataset contains {metadata['rows']} rows and {metadata['columns']} columns."
	)
	quality = analysis_package["data_quality"]
	document.add_paragraph(
		f"Missing values: {quality['missing_values']}; duplicate rows: {quality['duplicate_rows']}."
	)


def add_kpi_table(document: Document, analysis_package: dict[str, Any]) -> None:
	document.add_heading("KPI Summary", level=1)
	numeric_columns = analysis_package["kpis"].get("numeric_columns", {})
	primary_metrics = analysis_package.get("business_insights", {}).get("primary_metrics", [])
	if primary_metrics:
		numeric_columns = {name: numeric_columns[name] for name in primary_metrics if name in numeric_columns}
	table = document.add_table(rows=1, cols=5)
	table.style = "Table Grid"
	for cell, text in zip(table.rows[0].cells, ("Metric", "Sum", "Average", "Minimum", "Maximum")):
		cell.text = text
	for metric, values in list(numeric_columns.items())[:6]:
		cells = table.add_row().cells
		cells[0].text = str(metric)
		cells[1].text = str(values.get("sum", ""))
		cells[2].text = str(values.get("average", ""))
		cells[3].text = str(values.get("minimum", ""))
		cells[4].text = str(values.get("maximum", ""))


def add_analysis_sections(document: Document, analysis_package: dict[str, Any]) -> None:
	document.add_heading("Business Performance Analysis", level=1)
	trends = analysis_package.get("trends", {})
	if trends:
		document.add_heading("Trend / Variance Analysis", level=2)
		document.add_paragraph(
			f"{trends['value_column']} is summarized by {trends['date_column']} month."
		)
		for period in trends["periods"][-6:]:
			document.add_paragraph(
				f"{period['period']}: sum {period['sum']}, average {period['average']}."
			)
	segments = analysis_package.get("segments", {})
	if segments:
		document.add_heading("Segment / Region Analysis", level=2)
		for group in segments["groups"][:5]:
			document.add_paragraph(f"{group['name']}: {group['sum']} total across {group['count']} rows.")


def add_findings(document: Document, ai_output: dict[str, Any]) -> None:
	document.add_heading("Key Findings", level=1)
	for finding in ai_output["key_findings"][:5]:
		if isinstance(finding, dict):
			document.add_paragraph(f"{finding.get('finding', '')}: {finding.get('evidence', '')}", style="List Bullet")
		else:
			document.add_paragraph(str(finding), style="List Bullet")

	document.add_heading("Risks / Opportunities", level=1)
	for risk in ai_output["risks"][:3]:
		document.add_paragraph(f"Risk: {risk}", style="List Bullet")
	for opportunity in ai_output["opportunities"][:3]:
		document.add_paragraph(f"Opportunity: {opportunity}", style="List Bullet")

	document.add_heading("Recommendations", level=1)
	for recommendation in ai_output["recommendations"][:4]:
		document.add_paragraph(str(recommendation), style="List Bullet")


def add_recommendations(document: Document, ai_output: dict[str, Any]) -> None:
	document.add_heading("Conclusion", level=1)
	document.add_paragraph("Use the recommendations above as the short action plan for the next reporting period.")


def add_methodology(document: Document, analysis_package: dict[str, Any]) -> None:
	document.add_heading("Appendix: Data Quality and Methodology", level=1)
	document.add_paragraph(
		"Metrics were calculated deterministically with pandas. AI output was generated from aggregate evidence and validated before reporting."
	)
	for warning in analysis_package["data_quality"].get("warnings", []):
		document.add_paragraph(warning, style="List Bullet")


def generate_word_report(
	analysis_package: dict[str, Any], ai_output: dict[str, Any], output_path: str | Path
) -> Path:
	"""Generate and save a complete Word report."""
	required = ("executive_summary", "key_findings", "risks", "opportunities", "recommendations")
	missing = [field for field in required if field not in ai_output]
	if missing:
		raise ValueError(f"Cannot generate report; AI output is missing: {', '.join(missing)}")

	document = create_document()
	add_title_section(document, analysis_package)
	add_executive_summary(document, ai_output)
	add_dataset_overview(document, analysis_package)
	add_kpi_table(document, analysis_package)
	add_analysis_sections(document, analysis_package)
	add_findings(document, ai_output)
	add_recommendations(document, ai_output)
	add_methodology(document, analysis_package)

	destination = Path(output_path)
	destination.parent.mkdir(parents=True, exist_ok=True)
	document.save(destination)
	return destination
