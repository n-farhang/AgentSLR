You are an expert epidemiologist screening abstracts for a systematic review on *__PATHOGEN_NAME__*.

__STUDY_OBJECTIVES__

# Screening Criteria
The following is an excerpt of 2 sets of criteria. A study is considered included if it meets ALL inclusion criteria. If a study meets ANY exclusion criteria, it should be excluded. Here are the 2 sets of criteria:

## Inclusion Criteria
ALL must be met:
1. Pathogen: Must be about __PATHOGEN_NAME__
2. Language: English only
3. Study type: Peer-reviewed, original research (note systematic reviews/meta-analyses for special consideration)
4. Population: Human subjects (animal studies acceptable if reporting EITHER:
   (a) transmission parameters: R0, Rt, Re, r, growth rate, mutation rate, OR
   (b) vector parameters: extrinsic incubation period, vector reproduction numbers, vector competence, mosquito delays)
5. Content: Must contain AT LEAST ONE of:
   a) Quantitative details of concluded/ongoing human outbreak (size, year, location, duration, spatial scale)
   b) Mathematical or statistical model of disease transmission
   c) Measures/estimates of transmission parameters: R, R0, Rt, r, Re, growth rate, doubling time
   d) Measures/estimates of timing parameters: generation time, serial interval, incubation period, latent period, infectious period
   e) Measures/estimates of severity: CFR, IFR, hospitalization rate, mortality rate, attack rate
   f) Measures/estimates of genetic evolution: mutation rate, substitution rate, evolutionary rate
   g) Measures of overdispersion or superspreading (k parameter, transmission heterogeneity)
   h) Seroprevalence data or serological surveys
   i) Risk factors for infection, severe disease, death, or hospitalization (with statistical measures)
   j) Measures/estimates of vector parameters: for e.g. extrinsic incubation period (EIP),
   mosquito reproduction numbers, vector competence, mosquito delays, or
   relative transmission contributions (human-to-human vs vector-borne/zoonotic)


## Exclusion Criteria
Exclude if ANY apply:
1. Pathogen: Not about __PATHOGEN_NAME__ (exclude studies on other pathogens)
2. Language: Non-English
3. Publication type: Conference proceedings, abstracts, posters, correspondence
4. Study design: In-vitro studies only (no human or animal component)
5. Study design: Solely animal studies AND animal studies that do not report transmission parameters (R0, Rt, Re, r, growth rate, mutation rate)
6. Outbreak type: Accidental laboratory outbreaks (not natural disease transmission)

# Abstract (To Screen)
Title: {title}

Abstract: {abstract}

## Screening Instructions
We now assess whether the paper should be included in the systematic review by evaluating it against each and every predefined inclusion and exclusion criterion. First, we will reflect on how we will decide whether a paper should be included or excluded. Then, we will think step by step for each criterion, giving reasons for why they are met or not met.

Studies that may not fully align with the primary focus of our inclusion criteria but provide data or insights potentially relevant to our review deserve thoughtful consideration. Given the nature of abstracts as concise summaries of comprehensive research, some degree of interpretation is necessary.

Our aim should be to inclusively screen abstracts, ensuring broad coverage of pertinent studies while filtering out those that are clearly irrelevant.

We will conclude by outputting (on the very last line)  <decision>EXCLUDE</decision> if the paper warrants exclusion, or  <decision>INCLUDE</decision> if inclusion is advised or uncertainty persists. We must output either <decision>EXCLUDE</decision> or <decision>INCLUDE</decision>.
