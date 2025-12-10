from dataclasses import dataclass
from typing import Optional

@dataclass
class IncomeSource:
    name: str
    amount: float
    type: str # 'salary', 'bonus', 'rsu', 'iso_exercise'

@dataclass
class RSUGrant:
    grant_id: str
    shares: int
    vesting_schedule: dict # {year: shares}
    grant_price: float

@dataclass
class ISOGrant:
    grant_id: str
    shares: int
    strike_price: float
    vesting_schedule: dict # {year: shares}

class CompensationModel:
    def __init__(self, base_salary: float):
        self.base_salary = base_salary
        self.rsu_grants = []
        self.iso_grants = []
        self.other_income = []

    def add_rsu_grant(self, grant: RSUGrant):
        self.rsu_grants.append(grant)

    def add_iso_grant(self, grant: ISOGrant):
        self.iso_grants.append(grant)

    def calculate_total_income(self, year: int, current_stock_price: float) -> dict:
        """
        Returns a breakdown of income for a given year.
        """
        # Base Salary
        total_ordinary_income = self.base_salary
        
        # RSUs vesting this year
        rsu_income = 0.0
        for grant in self.rsu_grants:
            shares_vesting = grant.vesting_schedule.get(year, 0)
            rsu_income += shares_vesting * current_stock_price
        
        total_ordinary_income += rsu_income
        
        # ISOs are trickier - depends on exercise. 
        # This model assumes we just calculate potential value, actual exercise is an event.
        
        return {
            "ordinary_income": total_ordinary_income,
            "rsu_income_portion": rsu_income,
            "base_salary": self.base_salary
        }

    def calculate_iso_spread(self, year: int, current_stock_price: float, exercise_amount: dict) -> float:
        """
        Calculate AMT spread for exercised ISOs.
        exercise_amount: {grant_id: number_of_shares_exercised}
        """
        spread = 0.0
        for grant in self.iso_grants:
            amount = exercise_amount.get(grant.grant_id, 0)
            if amount > 0:
                spread += amount * (current_stock_price - grant.strike_price)
        return spread







