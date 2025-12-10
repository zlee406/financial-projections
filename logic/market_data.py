import os
import pandas as pd
import yfinance as yf
import streamlit as st

DATA_PATH = "data/sp500_history.csv"
CPI_DATA_PATH = "data/cpi_history.csv"
FRED_CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"


def get_market_data():
    """
    Fetches historical S&P 500 data from yfinance or loads from cache.
    Returns a DataFrame with 'Date' index and 'Close' column (and others).
    """
    if os.path.exists(DATA_PATH):
        # Load from cache
        df = pd.read_csv(DATA_PATH, index_col="Date", parse_dates=True)
        # Simple check to see if it's stale (optional, but for now just load it)
        return df
    else:
        # Fetch from yfinance
        # ^GSPC is the ticker for S&P 500
        ticker = "^GSPC"
        sp500 = yf.Ticker(ticker)
        # Max history
        df = sp500.history(period="max")
        
        # Save to cache
        # We only really need the Close/Adj Close, but saving all is fine
        df.to_csv(DATA_PATH)
        
        return df


def get_cpi_data() -> pd.DataFrame:
    """
    Fetches historical CPI (Consumer Price Index) data from FRED or loads from cache.
    Returns a DataFrame with 'Date' index and 'CPI' column.
    
    The CPI data is CPIAUCSL (Consumer Price Index for All Urban Consumers: All Items).
    """
    if os.path.exists(CPI_DATA_PATH):
        df = pd.read_csv(CPI_DATA_PATH, index_col="Date", parse_dates=True)
        return df
    else:
        # Fetch from FRED
        # FRED uses "observation_date" as the column name
        df = pd.read_csv(FRED_CPI_URL, index_col="observation_date", parse_dates=True)
        df.columns = ["CPI"]
        df.index.name = "Date"
        
        # Save to cache
        df.to_csv(CPI_DATA_PATH)
        
        return df


def get_monthly_inflation_rates() -> pd.Series:
    """
    Calculates monthly inflation rates from CPI data.
    Returns a Series with month-end dates as index and monthly inflation rate as values.
    """
    cpi_df = get_cpi_data()
    
    # Ensure we have a clean monthly series
    cpi_monthly = cpi_df['CPI'].resample('ME').last()
    
    # Calculate month-over-month inflation rate
    monthly_inflation = cpi_monthly.pct_change().dropna()
    
    return monthly_inflation


def get_annual_inflation_rates() -> pd.Series:
    """
    Calculates annual inflation rates from CPI data.
    Returns a Series with year-end dates as index and annual inflation rate as values.
    """
    cpi_df = get_cpi_data()
    
    # Get December CPI values for each year
    cpi_annual = cpi_df['CPI'].resample('YE').last()
    
    # Calculate year-over-year inflation rate
    annual_inflation = cpi_annual.pct_change().dropna()
    
    return annual_inflation


def get_annual_returns(df: pd.DataFrame):
    """
    Calculates annual returns from daily data.
    """
    # Resample to annual, take the last Close of the year
    annual_prices = df['Close'].resample('Y').last()
    annual_returns = annual_prices.pct_change().dropna()
    return annual_returns

