import os
import re
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def _sanitize(message: str) -> str:
    """Strip the ENTSO-E security token (and raw API key) from any string.

    ENTSO-E errors echo the full request URL, which embeds ``securityToken=<key>``
    in plaintext. We also scrub the raw key value in case it appears elsewhere.
    """
    text = str(message)
    text = re.sub(r"securityToken=[^&\s]+", "securityToken=***", text, flags=re.IGNORECASE)
    try:
        key = _get_entsoe_key()
    except Exception:
        key = None
    if key:
        text = text.replace(key, "***")
    return text

# Mapping from the app's country label to ENTSO-E bidding-zone code.
# entsoe-py resolves short codes like "ES" / "PT" internally.
_ENTSOE_ZONE = {
    "Spain": "ES",
    "Portugal": "PT",
}

# Local timezone used by the rest of the app (Iberian market, naive timestamps).
_LOCAL_TZ = "Europe/Madrid"


def _get_entsoe_key():
    """Fetch the ENTSO-E API key from Streamlit secrets or environment."""
    try:
        key = st.secrets.get("ENTSOE_API_KEY")
        if key:
            return key
    except Exception as e:
        logger.debug("st.secrets lookup failed: %s", e)
    return os.environ.get("ENTSOE_API_KEY")


def _to_local_naive_index(series_or_df):
    """Convert a tz-aware index to Europe/Madrid and drop tz info."""
    idx = series_or_df.index
    if getattr(idx, "tz", None) is not None:
        series_or_df = series_or_df.tz_convert(_LOCAL_TZ).tz_localize(None)
    return series_or_df


def _load_via_entsoe(start_date, end_date, country):
    """Fetch day-ahead prices from ENTSO-E at native resolution.

    Returns a DataFrame indexed by tz-naive local datetime with a single
    ``price`` column (EUR/MWh). Raises on any failure so the caller can
    trigger the MIBEL-library fallback.
    """
    from entsoe import EntsoePandasClient

    api_key = _get_entsoe_key()
    if not api_key:
        raise RuntimeError("ENTSOE_API_KEY is not configured")

    zone = _ENTSOE_ZONE.get(country, "ES")

    # Build tz-aware timestamps. ENTSO-E's "end" is exclusive, so add one day
    # to include the full end_date.
    start_ts = pd.Timestamp(start_date).tz_localize(_LOCAL_TZ)
    end_ts = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).tz_localize(_LOCAL_TZ)

    client = EntsoePandasClient(api_key=api_key)
    series = client.query_day_ahead_prices(zone, start=start_ts, end=end_ts)

    if series is None or len(series) == 0:
        raise RuntimeError("ENTSO-E returned no data")

    df = series.to_frame(name="price")
    df = _to_local_naive_index(df)

    # Trim strictly to the requested window (inclusive start, exclusive next day).
    window_start = pd.Timestamp(start_date)
    window_end = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    df = df.loc[(df.index >= window_start) & (df.index < window_end)]

    if df.empty:
        raise RuntimeError("ENTSO-E returned no data within the requested window")

    df.sort_index(inplace=True)
    df.attrs["source"] = "ENTSO-E"
    return df


def _load_via_mibel_library(start_date, end_date, country):
    """Legacy MIBEL importer (backed by the OMIEData package, kept as a fallback). Returns hourly prices."""
    from OMIEData.DataImport.omie_marginalprice_importer import (
        OMIEMarginalPriceFileImporter,
    )
    from OMIEData.Enums.all_enums import DataTypeInMarginalPriceFile

    if not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, datetime.min.time())
    if not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, datetime.min.time())

    df = OMIEMarginalPriceFileImporter(
        date_ini=start_date, date_end=end_date
    ).read_to_dataframe(verbose=False)

    if df.empty:
        return None

    if country == "Portugal":
        str_price = str(DataTypeInMarginalPriceFile.PRICE_PORTUGAL)
    else:
        str_price = str(DataTypeInMarginalPriceFile.PRICE_SPAIN)

    df_prices = df[df.CONCEPT == str_price].copy()
    if df_prices.empty:
        return None

    price_data = []
    for _, row in df_prices.iterrows():
        date = row["DATE"]
        for hour in range(1, 25):
            hour_col = f"H{hour}"
            if hour_col in row:
                timestamp = pd.Timestamp(date) + pd.Timedelta(hours=hour - 1)
                price_data.append({"datetime": timestamp, "price": row[hour_col]})

    result_df = pd.DataFrame(price_data)
    if result_df.empty:
        return None
    result_df.set_index("datetime", inplace=True)
    result_df.sort_index(inplace=True)
    result_df.attrs["source"] = "MIBEL library"
    return result_df


@st.cache_data(show_spinner=False)
def load_mibel_data(start_date, end_date, country="Spain"):
    """Load MIBEL Iberian day-ahead prices.

    Primary source: ENTSO-E Transparency Platform (native resolution, may be
    15-min or 60-min depending on the period/zone).
    Fallback: MIBEL library via the OMIEData package (hourly) if ENTSO-E fails or returns empty.

    Returns a DataFrame indexed by tz-naive ``datetime`` with a single
    ``price`` column. ``df.attrs['source']`` indicates which provider served
    the data.
    """
    # Try ENTSO-E first.
    try:
        df = _load_via_entsoe(start_date, end_date, country)
        return df
    except Exception as e:
        safe_err = _sanitize(e)
        logger.warning("ENTSO-E fetch failed, falling back to MIBEL library: %s", safe_err)
        st.info(
            "Primary data source is temporarily unavailable. "
            "Loading prices from the backup source instead..."
        )

    # MIBEL-library fallback.
    try:
        df = _load_via_mibel_library(start_date, end_date, country)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        logger.exception("MIBEL library fallback failed: %s", _sanitize(e))
        st.error(
            "Could not load market data right now. "
            "Please try again in a few minutes or pick a different date range."
        )
        return None
