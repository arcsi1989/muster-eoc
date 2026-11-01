# Model comparison

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

Written by `make eval-compare`: the golden set against each model of the configured provider listed in `config/evals.yaml`, with the checks and gates of the [evaluation report](report.md); cost estimated at the prices in `config/llm.yaml`. Ranked: models that pass the gate, cheapest per answer first, then the others by pass rate.

- Cheapest model that passes the gate: **claude-sonnet-5-5** ($0.01644 per answer, $1.4793 per run)
- Provider anthropic, 30 cases, each 3 time(s) per model
- Prompts: copilot copilot-v2, sitrep sitrep-v2
- Git commit: 6f10766+dirty

## Pass rate per category

| Rank | Model | Gate | Grounding and citations | Correct refusal | Data classification | Prompt injection | Drafting | All |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | claude-sonnet-5-5 | passed | 100% | 100% | 100% | 100% | 100% | 100% |
| 2 | claude-haiku-5-5 | FAILED | 83% | 100% | 100% | 100% | 100% | 93% |
| 3 | claude-opus-5-5 | FAILED | 78% | 100% | 100% | 100% | 100% | 91% |

## Latency, tokens and cost

Latency per answer, retries included; tokens and cost per run (every answer of every case).

| Rank | Model | Latency P50 (ms) | Latency P90 (ms) | Tokens in | Tokens out | Cost per answer | Cost per run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | claude-sonnet-5-5 | 3911 | 8293 | 522537 | 43422 | $0.01644 | $1.4793 |
| 2 | claude-haiku-5-5 | 3170 | 5898 | 614104 | 61450 | $0.00102 | $0.0921 |
| 3 | claude-opus-5-5 | 5547 | 12396 | 528784 | 49649 | $0.03453 | $3.1081 |

## Each model's results

- claude-sonnet-5-5: [report](comparison/claude-sonnet-5-5/report.md), [results](comparison/claude-sonnet-5-5/results.json)
- claude-haiku-5-5: [report](comparison/claude-haiku-5-5/report.md), [results](comparison/claude-haiku-5-5/results.json)
- claude-opus-5-5: [report](comparison/claude-opus-5-5/report.md), [results](comparison/claude-opus-5-5/results.json)
