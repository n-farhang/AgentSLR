# Instructions for extracting seroprevalence parameters
These parameters refer to estimations of seroprevalence in the paper. This may also be referred to as antibody prevalence. These parameters will all be expressed in a proportion or percentage of the population. When populating the `value` field, provide a proportion in between 0.0 and 1.0, copying the number of significant figures exactly from the article text. For example, a figure reported as `33%` should be submitted as `0.33`.

When deciding the parameter type, if IgG or IgM is mentioned, then extract with `parameter_type` equal to 'IgG' or 'IgM'. If both antibodies are tested for in the same test, then extract the `parameter_type` as the assay name and populate the `note` value with this information. If not, then please extract `parameter_type` as one of the following assay names:
- IgG: The prevalence of IgG antibodies.
- IgM: The prevalence of IgM antibodies.
- PRNT: PRNT refers to a plaque reduction neutralization test, which is another test for neutralizing antibodies.
- HAI/HI: HAI refers to a hemagglutination inhibition assay, which is another test for neutralizing antibodies in the blood.
- IFA: IFA refers to an immunofluorescence assay, a test to estimate seroprevalence in a population.
- Unspecified: If there is no assay specified, but it is indicated that some people had antibodies, then use this option.

Please extract the numerator and denominator of the central value of the seroprevalence. If only disaggregated numerators and denominators are available, please do not extract any numerator or denominator.

- Often seroprevalence studies use more than one assay. For example, an initial test using ELISA is conducted, but then a neutralisation test is needed to confirm this, for example, due to cross-reactivity. Please extract all seroprevalence estimates in the paper ensuring that you select the relevant assay type each time.
- Typically the sample type will be serum. Some pathogens (e.g. Nipah) seroprevalence, both IgG and IgM, may be based on sample types other than serum. If that is the case, please note the sample type in the `notes` field for that parameter extraction.
- The denominator for the neutralisation test should be as reported (for example, but not exclusively, a subset of the samples tested by ELISA).
- However, please do not extract from papers estimating an assay's sensitivity or specificity.
