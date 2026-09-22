import io

import pandas as pd
import pytest

from analyzer import (
    build_analysis_package,
    clean_data,
    detect_column_types,
    load_data,
    validate_data,
)


def test_load_csv_and_detect_columns():
    source = io.BytesIO(b"Date,Region,Revenue\n2025-01-01,West,100\n2025-02-01,East,200\n")
    source.name = "sales.csv"

    dataframe = load_data(source)

    assert list(dataframe.columns) == ["Date", "Region", "Revenue"]
    assert detect_column_types(dataframe) == {
        "date": ["Date"],
        "numeric": ["Revenue"],
        "categorical": ["Region"],
    }


def test_validation_reports_missing_and_duplicate_rows():
    dataframe = pd.DataFrame({"Region": ["West", "West"], "Revenue": [100, None]})

    quality = validate_data(dataframe)

    assert quality["missing_values"] == 1
    assert quality["duplicate_rows"] == 0
    assert quality["warnings"]


def test_clean_data_removes_only_safe_structural_issues():
    dataframe = pd.DataFrame({" Region ": [" West ", " West ", None], "Revenue": [100, 100, None]})

    cleaned = clean_data(dataframe)

    assert list(cleaned.columns) == ["Region", "Revenue"]
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["Region"] == "West"


def test_build_package_without_date_still_returns_kpis_and_segments():
    dataframe = pd.DataFrame({"Product": ["A", "B", "A"], "Amount": [10, 20, 30]})

    package = build_analysis_package(dataframe, "Sales", "Find the best product")

    assert package["metadata"]["rows"] == 3
    assert package["trends"] == {}
    assert package["segments"]["groups"][0]["name"] == "A"
    assert package["kpis"]["numeric_columns"]["Amount"]["sum"] == 60


def test_unsupported_file_type_is_rejected():
    source = io.BytesIO(b"not a spreadsheet")
    source.name = "sales.txt"

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_data(source)


def test_empty_dataset_is_rejected_by_analysis_package():
    with pytest.raises(ValueError, match="no usable rows"):
        build_analysis_package(pd.DataFrame(columns=["Revenue"]), "Sales")


def test_duplicate_rows_are_removed_before_analysis():
    dataframe = pd.DataFrame({"Region": ["West", "West"], "Revenue": [100, 100]})

    package = build_analysis_package(dataframe, "Sales")

    assert package["data_quality"]["duplicate_rows"] == 1
    assert package["metadata"]["rows"] == 1


def test_business_metrics_prioritize_financial_fields_and_relationships():
    dataframe = pd.DataFrame(
        {
            "Customer_Age": [25, 45, 35],
            "Customer_Income_INR_Month": [40000, 80000, 60000],
            "Card_Limit_INR": [100000, 300000, 200000],
            "Balance_INR": [20000, 150000, 50000],
            "Card_Type": ["Silver", "Gold", "Gold"],
        }
    )

    package = build_analysis_package(dataframe, "Finance")

    assert "Customer_Income_INR_Month" in package["business_insights"]["primary_metrics"]
    assert "Card_Limit_INR" in package["business_insights"]["primary_metrics"]
    assert "Customer_Age" in package["business_insights"]["context_metrics"]
    assert package["business_insights"]["relationships"]
    assert package["business_insights"]["segment_comparisons"][0]["groups"][0]["name"] == "Gold"