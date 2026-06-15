# Provider And Model Quality Drift Ledger

Owner: `@runtime-owners`
Source of truth: `tools/ops_runners/runtime/provider_quality_ledger.py`, `tools/ops_runners/runtime/canary_evidence.py`, and `tests/unit/runtime/quality/**`

PolicyOS records provider/model quality drift in
`policyos.provider_model_quality_ledger.v1` ledgers. The runtime quality bundle
ref is `provider_model_quality_ledger_ref`.

The ledger is built from deterministic simulated lanes and optional quarantined live
lanes. CI can populate the simulated lane metrics without network calls;
live-provider evidence can be attached later when a quarantined provider run is
available.

Each ledger entry is keyed by provider, model id, and model fingerprint. It does
not use raw credentials as keys and retained evidence samples are sanitized.
Hidden scenario answers and sentinel strings must not be written to public
exports, dashboard fixtures, or reusable memory.

Tracked metrics:

- schema failure rate and schema healing count
- JSON validity and tool-call validity
- grounding failure rate and citation faithfulness failure rate
- model disagreement rate
- latency, cost, and context pressure
- provider error rate
- selected-variant quality

Default production model choices must have recent evidence. Drift outcomes are:

- `approve`: the default model has fresh evidence within thresholds
- `require_review`: quality is usable but drift or pressure needs human review
- `demote`: the provider/model has crossed demotion thresholds
- `block_production_approval`: evidence is missing or stale for a production
  default

Build a ledger from canary evidence bundles:

```bash
uv run python -m tools.ops_runners.runtime.provider_quality_ledger \
  --input-root .polisyos/canary_evidence \
  --output .polisyos/provider_quality/provider_model_quality_ledger.json \
  --default-production-model simulated:policyos-sim-v1:fixture-fp:policy_drafting
```

The output contains `provider_model_quality_ledger_ref`, a deterministic
`sha256:` fingerprint over the sanitized ledger payload.

Controlled evidence-bound comparison:

```bash
uv run python -m tools.ops_runners.runtime.provider_quality_ledger \
  --input-root .polisyos/canary_evidence \
  --output .polisyos/provider_quality/provider_model_quality_ledger.json \
  --controlled-grounding-comparison-output .polisyos/provider_quality/controlled_grounding_comparison.json \
  --candidate-model gonka_proxy:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8 \
  --candidate-model gonka_proxy:moonshotai/Kimi-K2.6:moonshotai/Kimi-K2.6 \
  --default-controlled-model gonka_proxy:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:Qwen/Qwen3-235B-A22B-Instruct-2507-FP8:policy_drafting
```

The controlled comparison uses one frozen data ref, norm ref, method ref, and
claim ref. A default model is not promotable from this comparison until every
candidate has at least three bounded samples over the same evidence refs.
