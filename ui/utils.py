import streamlit as st
from logic import market_data

@st.cache_data
def load_market_data():
    return market_data.get_market_data()

