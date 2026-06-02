"""
Open Payments Executive Intelligence dashboard.

Run:  streamlit run app.py
(Run `python -m src.build` first to generate the artifacts.)
"""

import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from src import analytics, schema as S

ROOT = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(ROOT, "artifacts")

st.set_page_config(page_title="Open Payments Intelligence Platform",
                   page_icon="◆", layout="wide", initial_sidebar_state="collapsed")

# ---------- design tokens ----------
NAVY, TEAL, GREEN, AMBER, RED = "#1F3A5F", "#00838F", "#2E7D32", "#F39C12", "#C62828"
COLORWAY = [NAVY, TEAL, GREEN, AMBER, RED, "#6A1B9A", "#5D4037", "#558B2F"]
# One color per entity type, reused everywhere that entity appears (not rainbow bars).
# Deep, muted, cohesive tones; red is reserved for risk, so no neutral entity uses it.
C_HCP, C_HCO, C_SPECIALTY, C_MFR = "#1F4E79", "#2C7A7B", "#5B5E8C", "#4F7A3F"
TIER_COLORS = {"Critical": "#B71C1C", "High": "#E64A19", "Moderate": "#F9A825",
               "Low": "#9E9D24", "Minimal": "#9CA3AF"}
TIER_ORDER = ["Critical", "High", "Moderate", "Low", "Minimal"]

# Distinct, consistent color per nature-of-payment so categories are easy to identify.
NATURE_COLORS = {
    "Grant": "#C0392B",                                           # red (high-scrutiny)
    "Consulting Fee": "#1F4E79",
    "Compensation for serving as faculty or as a speaker": "#6A4C93",
    "Royalty or License": "#1F6F6B",
    "Honoraria": "#7D5A3C",
    "Food and Beverage": "#3E7CB1",
    "Travel and Lodging": "#C77F2E",
    "Education": "#4F7A3F",
    "Gift": "#A14A76",
    "Charitable Contribution": "#8A8A3F",
    "Entertainment": "#5C5C99",
    "Space rental or facility fees": "#566573",
    "Unknown": "#9CA3AF",
}

# ---------- theme system (light default; runtime dark-mode toggle) ----------
ACCENT = "#1F6FB0"  # works on both light and dark
THEMES = {
    "light": {"app_bg": "#ffffff", "text": "#0e1f33", "muted": "#51617a",
              "card_bg": "#ffffff", "border": "#dde4ee", "grid": "#e9eef5",
              "axis": "#33445c", "plot_bg": "white", "template": "plotly_white",
              "readout_bg": "linear-gradient(180deg,#f6faff,#eaf1fb)", "readout_border": "#d3e0f2"},
    "dark": {"app_bg": "#0f1722", "text": "#e8edf4", "muted": "#9fb0c6",
             "card_bg": "#16202e", "border": "#27333f", "grid": "#243140",
             "axis": "#9fb0c6", "plot_bg": "rgba(0,0,0,0)", "template": "plotly_dark",
             "readout_bg": "#16202e", "readout_border": "#2b3a4d"},
}


