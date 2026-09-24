# R6 — candidate-unbound N5 context map

Status: read-only source trace on `codex/e02-r2-held-review` at
`d08e31358a5ecc613104c540b7559eca79796c94`. This task changed documentation
only. No tests, native jobs, or four-base replay were run.

## Property

A `candidate_unbound` lever resolution from another `CycleSubstrateContext`
must not supply or shape the active N5 world identity. For this candidate path,
N5 may carry the active context's `WorldModelRecord` as
`simulation_pending_n5` only after the refusal resolves against that exact,
revalidated context. If the refusal does not resolve, the result is
`simulation_blocked` with no `WorldModelRecord` attached. The same-context
candidate-unbound case remains candidate work: absent a full N5 request, it may
remain `simulation_pending_n5` with the exact context WMR; it does not become
simulated or authoritative.

## Root cause and fallback

`InterventionLeverRefusal` is a strict, content-hashed record. Its model
validator proves that the supplied fields match its own `content_hash`; that
alone does not prove that those fields belong to the active cycle context
(`policy-engine/src/polisyos/runtime/quality/intervention_substrate.py@e4c7c30f81438908688a169cb3d51fbd3f66be20:266-307`).

The owner resolver performs the needed cross-record check. It revalidates the
active context, requires `candidate_unbound`, resolves exactly one candidate
by lever ID, instrument, and entry hash, then compares the refusal's
`context_binding_hash`, substrate input hash, registry hash, WMR hash, selected
registry entry hash, and source refs to that candidate/context. A mismatch
raises `WorldModelRecordError("world_identity_unresolved", ...)`
(`policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11:502-575`).
This identity check is the correct gate; do not weaken or bypass it.

The regression is in `JointSimulationPort.__call__`'s no-request branch. With
no complete N5 request, it calls `_boundary_world_model_record`; in a supplied
context that calls `_context_world_model_record`, which checks active problem
identity and resolves the candidate refusal
(`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:1773-1807,2264-2298,2335-2358`).
When the foreign refusal fails that check, the broad exception handler records
`world_identity_unresolved` but then revalidates only the active context and
restores its WMR
(`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:1797-1824`). The return status is selected from
`world_record is not None`, so this context-only fallback yields
`simulation_pending_n5` even though the candidate-to-context identity failed
(`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:1825-1844`). The returned WMR is the active
context's WMR, not the foreign WMR; the defect is that the foreign refusal is
ignored after it failed the identity gate, allowing the candidate to receive a
pending N5 state.

