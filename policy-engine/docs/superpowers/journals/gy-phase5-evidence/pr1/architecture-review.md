# Independent phase-5 architecture review — 2026-09-08

Reviewed the current S3 findings, PA1 findings and superseding `pa1/design.md`, the live
law owner, the actual natural-language job worker and job-status reader, the compiled/recursive
run DTO owners, and S8 authorization/admission/emission. This is a design review, not a claim
that unimplemented source passes. No production file or another agent's evidence was changed.

## S3: routing closure does not close the law correspondence predicate

**Blocking acceptance finding AR-S3-01 — same P38/P37 class one level deeper, not a new class.**
The live `resolve_law_bound_lever` derives its `admissible` status solely from
`evaluation.status == "admitted"`. It selects the law/knob declaration from the tracked
owner-fixture mapping and substitutes the resolved threshold's own `applies_to` when the
declaration omits it. This correctly measures a numeric legal threshold and does not measure
whether that threshold regulates the declared knob. S3's complete real mapping transposition
probe leaves the declaration intact and still produces admissible against a different legal
predicate. That is exactly the declared-predicate/proxy boundary S3 is meant to police.

The proposed repair should remain on `intervention_substrate.resolve_law_bound_lever`: carry
the candidate's true knob/provision/threshold/time trace, distinguish threshold evaluation
from mapping correspondence, and fail closed for authoritative correspondence until an actual
independently verified mapping witness resolves. Do not edit the fixture map to more plausible
provisions, introduce per-law checks, or let confidence/metadata/signed assertion stand in for
semantic correspondence. The second finding is the same class under P40; repair one general
admission invariant or declare and demonstrate the bounded residual.

**Standing after a routing repair:** not automatically `executed`. S3's literal mechanical
trace can be discharged while its authority-binding/free-growth gate remains unmet. The plan
binds the lex map as an L3→lever relation and §3.5.6 requires a genuinely new law/knob entry to
lift data-only plus a decisive validation-removal control whose genuine happy path remains
valid. Replacing all law-admissibility positives with permanent blocked outputs and counting
that as the same success would narrow the gate. A working candidate trace with explicit
`consumer_asserted` correspondence is valuable evidence, but it is not a verified law mapping.

Use `not_executed` while a lane-executable missing piece is still being investigated or built.
Use `blocked` at the law-correspondence acceptance conjunct only after the complete reusable-owner
discovery demonstrates that the needed independent mapping producer/evidence is an external or
governed dependency. In that event, finish the route/N4/N8/strangle/proof changes and the fail-closed
law repair, deliver them coherently, and retain this exact unresolved conjunct. Do not call the
task `not_executable`: unlike a completed negative-only task, S3 contains undischargeable positive
binding/lift obligations on the presently supplied evidence.

Falsifier for an `executed` claim: take the actual remaining real mapping, retain the complete
source denominator, then change its true legal subject while preserving declaration fields.
The correspondence gate must reject that transposition, and its accepted sibling must have a
resolved independent witness to the **same** law/knob relation. A fixture authored to assert
that relation cannot become the canonical denominator. Candidate-only free-growth should also
be demonstrated, but cannot replace this authority claim without a new ruling.

## PA1: the deployed sidecar design is viable, with one ownership boundary to settle

The superseding design chooses a real source event: `_process_control_job` persists
`runtime.compiled_recursive_generation_cycle` and then completes a natural-language job. The
proposed unconditional bridge, sidecar reference in progress/diagnostic refs, and current
owner-replay in `get_job_status` cover the previously absent producer→CAS→consumer→surface
chain. This is materially different from a helper that always emits a request and is never
called by the production worker.

The two source branches are correctly distinguished. An N6 research/quarantine/decision front
is a candidate-membership classification; it is not a Pareto frontier or an empirical value
proof. Preserve those exact labels/identities with dominance `not_established`. The authorized
branch must use a real signed S8 frontier, schedule and source-bound authorization through the
existing `NormativeValueScheduleOwner.recommend`/replay mechanism. Its positive control proves
permission to select under explicit test trust, not policy optimality or canonical promotion.
Do not label a sidecar's constant candidate-refusal branch a positive ranked-emitter path.

**Blocking design ambiguity AR-PA1-01 — same source-binding P37/P38 class one level deeper.**
The design makes S8 the composite-sidecar emitter while HTTP owns the
`CompiledRecursiveGenerationCycleRun` parser and compiled→leaf membership. S8 can validate a
`GenerationCycleRun` from CAS, but that does not prove that this leaf belongs to the supplied
compiled source. A direct S8 persist/project path that trusts caller-supplied compiled+leaf
refs would launder the missing premise even if the normal HTTP caller already checked it.

Resolve the owner boundary before implementation. The smallest owner-first split is:

- `control/generation_cycle.py` owns composition-sidecar production and projection, including
  canonical compiled-run parsing, derived complete leaf set, leaf byte identity and inclusion.
- Existing S8 owns the individual signed-ranking/request artifact and its complete output
  verifier. The composition owner obtains selections only by replaying that output, never by
  trusting copied status or a sidecar ranking field.
- Every public sidecar/status/audit projection follows the composition owner. Raw persistence
  of a wrapper is not authority. Alternatively, if S8 retains the sidecar contract, explicitly
  constrain its standalone authority to the leaf and carry compiled association as unverified
  until the HTTP owner recomputes it; do not imply S8 independently verified that association.

Do not pass `membership_valid=True`, a self-attested verification record, or an arbitrary
callback as the bridge. The decisive falsifier is a real leaf from run B combined with run A's
compiled ref while keeping candidate names, valid signatures and every sidecar marker intact.
Both persistence and the actual job-status consumer must refuse the mismatch. This tests the
present boundary once; it does not call for recursive verification of a generic verifier.

Additional acceptance requirements already present in the design should stay explicit:

- The exact `_process_control_job` path is exercised. Removing its new call while preserving
  markers must remove the actual CAS request/sidecar and turn integration red.
- A genuine source-bound signed frontier can use the **same service path** to select. Wrong
  rights role and missing schedule must reach their owner-specific refusal reasons, rather
  than merely fall into the candidate-only branch. Version-1 authorization lacking the new
  source binding remains readable but cannot authorize the new generation-bound route.
- Current projection replays time-sensitive authorization at the current trusted evaluation
  time. It must not reuse the sidecar's historical `evaluated_at` as proof that permission is
  still current. A once-authorized selection whose permission expires must not remain green
  in durable progress or copied diagnostic fields.
- Iterate the real derived leaf/candidate sets; empty, missing and malformed cases remain
  distinguishable. No static leaf list or familiar-candidate subset defines coverage.
- The sanctioned CAS adaptation may reuse the real ambient-enforcing FileSystemCAS target,
  but must not accept arbitrary duck-typed signature providers. Unwrapping the canonical
  resilience proxy also bypasses timeout/circuit-breaker behavior; either preserve that guard
  through the existing adapter owner or record the narrow local-store limitation explicitly.
  This latter item is an operational limitation, not a new authority gate or a reason to stop.

## Review disposition

S3 has an executable route/owner repair and an authority-correctness repair; an `executed`
task status still requires evidence for the unchanged law-binding/free-growth gate. PA1 can
close its actual negative-and-orchestration task once the compiled-membership owner is made
explicit and both candidate and signed-selection paths reach the real worker/CAS/status
consumer. No new acceptance constants, legal correspondence certificates, Pareto claims, or
promotion receipts are justified by this review.
