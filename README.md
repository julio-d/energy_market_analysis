# Energy Market Analysis Dashboard

A Streamlit web application for analyzing energy markets and battery storage arbitrage opportunities.

## What it does

- **OMIE Market Analysis**: Visualizes Spanish/Portuguese electricity market data
- **BESS Arbitrage Calculator**: Calculates potential profits from battery energy storage arbitrage


## Key Features

- Load OMIE market data for custom date ranges
- Calculate 1-cycle and 2-cycle arbitrage strategies
- Battery degradation modeling
- Financial analysis with ROI calculations
- Interactive charts and statistics

## How to run

```bash
streamlit run main.py
```

## Main Components

- `main.py` - Entry point and UI orchestration
- `arbitrage_calculator.py` - Core arbitrage calculation logic
- `data_loader.py` - OMIE data fetching
- `ren_api.py` - REN API integration
- `ui_components.py` - Streamlit UI components
- `plotting_utils.py` - Chart generation utilities

## Dependencies

Requires Python with Streamlit, pandas, and other data analysis libraries (see venv for full list).
