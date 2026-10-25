# Q2 source-input admission boundary

Status: bounded contract companion for the R7 source-audit candidate. This document does not claim a successful source audit, a package build/install, or Q2 closure.

## Admission boundary

The early source-audit preflight validates exact schema versions and field types, safe source-relative paths, and declared internal consistency before creating its output root or discovering the selected UV. It intentionally permits stale but well-formed resource/source digests and selected node IDs so prepare can recompute them from the selected source. The early gate therefore establishes typed shape and internal bindings; it does not establish that every shape-valid declaration agrees with the current selected source.

## Source-derived fixture semantics

The existing run.py verifier, verify_transitive_test_bindings, derives required fixture kinds from the selected test and helper-call closure. It compares that recomputed kind set with the primary manifest's fixture_paths keys, then checks fixture source files and callback bindings. A shape-valid empty or wrong-kind fixture map can pass the early gate.

In the R7 candidate, run_audit invokes this verifier after primary and supplemental ID collection and before writing proposed manifest files or returning a successful source-audit result. That order is based on source inspection. The independent review did not execute an integrated fresh-collection negative run_audit probe, so rejection against newly generated IDs and the absence of a successful receipt/proposals are not established by runtime evidence. The review's separate direct verifier call rejected an empty map using current manifest-selected IDs and source hashes recomputed in memory. Its separate run_audit probe matched the counterfactual source-object and working-manifest bytes, created the selected-creator output directories, and reached an intercepted UV lookup; it stopped before a UV process or pytest collection.

The dynamically imported verifier raises WaveFailure. The source-audit CLI's catch tuple does not list that runner exception type. Do not claim that this path emits a typed source_preflight_error receipt without a runtime probe.

## Bounded disposition

The R7 review remains NO_GO for the broader claim that every semantic fixture-map mismatch is rejected before UV or output creation. The R2 independent review approves GO_BOUNDED only for the schema/type/path/internal-consistency contract before UV discovery and output creation. It leaves source-derived fixture compatibility to the existing verifier after collection and preserves the prepare-time regeneration behavior.

This is the second finding in the same source-input admission/order class under P40. Stop per-field repair. The bounded residual is that a semantically inconsistent but shape-valid fixture map may incur selected-creator and collection work before the existing verifier rejects it. The minimum capability that could close that cost boundary is a reusable source-semantic precollection resolver that derives selected test IDs and fixture kinds from the exact source without relying on stale collected-ID declarations. The current verifier is coupled to the current collected-ID set, and no such reusable precollection resolver was identified.

The R7 receipt records 410 generated drift controls. The independent review observed 411 loop cases because the harness subtracts one from 411 substitutions even though the loop has no separate setup substitution. Preserve the original receipt; use 411 in later summaries.

## Evidence status and next falsifier

- The R7 helper's Git-blob self-binding remains unchanged.
- The R7 consumer census covers 35 source-audit consumer paths: 22 primary and 13 supplemental.
- A valid selected-UV 0.10.6 probe generated the two-file, 4,360-byte site closure and stopped before pytest. This is a positive creator control, not a semantic-map negative.
- A stale but internally self-consistent input control supports prepare regeneration; it is not a source-semantic compatibility check.
- Fresh-collection semantic rejection remains verification_missing. No build/install or full Q2 package wave was run.

After source freeze, use a real prepare result to obtain the current source-derived primary proposal and IDs. Hold those fresh IDs and source hashes fixed while testing two in-memory counterfactuals: an empty fixture map and a wrong fixture-kind key. Require the exact fixture-kind WaveFailure from verify_transitive_test_bindings, with no stale-source or unrelated failure. Then, if integrated no-proposal behavior must be established, run a bounded negative run_audit through actual fresh pytest collection and verify the semantic failure occurs before proposal files or a successful audit result. Do not substitute manifest-declared IDs for actual collected IDs.

