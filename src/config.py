import streamlit as st

def configure_page():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="Energy Markets Analysis",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Hide Streamlit branding only
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

def get_button_styles():
    """Return CSS styles for buttons"""
    return """
    <style>
    .stButton > button {
        height: 24px !important;
        min-height: 24px !important;
        font-size: 0.4rem !important;
        padding: 0.1rem 0.2rem !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        width: 100% !important;
        line-height: 1 !important;
    }
    </style>
    """

def get_large_button_styles():
    """Return CSS styles for larger buttons"""
    return """
    <style>
    .stButton > button {
        padding: 0.5rem 1rem !important;
        font-size: 1.1rem !important;
        font-weight: 500 !important;
        height: auto !important;
        min-height: 2rem !important;
    }
    </style>
    """

def get_stats_card_html(title, value, subtitle="", color="#ccc"):
    """Generate HTML for statistics cards"""
    return f"""
    <div style="background-color: #2a2a2a; padding: 0.7rem; border-radius: 0.3rem; margin: 0.3rem 0;">
        <h6 style="color: #ccc; margin-bottom: 0.3rem; font-size: 0.9rem;">{title}</h6>
        <div style="color: #ccc; font-size: 1rem; font-weight: bold;">{value}</div>
        <div style="color: {color}; font-size: 0.8rem;">{subtitle}</div>
    </div>
    """

def get_summary_stats_html(avg_price, max_price, min_price, arbitrage_value, show_arbitrage=True):
    """Generate HTML for summary statistics"""
    arbitrage_label = "Avg Daily Arbitrage" if show_arbitrage else "Price Volatility"
    
    return f"""
    <div style="background-color: #1e1e1e; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <h4 style="color: white; margin-bottom: 1rem;">Summary Statistics</h4>
        <div style="display: flex; justify-content: space-between; color: #ccc;">
            <div>
                <div style="font-size: 0.9rem; color: #888;">Average Price</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: white;">{avg_price:.2f} €/MWh</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; color: #888;">Maximum Price</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: white;">{max_price:.2f} €/MWh</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; color: #888;">Minimum Price</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: white;">{min_price:.2f} €/MWh</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; color: #888;">{arbitrage_label}</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: white;">{arbitrage_value:.2f} €/MWh</div>
            </div>
        </div>
    </div>
    """

def get_arbitrage_results_html(analysis_type, total_benefit, avg_daily_benefit, total_days, 
                               battery_capacity_mwh, efficiency, degradation_per_cycle,
                               total_investment, yearly_benefit, payback_years,
                               days_with_2_cycles=0, days_with_1_cycle=0, days_with_no_cycles=0,
                               avg_cycles_per_day=0):
    """Generate HTML for arbitrage results"""
    
    if analysis_type == "2 Cycles":
        return f"""
        <div style="background-color: #1e1e1e; padding: 1.5rem; border-radius: 0.5rem; margin: 1rem 0;">
            <h4 style="color: white; margin-bottom: 1rem;">2 Cycles BESS Arbitrage Results</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; color: #ccc;">
                <div>
                    <h5 style="color: #ccc; margin-bottom: 0.5rem;">Period Analysis ({total_days} days)</h5>
                    <div style="margin-bottom: 0.5rem;">Total Period Benefit: <strong>{total_benefit:,.2f} €</strong></div>
                    <div style="margin-bottom: 0.5rem;">Average Daily Benefit: <strong>{avg_daily_benefit:.2f} €/day</strong></div>
                    <div style="margin-bottom: 0.5rem;">Battery Capacity: <strong>{battery_capacity_mwh:.1f} MWh</strong></div>
                    <div style="margin-bottom: 0.5rem;">Round-trip Efficiency: <strong>{efficiency*100:.1f}%</strong></div>
                    <div style="margin-bottom: 0.5rem;">Degradation per Cycle: <strong>{degradation_per_cycle*100:.3f}%</strong></div>
                    <div>Avg Cycles/Day: <strong>{avg_cycles_per_day:.2f}</strong></div>
                </div>
                <div>
                    <h5 style="color: #ccc; margin-bottom: 0.5rem;">ROI & Investment Analysis</h5>
                    <div style="margin-bottom: 0.5rem;">Total Investment: <strong>{total_investment:,.0f} €</strong></div>
                    <div style="margin-bottom: 0.5rem;">Yearly Benefit: <strong>{yearly_benefit:,.2f} €/year</strong></div>
                    <div style="margin-bottom: 0.5rem;">Payback Period: <strong>{payback_years:.1f} years</strong></div>
                    <div style="margin-bottom: 0.5rem;">2-Cycle Days: <strong>{days_with_2_cycles}</strong></div>
                    <div style="margin-bottom: 0.5rem;">1-Cycle Days: <strong>{days_with_1_cycle}</strong></div>
                    <div>No-Cycle Days: <strong>{days_with_no_cycles}</strong></div>
                </div>
            </div>
        </div>
        """
    else:
        return f"""
        <div style="background-color: #1e1e1e; padding: 1.5rem; border-radius: 0.5rem; margin: 1rem 0;">
            <h4 style="color: white; margin-bottom: 1rem;">1 Cycle BESS Arbitrage Results</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; color: #ccc;">
                <div>
                    <h5 style="color: #ccc; margin-bottom: 0.5rem;">Period Analysis ({total_days} days)</h5>
                    <div style="margin-bottom: 0.5rem;">Total Period Benefit: <strong>{total_benefit:,.2f} €</strong></div>
                    <div style="margin-bottom: 0.5rem;">Average Daily Benefit: <strong>{avg_daily_benefit:.2f} €/day</strong></div>
                    <div style="margin-bottom: 0.5rem;">Battery Capacity: <strong>{battery_capacity_mwh:.1f} MWh</strong></div>
                    <div style="margin-bottom: 0.5rem;">Round-trip Efficiency: <strong>{efficiency*100:.1f}%</strong></div>
                    <div>Degradation per Cycle: <strong>{degradation_per_cycle*100:.3f}%</strong></div>
                </div>
                <div>
                    <h5 style="color: #ccc; margin-bottom: 0.5rem;">ROI & Investment Analysis</h5>
                    <div style="margin-bottom: 0.5rem;">Total Investment: <strong>{total_investment:,.0f} €</strong></div>
                    <div style="margin-bottom: 0.5rem;">Yearly Benefit: <strong>{yearly_benefit:,.2f} €/year</strong></div>
                    <div style="margin-bottom: 0.5rem;">Payback Period: <strong>{payback_years:.1f} years</strong></div>
                    <div style="margin-bottom: 0.5rem;">Successful Days: <strong>{days_with_1_cycle}</strong></div>
                    <div>Failed Days: <strong>{days_with_no_cycles}</strong></div>
                </div>
            </div>
        </div>
        """