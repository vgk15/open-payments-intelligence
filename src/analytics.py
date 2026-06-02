"""
Aggregations for the executive views: spend rollups by recipient, manufacturer,
nature of payment, specialty, geography, and time.
"""

from __future__ import annotations

import pandas as pd

from src import schema as S


def _latest_year(df: pd.DataFrame) -> int:
    return int(df[S.PROGRAM_YEAR].dropna().max())


def recipient_summary(df: pd.DataFrame, recipient_types: list[str]) -> pd.DataFrame:
    """One row per recipient with the features the dashboard and anomaly engine use."""
    d = df[df[S.RECIPIENT_TYPE].isin(recipient_types)].copy()
    latest = _latest_year(d)

    is_meal = d[S.NATURE].eq("Food and Beverage")
    is_prof = d[S.NATURE].isin(
        ["Consulting Fee", "Compensation for serving as faculty or as a speaker", "Honoraria"])
    # speaker programs are a distinct, high-scrutiny category (OIG 2020 Special Fraud Alert)
    is_speaker = d[S.NATURE].str.contains("speaker", case=False, na=False)
    # round-dollar = exact multiple of $500 and >= $1,000
    amt = d[S.AMOUNT]
    is_round = (amt >= 1000) & (amt.mod(500).eq(0))

    d = d.assign(_meal=is_meal, _prof=is_prof, _speaker=is_speaker,
                 _prof_amt=amt.where(is_prof, 0.0), _speaker_amt=amt.where(is_speaker, 0.0),
                 _round_amt=amt.where(is_round, 0.0))

    g = d.groupby([S.RECIPIENT_ID])
    summ = g.agg(
        recipient_name=(S.RECIPIENT_NAME, "first"),
        recipient_type=(S.RECIPIENT_TYPE, "first"),
        specialty=(S.SPECIALTY, "first"),
        state=(S.STATE, "first"),
        npi=(S.NPI, "first"),
        total_amount=(S.AMOUNT, "sum"),
        n_transactions=(S.AMOUNT, "size"),
        max_single_payment=(S.AMOUNT, "max"),
        n_manufacturers=(S.MANUFACTURER, "nunique"),
        n_meals=("_meal", "sum"),
        prof_amount=("_prof_amt", "sum"),
        speaker_amount=("_speaker_amt", "sum"),
        round_amount=("_round_amt", "sum"),
    ).reset_index()

    # top-manufacturer share (payer concentration)
    by_mfr = d.groupby([S.RECIPIENT_ID, S.MANUFACTURER])[S.AMOUNT].sum().reset_index()
    top = by_mfr.sort_values(S.AMOUNT, ascending=False).groupby(S.RECIPIENT_ID).head(1)
    top = top.rename(columns={S.MANUFACTURER: "top_manufacturer", S.AMOUNT: "top_mfr_amount"})
    summ = summ.merge(top[[S.RECIPIENT_ID, "top_manufacturer", "top_mfr_amount"]],
                      on=S.RECIPIENT_ID, how="left")
    summ["top_mfr_share"] = (summ["top_mfr_amount"] / summ["total_amount"]).clip(0, 1)
    summ["prof_share"] = (summ["prof_amount"] / summ["total_amount"]).clip(0, 1)
    summ["speaker_share"] = (summ["speaker_amount"] / summ["total_amount"]).clip(0, 1)
    summ["round_share"] = (summ["round_amount"] / summ["total_amount"]).clip(0, 1)

    # percentile of total spend WITHIN specialty (defensible peer benchmarking)
    summ["specialty_pct"] = (summ.groupby("specialty")["total_amount"]
                             .rank(pct=True) * 100).round(1)

    # year-over-year on total spend
    yr = d.groupby([S.RECIPIENT_ID, S.PROGRAM_YEAR])[S.AMOUNT].sum().unstack(fill_value=0.0)
    if latest in yr.columns:
        prior_cols = [c for c in yr.columns if c < latest]
        prior = yr[max(prior_cols)] if prior_cols else 0.0
        summ = summ.merge(
            pd.DataFrame({S.RECIPIENT_ID: yr.index,
                          "latest_year_amount": yr[latest].values,
                          "prior_year_amount": (prior.values if prior_cols else 0.0)}),
            on=S.RECIPIENT_ID, how="left")
        summ["yoy_growth"] = (summ["latest_year_amount"] - summ["prior_year_amount"]) / \
                             summ["prior_year_amount"].replace(0, pd.NA)
    return summ.sort_values("total_amount", ascending=False).reset_index(drop=True)


def by_dimension(df: pd.DataFrame, col: str, top: int | None = None) -> pd.DataFrame:
    out = (df.groupby(col)[S.AMOUNT].agg(total_amount="sum", n_transactions="size")
           .reset_index().sort_values("total_amount", ascending=False))
    return out.head(top) if top else out.reset_index(drop=True)


def gini(values) -> float:
    """Gini coefficient of spend across recipients (0 = even, 1 = fully concentrated)."""
    x = pd.Series(values).dropna().to_numpy(dtype=float)
    x = x[x >= 0]
    if x.size == 0 or x.sum() == 0:
        return 0.0
    x.sort()
    n = x.size
    cum = (2 * (pd.Series(range(1, n + 1)).to_numpy()) - n - 1) * x
    return float(cum.sum() / (n * x.sum()))


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    d = df.dropna(subset=[S.DATE]).copy()
    d["month"] = d[S.DATE].dt.to_period("M").dt.to_timestamp()
    return (d.groupby("month")[S.AMOUNT].sum().reset_index()
            .rename(columns={S.AMOUNT: "total_amount"}))
