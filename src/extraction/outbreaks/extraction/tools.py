# src/extraction/outbreaks/extraction/tools.py
"""
Tool call definitions for outbreak extraction.

This module defines the JSON schema for the outbreak extraction tool call.
"""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

COUNTRIES = [
    'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 
    'Antigua and Barbuda', 'Argentina', 'Armenia', 'Australia', 'Austria', 
    'Azerbaijan', 'Bahamas', 'Bahrain', 'Bangladesh', 'Barbados', 
    'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan', 
    'Bolivia (Plurinational State of)', 'Bosnia and Herzegovina', 'Botswana', 
    'Brazil', 'Brunei Darussalam', 'Bulgaria', 'Burkina Faso', 'Burundi', 
    'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada', 'Central African Republic', 
    'Chad', 'Chile', 'China', 'Colombia', 'Comoros', 'Congo', 'Cook Islands', 
    'Costa Rica', 'Côte d\'Ivoire', 'Croatia', 'Cuba', 'Cyprus', 
    'Czechia', 'Democratic People\'s Republic of Korea', 
    'Democratic Republic of the Congo', 'Denmark', 'Djibouti', 'Dominica', 
    'Dominican Republic', 'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 
    'Eritrea', 'Estonia', 'Eswatini', 'Ethiopia', 'Fiji', 'Finland', 'France', 
    'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece', 'Grenada', 
    'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti', 'Honduras', 
    'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran (Islamic Republic of)', 
    'Iraq', 'Ireland', 'Israel', 'Italy', 'Jamaica', 'Japan', 'Jordan', 
    'Kazakhstan', 'Kenya', 'Kiribati', 'Kuwait', 'Kyrgyzstan', 
    'Lao People\'s Democratic Republic', 'Latvia', 'Lebanon', 'Lesotho', 
    'Liberia', 'Libya', 'Lithuania', 'Luxembourg', 'Madagascar', 'Malawi', 
    'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania', 
    'Mauritius', 'Mexico', 'Federated States of Micronesia', 'Monaco', 
    'Mongolia', 'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 
    'Nauru', 'Nepal', 'Netherlands', 'New Zealand', 'Nicaragua', 'Niger', 
    'Nigeria', 'Niue', 'North Macedonia', 'Norway', 'Oman', 'Pakistan', 
    'Palau', 'Panama', 'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 
    'Poland', 'Portugal', 'Qatar', 'Republic of Korea', 'Republic of Moldova', 
    'Romania', 'Russian Federation', 'Rwanda', 'Saint Kitts and Nevis', 
    'Saint Lucia', 'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 
    'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 
    'Sierra Leone', 'Singapore', 'Slovakia', 'Slovenia', 'Solomon Islands', 
    'Somalia', 'South Africa', 'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 
    'Suriname', 'Sweden', 'Switzerland', 'Syrian Arab Republic', 'Tajikistan', 
    'Thailand', 'Timor-Leste', 'Togo', 'Tonga', 'Trinidad and Tobago', 
    'Tunisia', 'Türkiye', 'Turkmenistan', 'Tuvalu', 'Uganda', 'Ukraine', 
    'United Arab Emirates', 
    'United Kingdom of Great Britain and Northern Ireland', 
    'United Republic of Tanzania', 'United States of America', 'Uruguay', 
    'Uzbekistan', 'Vanuatu', 'Venezuela (Bolivarian Republic of)', 'Viet Nam', 
    'Yemen', 'Yugoslavia', 'Zambia', 'Zimbabwe'
]

OUTBREAK_SOURCES = [
    "Domestic animal",
    "Wild animal",
    "Date palm sap",
    "Unknown",
    "Other"
]

MODE_OF_DETECTION = [
    "Molecular (PCR etc)",
    "Symptoms",
    "Confirmed + Suspected",
    "Unspecified"
]

PRE_OUTBREAK_STATUS = [
    "Disease-free baseline",
    "Endemic equilibrium",
    "Unspecified",
    "Probable"
]

SEX_DISAGG_TYPES = [
    "Confirmed",
    "Suspected",
    "Other",
    "Unspecified"
]


