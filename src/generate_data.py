"""
Synthetic CMS Open Payments General Payments generator.

Produces a CSV using the *real* CMS raw column names, so the same loader/analytics path
works whether you point it at this file or at a real CMS download. Realistic shape:
the overwhelming majority of transactions are small "Food and Beverage" payments, with a
long tail of consulting/speaker/royalty payments.

Crucially, we deliberately inject known anomaly patterns into a tagged set of recipients
(extreme spend, single-payer concentration, round-dollar speaker fees, meal-bombing,
year-over-year surges, giant single payments) so the anomaly engine has real signal to
find and can be validated.
"""

import numpy as np
import pandas as pd

from src import schema

US_STATES = ["CA", "TX", "NY", "FL", "PA", "IL", "OH", "GA", "NC", "MI", "NJ", "MA", "WA", "AZ"]
PROGRAM_YEARS = [2022, 2023, 2024]

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Linda", "Michael", "Barbara",
         "David", "Susan", "Priya", "Wei", "Carlos", "Aisha", "Daniel", "Sofia"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Rodriguez", "Patel", "Nguyen", "Kim", "Khan", "Lee", "Cohen", "Okafor"]

MANUFACTURERS = [f"{p} {s}" for p in
                 ["Helix", "Northstar", "Apex", "Meridian", "Cardinal", "Vantage", "Orion",
                  "Solera", "Pinnacle", "Crestline", "Beacon", "Tidewater"]
                 for s in ["Therapeutics", "Biosciences", "Medical", "Pharma"]][:40]


def _round_to(x, base):
    return base * max(1, round(x / base))


