# Provider failure diagnostics — 2026-09-09

The completed predeclared sweeps stopped at concurrency 1: DeepSeek returned HTTP
429 on nine of twelve attempts; MiniMax returned malformed output on two of twelve.
The status alone does not identify whether a 429 originates in the proxy, an
upstream node or account policy. No concurrency knee is established.

The separate v2 declarations bind exactly one retry of each model's first failed
ordinal from its earliest completed level, using its original input, prompt hash,
model and configuration. This selection is explicitly outcome-informed diagnostic
work. Neither retry enters the frozen pilot or throughput denominator. The initial
DeepSeek v1 diagnostic declaration was never executed; v2 supersedes it and adds
safe structural observations of HTTP-success envelopes. Its earlier bytes remain.

The ordinary SDK's existing response hook exposes only a closed vocabulary of
provider error codes, numeric Retry-After, and success-envelope types, lengths and
JSON syntax. No provider error body or raw malformed content is retained. Provider
codes remain assertions; origin remains `not_established`.

Pattern pass: P27 reuses the existing SDK/extractor; P29 runs the actual diagnostic
redaction and removal; P32 does not turn an HTTP code into cause evidence; P35 does
not add diagnostic retries to an experimental denominator. The strict typed
extraction contract remains unchanged. This diagnostic grants no authority.

The structural red gate fails because the helper is absent; after implementation
both tests pass. Removing raw-content suppression while preserving diagnostic
markers fails the synthetic echo assertion. The earlier closed-code whitelist
removal likewise fails when an undeclared value can pass. Complete outputs are
the adjacent `error-diagnostic-*.json` captures; no generated view of source data
is retained.
