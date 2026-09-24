# R12 root cause map: N7 re-entry and bootstrap strangle

Status: read-only diagnosis against the Phase 0 integration tree at
`8cf3028c05438dda01ebe30225ef5119ed5637d5`. No tests, native jobs, source or
test edits, or governed artifact writes were performed. The four-base P41
baseline remains pending; the conclusions below are source-level hypotheses
until the broker records the exact cells.

## Classification

Both reported R12 symptoms belong with **R13 (ACQ-01, local world-growth route
and root-rebuilt stores)**. They do not belong with R2 (CYC-05 historical run
validity and deployment identity). The first symptom is a type-inaccurate
fixture exercising the legacy N7 arm that R13 must fence or mark contract-only.
The second is a gate that misclassifies one integrity-recomputation call while
failing to measure the local world-growth route. Do not create a separate R12
repair mechanism beside the R13 controller/owner work.

### E02-versus-main boundary

At both the execution base and main, the older `_reenter_cycle_after_n7_acquisition`
replayed an N7 receipt and updated grounding/cycle history. It synthesized a
reduced candidate projection from the receipt's source slots and world ref;
it did not look up or rebind the prior candidate's actual atom, nor rerun the
existing N5/N8 nodes. E02 commit `0c65c8122` added candidate/hash lookup,
receipt-to-candidate binding, and the `InterventionAtomBinding` prerequisite.
E02 commit `da8c5a3cd` then added `_rebuild_n7_acq01_route_context`, which
loads the route's local CAS and mints a new WMR/context during that in-cycle
re-entry. The root-rebuilt route helper and the error string do not occur in
the pinned main source (`5fd3ebcc1`); main's in-cycle re-entry remains the
older history/grounding update.

Main also has the distinct `AcquisitionWorldGrowthBridge` production path. It
performs native overlay/epoch admission and calls
`reenter_after_active_acquisition_overlay` after successful admission; that
method's contract says it cannot fetch, activate, mutate the prior run, or
enter through either legacy acquisition arm (`src/polisyos/runtime/quality/acquisition_world_growth.py:184-205,283-328,779-808`;
`src/polisyos/runtime/quality/generation_cycle.py:3801-3936`). E02's generic
`GenerationCycleController.run` still chooses the older local N7 arm when
planner routing returns no report (`generation_cycle.py:3727-3757,4242-4272`),
and the E02-specific context rebuild makes that arm a second WMR writer. This
is the R13 delta: preserve the existing history-only behavior only where it
cannot admit world growth, and route production growth through the main
bridge's overlay/passport/native-epoch chain.

## Symptom 1: `n7_reentry_candidate_atom_not_canonical`

### Property and root cause

After accepted N7 evidence changes a world basis, re-entry may bind the selected
candidate to the new world and rerun the existing N5/N8 owner only when the
selected intervention atom is canonical and its content is bound to the
receipt. The check must remain fail-closed for a candidate whose atom cannot be
rebound safely.

The E02 path obtains the selected candidate from
`_n7_candidate_bindings[(candidate_id, candidate_hash)]`, populated in
`_joint_value_node`, then `_n7_rederived_grounding_for_candidate` requires an
`InterventionAtomBinding` before reading its target slots. The re-entry method
performs the same type check, changes `world_model_record_ref`, recomputes the
atom ID/content hash, validates the rebound model, and passes it back to
`_joint_value_node` for N5/N8 (`src/polisyos/runtime/quality/generation_cycle.py:5369-5420,5659-5665,6388-6423`).
Those changes were introduced by E02 commit `0c65c8122`.

The failing base-passing test supplies a different contract: its
`_CounterexampleAwareGenerator` returns `_Candidate(atom=_Atom(...))`, where
`_Atom` is a frozen test dataclass containing only string IDs/hashes, status,
world ref, and target slots (`tests/unit/runtime/quality/test_generation_cycle.py:264-276,332-389`).
`test_acquisition_required_invokes_n7_and_records_same_cycle_reentry` then
drives that fake through the local recorded-owner acquisition arm
(`tests/unit/runtime/quality/test_generation_cycle.py:3553-3619`). The base
re-entry did not require a prior candidate or canonical atom; E02 added both
the N5 rebind and this type requirement. Thus the exact test failure is
explained by a test double that does not satisfy the new re-entry contract; it
does not show that the production N4 output violates the atom type.

