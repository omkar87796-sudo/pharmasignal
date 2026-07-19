"""
generate_synthetic_data.py
---------------------------
Generates a realistic, FAERS-schema-compatible adverse event dataset
for offline development/demo purposes. Baked-in "signals" are planted
so the PRR/ROR detector has something real to find (e.g. a drug that
genuinely over-reports a specific reaction relative to the rest of
the dataset, mimicking a true safety signal).

Swap this module for fetch_data.py + raw_reports_to_dataframe() when
you have live internet access to the openFDA API - the downstream
pipeline (signal_detection.py, severity_scoring.py) doesn't change.
"""

import numpy as np
import pandas as pd

np.random.seed(42)

DRUGS = [
    "IBUPROFEN", "METFORMIN", "ATORVASTATIN", "LISINOPRIL",
    "OMEPRAZOLE", "SERTRALINE", "AMOXICILLIN", "PREDNISONE",
    "WARFARIN", "TRAMADOL"
]

REACTIONS = [
    "NAUSEA", "HEADACHE", "DIZZINESS", "RASH", "FATIGUE",
    "GASTROINTESTINAL HAEMORRHAGE", "LIVER INJURY", "ANAPHYLACTIC REACTION",
    "MYOCARDIAL INFARCTION", "ACUTE KIDNEY INJURY", "SEIZURE",
    "HYPOGLYCAEMIA", "TENDON RUPTURE", "SUICIDAL IDEATION", "INSOMNIA"
]

# Planted true signals: (drug, reaction, relative_risk_multiplier)
PLANTED_SIGNALS = [
    ("TRAMADOL", "SEIZURE", 8.0),
    ("WARFARIN", "GASTROINTESTINAL HAEMORRHAGE", 6.0),
    ("SERTRALINE", "SUICIDAL IDEATION", 4.5),
    ("PREDNISONE", "TENDON RUPTURE", 5.0),
    ("ATORVASTATIN", "LIVER INJURY", 3.5),
]


def generate(n_reports: int = 15000) -> pd.DataFrame:
    rows = []
    report_id = 100000

    # base reaction probabilities (background rate across all drugs)
    base_probs = np.random.dirichlet(np.ones(len(REACTIONS)) * 2)

    for _ in range(n_reports):
        report_id += 1
        drug = np.random.choice(DRUGS)
        n_reactions_this_report = np.random.choice([1, 1, 1, 2, 2, 3])

        probs = base_probs.copy()
        for (sig_drug, sig_reaction, mult) in PLANTED_SIGNALS:
            if drug == sig_drug:
                idx = REACTIONS.index(sig_reaction)
                probs[idx] *= mult
        probs = probs / probs.sum()

        chosen_reactions = np.random.choice(
            REACTIONS, size=n_reactions_this_report, replace=False, p=probs
        )

        is_serious_reaction_set = any(
            r in ["GASTROINTESTINAL HAEMORRHAGE", "LIVER INJURY", "ANAPHYLACTIC REACTION",
                  "MYOCARDIAL INFARCTION", "ACUTE KIDNEY INJURY", "SEIZURE",
                  "TENDON RUPTURE", "SUICIDAL IDEATION"]
            for r in chosen_reactions
        )
        serious = 1 if (is_serious_reaction_set and np.random.random() < 0.75) else np.random.choice([0, 1], p=[0.85, 0.15])

        death = 1 if (serious and np.random.random() < 0.04) else 0
        hosp = 1 if (serious and np.random.random() < 0.35) else 0
        disabling = 1 if (serious and np.random.random() < 0.1) else 0
        life_threat = 1 if (serious and np.random.random() < 0.12) else 0

        age = int(np.clip(np.random.normal(52, 18), 1, 95))
        sex = np.random.choice([1, 2])  # 1=male, 2=female (FAERS convention)

        for reaction in chosen_reactions:
            rows.append({
                "safety_report_id": report_id,
                "drug": drug,
                "reaction": reaction,
                "serious": serious,
                "seriousness_death": death,
                "seriousness_hospitalization": hosp,
                "seriousness_disabling": disabling,
                "seriousness_life_threatening": life_threat,
                "patient_age": age,
                "patient_sex": sex,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate(15000)
    df.to_csv("/home/claude/pharmasignal/data/adverse_events_raw.csv", index=False)
    print(f"Generated {len(df)} rows across {df['safety_report_id'].nunique()} reports.")
    print(df.head())
