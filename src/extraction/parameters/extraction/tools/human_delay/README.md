# Human delay Parameter Extractor

From the [PERG wiki](https://github.com/mrc-ide/priority-pathogens/wiki/Parameter-Data): human delays "all refer to time intervals in the natural history of infection of the host."

The `parameter_class` `Human delay` has 9 possible `parameter_type`:
1. Human delay - admission to care>death
2. Human delay - admission to care>discharge/recovery
3. Human delay - generation time
4. Human delay - incubation period
5. Human delay - other human delay (go to section)
6. Human delay - symptom onset>admission to care
7. Human delay - symptom onset>death
8. Human delay - symptom onset>discharge/recovery
9. Human delay - time in care (length of stay)

## Remapping
PERG's annotation process records the names of `parameter_type`s with characters like `-` and `/` that can confuse language models and file systems. For robustness, we remap these values accordingly in our system:

| PERG value | Our value |
|---|---|
| `Human delay - admission to care>death` | `admission__to__death` |
| `Human delay - admission to care>discharge/recovery` | `admission__to__discharge_or_recovery` |
| `Human delay - generation time` | `generation_time` |
| `Human delay - incubation period` | `incubation_period` |
| `Human delay - other human delay (go to section)` | `other` |
| `Human delay - symptom onset>admission to care` | `onset__to__admission` |
| `Human delay - symptom onset>death` | `onset__to__death` |
| `Human delay - symptom onset>discharge/recovery` | `onset__to__discharge_or_recovery` |
| `Human delay - time in care (length of stay)` | `time_in_care` |


## Parameter types

### `admission__to__death`
