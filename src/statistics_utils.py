import streamlit as st
import pandas as pd
from config import get_summary_stats_html

def display_key_stats(data, show_arbitrage=True):
    """Display key statistics and return arbitrage value"""
    if data is None or data.empty:
        return None
    
    # Calculate statistics
    avg_price = data['price'].mean()
    max_price = data['price'].max()
    min_price = data['price'].min()
    
    # Calculate arbitrage value
    if show_arbitrage:
        df = data.copy()
        df['date'] = pd.to_datetime(df.index).date
        daily_stats = df.groupby('date')['price'].agg(['min', 'max'])
        daily_stats['arbitrage'] = daily_stats['max'] - daily_stats['min']
        arbitrage_value = daily_stats['arbitrage'].mean()
    else:
        arbitrage_value = data['price'].std()
    
    # Display using HTML from config
    html = get_summary_stats_html(avg_price, max_price, min_price, arbitrage_value, show_arbitrage)
    st.markdown(html, unsafe_allow_html=True)
    
    return arbitrage_value

def calculate_summary_statistics(daily_stats):
    """Calculate summary statistics for arbitrage analysis"""
    if daily_stats.empty:
        return None
    
    return {
        'median_benefit': daily_stats['daily_benefit'].median(),
        'std_benefit': daily_stats['daily_benefit'].std(),
        'mean_benefit': daily_stats['daily_benefit'].mean(),
        'max_benefit': daily_stats['daily_benefit'].max(),
        'min_benefit': daily_stats['daily_benefit'].min()
    }