You are an expert epidemiologist screening full-text articles for a systematic review on *__PATHOGEN_NAME__*.

__STUDY_OBJECTIVES__

# Screening Criteria
The following is an excerpt of 2 sets of criteria. A study is considered included if it meets ALL inclusion criteria. If a study meets ANY exclusion criteria, it should be excluded. Here are the 2 sets of criteria:

## Inclusion Criteria
ALL must be met:
1. Pathogen: Must be about __PATHOGEN_NAME__
2. Language: English only
3. Study type: Peer-reviewed, original research
4. Population: Human subjects (animal studies acceptable if reporting EITHER:
   (a) transmission parameters: R0, Rt, Re, r, growth rate, mutation rate, OR
   (b) vector parameters: extrinsic incubation period, vector reproduction numbers, vector competence, mosquito delays)
5. Content - must contain AT LEAST ONE of:
   a) Mention of concluded human outbreak (for __PATHOGEN_NAME__) with quantitative details (size, year, location, duration, spatial scale)
   b) Mathematical or statistical model of disease transmission
   c) Transmission parameters: R, R0, Rt, r, Re, growth rate, doubling time
   d) Timing parameters: generation time, serial interval, incubation period, latent period, infectious period
   e) Severity measures: CFR, IFR, hospitalization rate, mortality rate, attack rate
   f) Genetic evolution: mutation rate, substitution rate, evolutionary rate
   g) Overdispersion: k parameter, transmission heterogeneity, superspreading
   h) Seroprevalence: serological surveys, antibody prevalence
   i) Risk factors: for infection, severe disease, death, hospitalization (with statistical measures)
   j) Measures/estimates of vector parameters: for e.g. extrinsic incubation period (EIP),
   mosquito reproduction numbers, vector competence, mosquito delays, or
   relative transmission contributions (human-to-human vs vector-borne/zoonotic)
6. Data Extraction Requirement: Must contain extractable mathematical models, transmission models, or quantitative parameter estimates (with values or ranges) for disease modeling. This includes: reproduction numbers, transmission rates, incubation periods, case fatality ratios, model structures, intervention effects, or other modeling parameters. Articles without extractable quantitative parameters or models should be excluded.

## Exclusion Criteria
Exclude if ANY apply:
1. Not about __PATHOGEN_NAME__ (excludes other pathogens)
2. Non-English language
3. Conference proceedings, abstract-only, posters, correspondence, literature reviews, meta-analyses.
4. In-vitro studies only (no human/animal component)
5. Animal studies without transmission parameters (R0, Rt, Re, r, growth rate, mutation rate) or solely animal studies.
6. Case studies/reports with <10 human cases
7. Accidental laboratory outbreaks

# Full-text Article (To Screen)
Title: {title}

Full Text:
{fulltext}

# Screening Instructions

We now assess whether the paper should be included in the systematic review by evaluating it against each and every predefined inclusion and exclusion criterion. First, we will reflect on how we will decide whether a paper should be included or excluded. Then, we will think step by step for each criterion, giving reasons for why they are met or not met.

**Critically evaluate:** Does this paper contain extractable quantitative data, models, or parameters relevant to __PATHOGEN_NAME__ disease transmission and outbreak response? This is essential for inclusion.

We will conclude by outputting (on the very last line) <decision>EXCLUDE</decision> if the paper warrants exclusion, or <decision>INCLUDE</decision> if inclusion is advised or uncertainty persists. We must output either <decision>EXCLUDE</decision> or <decision>INCLUDE</decision>.
