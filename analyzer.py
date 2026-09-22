"""Deterministic business analysis for uploaded CSV and Excel datasets."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}


def load_data(uploaded_file: Any) -> pd.DataFrame:
	"""Load a CSV or Excel file from a path or file-like upload."""
	name = getattr(uploaded_file, "name", str(uploaded_file))
	suffix = Path(name).suffix.lower()
	if suffix not in SUPPORTED_EXTENSIONS:
		raise ValueError("Unsupported file type. Use CSV, XLS, or XLSX.")

	if hasattr(uploaded_file, "getvalue"):
		source = BytesIO(uploaded_file.getvalue())
	else:
		source = uploaded_file

	try:
		if suffix == ".csv":
			dataframe = pd.read_csv(source)
		else:
			dataframe = pd.read_excel(source)
	except (OSError, ValueError, ImportError) as exc:
		raise ValueError(f"Could not read {name}: {exc}") from exc

	return dataframe


def validate_data(dataframe: pd.DataFrame) -> dict[str, Any]:
	"""Return data-quality findings without modifying the input dataframe."""
	if not isinstance(dataframe, pd.DataFrame):
		raise TypeError("dataframe must be a pandas DataFrame")

	missing_by_column = {
		str(column): int(count)
		for column, count in dataframe.isna().sum().items()
		if count
	}
	duplicate_rows = int(dataframe.duplicated().sum())
	warnings: list[str] = []
	if dataframe.empty:
		warnings.append("The dataset is empty.")
	if duplicate_rows:
		warnings.append(f"{duplicate_rows} duplicate rows detected.")
	if missing_by_column:
		warnings.append("Missing values detected in one or more columns.")

	return {
		"is_empty": bool(dataframe.empty),
		"missing_values": int(dataframe.isna().sum().sum()),
		"missing_by_column": missing_by_column,
		"duplicate_rows": duplicate_rows,
		"warnings": warnings,
	}


def clean_data(dataframe: pd.DataFrame) -> pd.DataFrame:
	"""Apply safe cleanup that preserves business values and row meaning."""
	cleaned = dataframe.copy()
	cleaned.columns = [str(column).strip() for column in cleaned.columns]
	cleaned = cleaned.dropna(axis=0, how="all").dropna(axis=1, how="all")
	cleaned = cleaned.drop_duplicates().reset_index(drop=True)

	text_columns = [
		column
		for column in cleaned.columns
		if pd.api.types.is_object_dtype(cleaned[column])
		or pd.api.types.is_string_dtype(cleaned[column])
	]
	for column in text_columns:
		cleaned[column] = cleaned[column].map(
			lambda value: value.strip() if isinstance(value, str) else value
		)
	return cleaned


def detect_column_types(dataframe: pd.DataFrame) -> dict[str, list[str]]:
	"""Detect date, numeric, and categorical columns using deterministic rules."""
	date_columns: list[str] = []
	numeric_columns = [str(column) for column in dataframe.select_dtypes(include=np.number).columns]
	categorical_columns: list[str] = []

	for column in dataframe.columns:
		name = str(column)
		if name in numeric_columns:
			continue
		series = dataframe[column]
		parsed = pd.to_datetime(series, errors="coerce", format="mixed")
		if len(series) and parsed.notna().mean() >= 0.8:
			date_columns.append(name)
		else:
			categorical_columns.append(name)

	return {
		"date": date_columns,
		"numeric": numeric_columns,
		"categorical": categorical_columns,
	}


def _number(value: Any) -> int | float | None:
	if pd.isna(value):
		return None
	numeric = float(value)
	return int(numeric) if numeric.is_integer() else numeric


def _column_tokens(column: str) -> set[str]:
	return set(str(column).lower().replace("-", "_").split("_"))


def _is_identifier(column: str) -> bool:
	tokens = _column_tokens(column)
	return "age" not in tokens and bool(tokens & {"id", "number", "code", "zip", "postal", "phone", "account", "customer"}) and not bool(
		tokens & {"income", "age", "limit", "balance", "revenue", "sales", "amount"}
	)


def select_business_metrics(dataframe: pd.DataFrame) -> dict[str, list[str]]:
	"""Classify numeric fields so demographic and identifier fields are not KPIs."""
	primary: list[str] = []
	context: list[str] = []
	identifiers: list[str] = []
	financial_tokens = {
		"revenue", "sales", "amount", "income", "limit", "balance", "payment", "spend",
		"profit", "cost", "value", "loan", "credit", "purchase", "transaction",
	}
	for column in dataframe.select_dtypes(include=np.number).columns:
		name = str(column)
		tokens = _column_tokens(name)
		if _is_identifier(name):
			identifiers.append(name)
		elif tokens & financial_tokens:
			primary.append(name)
		else:
			context.append(name)
	if not primary:
		primary = context[:3]
		context = [column for column in context if column not in primary]
	return {"primary": primary, "context": context, "identifiers": identifiers}


def calculate_business_insights(
	dataframe: pd.DataFrame, column_info: dict[str, list[str]], metric_info: dict[str, list[str]]
) -> dict[str, Any]:
	"""Calculate business-facing comparisons and relationships."""
	primary = metric_info["primary"]
	financial_metrics = {}
	for column in primary[:8]:
		series = dataframe[column].dropna()
		if series.empty:
			continue
		financial_metrics[column] = {
			"average": _number(series.mean()),
			"median": _number(series.median()),
			"minimum": _number(series.min()),
			"maximum": _number(series.max()),
			"total": _number(series.sum()),
		}

	segment_comparisons: list[dict[str, Any]] = []
	metric = primary[0] if primary else None
	if metric and column_info["categorical"]:
		for category in column_info["categorical"][:4]:
			grouped = (
				dataframe.dropna(subset=[category, metric])
				.groupby(category)[metric]
				.agg(["mean", "count"])
				.sort_values("mean", ascending=False)
				.head(5)
				.reset_index()
			)
			segment_comparisons.append(
				{
					"group_column": category,
					"metric": metric,
					"groups": [
						{"name": str(row[category]), "average": _number(row["mean"]), "count": int(row["count"])}
						for row in grouped.to_dict("records")
					],
				}
			)

	relationships: list[dict[str, Any]] = []
	name_map = {column.lower(): column for column in dataframe.columns}
	income = next((name_map[name] for name in name_map if "income" in name), None)
	limit = next((name_map[name] for name in name_map if "limit" in name), None)
	balance = next((name_map[name] for name in name_map if "balance" in name or "outstanding" in name), None)
	if income and limit:
		ratio = dataframe[limit].div(dataframe[income].replace(0, np.nan)).dropna()
		relationships.append({"type": "credit_to_income", "average_ratio": _number(ratio.mean())})
	if balance and limit:
		utilization = dataframe[balance].div(dataframe[limit].replace(0, np.nan)).dropna()
		relationships.append({"type": "credit_utilization", "average_ratio": _number(utilization.mean())})

	return {
		"financial_metrics": financial_metrics,
		"segment_comparisons": segment_comparisons,
		"relationships": relationships,
		"primary_metrics": primary,
		"context_metrics": metric_info["context"],
	}


def calculate_kpis(dataframe: pd.DataFrame, analysis_type: str) -> dict[str, Any]:
	"""Calculate generic row and numeric-column KPIs."""
	numeric = dataframe.select_dtypes(include=np.number)
	columns: dict[str, dict[str, int | float | None]] = {}
	for column in numeric.columns:
		series = numeric[column].dropna()
		columns[str(column)] = {
			"sum": _number(series.sum()) if not series.empty else None,
			"average": _number(series.mean()) if not series.empty else None,
			"minimum": _number(series.min()) if not series.empty else None,
			"maximum": _number(series.max()) if not series.empty else None,
		}

	return {
		"analysis_type": analysis_type,
		"row_count": int(len(dataframe)),
		"column_count": int(len(dataframe.columns)),
		"numeric_columns": columns,
	}


def calculate_trends(dataframe: pd.DataFrame, column_info: dict[str, list[str]]) -> dict[str, Any]:
	"""Summarize numeric values by the first detected date column."""
	if not column_info["date"] or not column_info["numeric"]:
		return {}

	date_column = column_info["date"][0]
	numeric_column = column_info["numeric"][0]
	trend_data = dataframe[[date_column, numeric_column]].copy()
	trend_data[date_column] = pd.to_datetime(
		trend_data[date_column], errors="coerce", format="mixed"
	)
	trend_data = trend_data.dropna(subset=[date_column, numeric_column])
	if trend_data.empty:
		return {}

	trend_data["period"] = trend_data[date_column].dt.to_period("M").astype(str)
	grouped = trend_data.groupby("period")[numeric_column].agg(["sum", "mean"]).reset_index()
	return {
		"date_column": date_column,
		"value_column": numeric_column,
		"periods": [
			{"period": row["period"], "sum": _number(row["sum"]), "average": _number(row["mean"])}
			for row in grouped.to_dict("records")
		],
	}


def calculate_grouped_summaries(
	dataframe: pd.DataFrame, column_info: dict[str, list[str]]
) -> dict[str, Any]:
	"""Summarize the first categorical column against the first numeric column."""
	if not column_info["categorical"] or not column_info["numeric"]:
		return {}

	category_column = column_info["categorical"][0]
	numeric_column = column_info["numeric"][0]
	grouped = (
		dataframe.dropna(subset=[category_column, numeric_column])
		.groupby(category_column)[numeric_column]
		.agg(["sum", "mean", "count"])
		.sort_values("sum", ascending=False)
		.head(10)
		.reset_index()
	)
	return {
		"group_column": category_column,
		"value_column": numeric_column,
		"groups": [
			{
				"name": str(row[category_column]),
				"sum": _number(row["sum"]),
				"average": _number(row["mean"]),
				"count": int(row["count"]),
			}
			for row in grouped.to_dict("records")
		],
	}


def detect_basic_anomalies(
	dataframe: pd.DataFrame, column_info: dict[str, list[str]]
) -> list[dict[str, Any]]:
	"""Flag extreme numeric values using a conservative three-sigma rule."""
	anomalies: list[dict[str, Any]] = []
	for column in column_info["numeric"]:
		series = dataframe[column].dropna()
		if len(series) < 3 or series.std(ddof=0) == 0:
			continue
		mean = series.mean()
		std = series.std(ddof=0)
		extreme = dataframe[(dataframe[column] - mean).abs() > 3 * std]
		for index, row in extreme.head(20).iterrows():
			anomalies.append(
				{"row": int(index), "column": column, "value": _number(row[column]), "rule": "three_sigma"}
			)
	return anomalies


def build_analysis_package(
	dataframe: pd.DataFrame, analysis_type: str, business_objective: str = ""
) -> dict[str, Any]:
	"""Build the verified structured evidence package used by later phases."""
	quality_before = validate_data(dataframe)
	cleaned = clean_data(dataframe)
	if cleaned.empty:
		raise ValueError("The dataset contains no usable rows or columns.")
	column_info = detect_column_types(cleaned)
	metric_info = select_business_metrics(cleaned)
	return {
		"metadata": {
			"rows": int(len(cleaned)),
			"columns": int(len(cleaned.columns)),
			"analysis_type": analysis_type,
			"business_objective": business_objective,
		},
		"data_quality": quality_before,
		"columns": column_info,
		"metric_roles": metric_info,
		"kpis": calculate_kpis(cleaned, analysis_type),
		"business_insights": calculate_business_insights(cleaned, column_info, metric_info),
		"trends": calculate_trends(cleaned, column_info),
		"segments": calculate_grouped_summaries(cleaned, column_info),
		"anomalies": detect_basic_anomalies(cleaned, column_info),
	}
