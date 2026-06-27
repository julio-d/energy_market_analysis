"""
Throwaway test script: query ENTSO-E Transparency API for Spain aFRR + mFRR data.

Coverage (Spain, control area 10YES-REE------0):
  1. aFRR band (capacity) prices + quantities, per direction
  2. aFRR activation prices (€/MWh), per direction
  3. aFRR activation quantities (MW activated / offered), per direction
  4. mFRR activation prices (€/MWh), per direction
  5. mFRR activation quantities (MW activated / offered), per direction

mFRR has no band (capacity auction) in the Spanish system.

Run:
    python test_entsoe_afrr.py

Delete this file after verifying it works.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

try:
    import tomllib  # py311+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

from entsoe import EntsoePandasClient


def load_token() -> str:
    tok = os.environ.get("ENTSOE_API_KEY") or os.environ.get("ENTSOE_API_TOKEN")
    if tok:
        return tok
    secrets_path = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        with open(secrets_path, "rb") as f:
            data = tomllib.load(f)
        if "ENTSOE_API_KEY" in data:
            return data["ENTSOE_API_KEY"]
        if "entsoe" in data and isinstance(data["entsoe"], dict) and "ENTSOE_API_KEY" in data["entsoe"]:
            return data["entsoe"]["ENTSOE_API_KEY"]
    raise RuntimeError(
        "ENTSO-E API token not found. Set ENTSOE_API_TOKEN env var or add it to .streamlit/secrets.toml"
    )


def _section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _show(df) -> None:
    if df is None:
        return
    shape = getattr(df, "shape", None)
    cols = list(df.columns) if hasattr(df, "columns") else "<series>"
    print(f"shape={shape}  columns={cols}")
    print(df.head(8))
    print("...")
    print(df.tail(3))


def main() -> int:
    token = load_token()
    client = EntsoePandasClient(api_key=token)

    country = "ES"
    # Historical window with confirmed published data.
    start = pd.Timestamp("2024-06-01", tz="Europe/Madrid")
    end = pd.Timestamp("2024-06-02", tz="Europe/Madrid")

    print(f"ENTSO-E queries for {country}  {start}  ->  {end}")

    # ---------- aFRR band (capacity) ----------
    # documentType=A89 under the hood, processType A51 = aFRR, TMA A01 = daily
    _section("[1] aFRR BAND (capacity) - prices + quantities (Up/Down)")
    try:
        df = client.query_contracted_reserve_prices_procured_capacity(
            country, start=start, end=end,
            process_type="A51", type_marketagreement_type="A01",
        )
        _show(df)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # ---------- aFRR activation prices ----------
    # documentType=A84, processType=A16 (realised), businessType=A96 (aFRR)
    _section("[2] aFRR ACTIVATION prices (€/MWh, Up/Down)")
    try:
        df = client.query_activated_balancing_energy_prices(
            country, start=start, end=end,
            process_type="A16", business_type="A96",
        )
        _show(df)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # ---------- aFRR activation quantities ----------
    # query_aggregated_bids: processType A51 = aFRR -> Activated + Offered MW per direction
    _section("[3] aFRR ACTIVATION quantities (MW activated + offered, Up/Down)")
    try:
        df = client.query_aggregated_bids(
            country, start=start, end=end, process_type="A51",
        )
        _show(df)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # ---------- mFRR activation prices ----------
    _section("[4] mFRR ACTIVATION prices (€/MWh, Up/Down)")
    try:
        df = client.query_activated_balancing_energy_prices(
            country, start=start, end=end,
            process_type="A16", business_type="A97",
        )
        _show(df)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    # ---------- mFRR activation quantities ----------
    # processType A47 = mFRR direct activation (Spain's terciaria)
    _section("[5] mFRR ACTIVATION quantities (MW activated + offered, Up/Down)")
    try:
        df = client.query_aggregated_bids(
            country, start=start, end=end, process_type="A47",
        )
        _show(df)
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
