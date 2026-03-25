# utils/screening_prompts.py

# WHO Blueprint Pathogens
WHO_PATHOGENS = {
    "cchf": "Crimean-Congo haemorrhagic fever virus",
    "rvf": "Rift Valley fever virus",
    "marburg": "Marburg virus",
    "ebola": "Ebola virus",
    "lassa": "Lassa fever or Lassa mammarenavirus",
    "mers": "Middle East respiratory syndrome coronavirus (MERS-CoV)",
    "sars": "Severe Acute Respiratory Syndrome coronavirus (SARS-CoV)",
    "zika": "Zika virus",
    "nipah": "Henipa virus (Nipah virus, Hendra virus)",
}

def get_study_objectives(pathogen_name):
    """Generate pathogen-specific study objectives."""
    return f"""# Study Objectives
This systematic review aims to collate transmission and modelling parameters for *{pathogen_name}*.

The review seeks to:
1. Provide estimates of key infectious disease metrics (reproduction number, CFR, generation time, serial interval, incubation period, etc.)
2. Document historical outbreak characteristics (size, location, duration, deaths)
3. Identify mathematical/statistical models of transmission
4. Collate risk factors for infection, severe disease, and death
5. Summarize seroprevalence data
6. Support infectious disease modelling and outbreak response efforts

This information enables effective outbreak preparedness, resource targeting, and mathematical modelling for nowcasting and forecasting of *{pathogen_name}*.
"""
