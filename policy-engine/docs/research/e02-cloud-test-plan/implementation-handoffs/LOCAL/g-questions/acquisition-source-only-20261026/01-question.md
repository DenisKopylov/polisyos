# B09: source-only admitted occurrence versus semantic reissue

## Decision requested from G

Choose the versioned route/history contract for a genuine newly admitted source occurrence whose exact selected source profile and typed candidate-refresh rule are valid, but whose normalized canonical rows and applicable rule produce the same WMR-relevant semantic basis as the prior admitted occurrence.

Recommendation: retain the new source occurrence and its custody/provenance in the append-only route history, while retaining the prior WMR/N5/candidate occurrence. Represent this as a distinct, typed source-only/no-semantic-change result. It is not `quarantined_no_growth`: native membership did grow for the new epoch. It is not `reentry_completed`: no new N5 evaluation occurred. The public contract must keep source status, semantic evaluation status, and candidate authority distinct; it must not imply production currentness, issuer authority, calibrated evidence, or publication authority.

The current candidate tree does not have this outcome. Do not implement this recommendation as a string or reinterpret either existing outcome. G should select the status and exact versioned receipt/DTO migration before that contract is authored.

## Why the current chain cannot honestly express this case

The concrete served chain is request/authority → ordinary POST `/execute` → action service → selected WDI execution port → semantic-epoch admission → persisted world-growth owner receipt → route-loop terminal receipt → fresh GET route/history projection.

- `AcquisitionWorldGrowthRoute` selects an epoch, while `AcquisitionWorldGrowthBridge._paths` keeps one overlay per tenant/cell. `admitted_membership_delta` measures the selected epoch. A first observation in another epoch has a positive delta and is a real new admitted source occurrence.
- `AcquisitionWorldGrowthNoGrowthReceipt` is deliberately exact: it requires the same before/after membership snapshot and literal delta 0. It cannot describe a newly admitted epoch and must not be weakened.
- The execution result and route machinery have only `quarantined_no_growth` and `world_committed`; a world commit always enters N5 reentry. Terminal route receipts and durable action-head resolution accept only `quarantined_no_growth` and `reentry_completed`.
- The fresh GET DTO `RunCandidateSimulationAcquisitionHistoryEntry` accepts only `reentry_completed` and `quarantined_no_growth`. Quarantine forbids a newly selected source ref. Reentry requires a reentry receipt and new candidate source, while the current GET branch treats every non-quarantine terminal as reentry.

Therefore reusing no-growth would erase the positive source admission and violate its zero-delta invariant; forcing reentry would repeat expensive work for source/serialization identity alone; and dropping the source event would lose the requested occurrence/task binding.

## Alternatives and consequences

1. **Distinct source-only outcome (recommended).** Persist and join the newly admitted source/profile/epoch occurrence and semantic-basis comparison. Preserve prior WMR/N5/candidate pointers when the exact candidate-refresh semantic basis is unchanged. Version the owner result, route terminal receipt, durable action-outcome validator, history DTO, and GET projection. Existing outcomes retain their meaning.
2. **Every admitted epoch forces WMR/N5 reentry.** Keeps a two-outcome state machine, but treats epoch/UUID/transport/serialization churn as semantic change and causes repeated candidate work. This conflicts with the criterion's explicit new-name/UUID/time-only negative unless G defines the epoch itself as a semantic input.
3. **Retain only a no-growth/quarantined history item or discard the new occurrence.** The current no-growth type cannot validate the positive selected-epoch delta; discarding it loses immutable source custody and task binding. No acceptable implementation is established for this option.

The choice is a narrow additive contract/status decision, not authority to infer a law, issuer, currentness, or a new semantic mapping. Rule changes or canonical row/effect changes still trigger same-candidate N5 reissue. Source time remains `not_established` unless an actual source supplies it.

## Required distinguishing checks after G selects the contract

