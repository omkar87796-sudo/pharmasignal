"""
fetch_data.py
--------------
Pulls real-world adverse event reports from the FDA's openFDA API
(https://open.fda.gov/apis/drug/event/).

This is FREE, public, official FDA data (FAERS - FDA Adverse Event
Reporting System). No API key needed for reasonable usage.

NOTE: If running this in a sandboxed/offline environment, use
generate_synthetic_data.py instead, which produces data in the
EXACT same schema so the rest of the pipeline needs zero changes.
"""

import requests
import pandas as pd
import time

BASE_URL = "https://api.fda.gov/drug/event.json"


def fetch_adverse_events(drug_name: str, limit: int = 1000, max_records: int = 5000):
    """
    Fetch adverse event reports for a given drug from openFDA.

    Returns a list of raw JSON report dicts.
    """
    all_results = []
    skip = 0
    page_size = min(limit, 100)  # openFDA max per request is 100

    while len(all_results) < max_records:
        params = {
            "search": f'patient.drug.medicinalproduct:"{drug_name}"',
            "limit": page_size,
            "skip": skip,
        }
        resp = requests.get(BASE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"Stopped fetching at skip={skip}: HTTP {resp.status_code}")
            break

        batch = resp.json().get("results", [])
        if not batch:
            break

        all_results.extend(batch)
        skip += page_size
        time.sleep(0.2)  # be polite to the API

    return all_results[:max_records]


def raw_reports_to_dataframe(reports: list) -> pd.DataFrame:
    """
    Flattens raw FAERS JSON reports into a tidy dataframe:
    one row per (report, reaction) pair.
    """
    rows = []
    for r in reports:
        safety_report_id = r.get("safetyreportid")
        serious = r.get("serious", "0")
        seriousness_death = r.get("seriousnessdeath", "0")
        seriousness_hosp = r.get("seriousnesshospitalization", "0")
        seriousness_disabling = r.get("seriousnessdisabling", "0")
        seriousness_life_threat = r.get("seriousnesslifethreatening", "0")
        patient = r.get("patient", {})
        age = patient.get("patientonsetage")
        sex = patient.get("patientsex")

        drugs = patient.get("drug", [])
        reactions = patient.get("reaction", [])

        drug_names = [d.get("medicinalproduct", "UNKNOWN") for d in drugs]
        for reaction in reactions:
            pt = reaction.get("reactionmeddrapt", "UNKNOWN")
            for drug_name in drug_names:
                rows.append({
                    "safety_report_id": safety_report_id,
                    "drug": drug_name,
                    "reaction": pt,
                    "serious": int(serious) if str(serious).isdigit() else 0,
                    "seriousness_death": int(seriousness_death) if str(seriousness_death).isdigit() else 0,
                    "seriousness_hospitalization": int(seriousness_hosp) if str(seriousness_hosp).isdigit() else 0,
                    "seriousness_disabling": int(seriousness_disabling) if str(seriousness_disabling).isdigit() else 0,
                    "seriousness_life_threatening": int(seriousness_life_threat) if str(seriousness_life_threat).isdigit() else 0,
                    "patient_age": age,
                    "patient_sex": sex,
                })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    reports = fetch_adverse_events("ibuprofen", max_records=2000)
    df = raw_reports_to_dataframe(reports)
    df.to_csv("../data/adverse_events_raw.csv", index=False)
    print(f"Saved {len(df)} rows for {df['safety_report_id'].nunique()} reports.")
