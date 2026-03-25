## Reproduction number: parameter value extraction

We are extracting the basic (R0) and effective (Re) reproduction numbers. These are further broken down for vector-borne diseases (e.g. Zika) into the human and mosquito R0 and Re components (where each combines to form the overall R0 or Re, e.g. R0_human * R0_mosquito = R0, although other formulations may be described). These parameters should, as always, be selected as identified by the paper.

> NB: For R0 transmission between other animals, choose Reproduction number (Basic R0/Effective Re), then specify `other` for the `transmission` field. Transmission from non-vector animals to humans does not constitute a reproduction number transmission pathway.

Using the tool provided, extract the numerical value in the `value` field and specify the additional attributes in the corresponding fields.

Use the following instructions to fill fields in the tool call:
- `method` – specify the method used from:
    - Renewal equations / branching process - includes EpiEstim & Wallinga and Teunis for example - typically gives Re. Please see model extraction notes on how to identify renewal equations and branching processes.
    - Growth rate - will typically use Wallinga and Lipsitch to convert an estimated growth rate into reproduction number.
    - Compartmental model - fitted to data and where the parameters are then converted into a reproduction number.
    - Next generation matrix - typically gives R0.
    - Empirical - e.g. they reconstructed the transmission tree from contact tracing data, then counted secondary cases for each case - gives Re.
    - Genomic methods – please name the gene used in the notes.
    - Other - please write in notes.
- `transmission` – specify whether the reproduction number represents transmission from human to human, vector to human, animal to human or animal to animal.

Please extract reproduction numbers as written in the paper.
