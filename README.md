# InsightFlow

InsightFlow is a one-page Streamlit application that turns CSV or Excel business data into deterministic KPIs, evidence-backed AI insights, a Word report, and an executive PowerPoint presentation.

## Quick Start

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Add a Groq API key to `.env`:

```text
GROQ_API_KEY=your_key_here
```

Run the application:

```powershell
.\venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL shown by Streamlit, upload a `.csv`, `.xls`, or `.xlsx` file, choose an analysis type, and generate the reports.

## Test

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

## Architecture

1. `analyzer.py` loads, validates, cleans, and calculates deterministic evidence.
2. `agent_workflow.py` coordinates the Planner, Analyst, Insight, Report Planner, and Validator nodes.
3. `ai_insights.py` sends aggregate evidence to Groq and rejects unsupported AI claims.
4. `report_generator.py` and `ppt_generator.py` create downloadable artifacts.
5. `app.py` provides the single-page upload, progress, preview, and download experience.

Python and pandas remain authoritative for numerical analysis. The Groq API key is read from the environment and is never stored in source code.

## Project Layout

- `sample_data/sample_sales_data.csv`: small dataset for manual testing.
- `outputs/reports/`: generated Word reports.
- `outputs/presentations/`: generated PowerPoint files.
- `docs/`: product specification and implementation guide.