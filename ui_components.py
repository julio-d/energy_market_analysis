import streamlit as st
from datetime import datetime, timedelta
from config import get_button_styles

def render_header():
    """Render the main header"""
    st.title("⚡ Energy Markets Analysis")
    st.markdown("**OMIE Market • Standalone BESS Arbitrage Analysis**")

def render_date_selection():
    """Render date selection UI and return selected dates"""
    st.subheader("📅 Date Range Selection")
    
    # Apply button styles
    st.markdown(get_button_styles(), unsafe_allow_html=True)
    
    # Quick preset buttons
    render_quick_presets()
    
    # Custom date range selection
    render_custom_date_range()
    
    return st.session_state.applied_start_date, st.session_state.applied_end_date

def render_quick_presets():
    """Render quick preset buttons"""
    current_year = datetime.now().year
    current_date = datetime.now().date()
    
    st.write("**Quick Select:**")
    
    # Use proportional column widths based on text length, aligned left
    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10, spacer = st.columns([1.4, 1.4, 1.2, 1.2, 1.6, 1.6, 1, 0.8, 1.2, 1.6, 1])

    with col1:
        if st.button("This Year", key="this_year", help="Jan 1st to today"):
            st.session_state.applied_start_date = datetime(current_year, 1, 1).date()
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col2:
        if st.button("Last Year", key="last_year", help="Complete previous year"):
            st.session_state.applied_start_date = datetime(current_year - 1, 1, 1).date()
            st.session_state.applied_end_date = datetime(current_year - 1, 12, 31).date()
            st.rerun()
    with col3:
        if st.button("365d", key="last_365_days", help="Rolling 365 days"):
            st.session_state.applied_start_date = current_date - timedelta(days=365)
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col4:
        if st.button("90d", key="last_90_days", help="Rolling 90 days"):
            st.session_state.applied_start_date = current_date - timedelta(days=90)
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col5:
        if st.button("This Month", key="this_month", help="Month start to today"):
            st.session_state.applied_start_date = datetime(current_date.year, current_date.month, 1).date()
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col6:
        if st.button("Last Month", key="last_month", help="Complete previous month"):
            # Calculate last month
            if current_date.month == 1:
                last_month_start = datetime(current_date.year - 1, 12, 1).date()
                last_month_end = datetime(current_date.year, 1, 1).date() - timedelta(days=1)
            else:
                last_month_start = datetime(current_date.year, current_date.month - 1, 1).date()
                # Last day of last month
                last_month_end = datetime(current_date.year, current_date.month, 1).date() - timedelta(days=1)
            
            st.session_state.applied_start_date = last_month_start
            st.session_state.applied_end_date = last_month_end
            st.rerun()
    with col7:
        if st.button("30d", key="last_30_days", help="Rolling 30 days"):
            st.session_state.applied_start_date = current_date - timedelta(days=30)
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col8:
        if st.button("7d", key="last_7_days", help="Rolling 7 days"):
            st.session_state.applied_start_date = current_date - timedelta(days=7)
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col9:
        if st.button("Today", key="today", help="Today only"):
            st.session_state.applied_start_date = current_date
            st.session_state.applied_end_date = current_date
            st.rerun()
    with col10:
        if st.button("Yesterday", key="yesterday", help="Yesterday only"):
            yesterday = current_date - timedelta(days=1)
            st.session_state.applied_start_date = yesterday
            st.session_state.applied_end_date = yesterday
            st.rerun()

