# B108 R14: Core terminal transition and node-facing lifecycle boundary

Status: source candidate for independent review; no G acceptance or runtime closure is implied.

## Property and concrete divergence

The R13 reader reconciled `RUN_OUTPUT_ADDED` labels to the mutable RunManifest. The pinned R13 removal/re-emission falsifier showed that a caller could restore the exact event through generic `RunContext.emit("core", "RUN_OUTPUT_ADDED", ...)`. The reader checked event text and ref equality, not a protected Core transition. R14 makes the engine’s already-existing terminal `RUN_FINALIZED` record carry the exact workflow-finalization ref as an input. The ref must already be in the ordered Core output events and RunManifest, and the consumer additionally recomputes the existing finalization schema, selected workflow, state diff and CAS checks.

## Reuse-first options considered

- **Reuse:** keep Core’s existing run owner snapshot, typed `add_input` / `add_output`, worker receipt admission and terminal `RUN_FINALIZED`. Use its protected terminal writer for the one workflow transition link.
- **Extend:** add an optional typed workflow-finalization input to `RunContext.finalize`; histories without it remain not established for workflow-finalization currentness. Reject arbitrary generic Core-phase events and all `RUN_*` labels. At the orchestration boundary, nodes receive a restricted RunContext-compatible view with a detached RunManifest and no raw trace, output-registration or terminal-writer methods. The existing WorkerRunView staged receipt route remains the only node-worker route for typed worker operations.
- **Consolidate:** avoid a parallel signing service, owner-event ledger, self-asserted event owner field, or per-event allowlist. The owner’s terminal transition and the existing selected workflow-finalization receipt form the checked join.
- **Build new:** not justified; there is no need for new custody or external authority semantics.

## Migration, compatibility and limits

The `finalize(..., workflow_finalization_ref=...)` argument is optional for existing callers. Sync and async workflow executors supply it after registering the same selected-profile CAS ref. Legacy/finalized traces and crash-recovered finalizations without the input remain readable as run history but cannot establish the new workflow-finalization currentness property. Public exports are unchanged. The restriction is an in-process supported-node API boundary, not a Python sandbox or protection against arbitrary process/filesystem writes, reflection, monkeypatching, or compromised runtime code. No legal, issuer, calibration, production-currentness or signature claim is introduced.

## Acceptance falsifiers

1. In a real `WorkflowExecutor` chain, a node tries generic Core `emit`, accesses `.trace`, calls `.add_output`, and mutates its RunManifest copy while all other markers remain. Those attempts must not create an owner output; the genuine sync and async finalization still resolves current.
2. Remove only the terminal record’s workflow-finalization input while preserving the RUN_OUTPUT_ADDED row, manifest ref and CAS bytes: currentness must fail. Re-add an identical label through generic emit: it must still fail.
3. Run the real `BuildDecisionPacketNode.execute` on the current owner-linked report, then verify the persisted `scientist.decision_packet` ref and read the same bytes from CAS; the packet’s scoped governance projection is current. Keep the existing stale-input/no-put case.
4. Generic non-Core trace events, typed Core `add_output`, and the existing verified WorkerRunView receipt path continue to work.

The actual node path still must not be described as a sandbox. All source-only review and remaining verification are separate from this candidate decision.


## Whole-map currentness after downstream artifact production

The end-to-end producer/consumer witness uses the actual `RunGovernanceNode` and `BuildDecisionPacketNode` invocations in a `WorkflowExecutor` run. The governance report is current when the packet node resolves its exact engine-recorded input snapshot. The packet node then writes its `decision_packet_ref` and related outputs to `artifacts_index`; finalization also adds engine-owned report and research-DAG entries. At the completed workflow state, governance currentness is `stale` with `producer_source_projection_changed`. The packet written by the real node is persisted in CAS and its embedded governance projection is current for the input it consumed. This is the existing full-map source-basis contract exercised at the real consumer.

Do not infer that an owned descendant artifact is irrelevant to source currentness merely because its producer is engine-linked, its write is non-overwriting, or its ref traces to an earlier input. Those facts establish custody and lineage, not that the artifact is a derived projection rather than newly acquired source evidence. The falsifier preserves report and pass markers but injects an unowned artifact ref; the resolver remains stale. A source-map change after the report input is likewise stale, and re-running the packet against the completed state fails without writing a new packet.

The full-completed-state behavior is a narrow G choice if E02 requires the report to remain current after known descendant writes. Three options are available:

1. **Retain the current whole-map basis.** Any map delta invalidates the report for authority-grade currentness. This is the present fail-closed behavior and requires no migration. It can leave a completed workflow report stale after a consumer writes to a map the producer declared as read.
2. **Add typed mediated reads.** A versioned producer contract would record the exact effective map projection actually supplied to each pass, and currentness would recompute that projection at the consumer. This changes the producer/validator interface and requires migration for existing reports and any pass that receives broader state than its declared fields. The present pass context exposes whole maps; there is no complete read registry to reuse, so a declared subset alone would remain consumer-asserted.
3. **Add a typed derived-artifact relation.** A versioned relation could prove that a descendant artifact is a deterministic projection of an already-admitted basis, while independently acquired evidence remains source-bearing. The relation would need a producer-owned schema, recomputation rule and consumer bridge. Ownership, dependency order, matching hashes, or a run ID by themselves do not supply that semantic distinction. Existing artifacts do not carry this relation.

R14 keeps option 1 while G adjudicates whether either new contract is required. If G chooses an extension, it should name the authoritative producer for the relation/read witness, schema and compatibility path, actual consumers that recompute it, and a removal/mutation falsifier. Until then, whole-map currentness after descendant writes remains `not_established`/stale as reported by the source-bound resolver; this is not a claim that the packet itself is absent or that its candidate contents are invalid. No score, legal, issuer, permission, production-currentness or publication authority is inferred from the report projection.
