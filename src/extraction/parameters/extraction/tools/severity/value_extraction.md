## Severity: parameter value extraction

- `parameter_type` - we extract case fatality ratios (CFR), infection fatality ratios (IFR), and the proportion of cases that are symptomatic and asymptomatic.
  - Case fatality ratio (`CFR`) - the proportion of cases who end up dying of the disease. Note this depends on the case definition used, as the denominator is people identified as "cases". All CFRs should be extracted, even when a subset of the population is selected (e.g. severe cases); make sure to describe the population denominator in the context and notes.
  - Infection fatality ratio (`IFR`) - the proportion of infections who end up dying of the disease (harder to calculate but less context dependent).
  - Symptomatic proportion of infections - the proportion of total infections that are symptomatic.
  - Asymptomatic proportion of infections - the proportion of total infections that are asymptomatic.
- Parameter value - we don't do any calculation ourselves i.e. if a paper quotes number of deaths and number of cases, but not a CFR, we don't calculate the CFR.
- Ratio/prevalence values – please extract the `numerator` and `denominator` that generate the severity ratio. In line with the rule of 3, only extract the numerator and denominator of the central CFR value, even if disaggregated numerators and denominators are available. If there is no central value, do not extract any numerator or denominator. If the numerator and denominator are presented, but the percentage severity is not, extract the numerator, denominator and context, but leave the central value blank.
- `method` - we extract information about the method used to calculate CFR (or IFR), mainly whether it is:
  - a "`naive`" method, i.e. percentage mortality which computes total deaths divided by total cases (or infections); this is wrong because there may be many cases or infections who do not have final status information, so the naive estimate is typically an underestimate of true CFR (or IFR).
  - an `adjusted` method, which somehow accounts for infections or cases with unknown final status (e.g. calculates deaths / (deaths + recoveries) or does something more fancy).
  - an `unknown` method.
- `value_type`: mean, median, shape, etc. Please note that it may be the case that multiple measures of central tendency are provided, especially when the entire distribution of a parameter is presented. To avoid extracting multiple measures of centrality for the same parameter and to avoid bias, only one parameter `value_type` can be extracted. Central parameter types are prioritised based on the available uncertainty types in the following way:
- When SD/variance/CIs are available: extract `mean`.
- Else when only IQR/CrIs are available: extract `median`.
- If `mode` is presented, this should be prioritised _after_ the `mean` or `median`.
- If Weibull distribution parameters are presented: prioritise extraction of the `shape` rather than mean/CIs or median/CrIs. We can get mean/CIs from shape/scale analytically but can only get shape/scale from mean/CIs numerically.
- `statistical_approach` – if the central parameter estimates are summarised directly from empirical data, select `observed_sample_statistic`. If the central parameter is estimated using a transmission model, select `estimated_model_parameter`. Due to limited data sources, the Oropouche systematic review _only_ was extended to include `case_study` data.
