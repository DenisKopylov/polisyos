# Proof Trace Composability

Related references: [Scientist Causal Validity](causal-validity.md), [Run causal analysis](../../how-to/run-causal-analysis.md). Historical agenda evidence path: `docs/plans/archive/CAUSAL_ENGINE_RESEARCH_AGENDA.md`.

Owner: `@scientist-owners`  
Backup owner: `@platform-owners`  
Source of truth: `src/polisyos/ir/analytics/proof_composability.py`, `src/polisyos/foundry/methods/catalog/causal/proof_trace_composability.py`, `src/polisyos/ir/analytics/causal.py`, `src/polisyos/ir/analytics/evidence_bundle.py`, `tests/unit/ir/analytics/test_proof_composability_contract.py`, and `tests/unit/foundry/methods/catalog/causal/test_proof_trace_composability.py`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Scope: conservative replay contract for reusing an existing do-calculus / ID proof trace after fragment composition.

## Theorem Surface

PolicyOS treats proof replay across fragment boundaries as a conservative replay problem, not as unconditional reuse.

The implementation contract is the following projection-preserving replay theorem:

1. A proof trace may be marked `reusable` only when every replayed step keeps the same local graphical witness on the composed graph.
2. If no witness is known to be broken but one or more witnesses must be checked again on the composed graph, the trace is `revalidate`.
3. If any critical witness breaks, blind replay is unsound and the trace is `rederive`.
4. If the current kernel cannot classify the replay safely, the status is `unknown`.

This theorem is intentionally sufficient, not complete. It prevents the system from claiming identifiability purely because a fragment-local proof existed before composition.

## Artifact Contract

The composability surface is split into three layers:

- `EvidenceBundle.proof_steps`: the reusable trace surface. `ProofStep` now carries `step_id`, `theorem_family`, witness links, dependency links, and `local_status`.
- `ProofWitnessIndex`: the witness layer. Each witness records the obligation kind, support variables, mutilation/projection summary, and optional ancestry/district signatures.
- `ProofComposabilityCertificate`: the replay verdict. It records `reusable`, `revalidate`, `rederive`, or `unknown`, together with preserved/broken witness ids and graph-delta context.

`ProofBundle` integrates this surface through:

- `proof_trace_ref`
- `composability_status`
- `composability_certificate_ref`
- `witness_index_ref`
- `proof_support_projection_hash`
- `invalidated_by_graph_hashes`

On the primary inference path, `CausalEngine.audit(...)` now persists the
causal `EvidenceBundle` as the `proof_trace_ref` artifact and persists a
`ProofWitnessIndex` derived from the stored proof steps whenever a graph-backed
identification result is available. When the audited proof also has a graph,
witness index, and artifact store, the audit path immediately runs
`check_proof_trace_composability(...)`, persists a
`ProofComposabilityCertificate`, and writes the resulting non-unknown replay
status back to the `ProofBundle`.

## Operational Policy

Use the statuses as follows:

- `reusable`: replay the stored proof trace and reuse the estimand AST directly.
- `revalidate`: keep the trace structure, but rerun the recorded witness checks before trusting the proof.
- `rederive`: discard blind replay and run the identification algorithm on the composed graph.
- `unknown`: stay at the research boundary; do not promote replay to a trusted claim.

The runtime checker is `check_proof_trace_composability(...)`. It consumes a
`ProofWitnessIndex`, recomputes each witness `projection_hash`, ancestor
signature, and district signature on the composed graph, and emits a
`ProofComposabilityCertificate`. It only returns `reusable` when all recorded
witnesses are preserved. If a witness hash changes but an `m_separation`
obligation can still be checked successfully, the result is downgraded to
`revalidate`. If a critical ancestor/district/hedge witness breaks, the result
is `rederive`.

The cache key must include:

- query string or query hash
- theorem family
- proof trace hash
- witness projection hashes
- interface signature

Use `proof_composability_cache_key(...)` for this normalized key.

## Validation

```bash
uv run pytest tests/unit/ir/analytics/test_evidence_bundle.py tests/unit/ir/analytics/test_proof_composability_contract.py tests/unit/foundry/methods/catalog/causal/test_proof_trace_composability.py -q
```