def generate(seed: int = 7, n_physicians: int = 2600, n_npps: int = 350,
             n_hospitals: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    products = {m: f"{m.split()[0]}-{rng.integers(100, 999)}" for m in MANUFACTURERS}

    def mfr_product(rec_rng):
        m = MANUFACTURERS[rec_rng.integers(len(MANUFACTURERS))]
        return m, products[m]

    def add(year, rtype, rid, npi, fname, lname, hosp, spec, city, state, zp,
            mfr, amount, date, npay, form, nature, product):
        rows.append({
            "Program_Year": year,
            "Covered_Recipient_Type": rtype,
            "Covered_Recipient_Profile_ID": rid,
            "Covered_Recipient_NPI": npi,
            "Covered_Recipient_First_Name": fname,
            "Covered_Recipient_Last_Name": lname,
            "Teaching_Hospital_Name": hosp,
            "Covered_Recipient_Specialty_1": spec,
            "Recipient_City": city,
            "Recipient_State": state,
            "Recipient_Zip_Code": zp,
            "Applicable_Manufacturer_or_Applicable_GPO_Making_Payment_Name": mfr,
            "Total_Amount_of_Payment_USDollars": round(float(amount), 2),
            "Date_of_Payment": date,
            "Number_of_Payments_Included_in_Total_Amount": npay,
            "Form_of_Payment_or_Transfer_of_Value": form,
            "Nature_of_Payment_or_Transfer_of_Value": nature,
            "Name_of_Drug_or_Biological_or_Device_or_Medical_Supply_1": product,
        })

    def rand_date(year):
        return f"{year}-{rng.integers(1, 13):02d}-{rng.integers(1, 29):02d}"

    # ----- build recipient roster -----
    physicians = []
    for i in range(n_physicians):
        physicians.append({
            "rid": 100000 + i,
            "npi": int(1000000000 + rng.integers(0, 899999999)),
            "fname": FIRST[rng.integers(len(FIRST))],
            "lname": LAST[rng.integers(len(LAST))],
            "spec": schema.SPECIALTIES[rng.integers(len(schema.SPECIALTIES))],
            "state": US_STATES[rng.integers(len(US_STATES))],
            "rtype": "Covered Recipient Physician",
            # latent engagement: most low, a few high
            "engage": float(rng.beta(1.3, 6.0)),
        })
    for i in range(n_npps):
        physicians.append({
            "rid": 200000 + i,
            "npi": int(1000000000 + rng.integers(0, 899999999)),
            "fname": FIRST[rng.integers(len(FIRST))],
            "lname": LAST[rng.integers(len(LAST))],
            "spec": "Physician Assistants & Advanced Practice Nursing Providers",
            "state": US_STATES[rng.integers(len(US_STATES))],
            "rtype": "Covered Recipient Non-Physician Practitioner",
            "engage": float(rng.beta(1.2, 7.0)),
        })

    # ----- choose anomaly cohorts (tagged physician indices) -----
    idx = rng.permutation(len(physicians))
    anom = {
        "extreme_total": set(idx[0:18]),
        "concentration": set(idx[18:40]),
        "round_dollar": set(idx[40:60]),
        "meal_bomb": set(idx[60:78]),
        "yoy_surge": set(idx[78:98]),
        "giant_single": set(idx[98:110]),
    }

    # ----- generate per-physician payments -----
    for pi, p in enumerate(physicians):
        base_meals = 1 + rng.poisson(2 + 18 * p["engage"])  # most people: a few meals
        for year in PROGRAM_YEARS:
            year_scale = 1.0
            if pi in anom["yoy_surge"] and year == max(PROGRAM_YEARS):
                year_scale = rng.uniform(6, 12)  # sudden escalation in latest year

            # meals (small, frequent — the bulk of all Open Payments rows)
            n_meals = base_meals
            if pi in anom["meal_bomb"]:
                n_meals = int(base_meals + rng.integers(120, 320))
            for _ in range(int(n_meals * year_scale ** 0.0)):  # meals not scaled by surge
                m, prod = mfr_product(rng)
                add(year, p["rtype"], p["rid"], p["npi"], p["fname"], p["lname"], "",
                    p["spec"], "City", p["state"], f"{rng.integers(10000,99999)}",
                    m, rng.uniform(12, 180), rand_date(year), 1,
                    "In-kind items and services", "Food and Beverage", prod)

            # consulting / speaker / honoraria (the money that matters)
            n_prof = rng.poisson(0.6 + 5 * p["engage"])
            conc_mfr = MANUFACTURERS[rng.integers(len(MANUFACTURERS))]
            for _ in range(n_prof):
                if pi in anom["concentration"]:
                    m, prod = conc_mfr, products[conc_mfr]  # funnel through one payer
                else:
                    m, prod = mfr_product(rng)
                nature = rng.choice(
                    ["Consulting Fee", "Compensation for serving as faculty or as a speaker",
                     "Honoraria", "Travel and Lodging", "Education"],
                    p=[0.34, 0.30, 0.12, 0.14, 0.10])
                amt = rng.uniform(800, 5000) * (1 + 4 * p["engage"]) * year_scale
                if pi in anom["round_dollar"] and nature.startswith("Compensation"):
                    amt = _round_to(amt, 500)  # suspiciously clean speaker fees
                add(year, p["rtype"], p["rid"], p["npi"], p["fname"], p["lname"], "",
                    p["spec"], "City", p["state"], f"{rng.integers(10000,99999)}",
                    m, amt, rand_date(year), 1, "Cash or cash equivalent", nature, prod)

            # extreme-total cohort: pile on high-value consulting
            if pi in anom["extreme_total"]:
                for _ in range(rng.integers(6, 14)):
                    m, prod = mfr_product(rng)
                    add(year, p["rtype"], p["rid"], p["npi"], p["fname"], p["lname"], "",
                        p["spec"], "City", p["state"], f"{rng.integers(10000,99999)}",
                        m, rng.uniform(8000, 30000), rand_date(year), 1,
                        "Cash or cash equivalent", "Consulting Fee", prod)

            # giant single payment (e.g., royalty / license)
            if pi in anom["giant_single"] and year == max(PROGRAM_YEARS):
                m, prod = mfr_product(rng)
                add(year, p["rtype"], p["rid"], p["npi"], p["fname"], p["lname"], "",
                    p["spec"], "City", p["state"], f"{rng.integers(10000,99999)}",
                    m, rng.uniform(120000, 600000), rand_date(year), 1,
                    "Cash or cash equivalent", "Royalty or License", prod)

    # ----- teaching hospitals (HCOs) -----
    hosp_names = [f"{c} {t} Medical Center" for c in
                  ["Riverside", "Summit", "Lakeview", "Mercy", "St. Augustine", "Highland",
                   "Cedar", "Bayfront", "Granite", "Fairview", "Westgate", "Pioneer"]
                  for t in ["University", "Regional", "Memorial"]][:n_hospitals]
    for hi, hn in enumerate(hosp_names):
        scale = rng.lognormal(0.0, 1.0)
        state = US_STATES[rng.integers(len(US_STATES))]
        for year in PROGRAM_YEARS:
            for _ in range(int(2 + rng.poisson(6) * (1 + scale))):
                m, prod = mfr_product(rng)
                nature = rng.choice(["Grant", "Charitable Contribution", "Space rental or facility fees",
                                     "Education", "Consulting Fee"], p=[0.4, 0.2, 0.15, 0.15, 0.1])
                add(year, "Covered Recipient Teaching Hospital", 900000 + hi, "", "", "",
                    hn, "", "City", state, f"{rng.integers(10000,99999)}",
                    m, rng.uniform(2000, 90000) * (1 + scale), rand_date(year),
                    1, "Cash or cash equivalent", nature, prod)

    df = pd.DataFrame(rows)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


if __name__ == "__main__":
    import os
    out = os.path.join(os.path.dirname(__file__), "..", "data", "open_payments_synthetic.csv")
    df = generate()
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} payment rows -> {os.path.abspath(out)}")
    print(f"Total value: ${df['Total_Amount_of_Payment_USDollars'].sum():,.0f}")
