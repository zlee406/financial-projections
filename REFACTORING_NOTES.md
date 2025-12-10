# Simulation Bridge Refactoring

## Summary

Refactored `logic/simulation_bridge.py` to use structured dataclasses instead of dictionaries with `.get()` default values. This change enforces that the frontend provides all necessary values explicitly, rather than relying on backend defaults.

## Key Changes

### 1. New Dataclass Structures

Created strongly-typed input structures:

- `ChildInput` - Child configuration with name, birth year, optional profile
- `HousingProjectInput` - Housing project details
- `SpendingItemInput` - Individual spending items
- `MortgageInput` - Mortgage details
- `SpendingStrategyInputs` - Complete spending strategy configuration
- `IncomeStreamInput` - Income stream configuration
- `PortfolioStrategyInputs` - Complete portfolio and simulation configuration

### 2. Removed Dictionary Access with Defaults

**Before:**
```python
base_monthly = inputs.get("base_monthly_spend")
flexible_spending = portfolio_inputs.get("flexible_spending", False)
appreciation_rate = hp.get("appreciation_rate", 0.03)
```

**After:**
```python
base_monthly = inputs.base_monthly_spend
flexible_spending = portfolio_inputs.flexible_spending
appreciation_rate = hp.appreciation_rate
```

All defaults are now defined in the dataclass definitions, making them explicit and documented.

### 3. Functions Renamed and Signatures Updated

- `build_spending_model_from_dict()` → `build_spending_model()` - now takes `SpendingStrategyInputs`
- `run_simulation_wrapper()` → `run_simulation()` - now takes structured inputs

### 4. Backwards Compatibility

Added helper functions for transition:
- `dict_to_spending_inputs()` - Convert dict to `SpendingStrategyInputs`
- `dict_to_portfolio_inputs()` - Convert dict to `PortfolioStrategyInputs`
- `run_simulation_wrapper()` - Backwards-compatible wrapper for existing UI code

## Benefits

1. **Type Safety**: All fields are explicitly typed, making it clear what's required
2. **No Hidden Defaults**: Frontend must provide all values; no surprises from backend defaults
3. **Better IDE Support**: Autocomplete and type checking work properly
4. **Clearer Interface**: Dataclass definitions serve as documentation
5. **Easier Testing**: Can construct inputs without worrying about dict keys

## Migration Path

### For New Code

Use the structured approach directly:

```python
from logic.simulation_bridge import (
    SpendingStrategyInputs, 
    PortfolioStrategyInputs,
    run_simulation
)

spending = SpendingStrategyInputs(
    base_monthly_spend=5000.0,
    location="California",
    # ... all required fields
)

portfolio = PortfolioStrategyInputs(
    liquid_assets=500000.0,
    retirement_assets=300000.0,
    # ... all required fields
)

result, stats, schedule = run_simulation(spending, portfolio, df_market)
```

### For Existing Code

Continue using the wrapper (current UI code already does this):

```python
from logic.simulation_bridge import run_simulation_wrapper

# Works exactly as before
result, stats, schedule = run_simulation_wrapper(
    strategy_dict,  # Dictionary with spending strategy
    portfolio_dict,  # Dictionary with portfolio inputs
    df_market
)
```

## Frontend Responsibility

The frontend should now:

1. **Provide all required fields** - No relying on backend defaults
2. **Handle missing JSON values** - If loading old scenarios, fill in missing fields with UI defaults
3. **Validate inputs** - Ensure all required fields are present before calling backend

## Example: Required vs Optional Fields

### SpendingStrategyInputs
**Required:**
- `base_monthly_spend: float`
- `location: str`

**Optional (with defaults):**
- `children: List[ChildInput] = []`
- `has_mortgage: bool = False`
- `housing_projects: List[HousingProjectInput] = []`

### PortfolioStrategyInputs
**Required:**
- `liquid_assets: float`
- `retirement_assets: float`
- `stock_alloc_pct: float`
- `bond_return_pct: float`
- `inflation_rate: float`
- `current_age: int`
- `death_age: int`
- `strategy_type: str`
- `min_spend: float`
- `max_spend: float`

**Optional (with defaults):**
- `private_shares: float = 0`
- `flexible_spending: bool = False`
- `flexible_floor_pct: float = 0.75`
- `allow_early_retirement_access: bool = True`
- `retirement_access_age: int = 60`

## Testing

All existing tests continue to pass:
- `tests/test_chart_integration.py` - Uses `run_simulation_wrapper()` (backwards compatible)

## Future Work

Consider migrating the UI to use the structured inputs directly instead of dictionaries, which would:
1. Remove need for conversion functions
2. Provide better type safety in the UI layer
3. Catch missing fields at construction time