def _lighten(hex_color, f=0.45):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def inject_css(t):
    st.markdown(f"""
    <style>
    #MainMenu, footer, header [data-testid="stToolbar"] {{visibility: hidden;}}
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{background-color: {t['app_bg']};}}
    /* the top header bar (was leaving a white strip in dark mode) */
    [data-testid="stHeader"] {{background: {t['app_bg']}; }}
    .block-container {{padding-top: 2.4rem; padding-bottom: 2.5rem; max-width: 1480px;}}
    h1, h2, h3 {{color: {t['text']}; font-weight: 800; letter-spacing: -0.4px;}}
    h1 {{font-size: 2.05rem;}}
    [data-testid="stMarkdownContainer"] {{color: {t['text']};}}
    /* st.metric cards (Risk & Provider tabs) follow the theme */
    [data-testid="stMetric"] {{background: {t['card_bg']}; border: 1px solid {t['border']};
        border-radius: 12px; padding: 14px 16px;}}
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{color: {t['muted']} !important;}}
    [data-testid="stMetricValue"] {{color: {t['text']} !important;}}
    /* widget labels + captions stay readable in both themes */
    [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {{color: {t['text']} !important;}}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{color: {t['muted']} !important;}}
    /* sidebar surfaces + text */
    [data-testid="stSidebar"] {{background-color: {t['card_bg']}; border-right: 1px solid {t['border']};}}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {{color: {t['text']} !important;}}
    /* selected multiselect chips: always high-contrast (was low-contrast teal/dark) */
    span[data-baseweb="tag"] {{background-color: {ACCENT} !important; border-radius: 6px;}}
    span[data-baseweb="tag"], span[data-baseweb="tag"] * {{color: #ffffff !important; fill: #ffffff !important;}}
    .readout {{background: {t['readout_bg']}; border: 1px solid {t['readout_border']};
        border-left: 6px solid {ACCENT}; border-radius: 12px; padding: 20px 24px;
        font-size: 1.04rem; line-height: 1.7; color: {t['text']};}}
    .readout b {{color: {t['text']};}}
    .stTabs [data-baseweb="tab-list"] {{gap: 38px; border-bottom: 2px solid {t['border']};}}
    .stTabs [data-baseweb="tab"] {{height: 50px; padding: 0 4px; background: transparent;
        font-size: 1.05rem; font-weight: 700; color: {t['muted']}; letter-spacing: .2px;}}
    .stTabs [aria-selected="true"] {{color: {t['text']} !important; font-weight: 800;
        border-bottom: 3px solid {ACCENT};}}
    .stTabs [data-baseweb="tab-highlight"] {{background-color: transparent;}}
    .eyebrow {{color: {t['muted']}; font-weight:700; font-size:.8rem; letter-spacing:1.2px;
        text-transform:uppercase; margin: 8px 0 2px 0;}}
    .vintage {{color: {t['muted']}; font-size:.84rem; margin: -4px 0 12px 0;}}
    </style>
    """, unsafe_allow_html=True)


def _compact(x):
    """1-significant-decimal compact form, trailing .0 stripped (208.9M, 2.9K, 40)."""
    x = float(x)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            s = f"{x/div:.1f}".rstrip("0").rstrip(".")
            return f"{s}{suf}"
    return f"{x:,.0f}"


def money(x):
    return f"${_compact(x)}"


def num(x):
    """Compact count, truncated to 1 decimal (2,950 -> 2.9K) so it never rounds up."""
    x = float(x)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            v = int(x / div * 10) / 10
            s = f"{v:.1f}".rstrip("0").rstrip(".")
            return f"{s}{suf}"
    return f"{x:,.0f}"


def kpi(label, value, sub="", accent=None, delta=None):
    """Executive KPI card: fixed height + non-wrapping value so all cards are identical."""
    accent = accent or ACCENT
    if DARK:
        accent = _lighten(accent, 0.35)
    delta_html = ""
    if delta:
        col = "#E05757" if str(delta).strip().startswith("-") else "#46B56A"
        delta_html = (f"<div style='color:{col};font-weight:700;font-size:.84rem;"
                      f"margin-top:2px'>{delta}</div>")
    sub_html = (f"<div style='color:{T['muted']};font-size:.78rem;margin-top:3px'>{sub}</div>"
                if sub else "")
    return (f"<div style='background:{T['card_bg']};border:1px solid {T['border']};"
            f"border-left:5px solid {accent};border-radius:12px;padding:14px 16px;"
            f"box-shadow:0 1px 3px rgba(16,24,40,.06);height:150px;box-sizing:border-box;"
            f"overflow:hidden'>"
            f"<div style='color:{T['muted']};font-weight:700;font-size:.74rem;"
            f"text-transform:uppercase;letter-spacing:.6px'>{label}</div>"
            f"<div style='color:{T['text']};font-weight:800;font-size:1.9rem;line-height:1.2;"
            f"margin-top:6px;white-space:nowrap'>{value}</div>{delta_html}{sub_html}</div>")


