# PharmaSignal — AI-Assisted Adverse Event Signal Detection

A pharmacovigilance tool that detects potential drug safety signals from
adverse event reports using the same disproportionality statistics
(PRR, ROR) that regulators like the FDA and EMA use, then layers on
automated severity scoring and AI-drafted signal summaries to help a
safety reviewer triage findings faster.

Inspired by real pharmacovigilance/drug-safety products (e.g. Oracle
Argus Safety, Genpact's AI pharmacovigilance offerings) — built on FDA's
own public FAERS data.

## Why this project

Pharma companies hiring AI/ML engineers overwhelmingly need people who
can work with **regulated, high-stakes clinical data** — not just build
a generic classifier. This project demonstrates:
- Working with real regulatory data schemas (FAERS / openFDA)
- Understanding of actual pharmacovigilance methodology (PRR/ROR,
  case-count thresholds, chi-squared significance testing)
- Turning a statistical signal into something a *human reviewer* can
  act on (severity-weighted prioritization + draft narrative)
- Responsible AI framing: every output is explicitly labeled as a
  preliminary/draft finding requiring human sign-off — the kind of
  guardrail a real pharma safety team requires

## Architecture

```
openFDA FAERS API  ──►  fetch_data.py          (raw JSON → tidy dataframe)
                         │
                         ▼
                   signal_detection.py          (PRR / ROR / chi-squared
                         │                       per drug-reaction pair)
                         ▼
                   severity_scoring.py           (death/hosp/disability-
                         │                        weighted priority score +
                         │                        auto-drafted narrative)
                         ▼
                   dashboard/index.html          (signal worklist +
                                                   contingency table +
                                                   narrative viewer)
```

## Methodology

For each (drug, reaction) pair, a 2×2 contingency table is built:

|                  | Reaction of interest | All other reactions |
|------------------|----------------------|----------------------|
| Drug of interest | a                    | b                    |
| All other drugs  | c                    | d                    |

- **PRR** (Proportional Reporting Ratio) = [a/(a+b)] / [c/(c+d)]
- **ROR** (Reporting Odds Ratio) = (a·d) / (b·c)
- A signal is flagged using the standard **Evans et al. (2001)** criteria:
  PRR ≥ 2, chi-squared ≥ 4, case count ≥ 3

Signals are then re-ranked by a **priority score** = PRR × severity,
where severity is a weighted function of death/life-threatening/
disabling/hospitalization outcome rates — so a statistically modest
signal with several deaths can outrank a stronger statistical signal
with only mild outcomes.

## Data

The live pipeline (`src/fetch_data.py`) pulls real, public adverse event
reports from **FDA's openFDA API** (FAERS database) — no API key
required. This repo also ships a synthetic-but-schema-identical dataset
(`src/generate_synthetic_data.py`) with 5 deliberately planted signals,
used to validate that the statistical engine correctly recovers known
signals (it does — see below).

## Validation

Running the detector on the synthetic dataset (15,000 reports, 5 planted
signals) correctly recovered **all 5** planted signals with no false
negatives:

| Drug | Reaction | PRR | ROR | Priority score |
|------|----------|-----|-----|-----------------|
| Tramadol | Seizure | 6.85 | 8.74 | 7.16 |
| Sertraline | Suicidal ideation | 4.31 | 5.77 | 4.08 |
| Warfarin | GI haemorrhage | 3.78 | 7.33 | 3.71 |
| Atorvastatin | Liver injury | 3.29 | 3.87 | 3.05 |
| Prednisone | Tendon rupture | 2.83 | 5.90 | 2.69 |

## Running it

```bash
cd src
python3 generate_synthetic_data.py     # or fetch_data.py for live FAERS data
python3 signal_detection.py
python3 severity_scoring.py
```

Then open `dashboard/index.html` in any browser — it's a self-contained
static file with the analysis results embedded.

## Extending this (feature ideas if you want to keep building)

- Swap `fetch_data.py`'s single-drug query for a full drug-class scan
- Add a time-windowed view (signals emerging in the last N months vs.
  all-time) — real pharmacovigilance cares a lot about *new* signals
- Replace the rule-based narrative generator with an actual LLM call
  (Claude/GPT) constrained to only reference the computed statistics —
  useful talking point on hallucination control in regulated settings
- Add MedDRA hierarchy grouping (rolling up granular reaction terms to
  System Organ Class) for a more clinically standard view

## CV bullet you could use

> Built an adverse-event signal detection pipeline using FDA FAERS data
> and pharmacovigilance disproportionality statistics (PRR/ROR),
> including severity-weighted risk prioritization and automated draft
> safety-signal summaries; validated detection accuracy against known
> planted signals in a synthetic benchmark.
