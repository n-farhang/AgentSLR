# utils/schemas.py

VALID_PATHOGENS = [
    "lassa",
    "ebola",
    "marburg",
    "mers",
    "nipah",
    "sars",
    "zika",
    "rvf",
    "cchf",
]

PERG_PATHOGENS = [
    "ebola",
    "lassa",
    "marburg",
    "sars",
    "zika"
]

PARAMETER_CLASSES_MAPPING = {
    "Attack rate": "attack_rate",
    "Growth rate": "growth_rate",
    "Human delay": "human_delay",
    # "Mosquito": "mosquito",
    "Mutations": "mutation_rate",
    # "Other transmission parameters": "other",
    "Relative contribution": "relative_contribution",
    "Reproduction number": "reproduction_number",
    # "Risk factors": "risk_factors",
    "Seroprevalence": "seroprevalence",
    "Severity": "severity",
    # "Overdispersion": "overdispersion",
}

PARAMETER_TYPES_MAPPING = {
    'Attack rate': "attack_rate",
    'Growth rate (r)': "growth_rate",

    'Human delay - Admission to Critical Care/ICU to Discharge from Critical Care/ICU': "admission__to__discharge_or_recovery",
    'Human delay - Admission to care to Discharge from care': "admission__to__discharge_or_recovery",
    'Human delay - Diagnosis/test result to Death': "admission__to__death",
    'Human delay - Diagnosis/test result to Onset of neurologic symptoms': "other",
    'Human delay - Exposure/Infection to Recovery/non-Infectiousness': "other",
    'Human delay - Exposure/Infection to Recovery/non-Infectiousness (inverse parameter)': "other",
    'Human delay - First detection of anti-ZIKV IgM to Last detection of anti-ZIKV IgM': "other",
    'Human delay - First infection in country to first reporting in country': "other",
    'Human delay - NAAT-detectable infection to Seroconversion (IgM)': "other",
    'Human delay - NAAT-detectable infection to Seroreversion (IgM)': "other",
    'Human delay - Onset of antecedent symptoms to Onset of neurologic symptoms': "other",
    'Human delay - Onset of neurologic symptoms to Admission to care': "other",
    'Human delay - Onset of neurologic symptoms to Nadir of neurologic symptoms': "other",
    'Human delay - Onset of previous illness to Onset of neurologic symptoms': "other",
    'Human delay - Onset to Admission to care': "symptom_onset__to__admission",
    'Human delay - Onset to Implementation of vector control measures': "other",
    'Human delay - Onset to Negative PCR test in saliva': "other",
    'Human delay - Onset to Negative PCR test in serum/plasma': "other",
    'Human delay - Onset to Negative PCR test in urine': "other",
    'Human delay - Onset to Recovery/non-Infectiousness': "other",
    'Human delay - Onset to Return to area with active vectors': "other",
    'Human delay - Onset to Test result': "other",
    'Human delay - Onset to ZIKV IgG detection': "other",
    'Human delay - Onset to ZIKV IgM detection': "other",
    'Human delay - Onset to ZIKV RNA clearance from plasma': "other",
    'Human delay - Onset to ZIKV RNA clearance from saliva': "other",
    'Human delay - Onset to ZIKV RNA clearance from semen': "other",
    'Human delay - Onset to ZIKV RNA clearance from urine': "other",
    'Human delay - Recovery/non-Infectiousness to Susceptibility (inverse parameter)': "other",
    'Human delay - Reporting to Intervention': "other",
    'Human delay - generation time': "generation_time",
    'Human delay - incubation period': "incubation_period",
    'Human delay - incubation period (inverse parameter)': "incubation_period",
    'Human delay - infectious period': "infectious_period",
    'Human delay - infectious period (inverse parameter)': "infectious_period",
    'Human delay - latent period (inverse parameter)': "latent_period",
    'Human delay - serial interval': "serial_interval",

    'Mosquito delay - extrinsic incubation period': None,
    'Mosquito delay - extrinsic incubation period (EIP10)': None,
    'Mosquito delay - extrinsic incubation period (inverse parameter)': None,

    'Mutations - evolutionary rate': "evolutionary_rate",
    'Mutations - mutation rate': "mutation_rate",
    'Mutations - substitution rate': "substitution_rate",

    'Pregnancy loss proportion': None,

    'Relative contribution - sexual': "human_to_human",
    'Relative contribution - vector-borne': "zoonotic_to_human",

    # We need to map these to a separate column to compare with `transmission`
    'Reproduction number (Basic R0)': "basic_R0",
    'Reproduction number (Basic R0) - Sexual': "basic_R0",
    'Reproduction number (Basic R0) - Vector-borne': "basic_R0",
    'Reproduction number (Effective, Re)': "effective_Re",
    'Reproduction number (Effective; Re) - Sexual': "effective_Re",
    'Reproduction number (Effective; Re) - Vector-borne': "effective_Re",

    'Risk factors': None,

    'Seroprevalence - Biotinylated-EDIII antigen capture ELISA': "Unspecified",
    'Seroprevalence - HAI/HI': "HAI",
    'Seroprevalence - IFA': "IFA",
    'Seroprevalence - IgG': "IgG",
    'Seroprevalence - IgG and IgM': "Unspecified",
    'Seroprevalence - IgM': "IgM",
    'Seroprevalence - MIA': "Unspecified",
    'Seroprevalence - NS1 BOB ELISA': "Unspecified",
    'Seroprevalence - Neutralisation/PRNT': "PRNT",
    'Seroprevalence - Western blot': "Unspecified",

    'Severity - case fatality rate (CFR)': "CFR",
    'Severity - proportion of symptomatic cases': "proportion_of_symptomatic_cases",

    'Zika congenital syndrome (microcephaly) proportion': None,
}

