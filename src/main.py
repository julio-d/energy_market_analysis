import streamlit as st
from datetime import datetime, date, timedelta

# Import modules individually to catch any issues
try:
    from config import configure_page
    from ui_components import render_header, render_date_selection, render_country_selection, render_load_data_button
    from data_loader import load_omie_data
    from omie_tab import render_omie_tab
    from arbitrage_tab import render_arbitrage_tab
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please ensure all required modules are in the same directory")
    st.stop()

def main():
    # Configure page
    configure_page()
    
    # Render header
    render_header()
    
    # Initialize session state
    initialize_session_state()
    
    # Date range selection
    start_date, end_date = render_date_selection()
    
    # Country selection
    country = render_country_selection()
    
    # Load data button and status
    render_load_data_button(start_date, end_date, country)
    
    # Create tabs
    tab1, tab2 = st.tabs(["⚡ OMIE Market", "🔋 BESS Arbitrage"])
    
    # Render tabs
    with tab1:
        render_omie_tab()
    
    with tab2:
        render_arbitrage_tab()
    
    # Footer
    render_footer()

def initialize_session_state():
    """Initialize session state variables"""
    current_date = datetime.now().date()
    current_year = datetime.now().year
    
    if 'applied_start_date' not in st.session_state:
        st.session_state.applied_start_date = datetime(current_year, 1, 1).date()
    if 'applied_end_date' not in st.session_state:
        st.session_state.applied_end_date = current_date
    if 'data_submitted' not in st.session_state:
        st.session_state.data_submitted = False

def render_footer():
    """Render the footer"""
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;">
        ⚡ Energy Markets Analysis Dashboard v2.0<br>
        OMIE Market • Standalone BESS Arbitrage Analysis
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()