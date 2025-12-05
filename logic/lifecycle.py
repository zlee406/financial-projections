import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ChildCostPhase:
    name: str
    start_age: int
    end_age: int
    monthly_cost: float

@dataclass
class Child:
    name: str
    birth_year: int
    phases: List[ChildCostPhase] = field(default_factory=list)

    def get_cost_for_year(self, year: int) -> float:
        age = year - self.birth_year
        cost = 0.0
        for phase in self.phases:
            if phase.start_age <= age <= phase.end_age:
                cost += phase.monthly_cost * 12
        return cost

@dataclass
class SpendingItem:
    name: str
    monthly_amount: float
    start_year: Optional[int] = None
    end_year: Optional[int] = None

@dataclass
class HousingProject:
    name: str
    purchase_year: int
    price: float
    down_payment: float
    interest_rate: float
    term_years: int
    property_tax_rate: float = 0.01
    maintenance_rate: float = 0.01
    sale_year: Optional[int] = None
    appreciation_rate: float = 0.03
    selling_costs: float = 0.06

@dataclass
class Mortgage:
    monthly_payment: float
    years_remaining: int

# Retaining FuturePurchase alias if needed temporarily, but aim to replace usage
FuturePurchase = HousingProject 

@dataclass
class SpendingModel:
    current_age: int
    death_age: int
    base_monthly_spend: float = 0.0
    current_year: int = 2025
    children: List[Child] = field(default_factory=list)
    mortgage: Optional[Mortgage] = None # Existing mortgage
    housing_projects: List[HousingProject] = field(default_factory=list)
    spending_items: List[SpendingItem] = field(default_factory=list)
    
    # Legacy field support (can be removed if fully migrated, keeping for safety if app.py passes it)
    base_annual_spend: float = 0.0 

    def generate_schedule(self, inflation_rate: float = 0.0) -> pd.DataFrame:
        """
        Generates a DataFrame with 'Age', 'Required_Real_Spend', and breakdown columns.
        inflation_rate: used to deflate fixed nominal payments (like mortgages) to real dollars.
        """
        years_to_model = self.death_age - self.current_age + 1
        if years_to_model <= 0:
            return pd.DataFrame(columns=["Age", "Required_Real_Spend", "Base_Real", "Items_Real", "Mortgage_Real", "Housing_Real", "Child_Real"])
            
        ages = np.arange(self.current_age, self.death_age + 1)
        schedule = []
        
        # Helper to calculate mortgage payment
        def calc_annual_pmt(principal, rate, years):
            if principal <= 0: return 0.0
            if rate == 0:
                return (principal / (years * 12)) * 12
            r = rate / 12.0
            n = years * 12
            monthly = principal * (r * (1 + r)**n) / ((1 + r)**n - 1)
            return monthly * 12

        # Pre-calculate housing project details
        project_details_list = []
        for hp in self.housing_projects:
            loan_amount = hp.price - hp.down_payment
            annual_pmt_nominal = calc_annual_pmt(loan_amount, hp.interest_rate, hp.term_years)
            project_details_list.append({
                "nominal_pmt": annual_pmt_nominal,
                "obj": hp
            })

        for age in ages:
            year_offset = age - self.current_age
            simulation_year = self.current_year + year_offset
            
            # Deflator for nominal fixed payments to convert to Real 2025$
            # nominal_value / ((1+inf)^t) = real_value
            deflator = (1 + inflation_rate) ** year_offset
            
            # Components
            base_val = 0.0
            items_val = 0.0
            mortgage_val = 0.0
            housing_val = 0.0
            child_val = 0.0
            
            # 1. Base Spend (Monthly Items + Aggregate)
            base_val += (self.base_monthly_spend * 12)
            base_val += self.base_annual_spend # Legacy support
            
            for item in self.spending_items:
                # Handle optional start/end years
                start = item.start_year if item.start_year is not None else -9999
                end = item.end_year if item.end_year is not None else 9999
                
                if start <= simulation_year <= end:
                    items_val += (item.monthly_amount * 12)
            
            # 2. Existing Mortgage (Fixed Nominal -> Real)
            if self.mortgage and year_offset < self.mortgage.years_remaining:
                nominal_annual = self.mortgage.monthly_payment * 12
                mortgage_val = nominal_annual / deflator
                
            # 3. Housing Projects
            for proj_det in project_details_list:
                hp = proj_det["obj"]
                
                # Check if house is sold
                is_sold = hp.sale_year and simulation_year >= hp.sale_year
                if is_sold:
                    # If sold this exact year, we get equity back (negative spend)
                    if simulation_year == hp.sale_year:
                        # Calculate value at sale
                        years_owned = hp.sale_year - hp.purchase_year
                        sale_price = hp.price * ((1 + hp.appreciation_rate) ** years_owned)
                        
                        # Calculate remaining loan balance
                        # Simplified: standard amortization
                        remaining_balance = 0.0
                        loan_amount = hp.price - hp.down_payment
                        if loan_amount > 0:
                            # Standard remaining balance formula
                            r = hp.interest_rate / 12.0
                            n = hp.term_years * 12
                            p = years_owned * 12
                            if p < n:
                                if r == 0:
                                    remaining_balance = loan_amount * (1 - p/n)
                                else:
                                    remaining_balance = loan_amount * (((1+r)**n - (1+r)**p) / ((1+r)**n - 1))
                        
                        proceeds = sale_price * (1 - hp.selling_costs) - remaining_balance
                        
                        # Proceeds are nominal at sale year. Convert to Real.
                        real_proceeds = proceeds / deflator
                        housing_val -= real_proceeds
                    continue # No more expenses after sale
                
                # Purchase Year: Down Payment
                if simulation_year == hp.purchase_year:
                    # Down payment is Real
                    housing_val += hp.down_payment
                
                # Ownership years
                if simulation_year >= hp.purchase_year:
                    # Upkeep (Tax + Maint)
                    real_appreciation = (1 + hp.appreciation_rate) / (1 + inflation_rate) - 1
                    years_owned = simulation_year - hp.purchase_year
                    current_real_value = hp.price * ((1 + real_appreciation) ** years_owned)
                    
                    real_upkeep = current_real_value * (hp.property_tax_rate + hp.maintenance_rate)
                    housing_val += real_upkeep
                    
                    # Mortgage P&I (Nominal -> Real)
                    if years_owned < hp.term_years:
                        nominal_pmt = proj_det["nominal_pmt"]
                        real_pmt = nominal_pmt / deflator
                        housing_val += real_pmt

            # 4. Children
            for child in self.children:
                child_val += child.get_cost_for_year(simulation_year)
                    
            total_real_spend = base_val + items_val + mortgage_val + housing_val + child_val
            
            schedule.append({
                "Age": age,
                "Required_Real_Spend": total_real_spend,
                "Base_Real": base_val,
                "Items_Real": items_val,
                "Mortgage_Real": mortgage_val,
                "Housing_Real": housing_val,
                "Child_Real": child_val
            })
            
        return pd.DataFrame(schedule)
