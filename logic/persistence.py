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

