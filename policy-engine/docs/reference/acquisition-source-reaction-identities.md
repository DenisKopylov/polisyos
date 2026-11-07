# Acquisition source-reaction diagnostic identities

Owner: Runtime quality and acquisition owners.
Source of truth: `src/polisyos/runtime/quality/generation_cycle.py`, `src/polisyos/runtime/quality/acquisition_retained_continuation.py`, and `tests/unit/runtime/quality/test_generation_cycle_source_reaction_identities.py`.

The existing generation-cycle diagnostic constructors accept an optional selected
`source_reaction_ref` naming `runtime_quality.acquisition_evaluation_basis`. The
ref must be JSON with an explicit selected manifest profile. This is an identifier
input only: the acquisition evaluation owner verifies actual basis custody, current
action, current eligibility and retention before calling the cheap continuation.

With no ref, all existing IDs and serialized records retain their legacy meaning.
With a ref, IDs and record URIs include a full content namespace over the selected
basis view, case, candidate and original evaluation cycle index. Counterexample and
typed diagnostic, revision, refinement, VOI estimate, governance and search iteration
identities share this quantity. Their actual producer links and shared budget refs
remain intact. A changed budget or current diagnostic can therefore have its own
source-reaction identity while retaining the original evaluated occurrence.

The retained path still runs current grounding, candidate selection, scheduling,
value projection, revision policy, VOI and the verified current planner. Its internal
`GenerationCycleRecord` is an adapter to those owners; it is neither appended nor
persisted as another evaluated cycle. The cheap projection returns the fresh
counterexample, refinement decision, search iteration and revision separately for
the typed retained-continuation artifact. It does not grant new cycle or N5 claims.

Tests exercise the actual diagnostic constructors and revision owner, legacy IDs,
full selected-profile/case/candidate/cycle discrimination and malformed refs:
`tests/unit/runtime/quality/test_generation_cycle_source_reaction_identities.py`.
The first-action acquisition integration oracle must additionally demonstrate a
real admitted equivalent source after spend changes, a fresh continuation containing
those records, and unchanged original evaluation refs and N5 occurrence count.

Pattern pass: P08 keeps evaluation cycle distinct from current source reaction;
P29 exercises actual constructors and their consuming revision path; P37 treats
the ref as a namespace rather than an authority assertion; P38 removes the old
byte-equality proxy that rejected changed cheap diagnostics despite an equivalent
expensive evaluation basis. Integration remains `verification_missing` until the
actual acquisition action and fresh history oracle run.