OUTBREAK_TOOL_CALL = {
    "type": "function",
    "function":{
        "name": "extract_outbreak_data",
        "description": (
            "Extract outbreak information from the provided article text. "
            "Call this function once for each distinct outbreak reported. "
            "Outbreaks are distinct if they differ by location, time, or both."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "outbreak_start_day": {
                    "type": ["integer", "null"],
                    "description": "Day of outbreak start (1-31). Set to null if not provided."
                },
                "outbreak_start_month": {
                    "type": ["string", "null"],
                    "description": (
                        f"Month of outbreak start. Must be one of: {', '.join(MONTHS)}. "
                        "Set to null if not provided."
                    )
                },
                "outbreak_start_year": {
                    "type": ["integer", "null"],
                    "description": "Year of outbreak start. Set to null if not provided."
                },
                "outbreak_end_day": {
                    "type": ["integer", "null"],
                    "description": "Day of outbreak end (1-31). Set to null if not provided."
                },
                "outbreak_end_month": {
                    "type": ["string", "null"],
                    "description": (
                        f"Month of outbreak end. Must be one of: {', '.join(MONTHS)}. "
                        "Set to null if not provided."
                    )
                },
                "outbreak_end_year": {
                    "type": ["integer", "null"],
                    "description": "Year of outbreak end. Set to null if not provided."
                },
                "outbreak_duration_months": {
                    "type": ["number", "null"],
                    "description": (
                        "Duration of outbreak in months. ONLY extract if explicitly "
                        "stated in the paper. Do NOT calculate. Set to null if not stated."
                    )
                },
                "outbreak_is_currently_ongoing": {
                    "type": "boolean",
                    "description": "Whether the outbreak is ongoing (true) or concluded (false)."
                },
                "outbreak_country": {
                    "type": "string",
                    "description": (
                        "Country where outbreak occurred. MUST be one of the WHO standard country names. "
                        f"Valid values: {', '.join(COUNTRIES[:10])}... (full list available)"
                    )
                },
                "outbreak_location": {
                    "type": ["string", "null"],
                    "description": (
                        "Specific location within country (e.g., city, district, province). "
                        "Extract as written in paper. Use semicolons to separate multiple locations. "
                        "Do NOT include commas. Set to null if not provided."
                    )
                },
                "outbreak_location_type": {
                    "type": ["string", "null"],
                    "description": (
                        "Type of location unit as specified in paper (e.g., 'district', "
                        "'province', 'county', 'state'). Set to null if not specified."
                    )
                },
                "outbreak_source": {
                    "type": ["string", "null"],
                    "description": (
                        f"Source of outbreak. Must be one of: {', '.join(OUTBREAK_SOURCES)}. "
                        "Set to null if not provided."
                    )
                },
                "mode_of_detection": {
                    "type": ["string", "null"],
                    "description": (
                        f"How cases were detected. Must be one of: {', '.join(MODE_OF_DETECTION)}. "
                        "Set to null if not provided."
                    )
                },
                "method_of_case_definition": {
                    "type": ["string", "null"],
                    "description": "Method used to define cases. Set to null if not provided."
                },
                "pre_outbreak": {
                    "type": ["string", "null"],
                    "description": (
                        f"Pre-outbreak baseline. Must be one of: {', '.join(PRE_OUTBREAK_STATUS)}. "
                        "Set to null if not provided."
                    )
                },
                "cases_confirmed": {
                    "type": ["number", "null"],
                    "description": "Number of confirmed cases. Set to null if not provided."
                },
                "cases_probable": {
                    "type": ["number", "null"],
                    "description": "Number of probable cases. Set to null if not provided."
                },
                "cases_suspected": {
                    "type": ["number", "null"],
                    "description": "Number of suspected cases. Set to null if not provided."
                },
                "cases_unspecified": {
                    "type": ["number", "null"],
                    "description": "Number of unspecified cases. Set to null if not provided."
                },
                "cases_asymptomatic": {
                    "type": ["number", "null"],
                    "description": "Number of asymptomatic cases. Set to null if not provided."
                },
                "cases_severe": {
                    "type": ["number", "null"],
                    "description": (
                        "Number of severe cases as stated. If only hospitalizations are "
                        "given, extract hospitalization count here. Set to null if not provided."
                    )
                },
                "deaths": {
                    "type": ["number", "null"],
                    "description": "Number of deaths. Set to null if not provided."
                },
                "asymptomatic_transmission_described": {
                    "type": "boolean",
                    "description": "Whether asymptomatic transmission is described (true/false)."
                },
                "population_size_geographical_area": {
                    "type": ["number", "null"],
                    "description": "Population size of the geographical area. Set to null if not provided."
                },
                "type_cases_sex_disagg": {
                    "type": ["string", "null"],
                    "description": (
                        f"Type of cases for sex disaggregation. Must be one of: {', '.join(SEX_DISAGG_TYPES)}. "
                        "Set to null if sex disaggregation not provided."
                    )
                },
                "male_cases": {
                    "type": ["number", "null"],
                    "description": "Number of male cases. Set to null if not provided."
                },
                "prop_male_cases": {
                    "type": ["number", "null"],
                    "description": (
                        "Proportion or percentage of cases in males (0.0-1.0 for proportion, "
                        "0-100 for percentage). Set to null if not provided."
                    )
                },
                "female_cases": {
                    "type": ["number", "null"],
                    "description": "Number of female cases. Set to null if not provided."
                },
                "prop_female_cases": {
                    "type": ["number", "null"],
                    "description": (
                        "Proportion or percentage of cases in females (0.0-1.0 for proportion, "
                        "0-100 for percentage). Set to null if not provided."
                    )
                },
                "notes": {
                    "type": ["string", "null"],
                    "description": "Any additional notes or context. Set to null if not needed."
                }
            },
            "required": [
            "outbreak_start_day",
            "outbreak_start_month",
            "outbreak_start_year",
            "outbreak_end_day",
            "outbreak_end_month",
            "outbreak_end_year",
            "outbreak_duration_months",
            "outbreak_is_currently_ongoing",
            "outbreak_country",
            "outbreak_location",
            "outbreak_location_type",
            "outbreak_source",
            "mode_of_detection",
            "method_of_case_definition",
            "pre_outbreak",
            "cases_confirmed",
            "cases_probable",
            "cases_suspected",
            "cases_unspecified",
            "cases_asymptomatic",
            "cases_severe",
            "deaths",
            "population_size_geographical_area",
            "type_cases_sex_disagg",
            "male_cases",
            "prop_male_cases",
            "female_cases",
            "prop_female_cases",
            "notes"
        ]
    }
    }
}