The production N4 result contract is `ShadowGeneratedCandidate.atom:
InterventionAtomBinding`; its model validator requires a shadow-only atom and
matching atom/provenance content hashes (`src/polisyos/runtime/quality/design_generation.py:213-232`).
`N4GenerationPort` calls `generate_design_candidate_bundle_under_a` and returns
that owner result (`src/polisyos/runtime/quality/generation_cycle.py:1510-1555,5510-5560`).
This is the intended production shape. However, the consumer-side check at N7
currently establishes the type by `isinstance` and does not independently
revalidate the original atom's canonical hash before rebinding. Treat that
predicate as `consumer_asserted` at this boundary until re-entry verifies the
original atom and receipt binding together; the producer's typed output is
useful provenance, not a substitute for the consumer's currentness check.

### Production caller and R13 connection

The served natural-language job path calls
`ControlPlaneService.compile_and_run_recursive_generation_cycle`
(`src/polisyos/runtime/http/services/control/run_lifecycle.py:3297-3332`).
The recursive leaf constructs `GenerationCycleController` and calls
`controller.run(...)` (`src/polisyos/runtime/quality/recursive_generation_cycle.py:890-916`).
In `run`, an acquisition-required cycle first tries planner routing and
otherwise calls `_run_n7_acquisition_if_requested`; a returned receipt enters
`_reenter_cycle_after_n7_acquisition` (`src/polisyos/runtime/quality/generation_cycle.py:3727-3757`).
That fallback calls `run_acquisition_closed_loop` directly
(`:4242-4272`), rather than the existing served
`AcquisitionWorldGrowthBridge` path. The canonical bridge already uses the
runtime-supplied artifact store and native epoch admission, and its resume path
re-enters N6 after admission (`src/polisyos/runtime/quality/acquisition_world_growth.py:184-205,283-328,779-808`).
This makes the real correction an R13 route/authority change. The fake-atom
failure should not be repaired by weakening the atom gate.

### Removal probe and preserving control

- **Removal probe:** keep the acquisition request, route/schema markers, and
  selected candidate IDs intact; remove the production fence that prevents the
  legacy local gateway/rebuild arm from running. A production-scope served
  controller witness must turn red if the local gateway runs, a local WMR is
  minted, or a candidate atom is rebound without the overlay, passport, and
  native epoch admission. For the atom sub-property, give re-entry a same-ID
  candidate whose atom has forged or stale content while retaining its type
  and marker fields; the consumer must refuse before N5 sees it.
- **Preserving control:** ordinary candidate computation without an acquisition
  need still proceeds. The positive acquisition control is a canonical N4
  `ShadowGeneratedCandidate` through the existing served bridge, where N5 is
  called with the admitted world context. A fixture-only legacy test, if kept,
  must explicitly declare `authority_scope="contract_testing"` and use a
  validated `InterventionAtomBinding`; it cannot serve as the production
  positive witness.

## Symptom 2: acquisition-planner bootstrap strangle reports `drift`

### Property and root cause

The intended R13 property is that production N7 cannot construct or admit a
second world-growth path beside Data Forge overlay admission, passport, and
native epoch qualification. The reported `drift` comes from
`generation_cycle_substrate_fence` scanning the complete AST of only
`generation_cycle.py` for calls named `SubstrateRegistration`,
`build_substrate_registry`, or `build_substrate_registry_entry`, plus a string
literal containing `n6.bootstrap`; it separately executes
`_n7_substrate_registry` with an empty temporary repository and checks the
typed refusal (`tools/quality/validation/check_layer3_gy_acquisition_contract.py:161-221`).

The sole banned builder call in the merged file is
`build_substrate_registry_entry(registration)` at
`src/polisyos/runtime/quality/generation_cycle.py:4921`. Its enclosing
`_validate_n7_acq01_registry_binding` reads persisted baseline and post-write
registries, derives the expected entry, and compares the persisted exact delta
and entry at `:4917-4938`. This is validation of a CAS-backed owner result, not
a registry bootstrap/write. The call was introduced by E02 commit
`b2d4dde7c` as part of ACQ-01 registry-delta custody.

