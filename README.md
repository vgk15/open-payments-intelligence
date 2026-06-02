# Open Payments Intelligence Platform


**[▶ Click here to launch dashboard](https://open-payments-intelligence-kuhwtwnk9mzt3gvkjl2taa.streamlit.app/)**

**The problem:** Every year, drug and device manufacturers report billions of dollars in
payments to physicians and teaching hospitals under the **Physician Payments Sunshine Act**,
published in the public **CMS Open Payments** database. Buried in those millions of records are
the relationships that matter to executives, including both the commercial relationships that drive
brand performance and the anomalous ones that create anti-kickback and FCPA exposure. The data
is too large and too raw for a leadership team to read directly.

**Project Outcomes:** Raw CMS Open Payments data is translated into a decision-ready executive
dashboard with an **explainable compliance risk engine**, accomplishing 3 key tasks:

1. Summarizes industry-wide spend by nature of payment, specialty, geography, manufacturer, and year.
2. Scores every healthcare provider (HCP) 0 to 100 for compliance risk using interpretable signals and states the reason for each flag.
3. Allows compliance and commercial teams to deep-dive into any HCP, teaching hospital, or manufacturer.

The platform ships with a synthetic dataset modeled on the CMS General Payments data structure, including realistic, intentionally embedded anomalies. It operates immediately out of the box and can seamlessly ingest and analyze real CMS General Payments downloads using the same pipeline.

## Risk Engine

Each provider receives a 0–100 score and is triaged into a **risk tier** (Critical / High /
Moderate / Low / Minimal) — the way a compliance team actually prioritizes a review queue. The
score is built from transparent signals, every one of which is shown to the user with its reason:

| Signal | Documented Information |
|---|---|
| **Peer outlier** | Spend far above peers *in the same specialty* (robust z-score), with specialty percentile |
| **High total** | Total payments in the top 1% of all recipients |
| **Payer concentration** | One manufacturer is ≥80% of a recipient's money (kickback-risk pattern) |
| **Speaker program** | Material speaker-program fees — identified in OIG's 2020 Special Fraud Alert |
| **Round-dollar** | ≥70% of value in exact round-dollar payments (negotiated lump fees) |
| **Meal intensity** | Unusually high number of food/beverage transactions (over-detailing) |
| **Large single** | A single payment in the extreme tail |
| **YoY surge** | Sharp jump in spend versus the prior program year |
| **Consulting-heavy** | Consulting/speaker/honoraria dominate at high absolute value |
| **ML multivariate** | Isolation Forest catches odd *combinations* the rules miss |

### Executive Metrics

Beyond the watchlist, the summary surfaces the numbers a CCO or commercial lead answers for:
**value under review** (dollars tied to High/Critical providers), **high-scrutiny spend share**
(consulting / speaker / honoraria / royalty), **spend concentration** (Gini coefficient and
top-1% share), and **year-over-year** movement — wrapped in an auto-generated plain-English
executive readout.

## Setup

```bash
cd openpayments-intel
pip install -r requirements.txt
```

## Run

```bash
python -m src.build        # generate synthetic data, aggregate, score risk, write artifacts/
streamlit run app.py       # launch the executive dashboard
```

To use real data, download a CMS Open Payments *General Payments* CSV from
<https://openpaymentsdata.cms.gov/> and run:

```bash
python -m src.build --input /path/to/OP_DTL_GNRL_PGYR2023.csv
```

## Dashboard

- **Executive Summary** — total value, recipient/manufacturer counts, spend concentration, spend by nature/specialty/state, monthly trend.
- **Compliance Watchlist** — every recipient scored and ranked, with reason codes, filters by flag type, and CSV export.
- **HCP Explorer** — drill into one provider: why flagged, payment mix, top payers, full transaction list.
- **Teaching Hospitals (HCOs)** — top organizations by payments received.
- **Manufacturers & Competitive** — spend by manufacturer and where each one's money goes.

## Project layout

| Path | Purpose |
|------|---------|
| `src/schema.py` | Tidy schema + mapping from real CMS column names (handles year-to-year drift) |
| `src/generate_data.py` | Synthetic CMS-format data with embedded anomalies |
| `src/load.py` | Loads & normalizes synthetic or real CMS files (chunked for large downloads) |
| `src/analytics.py` | Recipient and dimensional spend rollups |
| `src/anomalies.py` | Explainable risk scoring + Isolation Forest |
| `src/build.py` | Orchestrates load → aggregate → score → persist |
| `app.py` | Streamlit executive dashboard |

## Notes for the compliance reader

- The demonstration data is synthetic; figures are illustrative, not real reported payments.
- A flag is a **review signal, not a finding.** Open Payments captures many legitimate
  high-value relationships (e.g., royalties to device inventors, bona fide research). The engine
  prioritizes what a human should look at, with the reasoning made explicit.
- This tool models the **General Payments** file. Open Payments also publishes separate
  **Research Payments** and **Ownership/Investment Interest** files; a production deployment
  would ingest all three (research dollars in particular should be assessed differently).
- The Sunshine Act sets an annually indexed **de minimis** per-payment threshold (~$13–14) and an
  aggregate annual threshold (~$130+); the round-dollar and meal-intensity signals are designed
  partly to surface patterns near those reporting boundaries.

## Tech

Python · pandas · NumPy · scikit-learn · Plotly · Streamlit
