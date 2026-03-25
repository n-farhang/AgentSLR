# Screening task
For your first task, you will be provided with the full text of a scientific article and a specific type of parameter. We are only extracting parameters that are estimated from or fitted to actual data. For transmission models, if it is only a theoretical model and they have just chosen parameters from other studies/randomly, then please don't extract these.

Scan the provided text and determine whether this article estimates any parameters of the provided type. Use the provided tool to report your decision:
- If the article estimates parameters of the specified type, set `contains_parameter` to `true` and provide a brief annotation with relevant text for the first parameter you find.
- If the article does not estimate parameters of the specified type, set `contains_parameter` to `false` and set `annotations` to `null`.
