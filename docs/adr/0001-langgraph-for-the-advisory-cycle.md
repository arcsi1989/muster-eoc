# LangGraph runs the advisory cycle

> Take-home challenge for the role of AI Solution Engineer (Zug). Not an official AECOM document. SGW, Bayport County and all data are fictional.

Only one of the eight advisory-cycle steps calls an LLM, and the package and its decisions are DB
tables anyway, so a plain Python pipeline with approvals as ordinary POSTs would have been simpler.
We use a LangGraph `StateGraph` anyway: its human-approval interrupt and checkpointing make the
"prepare, never act" flow explicit and resumable, and it shows a recognizable agent framework.

## Consequences

- The approval pause spans many HTTP requests (and possibly an advance to the next advisory), so
  the graph needs a persistent checkpointer, and `make demo-reset` must clear it with the DB.
- The graph state and the DB tables hold overlapping data; the DB stays the record that the API
  and audit log read.
