"""
Load and normalize Open Payments data.

Accepts either the synthetic demo CSV or a real CMS General Payments download, and maps
the raw CMS columns (which vary by program year) onto the tidy internal schema. Real CMS
files are large, so this reads only the columns we need and can chunk through big files.
"""

from __future__ import annotations

import pandas as pd

from src import schema


def _pick(colnames, candidates):
    """Return the first candidate present in colnames, else None."""
    cols = set(colnames)
    for c in candidates:
        if c in cols:
            return c
    return None


def _needed_raw_columns(header) -> dict:
    """Resolve which raw CMS column feeds each tidy field, given an actual file header."""
    resolved = {}
    for tidy, candidates in schema.CMS_TO_TIDY.items():
        src = _pick(header, candidates)
        if src:
            resolved[tidy] = src
    name_parts = {}
    for part, candidates in schema.NAME_PART_COLUMNS.items():
        src = _pick(header, candidates)
        if src:
            name_parts[part] = src
    return resolved, name_parts


def load(path: str, chunksize: int | None = None) -> pd.DataFrame:
    """Load a CMS-format CSV (synthetic or real) into the tidy schema."""
    header = pd.read_csv(path, nrows=0).columns.tolist()
    resolved, name_parts = _needed_raw_columns(header)
    usecols = list(set(resolved.values()) | set(name_parts.values()))

    reader = pd.read_csv(path, usecols=usecols, dtype=str, chunksize=chunksize,
                         low_memory=False)
    chunks = reader if chunksize else [reader]
    out = []
    for raw in chunks:
        out.append(_normalize(raw, resolved, name_parts))
    df = pd.concat(out, ignore_index=True)
    return df


def _normalize(raw: pd.DataFrame, resolved: dict, name_parts: dict) -> pd.DataFrame:
    df = pd.DataFrame()
    for tidy, src in resolved.items():
        df[tidy] = raw[src]

    # assemble recipient name (physician first/last, else teaching hospital)
    first = raw[name_parts["first"]] if "first" in name_parts else ""
    last = raw[name_parts["last"]] if "last" in name_parts else ""
    person = (pd.Series(first).fillna("").str.strip() + " "
              + pd.Series(last).fillna("").str.strip()).str.strip()
    hosp = raw[name_parts["hospital"]].fillna("").str.strip() if "hospital" in name_parts \
        else pd.Series([""] * len(raw))
    df[schema.RECIPIENT_NAME] = person.where(person.str.len() > 0, hosp)

    # types & cleanup
    df[schema.AMOUNT] = pd.to_numeric(df.get(schema.AMOUNT), errors="coerce")
    df[schema.N_PAYMENTS] = pd.to_numeric(df.get(schema.N_PAYMENTS), errors="coerce").fillna(1)
    df[schema.PROGRAM_YEAR] = pd.to_numeric(df.get(schema.PROGRAM_YEAR), errors="coerce").astype("Int64")
    df[schema.DATE] = pd.to_datetime(df.get(schema.DATE), errors="coerce")
    df[schema.RECIPIENT_TYPE] = (df.get(schema.RECIPIENT_TYPE, "")
                                 .map(schema.RECIPIENT_TYPE_MAP)
                                 .fillna(df.get(schema.RECIPIENT_TYPE)))
    for c in [schema.SPECIALTY, schema.STATE, schema.MANUFACTURER, schema.NATURE,
              schema.FORM, schema.PRODUCT]:
        if c in df:
            df[c] = df[c].fillna("Unknown").replace("", "Unknown")

    df = df[df[schema.AMOUNT].notna() & (df[schema.AMOUNT] > 0)]
    return df.reset_index(drop=True)
