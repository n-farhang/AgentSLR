# Uncertainty extraction task
For your next task, you will be provided with excerpts from a scientific article and an estimated parameter that has been extracted from that article. Your task is to scan the provided text and extract relevant uncertainty information for the given parameter. You will use the provided tool, which sets the schema you should follow when returning uncertainty information.

Parameter uncertainty represents the confidence in the central estimate, and decreases with more data, unlike variation which increases with additional data.

- Do not extract uncertainty unless a primary central parameter is also extracted. Uncertainty must correspond with the primary central parameter. If a primary central parameter is not available, i.e. only the “parameter range of central estimates” is available (e.g. Rt 1.5-2.3), do not extract any uncertainty.
- Single-type uncertainty is if only a standard deviation or coefficient of variation, for example, is reported rather than a range of paired values.
- Paired uncertainty is the option you will be using _most of the time_ -- this includes confidence and credible intervals.

The following details the selections you should make when using the tool call:
- `value_type` – mean, median, shape, etc. Please note that it may be the case that multiple measures of central tendency or variability are provided, especially when the entire distribution of a parameter is presented. To avoid extracting multiple measures of centrality and variability for the same parameter and to avoid bias, only one parameter value type can be extracted. Central parameter types are prioritised based on the available variability/uncertainty types in the following way:
    - When SD/variance/CIs are available: extract `mean`.
    - Else when only IQR/CrIs are available: extract `median`.
    - If `mode` is presented, this should be prioritised after the `mean` or `median`.
    - If Weibull distribution parameters are presented: prioritise extraction of the `shape` and `scale` parameters rather than mean/CIs or median/CrIs. We can get mean/CIs from shape/scale analytically but can only get shape/scale from mean/CIs numerically.
- `statistical_approach` – if the central parameter estimates are summarised directly from empirical data, extract `observed_sample_statistic`. If the central parameter is estimated using a transmission or other kind of model, extract `estimated_model_parameter` (e.g. an adjusted seroprevalence would be an estimated parameter, not an observed sample statistic). Due to limited data sources, the Oropouche systematic review was extended to include `case_study` data.