def style_fig(fig, height=None, legend_bottom=False):
    fig.update_layout(
        template=T["template"], colorway=COLORWAY,
        font=dict(family="Inter, 'Segoe UI', system-ui, sans-serif", size=14, color=T["text"]),
        title=dict(font=dict(size=18, color=T["text"], family="Inter, system-ui, sans-serif"),
                   x=0.01, xanchor="left"),
        margin=dict(l=10, r=10, t=56, b=10), height=height,
        plot_bgcolor=T["plot_bg"], paper_bgcolor=T["plot_bg"],
    )
    if legend_bottom:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.25))
    fig.update_xaxes(showgrid=True, gridcolor=T["grid"], zeroline=False,
                     tickfont=dict(size=13, color=T["axis"]), title_font=dict(size=13, color=T["axis"]))
    fig.update_yaxes(showgrid=True, gridcolor=T["grid"], zeroline=False,
                     tickfont=dict(size=13, color=T["text"]), title_font=dict(size=13, color=T["axis"]))
    return fig


def hbar(df, xcol, ycol, title, color=NAVY, as_money=True, height=380, color_map=None):
    """Strong, high-contrast horizontal bar with value labels (board-ready).

    If color_map is given, each bar is colored by its category value (so categories are
    easy to identify); otherwise a single solid color is used.
    """
    d = df.copy()
    d["_label"] = d[xcol].map(money) if as_money else d[xcol].map(lambda v: f"{v:,.0f}")
    fig = px.bar(d, x=xcol, y=ycol, orientation="h", title=title)
    bar_color = [color_map.get(v, "#9CA3AF") for v in d[ycol]] if color_map else color
    fig.update_traces(marker_color=bar_color, marker_line_width=0,
                      text=d["_label"], textposition="outside",
                      textfont=dict(size=13, color=T["text"]), cliponaxis=False)
    style_fig(fig, height=height)
    # headroom so the largest value label isn't clipped; automargin so y labels never cut off
    fig.update_layout(xaxis_title="", yaxis_title="", margin=dict(l=10, r=90, t=56, b=10))
    fig.update_xaxes(showticklabels=False, showgrid=False,
                     range=[0, float(d[xcol].max()) * 1.18])
    fig.update_yaxes(automargin=True, tickfont=dict(size=13, color=T["text"]))
    return fig


# Executive-friendly names for the internal risk-signal codes.
FLAG_LABELS = {
    "PEER_OUTLIER": "Spend far above specialty peers",
    "HIGH_TOTAL": "Top 1% by total payments",
    "PAYER_CONCENTRATION": "Single-manufacturer dependence",
    "SPEAKER_PROGRAM": "Elevated speaker-program fees",
    "ROUND_DOLLAR": "Round-dollar payment pattern",
    "MEAL_INTENSITY": "High meal / hospitality frequency",
    "LARGE_SINGLE": "Large one-time payment",
    "YOY_SURGE": "Sharp year-over-year increase",
    "CONSULTING_HEAVY": "Consulting / speaker-dominated spend",
    "ML_MULTIVARIATE": "Unusual overall payment profile",
}


def pct_rank_label(pct: float) -> str:
    """Render a within-specialty percentile as an executive-friendly 'Top X%'."""
    if pd.isna(pct):
        return "n/a"
    top = max(0.1, round(100 - pct, 1))
    return f"Top {top:.0f}%" if top >= 1 else f"Top {top:.1f}%"


SPEC_SHORT = {"Physician Assistants & Advanced Practice Nursing Providers": "PAs & APRNs"}


def short_spec(s):
    """Trim the CMS taxonomy to a readable specialty label."""
    last = str(s).split("|")[-1].strip()
    return SPEC_SHORT.get(str(s), SPEC_SHORT.get(last, last))


@st.cache_data
def load_artifacts():
    pay_path = os.path.join(ART, "payments.parquet")
    payments = pd.read_parquet(pay_path) if os.path.exists(pay_path) \
        else pd.read_csv(os.path.join(ART, "payments.csv"))
    payments[S.RECIPIENT_ID] = payments[S.RECIPIENT_ID].astype(str)
    hcp = pd.read_csv(os.path.join(ART, "hcp_summary.csv"))
    hco = pd.read_csv(os.path.join(ART, "hco_summary.csv"))
    hcp[S.RECIPIENT_ID] = hcp[S.RECIPIENT_ID].astype(str)
    hco[S.RECIPIENT_ID] = hco[S.RECIPIENT_ID].astype(str)
    with open(os.path.join(ART, "kpis.json")) as f:
        kpis = json.load(f)
    return payments, hcp, hco, kpis


