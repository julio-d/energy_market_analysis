import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, date
from data_loader import load_mibel_data

def fetch_pvgis_hourly(lat: float, lon: float, start_year: int, end_year: int, peak_power_kwp: float = 1000.0):
    """
    Fetch hourly PV power generation from PVGIS API (PVcalc endpoint).
    Returns a DataFrame with hourly generation (kW) indexed by datetime (UTC).
    """
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
    
    # PVGIS seriescalc supports years between 2005 and 2020 (or latest available TMY/historical range).
    if start_year < 2005 or start_year > 2020:
        start_year = 2020
    if end_year < 2005 or end_year > 2020:
        end_year = 2020
    if start_year > end_year:
        start_year = end_year
        
    params = {
        'lat': lat,
        'lon': lon,
        'outputformat': 'json',
        'startyear': start_year,
        'endyear': end_year,
        'pvcalculation': 1,
        'peakpower': peak_power_kwp,
        'loss': 14.0,  # standard system loss
        'angle': 35,   # optimal tilt or default
        'aspect': 0    # south facing
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code != 200:
            st.error(f"PVGIS API error: HTTP status {response.status_code}")
            return None
        
        data = response.json()
        if 'outputs' not in data or 'hourly' not in data['outputs']:
            st.error("Unexpected response format from PVGIS API.")
            return None
            
        hourly_list = data['outputs']['hourly']
        df = pd.DataFrame(hourly_list)
        
        # PVGIS datetime format: YYYYMMDD:HHMM
        def parse_pvgis_time(t_str):
            try:
                dt_part, hm_part = t_str.split(':')
                year = int(dt_part[0:4])
                month = int(dt_part[4:6])
                day = int(dt_part[6:8])
                hour = int(hm_part[0:2])
                minute = int(hm_part[2:4])
                return pd.Timestamp(year=year, month=month, day=day, hour=hour, minute=minute)
            except Exception:
                return pd.NaT

        df['datetime'] = df['time'].apply(parse_pvgis_time)
        df = df.dropna(subset=['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 'P' column is power output in Watts (W) for the given peakpower kWp (1 kWp default).
        # We want generation in kW per 1 kWp installed (or generic generation profile).
        # 1 W = 0.001 kW. For peakpower=1.0 kWp, P [W] / 1000 = power [kW].
        if 'P' in df.columns:
            df['generation_kw'] = df['P'] / 1000.0
        elif 'G(i)' in df.columns:
            df['generation_kw'] = df['G(i)'] / 1000.0
        else:
            df['generation_kw'] = pd.to_numeric(df.iloc[:, 1], errors='coerce').fillna(0) / 1000.0
            
        # Ensure timezone naive UTC index to match MIBEL data
        df.index = df.index.tz_localize(None)
        
        return df[['generation_kw']]
        
    except Exception as e:
        st.error(f"Failed to fetch or process PVGIS data: {e}")
        return None

def render_pv_plant_tab():
    """Render the PV Plant Simulation and Captured Price Tab"""
    st.subheader("☀️ PV Plant Simulation & Captured Price Analysis", help="Simulate a generic 1 MWp PV plant using PVGIS coordinates and analyze captured market prices and sun hours.")
    
    st.markdown("""
    Select a location preset or choose 'Custom' to enter custom coordinates. The tool queries PVGIS for hourly generation profiles (1 MWp nominal), 
    aligns them with the selected MIBEL market price period (matching market data frequency: hourly or 15-minute), calculates the **captured market price**, and displays sun hour statistics and shaded price charts.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    city_presets = {
        "Porto (Portugal)": ("41.1579", "-8.6291"),
        "Lisbon (Portugal)": ("38.7223", "-9.1393"),
        "Coimbra (Portugal)": ("40.2033", "-8.4103"),
        "Faro (Portugal)": ("37.0194", "-7.9304"),
        "Madrid (Spain)": ("40.4168", "-3.7038"),
        "Seville (Spain)": ("37.3891", "-5.9845"),
        "Barcelona (Spain)": ("41.3879", "2.1699"),
        "Malaga (Spain)": ("36.7213", "-4.4214"),
        "Custom": ("41.1579", "-8.6291")
    }

    with col1:
        preset = st.selectbox("Location Preset", list(city_presets.keys()), index=0)

    is_custom = (preset == "Custom")
    preset_lat, preset_lon = city_presets[preset]

    with col2:
        lat_input = st.text_input(
            "Latitude", 
            value=preset_lat, 
            disabled=not is_custom,
            help="Latitude in decimal degrees"
        )

    with col3:
        lon_input = st.text_input(
            "Longitude", 
            value=preset_lon, 
            disabled=not is_custom,
            help="Longitude in decimal degrees"
        )

    if st.button("Simulate PV Plant & Calculate Captured Price", type="primary"):
        try:
            lat = float(lat_input)
            lon = float(lon_input)
        except ValueError:
            st.error("Invalid latitude or longitude format. Please enter valid numeric coordinates.")
            return
            
        if not st.session_state.get('data_submitted', False):
            st.warning("⚠️ Please first select your date range and country in the main dashboard sidebar/filters and click 'Load Data' so market prices are loaded.")
            return
            
        start_date = st.session_state.submitted_start_date
        end_date = st.session_state.submitted_end_date
        country = st.session_state.submitted_country
        
        with st.spinner(f"Loading MIBEL market data for {country} ({start_date} to {end_date})..."):
            mibel_data = load_mibel_data(start_date, end_date, country)
            
        if mibel_data is None or mibel_data.empty:
            st.error("Failed to load MIBEL market data for the selected period.")
            return
            
        # Calculate interval duration (in hours) for each row in mibel_data
        # Handles mixed datasets (e.g. 1h before 2025-10-01 and 15min on/after 2025-10-01)
        time_diffs = mibel_data.index.to_series().diff().shift(-1)
        if len(time_diffs) > 1:
            time_diffs.iloc[-1] = time_diffs.iloc[-2]
        dt_hours = time_diffs.dt.total_seconds() / 3600.0
        dt_hours = dt_hours.fillna(1.0)
        dt_hours = dt_hours.apply(lambda x: x if x > 0 else 1.0)
        
        # Determine years required for PVGIS
        start_year = start_date.year
        end_year = end_date.year
        
        if start_year > 2020:
            start_year = 2020
        if end_year > 2020:
            end_year = 2020
        if start_year < 2005:
            start_year = 2005
        if end_year < start_year:
            end_year = start_year
            
        with st.spinner(f"Fetching PVGIS hourly generation for coordinates ({lat}, {lon}) ..."):
            pv_df = fetch_pvgis_hourly(lat, lon, start_year, end_year, peak_power_kwp=1000.0)
            
        if pv_df is None or pv_df.empty:
            st.error("Could not retrieve PVGIS generation data for these coordinates.")
            return
            
        # Map PVGIS hourly generation profile to target dates by matching month, day, hour
        pv_df_reset = pv_df.copy()
        pv_df_reset['month'] = pv_df_reset.index.month
        pv_df_reset['day'] = pv_df_reset.index.day
        pv_df_reset['hour'] = pv_df_reset.index.hour
        # Handle leap years or Feb 29
        pv_df_reset = pv_df_reset[~((pv_df_reset['month'] == 2) & (pv_df_reset['day'] == 29))]
        
        # Create target dataframe index based on mibel_data timestamps
        target_df = pd.DataFrame(index=mibel_data.index)
        target_df['month'] = target_df.index.month
        target_df['day'] = target_df.index.day
        target_df['hour'] = target_df.index.hour
        
        merged_pv = pd.merge(
            target_df.reset_index(),
            pv_df_reset[['month', 'day', 'hour', 'generation_kw']],
            on=['month', 'day', 'hour'],
            how='left'
        )
        datetime_col = merged_pv.columns[0]
        merged_pv = merged_pv.set_index(datetime_col)
        
        pv_df_aligned = merged_pv[['generation_kw']].fillna(0)
        
        # Interpolate linearly for sub-hourly intervals (e.g. 15-min) to smooth PV generation
        if (dt_hours < 1.0).any():
            pv_df_aligned = pv_df_aligned.interpolate(method='linear').fillna(0)
            
        # Combine price, generation kW, and interval duration dt_hours
        combined = pd.DataFrame({
            'price': mibel_data['price'],
            'generation_kw': pv_df_aligned['generation_kw'],
            'dt_hours': dt_hours
        }).dropna()
        
        if combined.empty:
            st.error("No overlapping timestamps between MIBEL price data and PVGIS simulation data for the selected date range.")
            return
            
        # Energy produced in each interval (kWh) = power (kW) * duration (hours)
        combined['energy_kwh'] = combined['generation_kw'] * combined['dt_hours']
        total_energy_kwh = combined['energy_kwh'].sum()
        total_duration_hours = combined['dt_hours'].sum()
        
        # Calculate captured price (volume-weighted average price during generation)
        if total_energy_kwh > 0:
            captured_price = (combined['price'] * combined['energy_kwh']).sum() / total_energy_kwh
        else:
            captured_price = 0
            
        # Time-weighted baseload price
        if total_duration_hours > 0:
            baseload_price = (combined['price'] * combined['dt_hours']).sum() / total_duration_hours
        else:
            baseload_price = combined['price'].mean()
            
        capture_rate = (captured_price / baseload_price * 100) if baseload_price != 0 else 0
            
        # Sun hours metrics (hours where generation power > 20.0 kW for 1 MWp plant)
        threshold = 20.0
        sun_mask = combined['generation_kw'] > threshold
        combined['sun_hours'] = combined['dt_hours'].where(sun_mask, 0.0)
        
        total_sun_hours = combined['sun_hours'].sum()
        
        # Daily sun hours max, min, avg
        daily_sun_hours = combined.resample('D')['sun_hours'].sum()
        max_daily_sun_hours = daily_sun_hours.max() if not daily_sun_hours.empty else 0
        min_daily_sun_hours = daily_sun_hours.min() if not daily_sun_hours.empty else 0
        avg_daily_sun_hours = daily_sun_hours.mean() if not daily_sun_hours.empty else 0
        
        # Display Metrics
        st.success(f"Simulation completed successfully for ({lat}, {lon})")
        
        if total_energy_kwh >= 10_000_000:  # >= 10,000 MWh -> GWh
            gen_str = f"{total_energy_kwh / 1_000_000:,.0f} GWh"
        elif total_energy_kwh >= 10_000:  # >= 10,000 kWh -> MWh
            gen_str = f"{total_energy_kwh / 1_000:,.0f} MWh"
        else:
            gen_str = f"{total_energy_kwh:,.0f} kWh"

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Captured Price", f"€{captured_price:.2f}/MWh", help="Volume-weighted average price received during solar generation hours (1 MWp plant)")
        with m2:
            st.metric("Baseload Price", f"€{baseload_price:.2f}/MWh", help="Simple arithmetic average market price over the period")
        with m3:
            st.metric("Capture Rate", f"{capture_rate:.1f}%", help="Captured Price / Baseload Price ratio")
        with m4:
            st.metric("Total Generation", gen_str, help="Total generated energy per 1 MWp installed capacity")
            
        st.markdown("---")
        
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Total Sun Hours", f"{total_sun_hours:,.0f} hrs", help="Total hours with active solar generation")
        with s2:
            st.metric("Avg Daily Sun Hours", f"{avg_daily_sun_hours:.0f} hrs/day")
        with s3:
            st.metric("Max Daily Sun Hours", f"{max_daily_sun_hours:.0f} hrs")
        with s4:
            st.metric("Min Daily Sun Hours", f"{min_daily_sun_hours:.0f} hrs")
            
        st.markdown("---")
        st.markdown("### 📊 Market Prices with Solar Generation Shading")
        st.markdown("The chart below shows market prices over the selected period. Hours with active sunlight/PV production are highlighted with transparent gold shading.")
        st.markdown(f"<div style='font-size:0.8rem; color:#666; font-style:italic; margin-top:-0.5rem; margin-bottom:1rem;'>Note: Sun hours and generation shading are determined based on an active generation threshold of >{threshold:.1f} kW for the 1 MWp plant.</div>", unsafe_allow_html=True)
        
        fig = go.Figure()
        
        # Add price line
        fig.add_trace(go.Scatter(
            x=combined.index,
            y=combined['price'],
            mode='lines',
            name='Market Price (€/MWh)',
            line=dict(color='#1f77b4', width=1.5)
        ))
        
        # Highlight sun hours using shapes
        shapes = []
        in_sun = False
        sun_start = None
        
        for idx, is_sun in sun_mask.items():
            if is_sun and not in_sun:
                in_sun = True
                sun_start = idx
            elif not is_sun and in_sun:
                in_sun = False
                shapes.append(dict(
                    type="rect",
                    xref="x",
                    yref="paper",
                    x0=sun_start,
                    x1=idx,
                    y0=0,
                    y1=1,
                    fillcolor="rgba(255, 215, 0, 0.2)",
                    layer="below",
                    line=dict(width=0),
                ))
        if in_sun:
            shapes.append(dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=sun_start,
                x1=combined.index[-1],
                y0=0,
                y1=1,
                fillcolor="rgba(255, 215, 0, 0.2)",
                layer="below",
                line=dict(width=0),
            ))
            
        if len(shapes) > 1500:
            shapes = shapes[:1500]
            
        fig.update_layout(
            title=f"MIBEL Market Prices & PV Production Shading ({country})",
            xaxis_title="Datetime",
            yaxis_title="Price (€/MWh)",
            shapes=shapes,
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='markers',
            marker=dict(size=15, color="rgba(255, 215, 0, 0.5)", symbol="square"),
            name="Solar Production Hours"
        ))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed preview table with generation_kw column
        with st.expander("🔍 View Simulation & Price Data Table"):
            display_df = combined.rename(columns={'generation_kw': 'generation (kW)'})
            display_df['sun_active'] = sun_mask
            st.dataframe(display_df.tail(100), use_container_width=True)
