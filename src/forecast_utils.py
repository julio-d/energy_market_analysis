import pandas as pd
from datetime import timedelta

def generate_hourly_forecast(historical_data, forecast_hours=24):
    """
    Generate hourly forecast based on mean of past 7 days at homologue hour.
    Args:
        historical_data: DataFrame with datetime index and 'price' column
        forecast_hours: Number of hours to forecast
    Returns:
        DataFrame with forecasted prices (datetime index, 'price' column, 'is_forecast'=True)
    """
    if historical_data is None or historical_data.empty:
        return None

    df = historical_data.copy()
    df['hour'] = pd.to_datetime(df.index).hour
    last_timestamp = df.index.max()
    last_7_days = df[df.index > (last_timestamp - timedelta(days=7))]
    hourly_means = last_7_days.groupby('hour')['price'].mean()

    forecast_data = []
    for h in range(forecast_hours):
        forecast_time = last_timestamp + timedelta(hours=h+1)
        hour_of_day = forecast_time.hour
        forecast_price = hourly_means.get(hour_of_day, df['price'].mean())
        forecast_data.append({
            'datetime': forecast_time,
            'price': forecast_price,
            'is_forecast': True
        })
    forecast_df = pd.DataFrame(forecast_data)
    forecast_df.set_index('datetime', inplace=True)
    return forecast_df

def calculate_forecast_hours(start_date, end_date):
    """
    Determine forecast horizon based on selected window.
    - If window >= 1 day: forecast 24 hours
    - If window < 1 day: forecast X hours (same as window)
    """
    delta = end_date - start_date
    window_hours = delta.days * 24 + delta.seconds // 3600
    if window_hours >= 24:
        return 24
    else:
        return max(1, window_hours)
