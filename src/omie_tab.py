import streamlit as st
from data_loader import load_omie_data
from plotting_utils import create_price_plot, create_average_day_plot, create_arbitrage_plot
from statistics_utils import display_key_stats

def render_omie_tab():
    """Render the OMIE Market analysis tab"""
    st.subheader("⚡ OMIE Market Analysis")
    
    if st.session_state.data_submitted:
        # Load OMIE data with submitted parameters
        with st.spinner(f"Loading {st.session_state.submitted_country} market data..."):
            omie_data = load_omie_data(
                st.session_state.submitted_start_date, 
                st.session_state.submitted_end_date, 
                st.session_state.submitted_country
            )
        
        if omie_data is not None:
            # Display key stats and store arbitrage value
            omie_arbitrage = display_key_stats(omie_data, show_arbitrage=True)
            
            # Aggregation selector
            aggregation = st.selectbox(
                "Data Aggregation Level",
                ["none", "daily", "monthly", "yearly"],
                key="omie_agg"
            )
            
            # Price plot
            price_fig = create_price_plot(omie_data, f"OMIE {st.session_state.submitted_country} Market Prices", aggregation)
            if price_fig:
                st.plotly_chart(price_fig, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Average day plot
                avg_day_fig = create_average_day_plot(omie_data, f"OMIE {st.session_state.submitted_country}")
                if avg_day_fig:
                    st.plotly_chart(avg_day_fig, use_container_width=True)
            
            with col2:
                # Arbitrage potential plot
                arbitrage_fig = create_arbitrage_plot(omie_data, f"OMIE {st.session_state.submitted_country}")
                if arbitrage_fig:
                    st.plotly_chart(arbitrage_fig, use_container_width=True)
        
        else:
            st.error("⚠️ Unable to load OMIE data. Please check the data source connection.")
    else:
        st.info("🔄 Please select your date range and country, then click 'Load Data' to view market analysis.")