This class is specific to the no-request branch. When request-building hints
are present, `_build_joint_simulation_request` errors are returned as blocked
before reaching this fallback (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:1711-1772`).

## Production caller

The production path is wired, not test-only:

1. `RunLifecycleService` delegates the run request to
   `compile_and_run_recursive_generation_cycle`
   (`policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@a3827ed1677df17f09827d479db7510ffdb70e6e:1598-1628,3297-3322`).
2. The HTTP composition builds or accepts the owner-bound context and passes
   it into `build_default_recursive_generation_cycle_controller`, then into
   the recursive leaf route
   (`policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py@055cca6c9424deac61fa61543143a2a2d2310b1a:558-595,638-670`; `policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py@ddff9abd228378166bce8437862ebe487ae00149:685-700,855-913`).
3. A `GenerationCycleController` owns a default `JointSimulationPort`; the
   generation result's non-binding grounding dispositions are projected into
   `_DispositionCandidate` values carrying a validated refusal, then the
   selected candidate reaches `_joint_value_node` and N5
   (`policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a:3416-3436,3470-3480,5510-5587,8416-8467,5659-5709`).

An existing served-path witness demonstrates HTTP → recursive leaf → N5 with
one owner context, but its candidate is atom-bound and its N5 block is for a
missing NCM spec; it is not an R6 foreign-refusal witness
(`policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py@b675681a801cb9a66ec3ca80faf636fd91bc92d9:1211-1312`).
Add an adversarial served-path case there if the class repair is implemented;
the direct port regression alone does not prove the live route carries the
candidate disposition unchanged.

## Smallest class-wide fix

In the no-request branch, do not restore a WMR after
`_boundary_world_model_record` fails candidate/context binding. Preserve the
error diagnostic, leave `world_record=None`, and return `simulation_blocked`.
The fallback is unnecessary for a valid context-bound candidate: that path
already returns the WMR from `_boundary_world_model_record`. Do not alter the
strict identity resolver, synthesize candidate identity, or patch only the
foreign test case. The mechanism write set is one source file:

- `policy-engine/src/polisyos/runtime/quality/generation_cycle.py`,
  `JointSimulationPort.__call__` no-request error path.

The test write set is:

- `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py`: retain
  and strengthen the foreign-context regression and marker-preserving removal
  probe; retain the same-context positive control.
- `policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py`:
  add the served HTTP → leaf → N5 foreign-refusal witness using the production
  composition.

No resolver, N4, HTTP composition, or WMR builder edit is indicated by this
trace. These are proposed writes only; no source or test files were changed in
this task.

## Behavioral probes

**Removal probe:** use two independently content-valid contexts for the same
problem shape and a foreign-context refusal whose declared fields and
self-content hash remain intact. The fixture contexts share the candidate
lever/instrument/entry identity while their `context_binding_hash` differs
because it binds the active problem ref (`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a:1908-1976,2054-2060`; `policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11:378-408`). After the fix, the foreign case must
block with `world_identity_unresolved` and no WMR. Remove the final
`observed != expected` context comparison in
`resolve_candidate_lever_world_identity` while preserving the refusal fields,
content hash, status, and WMR markers: the foreign case will then be accepted
by the partial candidate match, and the test must turn red by observing a
pending N5 result with the active WMR. This falsifies identity enforcement,
not marker presence.

**Same-context control:**
`test_joint_port_uses_verified_candidate_unbound_resolution_for_context_wmr`
must continue to produce `simulation_pending_n5`, carry the exact context WMR,
and have no `world_identity_unresolved` blocker. It confirms ordinary
candidate-band work remains available when identity resolves
(`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a:2029-2049`).

The existing negative witness is
`test_joint_port_rejects_candidate_unbound_resolution_from_another_context`;
it supplies a refusal built from another context and requires blocked status,
the identity blocker, and no WMR (`policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a:2051-2070`).
These test identities are proposed witnesses for the class. This map does not
claim they were replayed on the four bases.

## P37 / P38 and P40

- **P37 — predicate:** the active context's problem ref, registry, selected
  candidate rows, WMR, and content hashes are `recomputed` by typed model
  revalidation. The refusal's self-content hash is also `recomputed`, but proves
  only internal consistency. The refusal-to-selected-row comparison is
  `recomputed` from those content-bound records across all six fields; until it
  passes, the relationship is `not_established` and the gate must block without
  attaching a WMR or emitting pending N5. A valid context WMR alone does not
  establish candidate identity. The relevant validators and resolver are
  (`policy-engine/src/polisyos/runtime/quality/cycle_substrate.py@f24fcc8ded61aa07c0c4145ea27f929995533f11:110-145,411-425,502-575`; refusal self-hash:
  `policy-engine/src/polisyos/runtime/quality/intervention_substrate.py@e4c7c30f81438908688a169cb3d51fbd3f66be20:266-307`).
- **P38 — divergence:** the property is “a foreign candidate-unbound
  resolution cannot shape the active N5 world identity.” The identity resolver
  tests the correct equality, but the no-request catch then tests only whether
  the current context can be revalidated, and the status tests whether any WMR
  is present. The divergent case is the foreign refusal above: its identity
  check fails, but current-context revalidation succeeds and returns pending.
- **P40 bucket:** this is the R6 class `candidate identity failure swallowed by
  context-only fallback`. Remove the fallback at the shared N5 boundary; do
  not add instance-specific checks in N4, HTTP, or tests.

The current test-failure comparison belongs to the assigned R6/P41 replay
denominator. This source trace alone neither confirms nor rebuts a
PASS_TO_FAIL result and is not a closure receipt.
