"""Shared filesystem, formatting, and serialization helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent
REPORTS_DIR = ROOT_DIR / "outputs" / "reports"
PRESENTATIONS_DIR = ROOT_DIR / "outputs" / "presentations"


def ensure_output_dirs() -> None:
	REPORTS_DIR.mkdir(parents=True, exist_ok=True)
	PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(name: str) -> str:
	cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
	return cleaned or "insightflow_output"


def format_number(value: Any) -> str:
	if value is None:
		return "-"
	return f"{float(value):,.2f}".rstrip("0").rstrip(".")


def format_currency(value: Any) -> str:
	return f"${format_number(value)}"


def format_percentage(value: Any) -> str:
	return f"{format_number(value)}%"


def serialize_for_json(data: Any) -> str:
	return json.dumps(data, ensure_ascii=True, default=str, sort_keys=True)


def get_reporting_period(dataframe, date_column: str | None = None) -> str:
	if not date_column or date_column not in dataframe.columns:
		return "Period unavailable"
	dates = dataframe[date_column].dropna()
	if dates.empty:
		return "Period unavailable"
	parsed = __import__("pandas").to_datetime(dates, errors="coerce", format="mixed").dropna()
	if parsed.empty:
		return "Period unavailable"
	return f"{parsed.min():%Y-%m-%d} to {parsed.max():%Y-%m-%d}"


def create_output_filename(prefix: str, extension: str) -> str:
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
	suffix = extension if extension.startswith(".") else f".{extension}"
	return f"{safe_filename(prefix)}_{timestamp}{suffix}"
