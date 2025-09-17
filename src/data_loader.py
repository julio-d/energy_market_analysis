import streamlit as st
import pandas as pd
from datetime import datetime
from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter
from OMIEData.Enums.all_enums import DataTypeInMarginalPriceFile

@st.cache_data
def load_omie_data(start_date, end_date, country="Spain"):
    """Load OMIE data for the specified date range and country"""
    try:
        # Convert dates to datetime objects if they aren't already
        if not isinstance(start_date, datetime):
            start_date = datetime.combine(start_date, datetime.min.time())
        if not isinstance(end_date, datetime):
            end_date = datetime.combine(end_date, datetime.min.time())
        
        # Load OMIE marginal price data
        df = OMIEMarginalPriceFileImporter(
            date_ini=start_date, 
            date_end=end_date
        ).read_to_dataframe(verbose=False)
        
        if df.empty:
            return None
            
        # Filter for selected country prices
        if country == "Portugal":
            str_price = str(DataTypeInMarginalPriceFile.PRICE_PORTUGAL)
        else:  # Default to Spain
            str_price = str(DataTypeInMarginalPriceFile.PRICE_SPAIN)
        
        df_prices = df[df.CONCEPT == str_price].copy()
        
        if df_prices.empty:
            return None
        
        # Reshape data from wide to long format
        price_data = []
        for _, row in df_prices.iterrows():
            date = row['DATE']
            for hour in range(1, 25):  # H1 to H24
                hour_col = f'H{hour}'
                if hour_col in row:
                    timestamp = pd.Timestamp(date) + pd.Timedelta(hours=hour-1)
                    price_data.append({
                        'datetime': timestamp,
                        'price': row[hour_col]
                    })
        
        # Create DataFrame with datetime index
        result_df = pd.DataFrame(price_data)
        result_df.set_index('datetime', inplace=True)
        result_df.sort_index(inplace=True)
        
        return result_df
        
    except Exception as e:
        st.error(f"Error loading OMIE data: {str(e)}")
        return None