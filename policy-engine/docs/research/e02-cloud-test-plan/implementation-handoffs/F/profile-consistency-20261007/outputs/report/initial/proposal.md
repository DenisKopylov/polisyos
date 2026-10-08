# Independent discovery/report consumer proposal

Reviewer: `/root/report_review`, read-only; no children and no repository edits.
Source: `2c09571eb9e9efdb91c09b3b4871a49f4c013c1d`, tree `c9dcc58e520cb2c161c85a74e8a2161c32a7276f`; runtime subtree unchanged from reviewed4ee.
G dependency: `2abc17f46a033a7879663486ff9946a95786601f`.

## Existing boundary and minimal repair

`discovery_pipeline._maybe_reconcile` calls the canonical `ReconcileCausalGraph.pure_step` only when a nonnull literature prior or nonempty LLM hint list is supplied. Its broad `except Exception` currently returns the original PAG silently. `_run_unified_discovery` consumes only that graph, then constructs the existing strict `DiscoveryPipelineReport` with warnings and metadata. Both channels are already present in IR; this repair needs no new schema, enum, authority mechanism or PAG completion engine.

Return/carry the unchanged original PAG plus a stable requested-but-not-applied limitation through those report channels. Preserve the declared PAG marks and full graph metadata. A structured `report.metadata['reconciliation']` record can name the request, actual `applied=False`, bounded status/reason and canonical refusal detail; a warning prefix makes the limitation visible in the existing warning surface. For a non-request, emit no invented unsupported-reconciliation warning. Generic exceptions must remain visible as failed/no-op requests, not successful reconciliation. The all-algorithms-failed early return is another report path: either carry requested-but-not-run there or explicitly bound the new property to an actually produced PAG.

No metadata-name classifier, arbitrary node-name missingness inference, graph rewrite or shared gate is part of this report repair.

## Real consumer seam discovered by execution

The registered `UnifiedCausalDiscovery` declares output slot `discovery_pipeline_report` but returns only `report` plus determinism metadata. `components.io._COMMON_OUTPUT_ALIASES` has no alias for this slot. A real configured-PC MethodJob reaches the backend and then fails in output dematerialization with `MethodContractError: missing output for declared slot 'discovery_pipeline_report'`. Thus the initial static assumption that a generic report alias already normalized here was wrong; the complete failed attempt is retained.

Minimal producer-owned companion: return the canonical declared output slot while keeping the supported legacy `report` alias, or use the method's existing custom dematerialization hook. Do not repair this one facade by changing shared dispatcher/monitor semantics or adding a registry/shim. Canonical key plus supported report alias is compatible with existing report readers. The canonical monitor checks normalized slot keys; raw alias sidecars do not become missing/extra slot anomalies.

The maintained generic consumer chain is `MethodRegistry -> MethodDispatcher -> MethodBackend.run -> run_job -> method-result CAS -> fresh FileSystemCAS -> DiscoveryPipelineReport.model_validate`. The persisted raw method result contains the report, and the typed report reader retains warnings/metadata. `JobResult.warnings` currently aggregates only top-level `output['warnings']`; it does not promote nested report warnings. Do not assert that separate surface carries the report limitation unless actually changed and tested.

Literal source census used `git grep` at the pinned2c over all2,700 tracked Python files under `policy-engine/src` (2,914 tracked files of all types). Only the producer/IR declaration spell `DiscoveryPipelineReport`, `discovery_pipeline_report` or `unified_causal_discovery`. This bounds named maintained source consumers; computed/dynamic/external consumers remain unresolved. There is no demonstrated specialized policy/identification gate consumer, and this repair makes no such authority claim.

## Independent controls

- Real numerical discovery can use the actual configured causal-learn PC profile, seed710,160 independent synthetic rows with `Y=2X+Normal(0,0.1)`, no bootstrap and no regime-shift request. This is an economical report/wiring fixture; it is not empirical identification or production authority.
- Run three otherwise equivalent requests: no prior/hint, nonnull empty `LiteratureCausalPrior`, and one valid `LLMStructuralHint`. Genuine requested PAG reconciliation is unsupported even if the prior contributes no edges. Preserve the source consensus PAG byte-level semantic fields and the independent conditional request expectation.
- The requested cases must produce `applied=False` and visible limitation in the actual persisted typed report. The no-request case must not receive that warning. Real method result must survive canonical slot dematerialization; fresh reader must reconstruct the warning and structured metadata.
- Exercise both existing report branches if claiming all produced DiscoveryPipelineReport paths: a normal consensus report and all-algorithms-failed empty-PAG report. Unknown configured algorithm currently provides a real bounded no-result path rather than requiring a fabricated backend.
- A retained-marker probe should remove only runtime diagnostic forwarding/emission while leaving method FQN, graph enums, warning strings and report fields; persisted-report requested-negative tests must fail. Checking static prefix presence alone is decorative.
- Supported static graph repair is reviewed separately by another agent. No-request ordinary discovery must still return a partial PAG rather than being refused merely because the static reconciliation boundary is narrower.

## Measured immutable-base outputs

`baseline-consumer.stdout` / `.stderr`: first isolated export omitted a canonical architecture resource and stopped at import. Harness ERROR; no runtime property verdict. Exact2c architecture resources were then exported, without changing source.

`baseline-consumer.attempt2.stdout` / `.stderr`: actual PC backend executed, but registered MethodJob failed at the declared output slot. This is the real affected consumer companion defect, not a backend skip or authority result.

`baseline-pure-report.stdout` / `.stderr` / `.json`: actual documented `UnifiedCausalDiscovery.pure_step` ran all three requests successfully. All produced the same `X circle-circle Y` PAG; all report warnings were empty and reconciliation metadata absent. This proves the omission at the documented report producer; it does not substitute for the failed MethodJob consumer. The graph output and warning/result omissions are retained completely in JSON.

Importer `--check` passed before verification/navigation. Transferred baseline still has raw archives0 and product closure `not_established`; that navigation does not decide the new profile property.

Await exact immutable new discovery source for non-author review, then only affected real consumer checks. Existing source4ee graph/DiD/worker/catalog/science outcomes are carried only on unchanged blobs/inputs; no whole-head or G formal closure claimed.