- Actual current POST/owner path: same candidate, same bound profile and rule, selected epoch e+1, changed canonical value consumed by WMR/N5; new N5 input and history point to the new source occurrence; prior source and WMR remain readable.
- Actual current POST/owner path: selected epoch e+2 returns the same normalized rows with different raw JSON serialization/transport occurrence. The raw source occurrence is persisted and fresh GET can bind it, but the semantic basis matches; no new WMR/N5/candidate occurrence is produced.
- ID/time-only request replay over the already admitted same epoch reuses existing owner evidence and performs no second source fetch, as today.
- Remove the source-only terminal-to-history join while preserving markers and CAS bytes: fresh GET must lose the new occurrence or return a typed limitation, never silently present it as no-growth/reentry.
- Change value, applicable rule mapping, selected profile, or wrong sibling-profile ref separately; actual producer/consumer must reissue for semantic changes and refuse unbound/malformed/wrong-profile inputs. A declaration or test-only oracle mutation is not a positive.
- Preserve `publication_authority=false`, `currentness_status=not_established`, and existing authority refusal behavior through the new branch.

## Engineering scope and migration

Minimum source surfaces if option 1 is chosen: `runtime/quality/acquisition_world_growth.py` (semantic-basis owner and distinct receipt only if existing producer API can supply it); `runtime/http/services/acquisition_surface_execution.py`; `runtime/http/services/acquisition_action_service.py`; `runtime/quality/acquisition_route_loop.py`; `core/contracts/runtime.py`; `runtime/http/services/control/run_lifecycle.py`; `runtime/http/routes/runs.py`; their mirrored contract/owner/route/history tests; package README and release fragment. Inspect actual source before choosing exact names or schema numbers. Existing serialized artifacts remain readable; new history is append-only. A rollback may stop emitting the new outcome but cannot reinterpret or erase already persisted source occurrences.

No production source was read. The controlled fixture can prove wiring/semantics only. Authentic source time, issuer/custody/currentness, and production population remain separate external facts.

## Pattern pass

P04/P05/P07/P08/P10/P12/P14 and P29/P32/P37/P38/P40 apply. Existing risks: two-valued outcome collapses a newly admitted source occurrence into either a false zero-delta receipt or mandatory semantic reentry; UUID/time-only synthetic oracle is not a producer-to-GET test. Target: typed source occurrence + typed semantic decision, actual producer→CAS→bridge→N5 or retained-N5→fresh GET, with independent removal and wrong-profile controls. Current gaps: `semantic_test_missing` for a second admitted source epoch; the proposed typed source-only route is `absent/unallocated`. Research prose is not an admitted chain; do not report closure.

## Evidence sources

This packet is a proposal only: `code_acceptance=false`, `closure_ids=[]`, no global freeze.

- Original B09 criterion: `closure-decisions/coverage.json` B09; source B_r19 lines 301–312, source digest `62b0ba80257fe40aee4e48fda73caf00a617fa55d29c54693185e6996b0ce64c`.
- Historical source criterion: `docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/CYC-03.md`, B09 lines 49–61; same candidate re-evaluates for meaningful changed basis, UUID/time alone must not create repeated investigation, and source/task occurrence remains bound.
- Earlier route distribution note: `implementation-handoffs/L02/parallel-20261008-l02/prepared/l02_reissue.json` B09; states that source/profile-to-WMR rule and same-candidate positive plus ID/time negative were not ratified/tested there.
- Exact current source paths and byte pins are in `inputs.json`. The source pins refer to the current composed worktree at candidate HEAD `6ad021abaaec967ce48122e5f94985112dc19e59`; the files are a mix of committed and known working-tree bytes. This is not a source freeze or acceptance receipt.


## Existing semantic-epoch no-change is not a substitute

The current owner has an epoch-level `no_change` production receipt: semantic-epoch manifests compare their declared semantic fields and can record a no-change result while binding the prepared/admitted evidence. This is not proof that every effective WMR/N5 input is unchanged, is not a route terminal, and does not suppress the current generation-cycle reentry from appending a cycle. Reusing it as a source-only classifier would substitute epoch-semantic equality for the exact selected WMR/N5 input closure. The versioned source-only choice must bind to actual consumer-effective inputs (or keep the case unresolved); do not infer equivalence from the epoch receipt.

The exact `semantic_epoch.py` and `generation_cycle.py` committed blobs and current worktree bytes are separately pinned in `inputs.json`. The exact five fixture-path committed hashes, working-tree preimages, candidate postimages, and status are in the referenced fixture manifest. This separates clean committed input from existing dirty candidate source.
