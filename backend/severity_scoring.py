"""
severity_scoring.py
--------------------
Computes a composite severity/risk score per (drug, reaction) signal
using FAERS "seriousness" outcome flags (death, hospitalization,
disability, life-threatening). This turns a purely statistical signal
(PRR/ROR) into a risk-prioritized worklist - which signal should a
human safety reviewer look at FIRST.

Weighted scoring roughly follows how safety teams triage:
  death                -> highest weight
  life-threatening      -> high weight
  disabling              -> medium-high weight
  hospitalization        -> medium weight
"""

import pandas as pd

WEIGHTS = {
    "seriousness_death": 5.0,
    "seriousness_life_threatening": 3.0,
    "seriousness_disabling": 2.0,
    "seriousness_hospitalization": 1.5,
}


def compute_severity(df: pd.DataFrame, signals_df: pd.DataFrame) -> pd.DataFrame:
    """
    df: raw report-reaction level data
    signals_df: output of compute_disproportionality()
    Returns signals_df enriched with severity_score and outcome breakdown.
    """
    grouped = df.groupby(["drug", "reaction"]).agg(
        deaths=("seriousness_death", "sum"),
        life_threatening=("seriousness_life_threatening", "sum"),
        disabling=("seriousness_disabling", "sum"),
        hospitalizations=("seriousness_hospitalization", "sum"),
        n=("safety_report_id", "nunique"),
    ).reset_index()

    grouped["severity_score"] = (
        WEIGHTS["seriousness_death"] * (grouped["deaths"] / grouped["n"]) +
        WEIGHTS["seriousness_life_threatening"] * (grouped["life_threatening"] / grouped["n"]) +
        WEIGHTS["seriousness_disabling"] * (grouped["disabling"] / grouped["n"]) +
        WEIGHTS["seriousness_hospitalization"] * (grouped["hospitalizations"] / grouped["n"])
    ).round(3)

    merged = signals_df.merge(grouped, on=["drug", "reaction"], how="left")

    # priority score = combines statistical strength (PRR) with clinical severity
    merged["priority_score"] = (merged["PRR"].fillna(0) * merged["severity_score"].fillna(0)).round(2)

    return merged.sort_values("priority_score", ascending=False).reset_index(drop=True)


def generate_signal_narrative(row: pd.Series) -> str:
    """
    Auto-drafts a plain-English safety-signal summary paragraph for a
    single drug-reaction pair, in the style of a preliminary PSUR /
    signal evaluation note. Rule-based (not an LLM call) so it's fast,
    deterministic, and auditable - but written to read like a first-pass
    draft a safety scientist would then review and refine.
    """
    drug = row["drug"].title()
    reaction = row["reaction"].title()
    prr = row["PRR"]
    ror = row["ROR"]
    n = row["case_count"]
    deaths = int(row.get("deaths", 0))
    hosp = int(row.get("hospitalizations", 0))

    strength = "strong" if prr >= 4 else "moderate" if prr >= 2 else "weak"

    narrative = (
        f"A potential safety signal has been identified between {drug} and {reaction}. "
        f"Across {n} reports, this combination occurs {prr}x more frequently than expected "
        f"relative to the background reporting rate (PRR = {prr}, ROR = {ror}), representing "
        f"a {strength} disproportionality signal. "
    )

    if deaths > 0 or hosp > 0:
        narrative += (
            f"Of these reports, {deaths} involved a fatal outcome and {hosp} required "
            f"hospitalization, indicating this signal warrants clinical review. "
        )
    else:
        narrative += "No fatal outcomes were recorded among these reports. "

    narrative += (
        "This automated output is a preliminary screening result and should be confirmed "
        "by a qualified pharmacovigilance reviewer against individual case narratives "
        "before any regulatory action is considered."
    )
    return narrative


if __name__ == "__main__":
    df = pd.read_csv("data/adverse_events_raw.csv")
    signals = pd.read_csv("data/signal_results.csv")

    enriched = compute_severity(df, signals)
    enriched["narrative"] = enriched.apply(
        lambda r: generate_signal_narrative(r) if r["signal_detected"] else "", axis=1
    )
    enriched.to_csv("data/signals_enriched.csv", index=False)

    print("Top priority signals:\n")
    top = enriched[enriched["signal_detected"]].head(5)
    for _, row in top.iterrows():
        print(f"### {row['drug']} -> {row['reaction']}  (priority score: {row['priority_score']})")
        print(row["narrative"])
        print()
