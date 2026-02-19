## Arsenal Position Dashboard

A small Streamlit dashboard that visualises **Arsenal's Premier League league position** and **total points** by matchweek across seasons, using the historical `epl_final.csv` dataset.

### Project structure

- `epl_final.csv` – raw Premier League match results.
- `data_prep.py` – utilities to:
  - derive a `Matchweek` for each fixture in each season,
  - compute league tables after every matchweek,
  - extract Arsenal's position and points by matchweek.
- `app.py` – Streamlit dashboard entry point.
- `requirements.txt` – Python dependencies.

### Setup

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the dashboard from the `arsenal` directory:

```bash
streamlit run app.py
```

The app will open in your browser. Use the sidebar to select seasons and compare **Arsenal's league position** and **total points** across matchweeks.

