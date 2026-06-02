"""
Explainable anomaly / risk engine for Open Payments recipients.

Philosophy: an executive needs a *prioritized, defensible* watchlist, not a black box.
Each recipient gets a 0-100 composite risk score built from interpretable signals, and
every flag carries a plain-English reason. A multivariate Isolation Forest score is added
as a supplementary signal to catch odd combinations the rules miss.

Signals
  PEER_OUTLIER       total spend is a robust-z outlier WITHIN the recipient's specialty
  HIGH_TOTAL         total spend in the top 1% overall
  PAYER_CONCENTRATION one manufacturer is >=80% of the recipient's money (and it's material)
  ROUND_DOLLAR       >=70% of value is in exact round-dollar payments
  MEAL_INTENSITY     number of meal transactions in the top 1%
  LARGE_SINGLE       a single payment in the extreme tail (top 0.5%)
  YOY_SURGE          latest-year spend jumped sharply vs the prior year
  CONSULTING_HEAVY   consulting/speaker/honoraria dominate at high absolute value
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# weight each flag contributes to the composite (points, pre-normalization)
WEIGHTS = {
    "PEER_OUTLIER": 26,
    "HIGH_TOTAL": 16,
    "PAYER_CONCENTRATION": 16,
    "SPEAKER_PROGRAM": 16,
    "ROUND_DOLLAR": 12,
    "MEAL_INTENSITY": 10,
    "LARGE_SINGLE": 14,
    "YOY_SURGE": 14,
    "CONSULTING_HEAVY": 10,
}

MATERIAL_FLOOR = 5000.0  # ignore concentration/round-dollar below this total

# Compliance risk tiers — how a CCO actually triages a watchlist.
RISK_TIERS = [(70, "Critical"), (50, "High"), (25, "Moderate"), (1, "Low"), (0, "Minimal")]


def tier_for(score_value: int) -> str:
    for threshold, label in RISK_TIERS:
        if score_value >= threshold:
            return label
    return "Minimal"


def _robust_z_within(group: pd.Series) -> pd.Series:
    """Median/MAD z-score within a group (robust to the long Open Payments tail)."""
    med = group.median()
    mad = (group - med).abs().median()
    scale = 1.4826 * mad
    if scale == 0:
        return pd.Series(0.0, index=group.index)
    return (group - med) / scale


def score(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary.copy()
    n = len(df)
    if n == 0:
        return df

    # thresholds
    total_p99 = df["total_amount"].quantile(0.99)
    meals_p99 = df["n_meals"].quantile(0.99)
    single_p995 = df["max_single_payment"].quantile(0.995)

    # peer-relative robust z within specialty
    df["peer_z"] = (df.groupby("specialty")["total_amount"]
                    .transform(_robust_z_within).fillna(0.0))

    flags, reasons, points = [], [], np.zeros(n)
    cols = {
        "PEER_OUTLIER": df["peer_z"] >= 3.5,
        "HIGH_TOTAL": df["total_amount"] >= total_p99,
        "PAYER_CONCENTRATION": (df["top_mfr_share"] >= 0.80) & (df["total_amount"] >= MATERIAL_FLOOR),
        "ROUND_DOLLAR": (df["round_share"] >= 0.70) & (df["total_amount"] >= MATERIAL_FLOOR),
        "SPEAKER_PROGRAM": (df["speaker_amount"] >= 10000) & (df["speaker_share"] >= 0.40),
        "MEAL_INTENSITY": df["n_meals"] >= max(meals_p99, 30),
        "LARGE_SINGLE": df["max_single_payment"] >= max(single_p995, 25000),
        "CONSULTING_HEAVY": (df["prof_share"] >= 0.70) & (df["total_amount"] >= 10000),
    }
    if "yoy_growth" in df:
        cols["YOY_SURGE"] = (df["yoy_growth"] >= 3.0) & (df["prior_year_amount"] >= 1000)

    reason_text = {
        "PEER_OUTLIER": lambda r: "Total spend far exceeds peers in the same specialty",
        "HIGH_TOTAL": lambda r: f"Total ${r['total_amount']:,.0f} is in the top 1% of all recipients",
        "PAYER_CONCENTRATION": lambda r: f"{r['top_mfr_share']*100:.0f}% of payments come from one manufacturer ({r['top_manufacturer']})",
        "SPEAKER_PROGRAM": lambda r: f"{r['speaker_share']*100:.0f}% is speaker-program fees, an OIG high-scrutiny category",
        "ROUND_DOLLAR": lambda r: f"{r['round_share']*100:.0f}% is paid in exact round-dollar amounts",
        "MEAL_INTENSITY": lambda r: f"{int(r['n_meals'])} meal transactions (top 1%)",
        "LARGE_SINGLE": lambda r: f"Single payment of ${r['max_single_payment']:,.0f}",
        "YOY_SURGE": lambda r: f"Spend grew {r['yoy_growth']*100:.0f}% vs prior year",
        "CONSULTING_HEAVY": lambda r: f"{r['prof_share']*100:.0f}% is consulting and speaker fees",
    }

    flag_lists, reason_lists = [[] for _ in range(n)], [[] for _ in range(n)]
    for name, mask in cols.items():
        m = mask.fillna(False).to_numpy()
        points += m * WEIGHTS[name]
        for i in np.where(m)[0]:
            flag_lists[i].append(name)
            reason_lists[i].append(reason_text[name](df.iloc[i]))

    # supplementary multivariate outlier score (Isolation Forest)
    feats = df[["total_amount", "n_transactions", "max_single_payment", "n_manufacturers",
                "n_meals", "top_mfr_share", "prof_share", "round_share"]].fillna(0.0)
    feats = np.log1p(feats.clip(lower=0)) if False else feats  # keep raw; IF handles scale
    iso = IsolationForest(n_estimators=200, contamination=0.02, random_state=0)
    iso.fit(feats)
    iso_raw = -iso.score_samples(feats)  # higher = more anomalous
    iso_norm = (iso_raw - iso_raw.min()) / (np.ptp(iso_raw) + 1e-9)
    df["ml_outlier_score"] = (iso_norm * 100).round(1)
    iso_flag = iso.predict(feats) == -1
    points += iso_flag * 8
    for i in np.where(iso_flag)[0]:
        if "ML_MULTIVARIATE" not in flag_lists[i]:
            flag_lists[i].append("ML_MULTIVARIATE")
            reason_lists[i].append("Unusual combination of payment features (Isolation Forest)")

    df["risk_score"] = np.clip(points, 0, 100).round(0).astype(int)
    df["risk_tier"] = df["risk_score"].map(tier_for)
    df["n_flags"] = [len(f) for f in flag_lists]
    df["flags"] = ["; ".join(f) for f in flag_lists]
    df["reasons"] = [" | ".join(r) for r in reason_lists]
    return df.sort_values(["risk_score", "total_amount"], ascending=False).reset_index(drop=True)
