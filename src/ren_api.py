import requests
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import Optional, Dict, Any
import logging
import numpy as np

class RENAPIClient:
    """
    Client for REN (Redes Energéticas Nacionais) API
    Handles aFRR (GetSecResPrice) and mFRR (GetmFRRPrices) data retrieval
    """
    
    def __init__(self, base_url: str = "https://www.mercado.ren.pt/api", use_mock_data: bool = False):
        """
        Initialize REN API client
        
        Args:
            base_url: Base URL for REN API endpoints
            use_mock_data: If True, use mock data for development (default: True)
        """
        self.base_url = base_url
        self.use_mock_data = use_mock_data
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Energy-Markets-Dashboard/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict]:
        """
        Make HTTP request to REN API
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            JSON response data or None if error
        """
        try:
            url = f"{self.base_url}/{endpoint}"
            self.logger.info(f"Making request to: {url}")
            self.logger.info(f"Parameters: {params}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode JSON response: {e}")
            return None
    
    def get_secondary_reserve_prices(self, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Get aFRR secondary reserve prices using GetSecResPrice endpoint
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            DataFrame with aFRR price data or None if error
        """
        try:
            # Format dates for API (assuming ISO format)
            params = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'format': 'json'
            }
            
            # Call GetSecResPrice endpoint
            data = self._make_request('GetSecResPrice', params)
            
            if not data:
                return None
            
            # Convert to DataFrame (structure will depend on actual API response)
            # This is a template that may need adjustment based on actual API response
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and 'data' in data:
                df = pd.DataFrame(data['data'])
            else:
                df = pd.DataFrame([data])
            
            # Process datetime column (adjust column names based on actual API)
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'])
            elif 'date' in df.columns and 'hour' in df.columns:
                df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta(df['hour'], unit='h')
            
            # Ensure we have a price column (adjust based on actual API response)
            price_columns = ['price', 'afrr_price', 'secondary_reserve_price', 'value']
            price_col = None
            for col in price_columns:
                if col in df.columns:
                    price_col = col
                    break
            
            if price_col:
                df = df.rename(columns={price_col: 'price'})
            
            # Set datetime as index if available
            if 'datetime' in df.columns:
                df.set_index('datetime', inplace=True)
                df.sort_index(inplace=True)
            
            self.logger.info(f"Retrieved {len(df)} aFRR price records")
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing aFRR data: {e}")
            return None
    
    def get_mfrr_prices(self, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Get mFRR prices using GetmFRRPrices endpoint
        
        Args:
            start_date: Start date for data retrieval
            end_date: End date for data retrieval
            
        Returns:
            DataFrame with mFRR price data or None if error
        """
        try:
            # Format dates for API
            params = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'format': 'json'
            }
            
            # Call GetmFRRPrices endpoint
            data = self._make_request('GetmFRRPrices', params)
            
            if not data:
                return None
            
            # Convert to DataFrame (similar processing as aFRR)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and 'data' in data:
                df = pd.DataFrame(data['data'])
            else:
                df = pd.DataFrame([data])
            
            # Process datetime column
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'])
            elif 'date' in df.columns and 'hour' in df.columns:
                df['datetime'] = pd.to_datetime(df['date']) + pd.to_timedelta(df['hour'], unit='h')
            
            # Ensure we have a price column
            price_columns = ['price', 'mfrr_price', 'manual_frr_price', 'value']
            price_col = None
            for col in price_columns:
                if col in df.columns:
                    price_col = col
                    break
            
            if price_col:
                df = df.rename(columns={price_col: 'price'})
            
            # Set datetime as index if available
            if 'datetime' in df.columns:
                df.set_index('datetime', inplace=True)
                df.sort_index(inplace=True)
            
            self.logger.info(f"Retrieved {len(df)} mFRR price records")
            return df
            
        except Exception as e:
            self.logger.error(f"Error processing mFRR data: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test connection to REN API
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a simple request to test connectivity
            test_date = datetime.now() - timedelta(days=1)
            params = {
                'startDate': test_date.strftime('%Y-%m-%d'),
                'endDate': test_date.strftime('%Y-%m-%d'),
                'format': 'json'
            }
            
            response = self._make_request('GetSecResPrice', params)
            return response is not None
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


# Example usage and testing functions
def test_ren_api():
    """Test function for REN API client"""
    client = RENAPIClient()
    
    # Test connection
    if client.test_connection():
        print("✅ REN API connection successful")
    else:
        print("❌ REN API connection failed")
        return
    
    # Test data retrieval
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)  # Last week
    
    print(f"Testing data retrieval from {start_date.date()} to {end_date.date()}")
    
    # Test aFRR data
    afrr_data = client.get_secondary_reserve_prices(start_date, end_date)
    if afrr_data is not None:
        print(f"✅ aFRR data retrieved: {len(afrr_data)} records")
        print(afrr_data.head())
    else:
        print("❌ aFRR data retrieval failed")
    
    # Test mFRR data
    mfrr_data = client.get_mfrr_prices(start_date, end_date)
    if mfrr_data is not None:
        print(f"✅ mFRR data retrieved: {len(mfrr_data)} records")
        print(mfrr_data.head())
    else:
        print("❌ mFRR data retrieval failed")


if __name__ == "__main__":
    test_ren_api()
