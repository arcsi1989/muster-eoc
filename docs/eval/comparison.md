# Model comparison

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

Not run yet with a live provider. `make eval-compare` writes this page: the golden set (30 cases, each 3 times) against every model of the configured provider listed under `compare` in `config/evals.yaml` (default Claude Haiku, Sonnet and Opus 5.5), with the checks and gates of the [evaluation report](report.md). Per model it gives the pass rate per category, the gate, latency P50/P90 per answer, tokens, and the estimated cost per answer and per run at the prices in `config/llm.yaml`, ranked cheapest passing model first.

It needs `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`, and costs API money: about $8 for the three default models (see the README).
