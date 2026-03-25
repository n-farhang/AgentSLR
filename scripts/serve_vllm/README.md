# vLLM Serving Notes

These local serving helpers are examples for models that expose an OpenAI-compatible API to AgentSLR.

For the paper results, the serve configurations in this folder were based on the vLLM Recipes documentation:

- https://docs.vllm.ai/projects/recipes/en/latest/index.html

Representative recipe-style commands used for paper runs:

```bash
vllm serve deepseek-ai/DeepSeek-V3.2 \
  --tensor-parallel-size 8 \
  --api-key "6767" \
  --tokenizer-mode deepseek_v32 \
  --tool-call-parser deepseek_v32 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v3

vllm serve moonshotai/Kimi-K2.5 \
  --tensor-parallel-size 8 \
  --api-key "6767" \
  --async-scheduling \
  --mm-encoder-tp-mode data \
  --tool-call-parser kimi_k2 \
  --enable-auto-tool-choice \
  --reasoning-parser kimi_k2 \
  --trust-remote-code

vllm serve zai-org/GLM-4.7 \
  --tensor-parallel-size 8 \
  --api-key "6767" \
  --tool-call-parser glm47 \
  --reasoning-parser glm45 \
  --enable-auto-tool-choice
```

The default helper script in [`serve_client.sh`](serve_client.sh) uses the same local `gpt-oss` defaults as the main README, and you can override them with optional args when needed:

```bash
scripts/serve_vllm/serve_client.sh
scripts/pipeline/run_all_stages.sh \
  lassa data/agentslr openai/gpt-oss-120b gpt_oss_120b \
  --base-url http://localhost:6767/v1 \
  --api-key 6767
```
