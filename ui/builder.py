import streamlit as st
import plotly.express as px
from logic import persistence

def update_housing_project_cb(strat_name, project_index, field_name, key):
    """Callback to update housing project data and persist immediately."""
    new_value = st.session_state[key]
    # Ensure structure exists (it should if we are editing it)
    if strat_name in st.session_state.spending_strategies:
        projects = st.session_state.spending_strategies[strat_name].get("housing_projects", [])
        if 0 <= project_index < len(projects):
            projects[project_index][field_name] = new_value
            persistence.save_scenarios_to_disk(st.session_state.spending_strategies, st.session_state.portfolio_strategies)

def render_builder():
    st.header("Portfolio & Spending Manager")
    
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("1. Portfolio Strategies")
