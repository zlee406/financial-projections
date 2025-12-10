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

# Initialize retirement analysis inputs from disk if not already in session
retirement_keys = [
    "current_age", "death_age", "selected_portfolio_strategy", "selected_spending_strategy", 
    "strategy_type", "min_spend", "max_spend", "strategy_pct", "gk_init_rate",
    "flexible_spending", "flexible_floor_pct_slider", "allow_early_retirement_access",
    "early_withdrawal_penalty_pct", "retirement_access_age"
]
if not all(key in st.session_state for key in retirement_keys):
    loaded_retirement = persistence.load_retirement_analysis_inputs()
    for key, value in loaded_retirement.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Track previous retirement values for change detection
if "_prev_retirement_values" not in st.session_state:
    st.session_state._prev_retirement_values = {key: st.session_state.get(key) for key in retirement_keys}

# --- MAIN TABS ---
tab_builder, tab_fire, tab_compare, tab_tax = st.tabs(["Portfolio & Spending Builder", "Retirement Analysis", "Compare Strategies", "Income & Taxes"])

# --- TAB: BUILDER ---
with tab_builder:
    builder.render_builder()

# --- TAB: RETIREMENT ANALYSIS (now includes Year Analysis as sub-tabs) ---
with tab_fire:
    analysis.render_analysis()

# --- TAB: COMPARE STRATEGIES ---
with tab_compare:
    compare.render_comparison()

# --- TAB: INCOME & TAXES ---
with tab_tax:
    tax.render_tax()

# --- SAVE RETIREMENT ANALYSIS INPUTS ON CHANGE ---
# Check if any retirement analysis values have changed and save if so
current_retirement_values = {key: st.session_state.get(key) for key in retirement_keys}
if current_retirement_values != st.session_state._prev_retirement_values:
    persistence.save_retirement_analysis_inputs(current_retirement_values)
    st.session_state._prev_retirement_values = current_retirement_values.copy()
