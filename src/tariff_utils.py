"""Tariff band utilities: map MIBEL hourly prices to Portuguese tariff bands."""
import os
import pandas as pd
from datetime import date

_TARIFAS_CACHE = None

# Display order for bands in the results table
BAND_ORDER = ["Super Vazio", "Vazio", "Cheia", "Ponta", "Fora do Vazio", "Simples"]


def _get_tarifas_path():
    """Locate tarifas.xlsx (project root, one level above src/)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(here, "..", "data", "tarifas.xlsx")
    return os.path.normpath(candidate)


def load_tarifas():
    """Load and cache the tarifas.xlsx file."""
    global _TARIFAS_CACHE
    if _TARIFAS_CACHE is None:
        df = pd.read_excel(_get_tarifas_path())
        # Normalize column names (handle accented chars robustly)
        rename_map = {}
        for col in df.columns:
            low = col.lower()
            if "ciclo" in low and "tipo" in low:
                rename_map[col] = "tipo_ciclo"
            elif "dia" in low:
                rename_map[col] = "tipo_dia"
            elif "esta" in low:  # Estação
                rename_map[col] = "season"
            elif "come" in low:  # Hora de começo
                rename_map[col] = "start"
            elif "fim" in low:
                rename_map[col] = "end"
            elif low == "banda":
                rename_map[col] = "banda"
        df = df.rename(columns=rename_map)
        _TARIFAS_CACHE = df
    return _TARIFAS_CACHE


def get_tipo_ciclo_options():
    """Return the unique 'Tipo de Ciclo' options, ordered sensibly."""
    df = load_tarifas()
    preferred = [
        "Tetra-Horário Ciclo Semanal",
        "Tetra-Horário Ciclo Diário",
        "Tri-Horário Ciclo Semanal",
        "Tri-Horário Ciclo Diário",
        "Bi-Horário Ciclo Semanal",
        "Bi-Horário Ciclo Diário",
        "Simples",
    ]
    actual = list(df["tipo_ciclo"].unique())
    ordered = [c for c in preferred if c in actual]
    ordered += [c for c in actual if c not in ordered]
    return ordered


def _last_sunday(year, month):
    """Return the last Sunday of a given month."""
    d = date(year, month, 28)
    while d.month == month:
        next_d = date(year, month, d.day + 1) if d.day < 31 else None
        if next_d is None or next_d.month != month:
            break
        d = next_d
    # find last sunday <= d
    while d.weekday() != 6:
        d = date(year, month, d.day - 1)
    return d


def _is_summer(ts):
    """Portuguese DST: Summer = last Sunday of March to last Sunday of October."""
    year = ts.year
    dst_start = _last_sunday(year, 3)
    dst_end = _last_sunday(year, 10)
    d = ts.date() if hasattr(ts, "date") else ts
    return dst_start <= d < dst_end


def _day_type(ts):
    wd = ts.weekday()
    if wd == 5:
        return "Saturday"
    if wd == 6:
        return "Sunday"
    return "Weekday"


def _build_hour_to_band_map(tarifas_df, tipo_ciclo):
    """
    Build a dict: (day_type, season) -> list of 24 band labels.
    For each hour H in [0,23], pick the band with the largest coverage over [H, H+1).
    """
    sub = tarifas_df[tarifas_df["tipo_ciclo"] == tipo_ciclo].copy()
    result = {}
    # Gather unique (day_type, season) combos present for this ciclo
    combos = sub[["tipo_dia", "season"]].drop_duplicates().values.tolist()
    for day_type, season in combos:
        rows = sub[(sub["tipo_dia"] == day_type) & (sub["season"] == season)]
        hour_bands = []
        for H in range(24):
            # Compute overlap of each band with [H, H+1)
            best_band = None
            best_overlap = 0.0
            for _, r in rows.iterrows():
                s, e = float(r["start"]), float(r["end"])
                overlap = max(0.0, min(e, H + 1) - max(s, H))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_band = r["banda"]
            hour_bands.append(best_band)
        result[(day_type, season)] = hour_bands
    return result


def _resolve_band(hour_map, day_type, season):
    """Fallback logic to pick the right (day_type, season) entry from the map."""
    # Try exact match first
    if (day_type, season) in hour_map:
        return hour_map[(day_type, season)]
    # Try day_type with 'All' season
    if (day_type, "All") in hour_map:
        return hour_map[(day_type, "All")]
    # Try 'All' day_type with season
    if ("All", season) in hour_map:
        return hour_map[("All", season)]
    # Try all-all
    if ("All", "All") in hour_map:
        return hour_map[("All", "All")]
    return None


def assign_bands(price_df, tipo_ciclo):
    """
    Return a copy of price_df with an extra 'banda' column based on tipo_ciclo.
    price_df must have a DatetimeIndex and a 'price' column.
    """
    if price_df is None or price_df.empty:
        return None
    tarifas = load_tarifas()
    hour_map = _build_hour_to_band_map(tarifas, tipo_ciclo)

    df = price_df.copy()
    idx = pd.to_datetime(df.index)
    bands = []
    for ts in idx:
        dt = _day_type(ts)
        season = "Summer" if _is_summer(ts) else "Winter"
        hours = _resolve_band(hour_map, dt, season)
        if hours is None:
            bands.append(None)
        else:
            bands.append(hours[ts.hour])
    df["banda"] = bands
    return df


def compute_band_averages(price_df, tipo_ciclo):
    """
    Return a DataFrame: columns ['Period', 'Average Price (€/MWh)'] with average
    price per band for the given tipo_ciclo, ordered by BAND_ORDER.
    """
    df = assign_bands(price_df, tipo_ciclo)
    if df is None or "banda" not in df.columns:
        return pd.DataFrame(columns=["Period", "Average Price (€/MWh)"])
    grouped = df.dropna(subset=["banda"]).groupby("banda")["price"].mean()
    order = [b for b in BAND_ORDER if b in grouped.index]
    # Append any bands not in preferred order (safety)
    order += [b for b in grouped.index if b not in order]
    result = pd.DataFrame({
        "Period": order,
        "Average Price (€/MWh)": [round(float(grouped[b]), 2) for b in order]
    })
    return result
