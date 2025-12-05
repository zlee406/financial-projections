import streamlit as st
from logic import persistence
from ui import builder, analysis, compare, tax

st.set_page_config(page_title="Family Finance Dashboard", layout="wide")
st.title("Family Financial Planning & Tax Tool")

# --- SESSION STATE INITIALIZATION ---
if "comparison_scenarios" not in st.session_state:
    st.session_state.comparison_scenarios = []

# Initialize strategies from disk if not already in session
if "spending_strategies" not in st.session_state or "portfolio_strategies" not in st.session_state:
    loaded_spend, loaded_port = persistence.load_scenarios_from_disk()
    st.session_state.spending_strategies = loaded_spend
    st.session_state.portfolio_strategies = loaded_port

# --- MAIN TABS ---
tab_builder, tab_fire, tab_compare, tab_tax = st.tabs(["Portfolio & Spending Builder", "Retirement Analysis", "Compare Strategies", "Income & Taxes"])

# --- TAB: BUILDER ---
with tab_builder:
    builder.render_builder()

# --- TAB: RETIREMENT ANALYSIS ---
with tab_fire:
    analysis.render_analysis()

# --- TAB: COMPARE STRATEGIES ---
with tab_compare:
    compare.render_comparison()

# --- TAB: INCOME & TAXES ---
with tab_tax:
    tax.render_tax()
