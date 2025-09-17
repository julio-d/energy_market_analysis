import streamlit as st
from data_loader import load_omie_data
from ui_components import (render_battery_configuration, render_analysis_type_selection, 
                          render_summary_statistics_table, render_best_worst_days)
from arbitrage_calculator import calculate_arbitrage_benefits
from plotting_utils import create_daily_benefits_chart, create_degradation_plot, create_arbitrage_plot
from config import get_large_button_styles, get_arbitrage_results_html

def render_arbitrage_tab():
    """Render the Battery Arbitrage analysis tab"""
    st.subheader("🔋 Standalone BESS - OMIE Market Arbitrage Analysis", help="Analysis assumes a 1-hour batt ery system (1C)")
    
    if st.session_state.data_submitted:
        # Load OMIE data for arbitrage calculations with submitted parameters
        with st.spinner(f"Loading {st.session_state.submitted_country} market data for arbitrage analysis..."):
            omie_data = load_omie_data(
                st.session_state.submitted_start_date, 
                st.session_state.submitted_end_date, 
                st.session_state.submitted_country
            )
        
        if omie_data is not None:
            # Analysis type selection
            analysis_type = render_analysis_type_selection()
            
            # Battery configuration
            battery_capacity_mwh, efficiency, battery_cost_per_mwh, degradation_per_cycle = render_battery_configuration()
            
            # Apply custom CSS for larger button
            st.markdown(get_large_button_styles(), unsafe_allow_html=True)
            
            if st.button(f"Calculate Arbitrage Benefits", type="primary"):
                # Calculate arbitrage benefits
                daily_stats, roi_metrics, cycle_stats = calculate_arbitrage_benefits(
                    omie_data, analysis_type, battery_capacity_mwh, efficiency, 
                    battery_cost_per_mwh, degradation_per_cycle
                )
                
                # Display results
                display_arbitrage_results(
                    analysis_type, daily_stats, roi_metrics, cycle_stats,
                    battery_capacity_mwh, efficiency, degradation_per_cycle
                )
                
                # Show detailed daily breakdown
                display_daily_breakdown(daily_stats, analysis_type, battery_capacity_mwh, omie_data)
        
        else:
            st.error("⚠️ Unable to load OMIE data for arbitrage analysis. Please check the data source connection.")
    else:
        st.info("🔄 Please select your date range and country, then click 'Load Data' to perform BESS arbitrage analysis.")

def display_arbitrage_results(analysis_type, daily_stats, roi_metrics, cycle_stats, 
                             battery_capacity_mwh, efficiency, degradation_per_cycle):
    """Display arbitrage calculation results"""
    
    # Prepare parameters for HTML generation
    html_params = {
        'analysis_type': analysis_type,
        'total_benefit': roi_metrics['total_benefit'],
        'avg_daily_benefit': roi_metrics['avg_daily_benefit'],
        'total_days': roi_metrics['total_days'],
        'battery_capacity_mwh': battery_capacity_mwh,
        'efficiency': efficiency,
        'degradation_per_cycle': degradation_per_cycle,
        'total_investment': roi_metrics['total_investment'],
        'yearly_benefit': roi_metrics['yearly_benefit'],
        'payback_years': roi_metrics['payback_years']
    }
    
    # Add cycle-specific parameters
    if analysis_type == "2 Cycles":
        html_params.update({
            'days_with_2_cycles': cycle_stats['days_with_2_cycles'],
            'days_with_1_cycle': cycle_stats['days_with_1_cycle'],
            'days_with_no_cycles': cycle_stats['days_with_no_cycles'],
            'avg_cycles_per_day': cycle_stats['avg_cycles_per_day']
        })
    else:
        html_params.update({
            'days_with_1_cycle': cycle_stats['days_with_1_cycle'],
            'days_with_no_cycles': cycle_stats['days_with_no_cycles']
        })
    
    # Display results using HTML from config
    html = get_arbitrage_results_html(**html_params)
    st.markdown(html, unsafe_allow_html=True)
    
    # Add best/worst day statistics
    render_best_worst_days(daily_stats)

def display_daily_breakdown(daily_stats, analysis_type, battery_capacity_mwh, omie_data):
    """Display detailed daily breakdown charts and statistics"""
    st.subheader("📊 Daily Arbitrage Breakdown")
    
    # Create daily benefits chart
    fig_daily = create_daily_benefits_chart(daily_stats, analysis_type, battery_capacity_mwh)
    st.plotly_chart(fig_daily, use_container_width=True)
    
    # Add degradation visualization
    fig_degradation = create_degradation_plot(daily_stats)
    st.plotly_chart(fig_degradation, use_container_width=True)
    
    # Show summary statistics table
    render_summary_statistics_table(daily_stats)
    
    # Create arbitrage potential chart for the period
    fig_arbitrage = create_arbitrage_plot(omie_data, f"BESS Arbitrage Opportunities")
    if fig_arbitrage:
        st.plotly_chart(fig_arbitrage, use_container_width=True)