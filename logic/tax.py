from dataclasses import dataclass
from logic import tax_rules

@dataclass
class TaxResult:
    # Federal
    federal_ordinary_tax: float
    federal_ltcg_tax: float
    niit_tax: float
    regular_federal_total: float
    
    amti: float
    amt_tax: float
    is_amt_triggered: bool
    total_federal_liability: float
    
    payroll_tax: float
    
    # State
    state_tax: float
    ca_sdi_tax: float # CA Specific
    ca_amt_tax: float # CA Specific
    al_occupational_tax: float # AL Specific
    
    # Global
    total_tax: float
    effective_rate: float

class TaxEngine:
    def __init__(self, location: str, filing_status: str = "married_jointly"):
        self.location = location
        self.filing_status = filing_status
        
    def _calculate_marginal_tax(self, taxable_income: float, brackets: list) -> float:
        """
        Calculates tax based on progressive brackets.
        brackets: list of (threshold, rate) tuples.
        """
        current_tax = 0.0
        
        for i in range(len(brackets)):
            threshold, rate = brackets[i]
            
            if i < len(brackets) - 1:
                next_threshold = brackets[i+1][0]
            else:
                next_threshold = float('inf')
            
            lower_bound = threshold
            upper_bound = next_threshold
            
            if taxable_income > lower_bound:
                taxable_amount_in_bracket = min(taxable_income, upper_bound) - lower_bound
                current_tax += taxable_amount_in_bracket * rate
            
        return current_tax

    def calculate_federal_ordinary_tax(self, taxable_ordinary_income: float) -> float:
        return self._calculate_marginal_tax(taxable_ordinary_income, tax_rules.FEDERAL_BRACKETS_MFJ)

    def calculate_ltcg_tax(self, taxable_ordinary_income: float, ltcg_income: float) -> float:
        """
        Calculates tax on Long Term Capital Gains.
        LTCG stacks on top of Ordinary Income for bracket determination.
        """
        brackets = tax_rules.LTCG_BRACKETS_MFJ
        
        # Calculate tax on the total stack (Ordinary + LTCG) as if it were all subject to LTCG brackets
        tax_on_combined = self._calculate_marginal_tax(taxable_ordinary_income + ltcg_income, brackets)
        
        # Calculate tax on just the Ordinary base (to subtract it out)
        tax_on_ordinary_base = self._calculate_marginal_tax(taxable_ordinary_income, brackets)
        
        return tax_on_combined - tax_on_ordinary_base

    def calculate_niit(self, magi: float, net_investment_income: float) -> float:
        excess_magi = max(0, magi - tax_rules.NIIT_THRESHOLD_MFJ)
        subject_to_tax = min(net_investment_income, excess_magi)
        return subject_to_tax * tax_rules.NIIT_RATE

    def calculate_payroll_tax(self, w2_income: float) -> float:
        ss_tax = min(w2_income, tax_rules.SS_WAGE_BASE_2025) * tax_rules.SS_RATE
        med_tax = w2_income * tax_rules.MEDICARE_RATE
        add_med_tax = max(0, w2_income - tax_rules.ADDITIONAL_MEDICARE_THRESHOLD_MFJ) * tax_rules.ADDITIONAL_MEDICARE_RATE
        return ss_tax + med_tax + add_med_tax

    def calculate_amt(self, amti: float) -> float:
        excess_amti = max(0, amti - tax_rules.AMT_PHASEOUT_START_MFJ)
        reduction = excess_amti * 0.25
        available_exemption = max(0, tax_rules.AMT_EXEMPTION_MFJ - reduction)
        
        amt_base = max(0, amti - available_exemption)
        
        threshold_28 = tax_rules.AMT_RATES[1][0] 
        rate_26 = tax_rules.AMT_RATES[0][1]
        rate_28 = tax_rules.AMT_RATES[1][1]
        
        if amt_base <= threshold_28:
            return amt_base * rate_26
        else:
            return (threshold_28 * rate_26) + ((amt_base - threshold_28) * rate_28)

    def calculate_california_tax_regular(self, taxable_income: float) -> float:
        return self._calculate_marginal_tax(taxable_income, tax_rules.CA_BRACKETS_MFJ)

    def calculate_california_amt(self, amti: float) -> float:
        # Simplified CA AMT
        # Exemption Phaseout
        excess_amti = max(0, amti - tax_rules.CA_AMT_PHASEOUT_START_MFJ)
        reduction = excess_amti * 0.25
        available_exemption = max(0, tax_rules.CA_AMT_EXEMPTION_MFJ - reduction)
        
        amt_base = max(0, amti - available_exemption)
        return amt_base * tax_rules.CA_AMT_RATE

    def calculate_alabama_tax(self, taxable_income: float, federal_tax_paid: float) -> float:
        # Adjust for Fed Deduction
        al_taxable = max(0, taxable_income - federal_tax_paid) 
        return self._calculate_marginal_tax(al_taxable, tax_rules.AL_BRACKETS_MFJ)

    def run_projection(self, 
                       ordinary_income: float, 
                       ltcg_income: float = 0.0,
                       iso_spread: float = 0.0,
                       amt_adjustment_sale: float = 0.0) -> TaxResult:
        
        # --- 1. Regular Federal Tax ---
        agi = ordinary_income + ltcg_income
        
        taxable_ordinary = max(0, ordinary_income - tax_rules.STANDARD_DEDUCTION_MFJ)
        fed_ordinary_tax = self.calculate_federal_ordinary_tax(taxable_ordinary)
        
        # Determine taxable LTCG (Standard Deduction applies to ordinary first)
        total_taxable_income = max(0, agi - tax_rules.STANDARD_DEDUCTION_MFJ)
        taxable_ordinary_part = taxable_ordinary
        taxable_ltcg_part = total_taxable_income - taxable_ordinary_part
        
        fed_ltcg_tax = self.calculate_ltcg_tax(taxable_ordinary_part, taxable_ltcg_part)
        
        niit_tax = self.calculate_niit(agi, ltcg_income)
        
        regular_federal_total = fed_ordinary_tax + fed_ltcg_tax + niit_tax
        
        # --- 2. AMT Calculation ---
        amti = agi + iso_spread + amt_adjustment_sale
        amt_tax = self.calculate_amt(amti)
        
        # --- 3. Final Federal Liability ---
        total_federal_liability = max(regular_federal_total, amt_tax)
        is_amt_triggered = amt_tax > regular_federal_total
        
        # --- 4. Payroll Tax ---
        payroll_tax = self.calculate_payroll_tax(ordinary_income)
        
        # --- 5. State & Local Taxes ---
        state_tax = 0.0
        ca_sdi_tax = 0.0
        ca_amt_tax = 0.0
        al_occupational_tax = 0.0
        
        if self.location == "California":
            # CA Regular Tax
            # CA treats LTCG as Ordinary
            ca_regular_tax = self.calculate_california_tax_regular(total_taxable_income)
            
            # Mental Health Surcharge (on taxable income > 1M)
            if total_taxable_income > tax_rules.CA_MENTAL_HEALTH_SURCHARGE_THRESHOLD:
                excess = total_taxable_income - tax_rules.CA_MENTAL_HEALTH_SURCHARGE_THRESHOLD
                ca_regular_tax += excess * tax_rules.CA_MENTAL_HEALTH_SURCHARGE_RATE

            # CA AMT
            # CA AMTI is similar to Fed AMTI (AGI + Prefs).
            # Simplified: Use same AMTI base as Fed.
            ca_amt_tentative = self.calculate_california_amt(amti)
            
            state_tax = max(ca_regular_tax, ca_amt_tentative)
            ca_amt_tax = max(0, ca_amt_tentative - ca_regular_tax) # The "extra" paid
            
            # CA SDI
            ca_sdi_tax = ordinary_income * tax_rules.CA_SDI_RATE
            
        elif self.location == "Alabama":
            # AL State Tax
            state_tax = self.calculate_alabama_tax(total_taxable_income, total_federal_liability)
            
            # Birmingham Occupational Tax (Local)
            # 1% on Gross Compensation (Ordinary Income)
            al_occupational_tax = ordinary_income * tax_rules.AL_BIRMINGHAM_OCCUPATIONAL_TAX_RATE

        total_tax = total_federal_liability + state_tax + payroll_tax + ca_sdi_tax + al_occupational_tax

        return TaxResult(
            federal_ordinary_tax=fed_ordinary_tax,
            federal_ltcg_tax=fed_ltcg_tax,
            niit_tax=niit_tax,
            regular_federal_total=regular_federal_total,
            amti=amti,
            amt_tax=amt_tax,
            is_amt_triggered=is_amt_triggered,
            total_federal_liability=total_federal_liability,
            payroll_tax=payroll_tax,
            state_tax=state_tax,
            ca_sdi_tax=ca_sdi_tax,
            ca_amt_tax=ca_amt_tax,
            al_occupational_tax=al_occupational_tax,
            total_tax=total_tax,
            effective_rate=total_tax / agi if agi > 0 else 0
        )

# Helper for external calls
def calculate_taxes(income: float, location: str) -> float:
    engine = TaxEngine(location)
    result = engine.run_projection(income)
    return result.total_tax
