"""
Build pipeline: load (or generate) data -> aggregate -> score anomalies -> persist
artifacts the dashboard reads.

Usage:
  python -m src.build                      # generate synthetic data and build
  python -m src.build --input PATH.csv     # build from a real CMS General Payments CSV
"""

import argparse
import json
import os

import pandas as pd

from src import analytics, anomalies, load, schema as S
from src.generate_data import generate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ART = os.path.join(ROOT, "artifacts")
DATA = os.path.join(ROOT, "data")

HCP_TYPES = [S.PHYSICIAN, S.NPP]
HCO_TYPES = [S.TEACHING_HOSPITAL]


def main(input_path: str | None = None):
    os.makedirs(ART, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    if input_path:
        print(f"Loading real CMS file: {input_path}")
        df = load.load(input_path, chunksize=500_000)
    else:
        raw_path = os.path.join(DATA, "open_payments_synthetic.csv")
        if not os.path.exists(raw_path):
            print("Generating synthetic Open Payments data ...")
            generate().to_csv(raw_path, index=False)
        df = load.load(raw_path)

    print(f"Loaded {len(df):,} payment rows, ${df[S.AMOUNT].sum():,.0f} total value.")

    # recipient-level summaries + risk scoring
    hcp = anomalies.score(analytics.recipient_summary(df, HCP_TYPES))
    hco = analytics.recipient_summary(df, HCO_TYPES)

    # dimensional rollups
    nature = analytics.by_dimension(df, S.NATURE)
    specialty = analytics.by_dimension(df[df[S.RECIPIENT_TYPE].isin(HCP_TYPES)], S.SPECIALTY, top=15)
    state = analytics.by_dimension(df, S.STATE)
    manufacturer = analytics.by_dimension(df, S.MANUFACTURER)
    product = analytics.by_dimension(df, S.PRODUCT, top=20)
    trend = analytics.monthly_trend(df)

    # KPIs (framed for executives: dollars, exposure, concentration)
    flagged = hcp[hcp["risk_score"] > 0]
    high_plus = hcp[hcp["risk_tier"].isin(["High", "Critical"])]
    high_scrutiny_nat = ["Consulting Fee", "Compensation for serving as faculty or as a speaker",
                         "Honoraria", "Royalty or License"]
    high_scrutiny_spend = float(df[df[S.NATURE].isin(high_scrutiny_nat)][S.AMOUNT].sum())
    speaker_spend = float(df[df[S.NATURE].str.contains("speaker", case=False, na=False)][S.AMOUNT].sum())
    years = sorted(int(y) for y in df[S.PROGRAM_YEAR].dropna().unique())
    yoy_total = None
    if len(years) >= 2:
        by_year = df.groupby(S.PROGRAM_YEAR)[S.AMOUNT].sum()
        prev, cur = float(by_year.get(years[-2], 0)), float(by_year.get(years[-1], 0))
        yoy_total = (cur - prev) / prev if prev else None

    kpis = {
        "total_value": float(df[S.AMOUNT].sum()),
        "n_payments": int(len(df)),
        "n_hcps": int(hcp[S.RECIPIENT_ID].nunique()),
        "n_hcos": int(hco[S.RECIPIENT_ID].nunique()),
        "n_manufacturers": int(df[S.MANUFACTURER].nunique()),
        "median_payment": float(df[S.AMOUNT].median()),
        "pct_value_top1pct_hcp": float(
            hcp.nlargest(max(1, len(hcp) // 100), "total_amount")["total_amount"].sum()
            / hcp["total_amount"].sum()) if len(hcp) else 0.0,
        "gini_hcp": analytics.gini(hcp["total_amount"]),
        "n_flagged_hcps": int(len(flagged)),
        "high_risk_hcps": int(len(high_plus)),
        "value_under_review": float(high_plus["total_amount"].sum()),
        "high_scrutiny_spend": high_scrutiny_spend,
        "high_scrutiny_share": high_scrutiny_spend / float(df[S.AMOUNT].sum()) if len(df) else 0.0,
        "speaker_spend": speaker_spend,
        "tier_counts": hcp["risk_tier"].value_counts().to_dict(),
        "yoy_total": yoy_total,
        "program_years": years,
    }

    # persist
    df.to_parquet(os.path.join(ART, "payments.parquet")) if _has_parquet() else \
        df.to_csv(os.path.join(ART, "payments.csv"), index=False)
    hcp.to_csv(os.path.join(ART, "hcp_summary.csv"), index=False)
    hco.to_csv(os.path.join(ART, "hco_summary.csv"), index=False)
    nature.to_csv(os.path.join(ART, "nature_summary.csv"), index=False)
    specialty.to_csv(os.path.join(ART, "specialty_summary.csv"), index=False)
    state.to_csv(os.path.join(ART, "state_summary.csv"), index=False)
    manufacturer.to_csv(os.path.join(ART, "manufacturer_summary.csv"), index=False)
    product.to_csv(os.path.join(ART, "product_summary.csv"), index=False)
    trend.to_csv(os.path.join(ART, "monthly_trend.csv"), index=False)
    with open(os.path.join(ART, "kpis.json"), "w") as f:
        json.dump(kpis, f, indent=2)

    # report
    print(f"\nHCPs: {kpis['n_hcps']:,} | HCOs: {kpis['n_hcos']:,} | "
          f"Manufacturers: {kpis['n_manufacturers']}")
    print(f"Flagged HCPs: {kpis['n_flagged_hcps']:,} (high-risk >=50: {kpis['high_risk_hcps']:,})")
    print(f"Top 1% of HCPs hold {kpis['pct_value_top1pct_hcp']*100:.1f}% of all HCP value.\n")
    print("Top 8 watchlist:")
    cols = ["recipient_name", "specialty", "total_amount", "risk_score", "flags"]
    with pd.option_context("display.max_colwidth", 40, "display.width", 160):
        print(hcp[cols].head(8).to_string(index=False))
    print(f"\nArtifacts written to {ART}")


def _has_parquet():
    try:
        import pyarrow  # noqa: F401
        return True
    except Exception:
        return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="Path to a real CMS General Payments CSV")
    args = ap.parse_args()
    main(args.input)
