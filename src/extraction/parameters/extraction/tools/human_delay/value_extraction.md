## Human delay: parameter value extraction

These parameters all refer to time intervals in the natural history of infection of the host.

### Delay type
The `delay_type` field records the specific type of time interval. It can take one of the following values:
- `generation_time`: The generation time is the time interval between infector exposure to infection and infectee exposure to infection. It may be used in reproduction number estimation, but given the difficulties in its observation, it may be replaced by the serial interval (see below).
- `serial_interval`: The serial interval is is the time interval between infector symptom onset and infectee symptom onset. It is frequently used in reproduction number estimation, as a substitute for the generation time.
- `latent_period`: The latent period is the time interval between exposure to infection and infectiousness. It is sometimes used interchangeably with the incubation period (see below). It may also be referred to as the latency period or the pre-infectious period.
- `incubation_period`: The incubation period is the time interval between exposure to infection and symptom onset. It often coincides with the latent period, but may be shorter (symptom onset before infectiousness, e.g. SARS) or longer (infectiousness before symptom onset, e.g. Covid-19). It may also be referred to as the intrinsic incubation period (in the context of vector-borne diseases) or a subclinical infection.
- `infectious_period`: The infectious period is the time interval during which the host remains infectious. It directly follows the latent period (see above). It may also be referred to as the infective period, the contagious period, the transmission period or the communicability period.
- `time_in_care`: The time in care is the time interval between admission to care and discharge from care or death. Unless there is a delay in receiving care, it directly follows the time from symptom to careseeking (see above). It may vary according to health outcome and is typically highly skewed. It may also be referred to as the length of stay (LOS).

Human delays other than the six listed above may also be reported, for example the time from symptom onset to recovery, symptom onset to death, time from seeking care to admission to care etc. We allow `delay_type` to take on one of these other time interval values:
- `admission__to__death`
- `admission__to__discharge_or_recovery`
- `symptom_onset__to__admission`
- `symptom_onset__to__death`
- `symptom_onset__to__discharge_or_recovery`

In the case that _none_ of the above values apply to a human delay parameter you have found, set `delay_type = 'other'` and record the type of delay in the `delay_type_note` field.

### Value and unit
Use the `value` and `unit` fields to record the parameter estimate (e.g. $x$ hours, days, weeks, or other).
