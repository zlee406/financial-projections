# Federal Tax Constants (2025 Estimates)

TAX_GLOBAL = {
    "year": 2025,
    "filing_status_default": "married_jointly"
}

# Standard Deduction
STANDARD_DEDUCTION_MFJ = 30000

# Federal Ordinary Income Brackets (2025 Projected)
FEDERAL_BRACKETS_MFJ = [
    (0,       0.10),
    (23850,   0.12),
    (96950,   0.22),
    (206700,  0.24),
    (394600,  0.32),
    (501050,  0.35),
    (751600,  0.37)
]

# Long Term Capital Gains Brackets (2025 Projected)
LTCG_BRACKETS_MFJ = [
    (0,      0.00),
    (96700,  0.15),
    (600050, 0.20)
]

# Net Investment Income Tax (NIIT)
NIIT_THRESHOLD_MFJ = 250000
NIIT_RATE = 0.038

# Alternative Minimum Tax (AMT) Parameters (2025 Estimates)
AMT_EXEMPTION_MFJ = 137000
AMT_PHASEOUT_START_MFJ = 1218700
AMT_RATES = [
    (0,      0.26),
    (232600, 0.28)
]

# Payroll Tax (Social Security & Medicare)
SS_WAGE_BASE_2025 = 176100 
SS_RATE = 0.062
MEDICARE_RATE = 0.0145
ADDITIONAL_MEDICARE_THRESHOLD_MFJ = 250000
ADDITIONAL_MEDICARE_RATE = 0.009

# State Tax Constants (California)
CA_BRACKETS_MFJ = [
    (0,        0.010),
    (20824,    0.020),
    (49368,    0.040),
    (77918,    0.060),
    (108162,   0.080),
    (136700,   0.093),
    (698272,   0.103),
    (837922,   0.113),
    (1396542,  0.123)
]
CA_MENTAL_HEALTH_SURCHARGE_THRESHOLD = 1000000
CA_MENTAL_HEALTH_SURCHARGE_RATE = 0.01
CA_STANDARD_DEDUCTION_MFJ = 10726 

# CA SDI (State Disability Insurance)
# 2025: Cap removed, rate is 1.1% (approx estimate based on 2024 removal of cap)
CA_SDI_RATE = 0.011

# CA AMT (Simplified)
# CA AMT Rate is flat 7%
# CA AMT Exemption MFJ (approx 2024 values)
CA_AMT_RATE = 0.07
CA_AMT_EXEMPTION_MFJ = 114000 # Approx
CA_AMT_PHASEOUT_START_MFJ = 429000 # Approx

# Alabama
AL_BRACKETS_MFJ = [
    (0,    0.02),
    (1000, 0.04),
    (6000, 0.05)
]
AL_STANDARD_DEDUCTION_MFJ = 25500

# AL Local (Birmingham)
# Occupational Tax on Gross Income
AL_BIRMINGHAM_OCCUPATIONAL_TAX_RATE = 0.01
