import pandas as pd
import plotly.express as px

def create_price_plot(data, title, aggregation="none", forecast_data=None):
    """Create interactive price plot with optional forecast overlay for future timestamps (hourly view only)"""
    if data is None or data.empty:
        return None
    
    df = data.copy()
    df['datetime'] = pd.to_datetime(df.index)
    
    if aggregation == "daily":
        df_agg = df.groupby(df['datetime'].dt.date)['price'].mean().reset_index()
        df_agg.columns = ['date', 'price']
        fig = px.line(df_agg, x='date', y='price', title=f"{title} - Daily Average")
    elif aggregation == "monthly":
        df_agg = df.groupby(df['datetime'].dt.to_period('M'))['price'].mean().reset_index()
        df_agg['date'] = df_agg['datetime'].astype(str)
        fig = px.line(df_agg, x='date', y='price', title=f"{title} - Monthly Average")
    elif aggregation == "yearly":
        df_agg = df.groupby(df['datetime'].dt.year)['price'].mean().reset_index()
        df_agg.columns = ['year', 'price']
        fig = px.line(df_agg, x='year', y='price', title=f"{title} - Yearly Average")
    else:
        fig = px.line(df, x=df.index, y='price', title=f"{title} - Price Evolution")
        fig.update_traces(name='Historical', showlegend=True,
                          hovertemplate='Historical: %{y:.2f} €/MWh<br>%{x}<extra></extra>')
        # Overlay forecast if provided and not empty
        if forecast_data is not None and not forecast_data.empty:
            fig.add_scatter(
                x=forecast_data.index,
                y=forecast_data['price'],
                mode='lines',
                name='Forecast',
                line=dict(dash='dash', color='orange', width=2),
                hovertemplate='Forecast: %{y:.2f} €/MWh<br>%{x}<extra></extra>'
            )
    
    # Update axis labels
    fig.update_layout(
        xaxis_title="Date/Time",
        yaxis_title="Price (€/MWh)",
        hovermode='closest' if (aggregation == "none" and forecast_data is not None and not forecast_data.empty) else 'x unified'
    )
    
    return fig

def create_average_day_plot(data, title):
    """Create average day profile plot"""
    if data is None or data.empty:
        return None
    
    df = data.copy()
    df['hour'] = pd.to_datetime(df.index).hour
    avg_day = df.groupby('hour')['price'].mean().reset_index()
    
    fig = px.line(avg_day, x='hour', y='price', title=f"{title} - Average Daily Pattern")
    
    fig.update_layout(
        xaxis_title="Hour of Day",
        yaxis_title="Average Price (€/MWh)",
        xaxis=dict(
            tickmode='linear', 
            tick0=0, 
            dtick=2
        ),
        hovermode='x unified'
    )
    
    return fig

def create_price_histogram_plot(bin_edges, hours, title, bin_width=5.0):
    """Create a bar chart of hours spent per price bin.

    ``bin_edges`` has length ``len(hours) + 1``. Bins are displayed as
    ``[low, high)`` intervals. Returns None for empty input.
    """
    if bin_edges is None or len(bin_edges) < 2 or hours is None or len(hours) == 0:
        return None

    lows = bin_edges[:-1]
    highs = bin_edges[1:]
    labels = [f"[{lo:g}, {hi:g})" for lo, hi in zip(lows, highs)]
    centers = [(lo + hi) / 2 for lo, hi in zip(lows, highs)]

    df_hist = pd.DataFrame({
        "bin": labels,
        "center": centers,
        "low": lows,
        "high": highs,
        "hours": hours,
    })

    fig = px.bar(
        df_hist,
        x="center",
        y="hours",
        title=title,
        custom_data=["low", "high"],
    )
    fig.update_traces(
        width=bin_width * 0.95,
        hovertemplate="Price: [%{customdata[0]:g}, %{customdata[1]:g}) €/MWh<br>Hours: %{y:.2f}<extra></extra>",
    )
    fig.update_layout(
        xaxis_title="Price Bin (€/MWh)",
        yaxis_title="Hours",
        bargap=0.05,
    )
    return fig


def create_arbitrage_plot(data, title):
    """Create daily arbitrage potential plot"""
    if data is None or data.empty:
        return None
    
    df = data.copy()
    df['date'] = pd.to_datetime(df.index).date
    daily_stats = df.groupby('date')['price'].agg(['min', 'max']).reset_index()
    daily_stats['arbitrage_potential'] = daily_stats['max'] - daily_stats['min']
    
    fig = px.line(daily_stats, x='date', y='arbitrage_potential', 
                  title=f"{title} - Daily Arbitrage Potential")
    
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Arbitrage Potential (€/MWh)",
        hovermode='x unified'
    )
    
    return fig

def create_daily_benefits_chart(daily_stats, analysis_type, battery_capacity_mwh):
    """Create a chart showing daily benefits with degradation"""
    hover_data_cols = ['remaining_capacity']
    
    if analysis_type == "2 Cycles":
        hover_data_cols.extend(['cycles_used', 'cumulative_cycles'])
        chart_title = f"Daily Arbitrage Benefits with Degradation ({analysis_type}) - {battery_capacity_mwh} MWh Battery"
    else:
        hover_data_cols.extend(['min', 'max', 'min_time', 'max_time'])
        chart_title = f"Daily Arbitrage Benefits with Degradation ({analysis_type}) - {battery_capacity_mwh} MWh Battery"
    
    fig_daily = px.bar(daily_stats, x='date', y='degraded_benefit', 
                     title=chart_title,
                     hover_data=hover_data_cols)
    fig_daily.update_layout(
        xaxis_title="Date",
        yaxis_title="Daily Benefit (€)",
        hovermode='x unified'
    )
    
    return fig_daily

def create_degradation_plot(daily_stats):
    """Create battery capacity degradation visualization"""
    fig_degradation = px.line(daily_stats, x='date', y='remaining_capacity', 
                            title=f"Battery Capacity Degradation Over Time")
    fig_degradation.update_layout(
        xaxis_title="Date",
        yaxis_title="Remaining Capacity (MWh)",
        hovermode='x unified'
    )
    
    return fig_degradation