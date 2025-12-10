import json
import os
from typing import Tuple, Dict, Any

DATA_FILE = "data/strategies.json"

def load_scenarios_from_disk(filepath: str = DATA_FILE) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads strategies from JSON file if exists, else returns empty dicts."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                return data.get("spending_strategies", {}), data.get("portfolio_strategies", {})
        except Exception as e:
            # In a real app, logging would go here
            print(f"Error loading data: {e}")
            pass
    return {}, {}

def save_scenarios_to_disk(spending_strategies: Dict[str, Any], portfolio_strategies: Dict[str, Any], filepath: str = DATA_FILE) -> None:
    """Saves current strategies to JSON file."""
    data = {
        "spending_strategies": spending_strategies,
        "portfolio_strategies": portfolio_strategies
    }
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")
        raise e

def load_retirement_analysis_inputs(filepath: str = DATA_FILE) -> Dict[str, Any]:
    """Loads retirement analysis inputs from JSON file if exists, else returns defaults."""
    defaults = {
        "current_age": 30,
        "death_age": 95,
        "selected_portfolio_strategy": None,
        "selected_spending_strategy": None,
        "strategy_type": "Constant Dollar (Targets Schedule)",
        "min_spend": 30000.0,
        "max_spend": 200000.0,
        "strategy_pct": 4.0,
        "gk_init_rate": 4.5,
        "flexible_spending": False,
        "flexible_floor_pct_slider": 75,
        "allow_early_retirement_access": True,
        "early_withdrawal_penalty_pct": 10,
        "retirement_access_age": 60
    }
    
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                saved_inputs = data.get("retirement_analysis_inputs", {})
                # Merge saved values with defaults (so new keys get default values)
                merged = defaults.copy()
                merged.update(saved_inputs)
                return merged
        except Exception as e:
            print(f"Error loading retirement analysis inputs: {e}")
            pass
    return defaults

def save_retirement_analysis_inputs(inputs: Dict[str, Any], filepath: str = DATA_FILE) -> None:
    """Saves retirement analysis inputs to JSON file, preserving other data."""
    # Load existing data first
    existing_data = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error loading existing data: {e}")
    
    # Update retirement analysis inputs
    existing_data["retirement_analysis_inputs"] = inputs
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "w") as f:
            json.dump(existing_data, f, indent=2)
    except Exception as e:
        print(f"Error saving retirement analysis inputs: {e}")
        raise e