if not os.path.exists(os.path.join(ART, "kpis.json")):
    # First run (e.g. fresh Streamlit Cloud deploy): generate the data + artifacts.
    with st.spinner("Preparing demonstration data (first run only, ~15s)..."):
        from src.build import main as _build
        _build()

payments, hcp_all, hco_all, K = load_artifacts()

# ---------- header ----------
st.title("Open Payments Intelligence Platform")
st.caption("Industry-wide manufacturer payments to healthcare providers and organizations, "
           "with an explainable Sunshine Act compliance risk engine.")
_years = ", ".join(str(y) for y in K["program_years"])
st.markdown(
    f"<div class='vintage'>Program Years {_years} &nbsp;|&nbsp; {num(K['n_payments'])} "
    f"Payment Records &nbsp;|&nbsp; Synthetic Demonstration Data in the CMS Open Payments Schema</div>",
    unsafe_allow_html=True)

# ---------- always-visible filter + display bar ----------
yrs = sorted(int(y) for y in payments[S.PROGRAM_YEAR].dropna().unique())
types = sorted(payments[S.RECIPIENT_TYPE].dropna().unique())
states = sorted(payments[S.STATE].dropna().unique())
fc = st.columns([1.5, 1.5, 1.5, 0.9])
sel_years = fc[0].multiselect("Program Year", yrs, default=yrs)
sel_types = fc[1].multiselect("Recipient Type", types, default=types)
sel_states = fc[2].multiselect("State", states, default=[])
DARK = fc[3].toggle("Dark mode", value=False, key="dark_mode")

T = THEMES["dark"] if DARK else THEMES["light"]
if DARK:
    C_HCP, C_HCO, C_SPECIALTY, C_MFR = (_lighten(c) for c in (C_HCP, C_HCO, C_SPECIALTY, C_MFR))
    NATURE_COLORS = {k: _lighten(v, 0.40) for k, v in NATURE_COLORS.items()}
    TIER_COLORS = {k: _lighten(v, 0.16) for k, v in TIER_COLORS.items()}
inject_css(T)
st.caption("Filters drive all spend analytics. Risk scores are computed across all program "
           "years. Flags are review signals, not findings.")

# ---------- apply filters ----------
fp = payments[payments[S.PROGRAM_YEAR].isin(sel_years) & payments[S.RECIPIENT_TYPE].isin(sel_types)]
if sel_states:
    fp = fp[fp[S.STATE].isin(sel_states)]
hcp = hcp_all[hcp_all["recipient_type"].isin(sel_types)]
if sel_states:
    hcp = hcp[hcp["state"].isin(sel_states)]

st.write("")
tabs = st.tabs(["Overview", "Risk & Compliance", "Provider Detail",
                "Hospitals & Health Systems", "Competitive Landscape"])