PROVENANCE_TOOL_CALL = {
    "type": "function",
    "function": {
        "name": "extract_outbreak_provenance",
        "description": "Extract excerpts from the article that support each extracted outbreak field value. Provide direct quotes that justify each value selected for this specific outbreak.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "outbreak_country_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote from the article mentioning the outbreak country."
                },
                "outbreak_location_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote from the article mentioning the specific location."
                },
                "outbreak_start_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote supporting the outbreak start date (day/month/year)."
                },
                "outbreak_end_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote supporting the outbreak end date (day/month/year)."
                },
                "outbreak_duration_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote explicitly stating the outbreak duration. Only provide if duration was explicitly stated."
                },
                "outbreak_source_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote describing the source of the outbreak."
                },
                "mode_of_detection_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote describing how cases were detected/confirmed."
                },
                "method_of_case_definition_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote describing the case definition method."
                },
                "pre_outbreak_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote describing the pre-outbreak baseline status."
                },
                "cases_confirmed_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the confirmed case count."
                },
                "cases_probable_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the probable case count."
                },
                "cases_suspected_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the suspected case count."
                },
                "cases_unspecified_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the unspecified case count."
                },
                "cases_asymptomatic_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the asymptomatic case count."
                },
                "cases_severe_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the severe case or hospitalization count."
                },
                "deaths_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the death count."
                },
                "asymptomatic_transmission_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote describing asymptomatic transmission if mentioned."
                },
                "population_size_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with the population size of the geographical area."
                },
                "sex_disaggregation_excerpt": {
                    "type": ["string", "null"],
                    "description": "Direct quote with sex disaggregation data (male/female cases)."
                }
            },
            "required": [
                "outbreak_country_excerpt",
                "outbreak_location_excerpt",
                "outbreak_start_excerpt",
                "outbreak_end_excerpt",
                "outbreak_duration_excerpt",
                "outbreak_source_excerpt",
                "mode_of_detection_excerpt",
                "method_of_case_definition_excerpt",
                "pre_outbreak_excerpt",
                "cases_confirmed_excerpt",
                "cases_probable_excerpt",
                "cases_suspected_excerpt",
                "cases_unspecified_excerpt",
                "cases_asymptomatic_excerpt",
                "cases_severe_excerpt",
                "deaths_excerpt",
                "asymptomatic_transmission_excerpt",
                "population_size_excerpt",
                "sex_disaggregation_excerpt"
            ]
        }
    }
}