The false red is not the underlying R13 defect. `_rebuild_n7_acq01_route_context`
reads `capture_store_root`, reconstructs `FileSystemCAS(store_root)`, and later
builds a WMR/context from that route (`generation_cycle.py:5023-5040,5087-5094,5280-5333`).
This local path avoids the forbidden registry constructors while minting a
world record, so the current scanner could turn green after a narrow exception
while the world-growth bypass remained reachable.

### P37/P38

- **P37:** the AST parser recomputes the syntactic call-name census for one
  source file, and the empty-root probe recomputes the refusal for that
  synthetic input. The claim that every occurrence of a builder name is a
  production bootstrap producer is `not_established`; call role and persisted
  effects are not reconciled. The empty-root refusal does not supply evidence
  about the served caller or its world writes.
- **P38:** the property is “production acquisition reaches the canonical
  authorized Data Forge overlay/passport/native-epoch route.” The gate turns
  on call spellings and a temporary-root failure. It reports false drift on a
  persisted-entry verifier at line 4921, and it could report green while the
  local `FileSystemCAS`/WMR path at lines 5087-5094 and 5280-5333 remains
  reachable. The gate measures builder names, not who owns the write or what
  world admission occurred.

### Removal probe and preserving control

- **Removal probe:** retain the AST marker strings and route metadata, but
  re-enable the production default path through `RealAcquisitionOwnerGateway`
  and local route-context rebuild. A served production-scope acquisition test
  must fail on the observed gateway call or local WMR write even if the
  bootstrap-name scan remains empty. Separately, make a fake/forged route
  payload keep all names and hashes but alter the actual persisted registry
  delta; the content-bound registry check must refuse.
- **Preserving control:** an integrity-only call to
  `build_substrate_registry_entry` over an already loaded persisted
  registration remains allowed to prove the exact owner delta. The canonical
  served WDI path must still complete overlay admission and native epoch
  qualification using its supplied store. The bootstrap test should retain its
  empty-owner refusal assertion as a distinct sub-property, not treat it as the
  whole production strangle.

## Proposed R13 write set and verification order

Serialize all `generation_cycle.py` work under the R13 lease. The focused write
set for these two R12 symptoms is:

1. `src/polisyos/runtime/quality/generation_cycle.py`: fence or remove the
   production local N7 acquisition/rebuild arm; use the canonical bridge's
   active admitted world for re-entry; verify the original atom and receipt
   binding before updating its world ref. Do not weaken `InterventionAtomBinding`.
2. `tools/quality/validation/check_layer3_gy_acquisition_contract.py` and
   `tests/unit/runtime/quality/test_acquisition_planner.py`: separate the
   bootstrap-registration predicate from persisted-entry verification and add
   the production behavioral strangle witness. Do not exempt a whole helper
   family based only on function names.
3. `tests/unit/runtime/quality/test_generation_cycle.py`: either change the
   legacy-loop test into an explicitly contract-only canonical-atom fixture,
   or make it assert the typed acquisition/costed route without a local
   receipt. Add the same-ID forged-content removal probe and a no-acquisition
   candidate control.
4. Preserve the served acquisition witnesses in
   `tests/integration/core_runtime/test_acquisition_world_growth_chain.py`,
   `test_acquisition_tenant_custody.py`, and the served-authority test. These
   are the evidence for the canonical bridge and must be included in the
   four-base touched-file replay.

The broader root-store census and dependency map is in the R13 candidate map
on `codex/e02-r2-partial-triage`; this R12 note does not claim those other
store sites are closed.

Pattern pass: P27/P28 (canonical owner and legacy strangle), P29 (behavioral
property probe), P31/P32 (class-wide intake and substance over type/markers),
P37/P38 (predicate source and proxy measurement). The exact touched paths must
be re-censused after R13 chooses its production route. No test or validator
was run during this diagnosis, so its status is **pending P41 baseline**.
