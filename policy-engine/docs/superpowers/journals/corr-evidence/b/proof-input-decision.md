# Shared exact-source intake decision — 2026-09-09

The deciding execution is `cg3-world-time-owner-replay.json` (RC0): the complete
actual WMR set and all reference nodes show that fresh record creation time
changes the scaffold epoch while all projected edges remain identical. The
independent CG3 write/check red is retained. This is the same proof-input binding
class in CG2 and CG3, not a reason to remove `as_of` from their hash or alter a
world record's genuine timestamp.

Extend the existing `grounding_calibration` owner with a strict
`GroundingProofWorldInput` DTO, a producer reading an existing Core-verified WMR,
and one loader/parser used by both report owners. The data-only declaration lives
at `architecture/policy_design_case/corr/grounding_proof_world_input.json`.
Its fields are schema version, `synthetic: true`, mechanism-only purpose, actual
source `ArtifactRef`, relative CAS storage locator, source schema version,
logical world content hash, exact source record creation time, declaration time,
and a recomputed declaration content hash. The source ref binds the complete
original bytes; the logical hash and creation time are separately checked and
never compared as if they were the CAS identity. No result or success field is
supplied by its author. The producer derives the metadata from the verified
source. The sole loader revalidates the declaration and resolves the exact
artifact using Core and the existing `load_world_model_record` owner, then checks
kind/media/schema, logical content and original creation time.

The official declaration pins the ORIGINAL A input `e9694967…`, selected before
these report outcomes. Neither the later writer nor checker artifact is promoted
to the official denominator. Both report owners replace their fresh-builder
intake with that same declared source, expose its binding ref/hash, and retain
all existing scaffold/control identities. The existing A refusal CLI receives a
separate producer option to emit this declaration from its explicit world CAS
and ref; it does not change the frozen A frame/suite. Existing scaffold and WMR
algorithms remain unchanged. A source unavailable at its declared CAS location
refuses. A fresh builder may substitute nothing: equal logical content does not
recover the original bytes/time. Original-pin availability elsewhere remains an
explicit custody/acquisition requirement unless an existing exact-byte archive
supplies it. There is no copied WMR fixture or retimed source.

The report envelopes advance CG2 v2→v3 and CG3 v2→v3 for their new load-bearing
source binding. Runtime CG2/CG3 certificate and CG3 child v2 epochs stay intact.
The actual prior CG3 v2 artifact and its failed freshness check are preserved by
root's ordinary-history checkpoint `155645235e5a75b9b4053e83770df609eb26ef94`.
Historical source bytes are never restamped as current evidence.

Targeted falsifiers are: actual original source loads repeatedly with identical
bytes/time/scaffold; a rehashed declaration with wrong time, logical hash,
schema, kind or missing/fake byte ref refuses through this same intake; corrupt
CAS bytes fail Core integrity; another independently addressed real source can
be declared as a separate data-only control and changes the source epoch without
code change; removing the actual source-matching predicate turns the unchanged
refusal control red while the genuine original-source positive stays valid.
The default transition is run-emitted/recomputed in the proof report, with the
legacy fresh-input drift already deciding the pre-repair red. Independent full
write→check and surgical persisted-artifact corruption settle report stability;
all original control/mutation identity sets are retained.

Owned edits are `grounding_calibration.py`, its mirrored targeted test additions,
`check_grounding_refusal_sensitivity.py`'s declaration option, the narrow CG2/CG3
report intakes/metadata, the emitted binding and current reports, and B evidence.
Root owns shared registry/lifecycle/release companions. P27 selects the existing
calibration/Core owners; P28 flips the default source intake; P29/P37 require
actual resolve/recompute and removal; P35 retains complete source/control sets;
P40 closes both report consumers with one invariant. No protected legal truth or
canonical current-world authority is inferred from this synthetic mechanism.