# For now, this mapping applies to the `parameter_unit` field for attack rate
# Unsure if it will generalise to other parameters, we'll see...
PARAMETER_UNITS_MAPPING = {
    # Time units
    "Days": "days",
    "Hours": "hours",
    "Weeks": "weeks",
    # Rate units
    "No units": "no_units",
    "Per day": "per_day",
    "Per hour": "per_hour",
    "Per week": "per_week",
    "Per year": "per_year",
    "Percentage (%)": "percentage",
    # Population rate units
    "Per 1,000 births": "per_1000_births",
    "Per 10,000 population": "per_10000_population",
    "Per 100,000 population": "per_100000_population",
    # Genomic/mutation units
    "Mutations/site/generation (mu)": "mutations_per_site_per_generation",
    "Mutations/genome/generation (U)": "mutations_per_genome_per_generation",
    "Mutations/year": "mutations_per_year",
    "Substitutions/site/year": "substitutions_per_site_per_year",
    "SNPs/nucleotide sequenced": "snps_per_nucleotide_sequenced",
    "Indels/base sequenced": "indels_per_base_sequenced",
    # Other/special units
    "E10": "e10",
    "Max. nr. of cases superspreading (related to case)": "max_superspreading_cases",
    "Unspecified": "unspecified",
}

METHOD_MAPPING = {
    "Adjusted": "adjusted",
    "Naive": "naive",
    "Naïve": "naive",  # Special character variant
    "naïve": "naive",  # Lowercase special character variant
    "Unspecified": "unspecified",
}

VALUE_TYPE_MAPPING = {
    "Central": "central",
    "Maximum likelihood": "maximum_likelihood",
    "Mean": "mean",
    "Median": "median",
    "Mode": "mode",
    "Other": "other",
    "Shape": "shape",
    "Standard Deviation": "other",  # Not a central tendency measure
    "Unspecified": "unspecified",
}

STATISTICAL_APPROACH_MAPPING = {
    "Estimated model parameter": "estimated_model_parameter",
    "Observed sample statistic": "observed_sample_statistic",
    "Unspecified": "unspecified",
}

SINGLE_TYPE_UNCERTAINTY_MAPPING = {
    "Maximum": "other",
    "Other": "other",
    "Standard Deviation": "standard_deviation",
    "Standard deviation": "standard_deviation",  # Lowercase variant
    "Standard deviation (Sd) [Estimator]": "standard_deviation",
    "Standard deviation (Sd) [Sample]": "standard_deviation",
    "Standard Error": "standard_error",
    "Standard error": "standard_error",  # Lowercase variant
    "Variance": "variance",
}

PAIRED_UNCERTAINTY_MAPPING = {
    "90% CI": "CI90%",
    "90% CrI": "CRI90%",
    "95% CI": "CI95%",
    "95% CrI": "CRI95%",
    "HDPI 95%": "highest_posterior_density_interval_95%",  # Typo variant in PERG
    "HPDI 95%": "highest_posterior_density_interval_95%",
    "IQR": "IQR",
    "Inter Quartile Range (IQR) [Sample]": "IQR",
    "Other": "other",
    "Range": "range",
    "Range [Sample]": "range",
    "Unspecified": "unspecified",
}

DISTRIBUTION_TYPE_MAPPING = {
    "Weibull": "Weibull"
}

POPULATION_SEX_MAPPING = {
    "Both": "Both",
    "Female": "Female",
    "Male": "Male",
    "Unspecified": "Unspecified",
}

POPULATION_SAMPLE_TYPE_MAPPING = {
    "Community based": "Community based",
    "Contact based": "Contact based",
    "Hospital based": "Hospital based",
    "Household based": "Household based",
    "Housing estate based": "Housing estate based",
    "Mixed settings": "Mixed settings",
    "Other": "Other",
    "Population based": "Population based",
    "School based": "School based",
    "Trade / business based": "Trade / business based",
    "Travel based": "Travel based",
    "Unspecified": "Unspecified",
}

POPULATION_GROUP_MAPPING = {
    "Animal workers": "Animal workers",
    "Blood donors": "Other",  # Map to Other since not in our schema
    "Butchers": "Other",  # Map to Other since not in our schema
    "Children": "Children",
    "General population": "General population",
    "Healthcare workers": "Healthcare workers",
    "Household contacts of survivors": "Household contacts of survivors",
    "Mixed groups": "Mixed groups",
    "Other": "Other",
    "Outdoor workers": "Other",  # Map to Other since not in our schema
    "Persons under investigation": "Persons under investigation",
    "Pregnant women": "Pregnant women",
    "Unspecified": "Unspecified",
}
