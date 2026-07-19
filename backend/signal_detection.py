"""
signal_detection.py
--------------------
Implements the two standard pharmacovigilance disproportionality
statistics used by real drug safety teams and regulators to detect
"signals" - i.e. is a drug associated with a reaction MORE than you'd
expect by chance, given everything else in the database?

PRR = Proportional Reporting Ratio   (used by MHRA, EMA)
ROR = Reporting Odds Ratio           (used by FDA, widely in literature)

Both are computed from a 2x2 contingency table for each (drug, reaction) pair:

                    Reaction of interest   All other reactions
Drug of interest            a                      b
All other drugs             c                      d

PRR = [a / (a+b)] / [c / (c+d)]
ROR = (a * d) / (b * c)

A signal is typically flagged when, by convention (e.g. Evans et al. 2001):
  - PRR >= 2
  - Chi-squared >= 4
  - a (case count) >= 3
"""

import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency


def compute_disproportionality(df: pd.DataFrame) -> pd.DataFrame:
    """
    df must have columns: drug, reaction (one row per report-reaction pair)
    Returns a dataframe with one row per (drug, reaction) pair and the
    PRR, ROR, chi-squared stat, and signal flag.
    """
    total_reports = df["safety_report_id"].nunique()

    # counts of (drug, reaction) pairs -> a
    pair_counts = df.groupby(["drug", "reaction"])["safety_report_id"].nunique().reset_index()
    pair_counts.columns = ["drug", "reaction", "a"]

    # total reports per drug -> a + b
    drug_totals = df.groupby("drug")["safety_report_id"].nunique().to_dict()

    # total reports per reaction -> a + c
    reaction_totals = df.groupby("reaction")["safety_report_id"].nunique().to_dict()

    results = []
    for _, row in pair_counts.iterrows():
        drug, reaction, a = row["drug"], row["reaction"], row["a"]

        drug_total = drug_totals[drug]
        reaction_total = reaction_totals[reaction]

        b = drug_total - a                       # this drug, other reactions
        c = reaction_total - a                    # other drugs, this reaction
        d = total_reports - drug_total - reaction_total + a  # other drugs, other reactions

        if a < 3:  # standard minimum case-count threshold (Evans et al.)
            continue

        # PRR
        try:
            prr = (a / (a + b)) / (c / (c + d))
        except ZeroDivisionError:
            prr = np.nan

        # ROR
        try:
            ror = (a * d) / (b * c) if (b > 0 and c > 0) else np.nan
        except ZeroDivisionError:
            ror = np.nan

        # Chi-squared test on the 2x2 table
        table = [[a, b], [c, d]]
        try:
            chi2, p_value, _, _ = chi2_contingency(table, correction=True)
        except ValueError:
            chi2, p_value = np.nan, np.nan

        is_signal = bool(prr >= 2 and chi2 >= 4 and a >= 3)

        results.append({
            "drug": drug,
            "reaction": reaction,
            "case_count": a,
            "a": int(a),
            "b": int(b),
            "c": int(c),
            "d": int(d),
            "drug_total_reports": drug_total,
            "reaction_total_reports": reaction_total,
            "PRR": round(prr, 2) if prr == prr else None,
            "ROR": round(ror, 2) if ror == ror else None,
            "chi_squared": round(chi2, 2) if chi2 == chi2 else None,
            "p_value": round(p_value, 5) if p_value == p_value else None,
            "signal_detected": is_signal,
        })

    result_df = pd.DataFrame(results)
    return result_df.sort_values(["signal_detected", "PRR"], ascending=[False, False]).reset_index(drop=True)


if __name__ == "__main__":
    df = pd.read_csv("data/adverse_events_raw.csv")
    signals = compute_disproportionality(df)
    signals.to_csv("data/signal_results.csv", index=False)
    print(f"Computed disproportionality for {len(signals)} drug-reaction pairs.")
    print(f"Flagged {signals['signal_detected'].sum()} potential safety signals.\n")
    print(signals[signals["signal_detected"]].head(15).to_string(index=False))
