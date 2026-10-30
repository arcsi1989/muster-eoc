"""Agent tracing (CR-03 C3): a span for every advisory-cycle node and every grounded generation.
`instrument` opens spans through the OpenTelemetry API; `store` decides where they go (the
trace_span table, and an OTLP endpoint when one is set) and answers the run trace."""
