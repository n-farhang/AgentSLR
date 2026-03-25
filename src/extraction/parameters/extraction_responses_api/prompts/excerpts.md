# Summary extraction task
For your first task, you will be provided with the full text of a scientific article and a specific type of parameter. We are only extracting parameters that are estimated from or fitted to actual data. For transmission models, if it is only a theoretical model and they have just chosen parameters from other studies/randomly, then please don’t extract these.

Your task is to scan the provided text and determine whether this article estimates any parameters of the provided type. If it does, you must use the provided tool to extract relevant summaries from the text about this parameter. If the article makes no mention of the parameter, simply do not call the tool.

If there are multiple pieces of information about the same parameter, return them as separate list items. You will need to call the tool multiple times if there are multiple separate parameter estimates of the provided type.

In future steps, we will be using the provided summaries to extract structured information about the parameter, including:
1. The estimated value
2. Uncertainty intervals
3. Sample study population

Please make sure your summaries provide all of this information if it is provided. Please be thorough: err on the side of extracting more information rather than less.
