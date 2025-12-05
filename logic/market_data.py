import os
import pandas as pd
import yfinance as yf
import streamlit as st

DATA_PATH = "data/sp500_history.csv"

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

def get_annual_returns(df: pd.DataFrame):
    """
    Calculates annual returns from daily data.
    """
    # Resample to annual, take the last Close of the year
    annual_prices = df['Close'].resample('Y').last()
    annual_returns = annual_prices.pct_change().dropna()
    return annual_returns

