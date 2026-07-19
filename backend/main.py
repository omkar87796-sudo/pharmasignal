"""
main.py — PharmaSignal API
----------------------------
FastAPI backend exposing the adverse event signal detection pipeline.

Endpoints:
  GET  /                       -> health check
  GET  /api/signals            -> precomputed signals (fast, from synthetic dataset)
  GET  /api/analyze/{drug}     -> LIVE analysis: pulls real FAERS data for a drug,
                                   runs PRR/ROR against the precomputed background
                                   dataset, returns fresh results
  GET  /api/drugs              -> list of drugs available in the precomputed dataset

Run locally:
  uvicorn main:app --reload --port 8000

Deploy on Render:
  Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os

from signal_detection import compute_disproportionality
from severity_scoring import compute_severity, generate_signal_narrative

try:
    from fetch_data import fetch_adverse_events, raw_reports_to_dataframe
    LIVE_FETCH_AVAILABLE = True
except Exception:
    LIVE_FETCH_AVAILABLE = False

app = FastAPI(title="PharmaSignal API", version="1.0.0")

# Allow the Vercel frontend (and localhost during dev) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pharmasignal.vercel.app", "https://pharmasignal-ko6vdn8rh-omkar87796-sudos-projects.vercel.app"],  # tighten this to your exact Vercel URL after deploying
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_RAW_DF = None
_ENRICHED_DF = None


def load_precomputed():
    """Load precomputed synthetic-dataset results once, cache in memory."""
    global _RAW_DF, _ENRICHED_DF
    if _RAW_DF is None:
        _RAW_DF = pd.read_csv(os.path.join(DATA_DIR, "adverse_events_raw.csv"))
    if _ENRICHED_DF is None:
        path = os.path.join(DATA_DIR, "signals_enriched.csv")
        if os.path.exists(path):
            _ENRICHED_DF = pd.read_csv(path)
        else:
            signals = compute_disproportionality(_RAW_DF)
            _ENRICHED_DF = compute_severity(_RAW_DF, signals)
            _ENRICHED_DF["narrative"] = _ENRICHED_DF.apply(
                lambda r: generate_signal_narrative(r) if r["signal_detected"] else "", axis=1
            )
    return _RAW_DF, _ENRICHED_DF


@app.get("/")
def health():
    return {"status": "ok", "service": "PharmaSignal API"}


@app.get("/api/drugs")
def list_drugs():
    raw_df, _ = load_precomputed()
    return {"drugs": sorted(raw_df["drug"].unique().tolist())}


@app.get("/api/signals")
def get_signals(only_flagged: bool = True):
    """
    Returns precomputed signals from the background (synthetic) dataset.
    Fast — no external calls.
    """
    _, enriched = load_precomputed()
    df = enriched[enriched["signal_detected"]] if only_flagged else enriched
    df = df.sort_values("priority_score", ascending=False)
    df = df.where(pd.notnull(df), None)
    return {"count": len(df), "signals": df.to_dict("records")}


@app.get("/api/analyze/{drug}")
def analyze_drug_live(drug: str, max_records: int = 1000):
    """
    Pulls LIVE adverse event reports for `drug` from FDA's openFDA API,
    merges them into the background dataset, and recomputes PRR/ROR
    signals specific to that drug. Slower (external API call) but uses
    real, current FAERS data.
    """
    if not LIVE_FETCH_AVAILABLE:
        raise HTTPException(status_code=503, detail="Live fetch module unavailable")

    raw_df, _ = load_precomputed()

    reports = fetch_adverse_events(drug, max_records=max_records)
    if not reports:
        raise HTTPException(status_code=404, detail=f"No FAERS reports found for '{drug}'")

    live_df = raw_reports_to_dataframe(reports)
    if live_df.empty:
        raise HTTPException(status_code=404, detail=f"No usable reaction data for '{drug}'")

    # Merge live data into the background dataset for a fair PRR/ROR comparison
    combined = pd.concat([raw_df, live_df], ignore_index=True)

    signals = compute_disproportionality(combined)
    signals = signals[signals["drug"].str.upper() == drug.upper()]

    enriched = compute_severity(combined, signals)
    enriched["narrative"] = enriched.apply(
        lambda r: generate_signal_narrative(r) if r["signal_detected"] else "", axis=1
    )
    enriched = enriched.sort_values("priority_score", ascending=False)
    enriched = enriched.where(pd.notnull(enriched), None)

    return {
        "drug": drug,
        "reports_fetched": len(reports),
        "count": len(enriched),
        "signals": enriched.to_dict("records"),
    }