# ================= EXECUTIVE SUMMARY =================
with tabs[0]:
    total = float(fp[S.AMOUNT].sum())
    n_hcp = fp[fp[S.RECIPIENT_TYPE].isin([S.PHYSICIAN, S.NPP])][S.RECIPIENT_ID].nunique()
    n_hco = fp[fp[S.RECIPIENT_TYPE] == S.TEACHING_HOSPITAL][S.RECIPIENT_ID].nunique()
    hs_nat = ["Consulting Fee", "Compensation for serving as faculty or as a speaker",
              "Honoraria", "Royalty or License"]
    hs_spend = float(fp[fp[S.NATURE].isin(hs_nat)][S.AMOUNT].sum())
    hs_share = hs_spend / total if total else 0
    hcp_tot = fp[fp[S.RECIPIENT_TYPE].isin([S.PHYSICIAN, S.NPP])].groupby(S.RECIPIENT_ID)[S.AMOUNT].sum()
    top1 = (hcp_tot.nlargest(max(1, len(hcp_tot)//100)).sum()/hcp_tot.sum()) if len(hcp_tot) else 0
    g = analytics.gini(hcp_tot)
    crit = int((hcp["risk_tier"] == "Critical").sum())
    high = int((hcp["risk_tier"] == "High").sum())
    under_review = float(hcp[hcp["risk_tier"].isin(["Critical", "High"])]["total_amount"].sum())
    by_year = fp.groupby(S.PROGRAM_YEAR)[S.AMOUNT].sum()
    yoy = None
    if len(sel_years) >= 2:
        cur, prev = by_year.get(sel_years[-1]), by_year.get(sel_years[-2])
        if cur is not None and prev:
            yoy = (cur - prev) / prev

    st.markdown("<div class='eyebrow'>At a glance</div>", unsafe_allow_html=True)
    c = st.columns(5)
    c[0].markdown(kpi("Total Amount", money(total),
                      sub="reported transfers of value", accent=NAVY,
                      delta=(f"{yoy*100:+.0f}% vs prior year" if yoy is not None else None)),
                  unsafe_allow_html=True)
    c[1].markdown(kpi("Providers", num(n_hcp),
                      sub=f"{num(n_hco)} hospitals, {num(fp[S.MANUFACTURER].nunique())} mfrs",
                      accent=TEAL), unsafe_allow_html=True)
    c[2].markdown(kpi("High-Risk Providers", num(high + crit),
                      sub="High &amp; Critical tiers", accent=RED), unsafe_allow_html=True)
    c[3].markdown(kpi("Spend Under Review", money(under_review),
                      sub="tied to high-risk providers", accent=RED), unsafe_allow_html=True)
    c[4].markdown(kpi("High-Scrutiny Spend", f"{hs_share*100:.0f}%",
                      sub="consulting, speaker, royalty", accent=AMBER), unsafe_allow_html=True)

    st.write("")
    st.markdown(
        f"<div class='readout'>Across <b>{money(total)}</b> in reported "
        f"payments ({num(len(fp))} records) to <b>{num(n_hcp)} HCPs</b> and {num(n_hco)} HCOs from "
        f"{fp[S.MANUFACTURER].nunique()} manufacturers, the top 1% of providers received "
        f"<b>{top1*100:.0f}%</b> of all HCP value, a concentrated relationship base. "
        f"High-scrutiny categories (consulting, speaker, honoraria, royalty) make up "
        f"<b>{hs_share*100:.0f}%</b> of spend. <b>{high + crit} providers</b> fall in the High or "
        f"Critical risk tier, representing <b>{money(under_review)}</b> that warrants compliance "
        f"review, prioritized on the Risk &amp; Compliance tab with documented reasons."
        + (f" Total spend is <b>{yoy*100:+.0f}%</b> versus the prior program year." if yoy is not None else "")
        + "</div>", unsafe_allow_html=True)

    st.write("")
    st.markdown("<div class='eyebrow'>Largest relationships</div>", unsafe_allow_html=True)
    hcp_mask = fp[S.RECIPIENT_TYPE].isin([S.PHYSICIAN, S.NPP])

    left, right = st.columns(2)
    with left:
        topdocs = (fp[hcp_mask].groupby(S.RECIPIENT_ID)
                   .agg(name=(S.RECIPIENT_NAME, "first"), total=(S.AMOUNT, "sum"))
                   .nlargest(10, "total").sort_values("total"))
        st.plotly_chart(hbar(topdocs, "total", "name",
                             "Top 10 HCPs by Total Amount", color=C_HCP),
                        use_container_width=True)
    with right:
        tophco = (fp[fp[S.RECIPIENT_TYPE] == S.TEACHING_HOSPITAL].groupby(S.RECIPIENT_ID)
                  .agg(name=(S.RECIPIENT_NAME, "first"), total=(S.AMOUNT, "sum"))
                  .nlargest(10, "total").sort_values("total"))
        st.plotly_chart(hbar(tophco, "total", "name",
                             "Top 10 Teaching Hospitals (HCOs) by Amount", color=C_HCO),
                        use_container_width=True)

    st.write("")
    st.markdown("<div class='eyebrow'>Spend Breakdown</div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        nat = analytics.by_dimension(fp, S.NATURE).head(8).sort_values("total_amount")
        st.plotly_chart(hbar(nat, "total_amount", S.NATURE,
                             "Spend by Nature of Payment", color_map=NATURE_COLORS),
                        use_container_width=True)
    with right:
        sp = analytics.by_dimension(fp[hcp_mask], S.SPECIALTY, top=8).copy()
        sp[S.SPECIALTY] = sp[S.SPECIALTY].map(short_spec)
        st.plotly_chart(hbar(sp.sort_values("total_amount"), "total_amount", S.SPECIALTY,
                             "Top Specialties by Spend", color=C_SPECIALTY),
                        use_container_width=True)

    st.write("")
    st.markdown("<div class='eyebrow'>Geography &amp; trend</div>", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        state = analytics.by_dimension(fp, S.STATE)
        fig = px.choropleth(state, locations=S.STATE, locationmode="USA-states",
                            color="total_amount", scope="usa",
                            color_continuous_scale=["#cfe0f2", ACCENT], title="Spend by State")
        fig.update_coloraxes(colorbar_title="Total<br>Amount")
        st.plotly_chart(style_fig(fig, height=380), use_container_width=True)
    with right:
        tr = analytics.monthly_trend(fp)
        tr["month"] = pd.to_datetime(tr["month"])
        fig = px.area(tr, x="month", y="total_amount", title="Monthly Spend Trend",
                      labels={"total_amount": "Total Amount (USD)", "month": ""})
        fig.update_traces(line_color=ACCENT, line_width=2.5, fillcolor="rgba(31,111,176,0.15)")
        st.plotly_chart(style_fig(fig, height=380), use_container_width=True)

# ================= COMPLIANCE WATCHLIST =================
with tabs[1]:
    st.subheader("Provider Risk & Compliance Review")
    st.caption("Every provider scored 0 to 100 from transparent signals and triaged into risk "
               "tiers. Each row documents the basis for review.")

    # risk-tier summary as bold, color-coded cards (board-friendly at a glance)
    tc = hcp["risk_tier"].value_counts().reindex(TIER_ORDER).fillna(0).astype(int)
    tier_value = hcp.groupby("risk_tier")["total_amount"].sum().reindex(TIER_ORDER).fillna(0)
    cards = st.columns(5)
    for col, tier in zip(cards, TIER_ORDER):
        col.markdown(
            f"<div style='background:{TIER_COLORS[tier]};border-radius:12px;padding:14px 16px;"
            f"color:white;box-shadow:0 1px 2px rgba(16,24,40,.08)'>"
            f"<div style='font-size:.82rem;font-weight:600;opacity:.95'>{tier} Risk</div>"
            f"<div style='font-size:1.7rem;font-weight:800;line-height:1.2'>{tc[tier]:,}</div>"
            f"<div style='font-size:.8rem;opacity:.95'>{money(tier_value[tier])} total</div>"
            f"</div>", unsafe_allow_html=True)

    st.write("")
    f1, f2, f3 = st.columns(3)
    sel_tier = f1.multiselect("Risk Tier", TIER_ORDER, default=["Critical", "High"])
    min_total = f2.number_input("Minimum Total Amount ($)", 0, 1_000_000, 0, 1000)
    flag_codes = sorted({fl for s in hcp["flags"].dropna() for fl in s.split("; ") if fl})
    label_to_code = {FLAG_LABELS.get(c, c): c for c in flag_codes}
    picked = f3.multiselect("Risk Indicator Present", sorted(label_to_code))
    pick_flags = [label_to_code[p] for p in picked]

    w = hcp[hcp["risk_tier"].isin(sel_tier) & (hcp["total_amount"] >= min_total)].copy()
    for fl in pick_flags:
        w = w[w["flags"].str.contains(fl, na=False)]
    w = w.sort_values("risk_score", ascending=False)

    k = st.columns(3)
    k[0].metric("Providers in Review Queue", f"{len(w):,}")
    k[1].metric("Combined Amount", money(w["total_amount"].sum()))
    k[2].metric("Avg. Indicators Each", f"{w['n_flags'].mean():.1f}" if len(w) else "0")

    show = w[["recipient_name", "risk_tier", "risk_score", "specialty", "state",
              "total_amount", "specialty_pct", "n_flags", "reasons"]].copy()
    show["specialty"] = show["specialty"].map(short_spec)
    show["specialty_pct"] = show["specialty_pct"].map(pct_rank_label)
    show = show.rename(columns={
        "recipient_name": "Provider", "risk_tier": "Risk Tier", "risk_score": "Risk Score",
        "specialty": "Specialty", "state": "State", "total_amount": "Total Amount",
        "specialty_pct": "Specialty Spend Rank", "n_flags": "Indicators",
        "reasons": "Basis for Review"})

    def _tier_bg(col):
        return [f"background-color:{TIER_COLORS.get(v,'#fff')};color:white;font-weight:700;"
                "text-align:center" for v in col]

    styler = (show.style
              .apply(_tier_bg, subset=["Risk Tier"])
              .format({"Total Amount": "${:,.0f}", "Risk Score": "{:.0f}"})
              .background_gradient(subset=["Risk Score"], cmap="OrRd", vmin=0, vmax=100))
    st.dataframe(styler, use_container_width=True, hide_index=True, height=430)
    st.download_button("Export Review Queue (CSV)",
                       data=w.to_csv(index=False).encode("utf-8"),
                       file_name="compliance_review_queue.csv", mime="text/csv", disabled=w.empty)

# ================= HCP EXPLORER =================
with tabs[2]:
    st.subheader("Provider Detail")
    st.caption("Drill into any individual provider's payment profile and basis for review.")
    names = hcp.sort_values("risk_score", ascending=False)
    labels = {r["recipient_id"]: f"{r['recipient_name']}  ({money(r['total_amount'])}, "
                                 f"risk {int(r['risk_score'])}, {r['risk_tier']})"
              for _, r in names.iterrows()}
    pick = st.selectbox("Select a provider (sorted by risk)", options=list(names["recipient_id"]),
                        format_func=lambda rid: labels.get(rid, str(rid)))
    row = hcp[hcp["recipient_id"] == pick].iloc[0]

    badge = (f"<span style='background:{TIER_COLORS[row['risk_tier']]};color:white;"
             f"padding:3px 12px;border-radius:14px;font-weight:700'>{row['risk_tier']} Risk</span>")
    st.markdown(f"**{row['recipient_name']}** &nbsp; {badge} &nbsp; "
                f"<span style='color:{T['muted']}'>{short_spec(row['specialty'])}, {row['state']}</span>",
                unsafe_allow_html=True)
    c = st.columns(4)
    c[0].metric("Total Amount", money(row["total_amount"]))
    c[1].metric("Risk Score", int(row["risk_score"]))
    c[2].metric("Specialty Spend Rank", pct_rank_label(row["specialty_pct"]),
                help="Where this provider ranks on total payments among peers in the same specialty.")
    c[3].metric("Top Payer Share", f"{row['top_mfr_share']*100:.0f}%",
                help="Share of payments from the single largest manufacturer.")

    if isinstance(row["reasons"], str) and row["reasons"]:
        st.markdown("**Basis for Review:**")
        for reason in row["reasons"].split(" | "):
            st.markdown(f"- :red[{reason}]")
    else:
        st.success("No risk indicators. Payments are within expected ranges for specialty peers.")

    pr = payments[payments[S.RECIPIENT_ID] == pick]
    d1, d2 = st.columns(2)
    with d1:
        bn = pr.groupby(S.NATURE)[S.AMOUNT].sum().reset_index().sort_values(S.AMOUNT)
        st.plotly_chart(hbar(bn, S.AMOUNT, S.NATURE, "Amount by Nature of Payment",
                             color_map=NATURE_COLORS, height=340),
                        use_container_width=True)
    with d2:
        bm = pr.groupby(S.MANUFACTURER)[S.AMOUNT].sum().reset_index() \
            .sort_values(S.AMOUNT, ascending=False).head(10).sort_values(S.AMOUNT)
        st.plotly_chart(hbar(bm, S.AMOUNT, S.MANUFACTURER, "Paying Manufacturers",
                             color=C_MFR, height=340), use_container_width=True)
    st.markdown("##### Transaction Detail")
    tx = (pr[[S.PROGRAM_YEAR, S.DATE, S.MANUFACTURER, S.NATURE, S.PRODUCT, S.AMOUNT]]
          .sort_values(S.AMOUNT, ascending=False)
          .rename(columns={S.PROGRAM_YEAR: "Program Year", S.DATE: "Date",
                           S.MANUFACTURER: "Manufacturer", S.NATURE: "Nature of Payment",
                           S.PRODUCT: "Product", S.AMOUNT: "Amount"}))
    st.dataframe(tx, use_container_width=True, hide_index=True, height=260,
                 column_config={"Amount": st.column_config.NumberColumn(format="$%.2f"),
                                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD")})

# ================= HCOs =================
with tabs[3]:
    st.subheader("Hospitals & Health Systems")
    st.caption("Teaching hospitals and healthcare organizations (HCOs) ranked by total "
               "manufacturer payments received.")
    hco = hco_all.copy()
    if sel_states:
        hco = hco[hco["state"].isin(sel_states)]
    top = hco.nlargest(10, "total_amount").sort_values("total_amount")
    st.plotly_chart(hbar(top, "total_amount", "recipient_name",
                         "Top 10 Teaching Hospitals by Total Amount Received",
                         color=C_HCO, height=440), use_container_width=True)

    st.markdown("##### All Organizations")
    tbl = hco[["recipient_name", "state", "total_amount", "n_transactions", "n_manufacturers",
               "max_single_payment", "top_manufacturer", "top_mfr_share"]].copy()
    tbl["top_mfr_share"] = (tbl["top_mfr_share"] * 100).round(0)
    tbl = tbl.rename(columns={
        "recipient_name": "Organization", "state": "State", "total_amount": "Total Amount",
        "n_transactions": "Transactions", "n_manufacturers": "Manufacturers",
        "max_single_payment": "Largest Payment", "top_manufacturer": "Top Payer",
        "top_mfr_share": "Top Payer Share"})
    st.dataframe(tbl, use_container_width=True, hide_index=True,
                 column_config={
                     "Total Amount": st.column_config.NumberColumn(format="$%d"),
                     "Largest Payment": st.column_config.NumberColumn(format="$%d"),
                     "Top Payer Share": st.column_config.NumberColumn(format="%d%%")})

# ================= MANUFACTURERS / COMPETITIVE =================
with tabs[4]:
    st.subheader("Competitive Landscape")
    st.caption("Because Open Payments is industry-wide, this doubles as competitive intelligence, "
               "showing every manufacturer's footprint, not just one company's.")
    mf = analytics.by_dimension(fp, S.MANUFACTURER)
    st.plotly_chart(hbar(mf.head(10).sort_values("total_amount"), "total_amount", S.MANUFACTURER,
                         "Top 10 Manufacturers by Total Amount", color=C_MFR, height=440),
                    use_container_width=True)

    st.markdown("##### Manufacturer Spend Detail")
    sel = st.selectbox("Manufacturer", mf[S.MANUFACTURER].tolist())
    sub = fp[fp[S.MANUFACTURER] == sel]
    c1, c2 = st.columns(2)
    with c1:
        bn = sub.groupby(S.NATURE)[S.AMOUNT].sum().reset_index().sort_values(S.AMOUNT)
        st.plotly_chart(hbar(bn, S.AMOUNT, S.NATURE, f"{sel}: Amount by Nature",
                             color_map=NATURE_COLORS, height=360), use_container_width=True)
    with c2:
        th = (sub[sub[S.RECIPIENT_TYPE] != S.TEACHING_HOSPITAL]
              .groupby(S.RECIPIENT_NAME)[S.AMOUNT].sum().reset_index()
              .sort_values(S.AMOUNT, ascending=False).head(10).sort_values(S.AMOUNT))
        st.plotly_chart(hbar(th, S.AMOUNT, S.RECIPIENT_NAME, f"{sel}: Top 10 HCP Recipients",
                             color=C_HCP, height=360), use_container_width=True)
