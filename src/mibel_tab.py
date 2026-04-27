import streamlit as st
from data_loader import load_mibel_data
from plotting_utils import (
    create_price_plot,
    create_average_day_plot,
    create_arbitrage_plot,
    create_price_histogram_plot,
)
from statistics_utils import display_key_stats
from forecast_utils import generate_hourly_forecast, calculate_forecast_hours
from tariff_utils import get_tipo_ciclo_options, compute_band_averages
from price_distribution import (
    compute_price_histogram,
    count_hours_matching_conditions,
    infer_step_hours,
)
from llm_chat import render_chat_tab

def render_mibel_tab():
    """Render the MIBEL Market analysis tab"""
    st.subheader("⚡ MIBEL Spot Market Analysis")
    
    if st.session_state.data_submitted:
        # Load MIBEL data with submitted parameters
        with st.spinner(f"Loading {st.session_state.submitted_country} market data..."):
            mibel_data = load_mibel_data(
                st.session_state.submitted_start_date, 
                st.session_state.submitted_end_date, 
                st.session_state.submitted_country
            )
        
        if mibel_data is not None:
            # Display key stats and store arbitrage value
            mibel_arbitrage = display_key_stats(mibel_data, show_arbitrage=True)
            
            # Aggregation selector ("none" keeps native resolution, which may
            # be 15-min when ENTSO-E provides PT15 granularity).
            aggregation = st.selectbox(
                "Data Aggregation Level",
                ["none", "hourly", "daily", "monthly", "yearly"],
                key="mibel_agg"
            )

            # Build the plotting dataframe according to aggregation.
            # For "hourly" we resample to 1H mean and pass "none" downstream
            # so the plotting utilities render the time series as-is.
            if aggregation == "hourly":
                plot_data = mibel_data.resample("1h").mean().dropna()
                plot_data.attrs["source"] = mibel_data.attrs.get("source", "n/a")
                downstream_agg = "none"
            else:
                plot_data = mibel_data
                downstream_agg = aggregation

            # CSV Export Button (native or hourly)
            if aggregation in ("none", "hourly"):
                csv_data = plot_data.to_csv()
                csv_filename = f"{st.session_state.submitted_country}_prices_{st.session_state.submitted_start_date}_{st.session_state.submitted_end_date}.csv"
                st.download_button(
                    label="📥 Export Prices to CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    key="export_mibel_csv"
                )

            # Forecast overlay (only for time-series views). Forecast logic
            # assumes hourly input, so feed it an hourly-resampled copy.
            forecast_data = None
            if aggregation in ("none", "hourly"):
                forecast_hours = calculate_forecast_hours(
                    st.session_state.submitted_start_date, st.session_state.submitted_end_date)
                hourly_for_forecast = mibel_data.resample("1h").mean().dropna()
                forecast_data = generate_hourly_forecast(hourly_for_forecast, forecast_hours=forecast_hours)

            # Price plot (with forecast overlay if time-series)
            price_fig = create_price_plot(
                plot_data,
                f"MIBEL {st.session_state.submitted_country} Market Prices",
                downstream_agg,
                forecast_data=forecast_data
            )
            if price_fig:
                st.plotly_chart(price_fig, use_container_width=True)
                _render_source_caption(mibel_data)

            col1, col2 = st.columns(2)
            
            with col1:
                # Average day plot
                avg_day_fig = create_average_day_plot(mibel_data, f"MIBEL {st.session_state.submitted_country}")
                if avg_day_fig:
                    st.plotly_chart(avg_day_fig, use_container_width=True)
                    _render_source_caption(mibel_data)
            
            with col2:
                # Arbitrage potential plot
                arbitrage_fig = create_arbitrage_plot(mibel_data, f"MIBEL {st.session_state.submitted_country}")
                if arbitrage_fig:
                    st.plotly_chart(arbitrage_fig, use_container_width=True)
                    _render_source_caption(mibel_data)

            # Price distribution & query (computed on native-resolution data)
            st.divider()
            st.markdown("### 📊 Price Distribution & Query")

            step_hours = infer_step_hours(mibel_data)
            granularity_min = int(round(step_hours * 60))
            st.caption(
                f"Granularity: {granularity_min}-min → {step_hours:g} h per sample"
            )

            bin_edges, hours_per_bin, _ = compute_price_histogram(mibel_data, bin_width=5.0)
            hist_fig = create_price_histogram_plot(
                bin_edges,
                hours_per_bin,
                f"MIBEL {st.session_state.submitted_country} - Hours per Price Bin",
                bin_width=5.0,
            )
            if hist_fig:
                st.plotly_chart(hist_fig, use_container_width=True)
                _render_source_caption(mibel_data)
            else:
                st.info("Not enough data to build price histogram.")

            st.markdown("#### 🔎 Hours matching a price condition")
            operators = [">", "<", ">=", "<=", "="]

            q_col1, q_col2 = st.columns(2)
            with q_col1:
                operator1 = st.selectbox(
                    "Operator",
                    operators,
                    key="mibel_price_query_op",
                )
            with q_col2:
                threshold1 = st.number_input(
                    "Price (€/MWh)",
                    value=0.0,
                    step=1.0,
                    format="%.2f",
                    key="mibel_price_query_val",
                )

            use_second = st.checkbox(
                "Add second condition (AND)",
                key="mibel_price_query_use2",
            )
            operator2 = None
            threshold2 = None
            if use_second:
                q2_col1, q2_col2 = st.columns(2)
                with q2_col1:
                    operator2 = st.selectbox(
                        "Operator (2nd)",
                        operators,
                        index=1,
                        key="mibel_price_query_op2",
                    )
                with q2_col2:
                    threshold2 = st.number_input(
                        "Price (€/MWh) (2nd)",
                        value=0.0,
                        step=1.0,
                        format="%.2f",
                        key="mibel_price_query_val2",
                    )

            run_query = st.button("Run", key="mibel_price_query_run")

            if run_query:
                conditions = [(operator1, float(threshold1))]
                if use_second:
                    conditions.append((operator2, float(threshold2)))
                matching_hours, total_hours = count_hours_matching_conditions(
                    mibel_data, conditions
                )
                pct = (matching_hours / total_hours * 100.0) if total_hours > 0 else 0.0
                condition_label = " AND ".join(
                    f"price {op} {val:g} €/MWh" for op, val in conditions
                )
                m1, m2 = st.columns(2)
                m1.metric(
                    f"Hours where {condition_label}",
                    f"{matching_hours:.2f} h",
                )
                m2.metric("Share of period", f"{pct:.2f} %")
                if any(op == "=" for op, _ in conditions):
                    st.caption(
                        "Note: '=' uses exact equality; raw floating-point prices rarely match exactly."
                    )

            # Tariff bands (Portuguese consumption periods)
            st.divider()
            st.markdown("### 📑 Average Price by Tariff Band")
            ciclo_options = get_tipo_ciclo_options()
            default_idx = ciclo_options.index("Tetra-Horário Ciclo Semanal") if "Tetra-Horário Ciclo Semanal" in ciclo_options else 0
            tipo_ciclo = st.selectbox(
                "Tipo de Ciclo",
                ciclo_options,
                index=default_idx,
                key="mibel_tipo_ciclo"
            )
            band_table = compute_band_averages(mibel_data, tipo_ciclo)
            if band_table is not None and not band_table.empty:
                st.dataframe(band_table, hide_index=True, use_container_width=True)
            else:
                st.info("No tariff band data available for the selected cycle.")
            st.divider()
            render_chat_tab(mibel_data, st.session_state.submitted_country)

            # (smoke-test expander removed)

        else:
            st.error("⚠️ Unable to load MIBEL data. Please check the data source connection.")
    else:
        st.info("🔄 Please select your date range and country, then click 'Load Data' to view market analysis.")
def _render_source_caption(df):
    """Render a very small caption under a plot indicating the data provider."""
    source = df.attrs.get("source", "n/a") if df is not None else "n/a"
    st.markdown(
        f"<div style='font-size:0.65rem;color:#888;margin-top:-0.5rem;margin-bottom:0.5rem;'>Source: {source}</div>",
        unsafe_allow_html=True,
    )