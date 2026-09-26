# R13-D — N5/N8 runtime-store continuity

Status: bounded repair on `codex/e02-r2`; R13 as a whole remains open.

## Property and production caller

A persisted N5 result and its N8 replay use the exact store supplied by the
runtime. The recursive parent checks that a result store exists before it runs
N5. A selected `ArtifactRef` must resolve its selected typed manifest view; a
generic view of identical bytes cannot silently substitute. The production
composition is the HTTP control service's `PromotionRuntime.store`, passed
through the recursive generation controller to leaf N6 and its N5/N8 ports.
`AcquisitionWorldGrowthBridge` supplies the same runtime to re-entry. Explicit
store injection remains available to contract tests; a production controller
cannot replace a present `PromotionRuntime.store` with another object.

Implementation inputs: `src/polisyos/runtime/quality/generation_cycle.py@sha256:a40239a067ade9336b0edec3fbbe2ee3c09223cb42031bea39900b60385a1c42`;
`src/polisyos/runtime/quality/recursive_generation_cycle.py@sha256:381c928d9dd2a9d9eaef88bf0d40c27db068b3b95f5ffecb9e1614b5bba71ac7`.

## Behavioral evidence

- The integrated focused test group passed 9/9 with guarded tenant-store
  replay, selected-view corruption, timeout/unavailability, and parent preflight
  cases. JUnit:
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_INTEGRATED_FOCUSED_V2.junit.xml@sha256:a498ca7ca4ef6312e266812e8f23c05296d1b8938faa145ec8dcb01c02f964a7`.
- Removing selected-view enforcement while retaining the selected-view markers
  makes the distinguishing test red:
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_SELECTED_VIEW_REMOVAL_RED.junit.xml@sha256:bd740958c61a3a8044372bc6ebd35e554f7ceceefa1e50bffd7621860637f4a6`.
  Moving the parent no-store guard after the N5 controller call, with its marker
  retained, turns the sentinel red; restoring the source turns it green. The
  mutation, JUnits and restored source hashes are in
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_PARENT_NOSTORE_REMOVAL_PROBE.md@sha256:b372ef933a2c336456cd4b4c7f8319889feda7a711e879742ed1190a352027bb`.
- The ordinary served N4 candidate path remains available: all three tenant
  variants passed in
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_SERVED_CONTROL.junit.xml@sha256:9eab35b91cc7b665066fb97b60166762063a1dcb953ef07cada6cb16390406bd`.
- The exact `2522cf2ee` slice-base replay compared every case in both touched
  test files. `test_acq_01.py` has the same 20 identities and 14 pass / 6 fail
  at base and candidate. `test_cyc_02.py` has six common identities, five pass
  and one fail at both states; seven added candidate cases pass. Thus there is
  zero base-pass to candidate-fail transition in this denominator. The six
  acquisition reds and one parent red were reproduced at the base; their cause
  ownership is **not established** under strict P41 because changed source
  intersects the test inputs. Complete per-ID and origin receipts:
  `/Users/deniskopylov/.codex/scratch/p41-r13d-slice-base-2522-20260926/P41_SLICE_ATTRIBUTION.md@sha256:ffa847c08f7b1bad39a7d76f0287a0b6d2cfa533e6d2ffe5d4ade1c4b4293b19`;
  independent review
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_P41_SLICE_BASE_ADDENDUM.md@sha256:e12fffd0e962a3e6a5d33332a0f920ed904d41ba25760c1d6e08a41859b00fec`.
- The direct `JointSimulationPort` census covers 25 constructor sites in five
  files over 2,695 source and 2,728 test Python files. It finds the ordinary
  direct test calls stop before N5 persistence or return pending without an N5
  request. This is a source census, not a passing test receipt:
  `/Users/deniskopylov/.codex/scratch/e02-r13-direct-n5-importer-map-20260926.md@sha256:18a6de54d18cadd4dc590b70e40a03d6c4f8d6aa3e4ad26266bbec6a98cbcb03`.
  A focused three-case direct-control run had two passes and one failure. The
  failing `test_value_gate.py::test_empty_hints_with_unresolved_candidate_wmr_ref_refuses_typed`
  selector reports the same pre-store blocker tuple at exact slice base and
  candidate, so there is no pass-to-fail transition; ownership remains
  `not_established` under P41. Current JUnit:
  `/Users/deniskopylov/.codex/scratch/e02-r13-d-exact-store-20260926/R13D_DIRECT_N5_CONTROL.junit.xml@sha256:dfd449e12b72097ffaff6b16501f6f3971757b60ee7044bc084631f11606f84a`;
  base JUnit:
  `/Users/deniskopylov/.codex/scratch/p41-r13d-slice-base-2522-20260926/value_gate_selector/junit.xml@sha256:578e563669c056b11fbd281a3f4d438067f07d141a5b38718187465542f3629e`.

The tests use a symlink to read-only `production_data`;
`/Users/deniskopylov/polisyos/policy-engine/production_data/manifest.json@sha256:9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`
identifies the data input. No bulk data is copied into receipts.

## Gate predicates and limits

The selected-view replay recomputes the manifest profile, content digest,
byte length and N5 receipt binding from the runtime-supplied store. The store's
tenant ownership is independently enforced by the supplied guarded store in
the focused negative; generic backend and cache/namespace wrappers have no
complete two-tenant witness. The production `PromotionRuntime.store` identity
is checked by object identity at controller construction. A caller that lacks
that runtime can still do candidate work until N5 needs persistence, but cannot
claim a durable N5 result from a root path.

The property is runtime-store custody for N5/N8. This implementation observes
an in-process supplied store identity and selected manifest bytes; it does not
prove every remote backend or cache wrapper preserves tenant and cell custody.
That divergent case remains the existing R13/P31 residual. The composed-WMR
and NCM producer/reader pair still uses a root-rebuilt store, so R13-G must move
both sides together. The positive recursive-parent persistence test currently
stops upstream on R2 `strangle_receipt_currentness_not_established`; this slice
does not weaken that authority gate or claim a positive parent replay.

The broad direct-N5 importer attempt timed out at 180 seconds without a JUnit
and is `UNRUN`. The lane-wide four-base touched-file gate remains open. No
trust-posture pin, loaded-runtime manifest, or GY promotion epoch was reissued.
