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

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
streamlit run main.py
```
or
```bash
python run.py
```

## Project Structure

```
├── src/                    # Source code
│   ├── main.py            # Main application logic
│   ├── arbitrage_calculator.py  # Core arbitrage calculations
│   ├── data_loader.py     # OMIE data fetching
│   ├── ren_api.py         # REN API integration
│   ├── ui_components.py   # Streamlit UI components
│   └── plotting_utils.py  # Chart generation utilities
├── docs/                  # Documentation
├── main.py               # Entry point
├── run.py                # Alternative runner script
└── requirements.txt      # Python dependencies
