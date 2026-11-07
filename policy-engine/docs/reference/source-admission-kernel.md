# Registered materialization owner kernel

Owner: Scientist validation and Core contract owners.
Source of truth: `src/polisyos/scientist/validation/source_admission_owner.py`, `src/polisyos/core/contracts/decision_validity.py`, and the registered-source admission tests under `tests/unit/scientist/validation/`.

This extends the existing DecisionValidityService for G27-02; it does not create a
simulation ledger or confer external SQL currentness. This source-only profile is
`bridge_missing` / `verification_missing` until the actual Runtime/Fabric producer,
Foundry basis and served consumers are composed and checked. No G acceptance or
closure is assigned, and the historical B13/B198 dispositions remain unchanged.

## Reuse and the single authoritative quantity

Reuse actual Core CAS full selected-profile/raw-byte/ownership readers, the
DataSnapshotOwnerBound generic field/role requirements, the existing validity
owner lock and its typed contract family. Extend that owner with one immutable
quantity holding registration, source facts, occurrences, admissions/epochs,
selection, event identities/dedupe and per-use heads. Consolidate all covered
source current-use reads through it; mutable legacy packet fields are not a
second admission authority.

The inspected existing alternatives were `core/security/anchor_lineage.py`
(atomic head but state contains all records and recovery scans transactions),
`core/artifacts/ownership.py` (its own purpose/fence and full artifact snapshot),
and existing validity atomic-file helpers (serialization without a multi-file
commit). They provide useful persistence patterns, but none of these selected
ports is a reusable bounded-key source index under the existing validity fence.
This is a bounded source search, not a repository-wide absence claim. Build only
one private path-copy hash index part here, rather than repurposing another
sovereign state owner or copying every packet/history on each transition.

One constant-size fsynced root under `decision_validity/epoch_batch.lock` points
to reusable immutable index/fact/event objects. Orphans before publication have
no authority. Dedupe is reachable only through that committed root. An uncertain
root replacement is actually re-fsynced before an original receipt or positive
read is returned. No source transition scans all source heads or event history;
the actual I/O oracle rejects unrelated fact-value reads and growing root bytes.
This does not claim the cost of the existing Core CAS ownership index or
unverified NFS/distributed filesystem durability.

## Scope, origin and lifecycle

A private neutral port accepts only registered issuer/capture identities. Its
minting helpers are trusted-composition seams, not public candidate factories.
C106 must bind the real installed Runtime grant/config and actual canonical
registered provider capture. A callback/string/DTO alone is not authority; no
current source producer/factory wiring is claimed in this kernel proposal.
The public unconfigured and lookalike paths fail closed. Storage-unit positives
explicitly seed private state and are not real producer proof.

The issuer freezes tenant/cell/provider, configured logical registration key,
exact view/use refs and explicit permitted operations. Owner-issued incarnation
survives rereads and credential rotation; acquisition occurrences are separate
from CAS content deduplication. Typed materialization carries actual capture,
request/snapshot/data/schema/quality plus schema-derived optional evidence and
warnings. Actual Core tenant-scoped selected-view ownership and raw content are
verified; binary inputs are not forced through a JSON reader.

Admit never changes default selection. Explicit supersede selects an active
carrier. Withdraw targets the exact revision/use; readmit creates a new epoch and
never revives old carriers. Source predecessor and full command/target identity
are load bearing; a changed duplicate or absent predecessor refuses. Timestamps
are not sorted to infer committed order. Existing independent carriers survive
unrelated global generations.

## Fresh consumer contract

CAS reads happen outside the common owner fence. A second fenced read selects
one durable root and checks the exact committed carrier/fact/epoch/registration.
The projection binds the ordered, repeated actual carrier vector and selection
query by `basis_digest`, reports `selection_checked`, root/generation/rule and
`owner_fence_linearization_point`. Any required withdrawn carrier blocks the
conjunction; other missing/incomplete/legacy scope is unknown; current requires
all facts/content and an exact bound query. A prior valid answer is not guaranteed
until network delivery. This projection is internal admission, not scientific or
legal validity.

C106 must derive the complete supported Foundry basis, bind the actual returned
projection to that basis/query and execute this same owner for both default and
explicit/cached API selection. No snapshot-to-latest-carrier shortcut, public
Research DAG protected refs, rewritten SimulationResult/history, success-marker
authority or automatic local replay of missing cloud bytes is allowed.

## Pattern and verification boundary

P01/P02 producer/bridge reality remains explicit; P05/P32/P37 require the actual
configured issuer and captured producer relation; P31/P40 widen the entire
root-reachable fact/event/index quantity once; P29/P38 controls remove runtime
properties while keeping markers; P07/P08 retain exact refs, rule and time roles;
P14 separates source review, store-unit evidence, real runtime, G and closure.
The new source/test/control bundle is pending independent review and all runtime.
See `docs/research/e02-cloud-test-plan/implementation-handoffs/C105/structural-owner-r2/EXECUTION.md`.