def render_custom_date_range():
    """Render custom date range selection"""
    with st.expander("🔧 Custom Date Range", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            start_date_input = st.date_input(
                "Start Date",
                value=st.session_state.applied_start_date,
                min_value=datetime(2022, 1, 1),
                max_value=datetime.now()
            )
        
        with col2:
            end_date_input = st.date_input(
                "End Date",
                value=st.session_state.applied_end_date,
                min_value=datetime(2022, 1, 1),
                max_value=datetime.now()
            )
        
        # Update session state when custom dates are changed
        if start_date_input != st.session_state.applied_start_date:
            st.session_state.applied_start_date = start_date_input
        if end_date_input != st.session_state.applied_end_date:
            st.session_state.applied_end_date = end_date_input

def render_country_selection():
    """Render country selection"""
    return st.selectbox(
        "Select Country",
        ["Spain", "Portugal"],
        key="global_country_selection",
        help="Choose which country's electricity prices to analyze in both tabs"
    )

def render_load_data_button(start_date, end_date, country):
    """Render load data button and status"""
    # Submit button for data loading
    if st.button("Load Data", type="primary", help="Click to load data for the selected date range and country"):
        st.session_state.data_submitted = True
        st.session_state.submitted_start_date = start_date
        st.session_state.submitted_end_date = end_date
        st.session_state.submitted_country = country
        st.rerun()

    # Show current selection
    if st.session_state.data_submitted:
        st.success(f"📊 **Loaded Data:** {st.session_state.submitted_start_date} → {st.session_state.submitted_end_date} | {st.session_state.submitted_country}")
    else:
        st.info(f"📊 **Current Selection:** {start_date} → {end_date} | {country} (Click 'Load Data' to analyze)")

def render_battery_configuration():
    """Render battery configuration inputs"""
    col1, col2 = st.columns(2)
    
    with col1:
        battery_capacity_mwh = st.number_input(
            "Battery Capacity (MWh)",
            min_value=0.1,
            value=1.0,
            step=0.1,
            help="Energy storage capacity of the battery in MWh"
        )
        
        efficiency = st.number_input(
            "Round-trip Efficiency (%)",
            min_value=50.0,
            max_value=100.0,
            value=85.0,
            step=1.0,
            help="Battery round-trip efficiency (charge + discharge losses)"
        ) / 100
    
    with col2:
        battery_cost_per_mwh = st.number_input(
            "Battery Cost (€/MWh)",
            min_value=0.0,
            value=300000.0,
            step=10000.0,
            help="Total cost of battery system per MWh of capacity"
        )
        
        degradation_per_cycle = st.number_input(
            "Degradation per Cycle (%)",
            min_value=0.0,
            max_value=1.0,
            value=0.02,
            step=0.001,
            format="%.3f",
            help="Capacity loss per charge-discharge cycle (typical: 0.02%)"
        ) / 100
    
    return battery_capacity_mwh, efficiency, battery_cost_per_mwh, degradation_per_cycle

def render_analysis_type_selection():
    """Render analysis type selection"""
    return st.radio(
        "Select Analysis Type:",
        ["1 Cycle", "2 Cycles"],
        horizontal=True,
        help="1 Cycle: Single charge-discharge per day. 2 Cycles: Two charge-discharge cycles per day with time constraints."
    )

def render_summary_statistics_table(daily_stats):
    """Render summary statistics table"""
    st.subheader("📈 Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    # Find best and worst day dates (only from days with arbitrage opportunities)
    arbitrage_days = daily_stats[daily_stats['arbitrage_possible']]
    if len(arbitrage_days) > 0:
        best_day_idx = arbitrage_days['daily_benefit'].idxmax()
        worst_day_idx = arbitrage_days['daily_benefit'].idxmin()
        best_day_date = daily_stats.loc[best_day_idx, 'date']
        worst_day_date = daily_stats.loc[worst_day_idx, 'date']
        best_day_value = daily_stats.loc[best_day_idx, 'daily_benefit']
        worst_day_value = daily_stats.loc[worst_day_idx, 'daily_benefit']
    else:
        best_day_date = worst_day_date = "N/A"
        best_day_value = worst_day_value = 0
    
    with col1:
        st.markdown(f"""
        <div style="background-color: #2a2a2a; padding: 0.5rem; border-radius: 0.3rem;">
            <div style="color: #666; font-size: 0.8rem; margin-bottom: 0.2rem;">Best Day</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #ccc; margin-bottom: 0.1rem;">{best_day_value:.2f} €/MWh</div>
            <div style="color: #81C784; font-size: 0.7rem;">{best_day_date}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background-color: #2a2a2a; padding: 0.5rem; border-radius: 0.3rem;">
            <div style="color: #666; font-size: 0.8rem; margin-bottom: 0.2rem;">Worst Day</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #ccc; margin-bottom: 0.1rem;">{worst_day_value:.2f} €/MWh</div>
            <div style="color: #EF9A9A; font-size: 0.7rem;">{worst_day_date}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background-color: #2a2a2a; padding: 0.5rem; border-radius: 0.3rem;">
            <div style="color: #666; font-size: 0.8rem; margin-bottom: 0.2rem;">Median Benefit</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #ccc; margin-bottom: 0.1rem;">{daily_stats['daily_benefit'].median():.2f} €/MWh</div>
            <div style="height: 0.7rem;"></div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div style="background-color: #2a2a2a; padding: 0.5rem; border-radius: 0.3rem;">
            <div style="color: #666; font-size: 0.8rem; margin-bottom: 0.2rem;">Std Deviation</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #ccc; margin-bottom: 0.1rem;">{daily_stats['daily_benefit'].std():.2f} €/MWh</div>
            <div style="height: 0.7rem;"></div>
        </div>
        """, unsafe_allow_html=True)

def render_best_worst_days(daily_stats):
    """Render best and worst day statistics"""
    if len(daily_stats) > 0:
        best_day_idx = daily_stats['degraded_benefit'].idxmax()
        worst_day_idx = daily_stats['degraded_benefit'].idxmin()
        best_day_benefit = daily_stats.loc[best_day_idx, 'degraded_benefit']
        worst_day_benefit = daily_stats.loc[worst_day_idx, 'degraded_benefit']
        best_day_date = daily_stats.loc[best_day_idx, 'date']
        worst_day_date = daily_stats.loc[worst_day_idx, 'date']
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div style="background-color: #2a2a2a; padding: 0.7rem; border-radius: 0.3rem; margin: 0.3rem 0;">
                <h6 style="color: #ccc; margin-bottom: 0.3rem; font-size: 0.9rem;">🏆 Best Day</h6>
                <div style="color: #ccc; font-size: 1rem; font-weight: bold;">{best_day_benefit:.2f} €</div>
                <div style="color: #81C784; font-size: 0.8rem;">{best_day_date}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background-color: #2a2a2a; padding: 0.7rem; border-radius: 0.3rem; margin: 0.3rem 0;">
                <h6 style="color: #ccc; margin-bottom: 0.3rem; font-size: 0.9rem;">📉 Worst Day</h6>
                <div style="color: #ccc; font-size: 1rem; font-weight: bold;">{worst_day_benefit:.2f} €</div>
                <div style="color: #EF9A9A; font-size: 0.8rem;">{worst_day_date}</div>
            </div>
            """, unsafe_allow_html=True)