# G: continuation intake, first wave 2026-10-06

Base: `198076863e143dea9f89f02734b13d50dae3eed5`. Code acceptance and finding
closure are separate. Original histories are preserved; G publishes only
`codex/e02-integration`. Current owner heads remain immutable review inputs;
new commits require delta/dependency/evidence reconciliation.

## Accepted: B direct CAS put regression

Topic `aff2d90cd336f905054d6e96109906d2ebf1ece2`; implementation
`b16cf7f6ccb1311e74a6fc8af3dc6e16526e4db4`, tree
`6a2c69c191f2aa7514d6809b055d54e085f821b7`. Complete footprint is the new
`test_put_integrity_retry.py`, committed handoff and five bound outputs;
production source did not change. Independent identity, owner/companion and
runtime/oracle reviews support bounded GO. Same-size corrupt bytes and false
selected-manifest byte size exercise real duplicate put refusal; operator
restoration, missing-sidecar controls and fresh-instance reads are meaningful.
G independently ran the exact candidate: **30 PASS**, no skips/failures/errors,
20.61 s pytest / 25.888 s wall. Source/test blobs matched before/after.
[Receipt and complete output](../checks/2026-10-06-first-wave/b-cas-focused.json).
B151 is not formally closed. Full CAS generation, ownership, crash and locking
criteria remain the canonical B queue. No upstream runtime contract changed,
so this test-only merge does not trigger another consumer wave.

## B durability: keep the broader admission claim held

Topic `80d39780d72ea2d431df9470674ed0e4d703587f`; implementation
`bff2464a1303c76e387f4cd2d0cbb995e02d4bea`, tree
`71f1cfbff46fa832f40b4a032f0a1467c486eac8`. G's isolated three-file run gave
**40 PASS** in 9.40 s; this establishes the tested cold/sparse/bootstrap paths,
not every wire-admission premise.
[Focused receipt](../checks/2026-10-06-first-wave/b-durability-focused.json).

Independent static review found a supported-version escape. The separate
[real candidate probe](../checks/2026-10-06-first-wave/b37-independent-oracle.json)
confirmed it: a complete `schema_version="99.0"` snapshot is admitted, and
`record_spend` republishes it as `1.0`, changing the bytes. The process exits 0
because its scoped cold/middleware/wrong-type controls pass; the observed
unsupported-version property is **FAIL**. Full output and executable probe
are adjacent. A foreign nonempty contract string is a diagnostic boundary;
this report makes no cryptographic-authenticity claim.

P40 bucket: same snapshot-admission class one level deeper, predating this
slice; no P41 inherited verdict is asserted. B should widen the inlet to the
supported compatibility quantity with explicit migrations/refusal, or state
and test a finite residual. Do not ladder-patch individual consumers. Before
claiming backward compatibility, exercise bytes emitted by the actual base
writer, including omitted nullable fields. Full fault/crash/fsync/process,
production-factory reachability and B37 closure remain pending.

## D search: evidence and compatibility HOLD

Topic `8c855e68b1f2fd981f284602ce7a54f5e472255d`; verified source
`35d2654368be05b70cfec506fd04568df63d9fc0`, tree
`a7a535c2b9885e712482d9aecc594a6dc78c6c70`. Independent reviews support the
bounded SearchSpace/action identity and Base/Random/Sobol state mechanisms.
No full fitted-GP/RL/deployed resume claim follows.

The receipt's three raw deciding logs are absent from that exact topic tree;
its declared 51 PASS is not available evidence. Commit bound moderate outputs
or supply a new exact-candidate replay. Supply the common handoff fields,
canonical predicate-basis label, property/discriminator and finding map.
`StrategyState`/`SearchSpace` are documented public surfaces; the release
fragment needs surface classification and structured breaking/migration refs,
including stricter normalization preconditions. B127's real optimizer
pending/completed/Evaluation composition remains separate. G's local Torch,
GPyTorch and BoTorch profile is unavailable: local backend replay **UNRUN**;
no heavyweight environment was installed merely to restate cloud evidence.

## Additional received slices under independent review

D transfer `e35cd7c69cb4ca71bdd107b99151b8c45b0ebd41` binds native immutable
vector-generation source `de7fce6cf5f91a63b1b573f1de72d17c792b5c34`. Its recorded
barrier/removal controls and captured-pointer public readers support bounded
atomicity; B129/B133 exact CAS history remain open. The new test imports
optional `hnswlib` unconditionally, while the supported minimal Fast profile
omits that backend. D must use an explicit optional-backend skip/selection,
retaining a real native run where installed. Absence is SKIP/UNRUN, not PASS.

E DDM `2d985e4afb327a37699fecd58cce4279ce1c39d3`, DoE
`fd6b8f991a77fbb8e9551bce8761766581da15f3`, and FRC
`213dfb7c4d9768e90e0b443d093c4b1685e8536a` have committed receipts and are
reviewed on their distinct final implementation trees. DoE has a second
stability commit beyond its original 117-PASS wave; that wave is not proof of
the changed stability code. DoE numeric interaction and paired-order oracle,
DDM source/feed/compatibility, and FRC independent train/holdout/unit/admission
questions remain under review. E producers do not acquire A's default
HTTP/cycle/S10 writer. No finding closure is declared for these slices.

Pattern pass: P29/P32/P37/P38 distinguish real runtime predicates from markers
and declarations; P35 uses complete diff and receipt sets; P40 separates class
repair from bounded residual; P41 preserves unknown red attribution. Broad
regression remains after shared source freeze. Production data remains local
read-only; generic CAS/ledger tests require no full dataset.

## Diagnostic source follow-up

The G standalone probe was linted and formatted after checkpoint-08; the
original executed script stays addressable at `b37-oracle.py@c9af0f65f`.
[Fresh v3 receipt](../checks/2026-10-06-first-wave/b37-independent-oracle-v3.json)
records the corrected diagnostic source, a repeat on the same immutable B
candidate, and the same observed `99.0` → `1.0` failure. Fixtures remain in
ignored scratch. Product code and the CAS/Budget pytest waves were not changed
or replayed.

## E owner follow-up after the four-slice review

These are acceptance/verification actions, not new finding closures or claims
that the mechanisms have no value. Exact heads are pinned above.

- **DDM:** the old closed schema (`additionalProperties=false`) and new schema
  retain the same `$id`, while new writes add `readiness_effective_at`,
  `readiness_event_id`, `readiness_expires_at` and `source_binding_digest`.
  Declare the schema/version and migration boundary; new-reader/old-record
  compatibility does not imply old-reader/new-record compatibility. Source
  DTO agreement and caller-supplied `now`/trigger lists establish a bounded
  library reconciliation, not independently established current feed or
  authority. LA-054/055 stay limited. Bind complete deciding outputs to their
  exact source; basename-only references need explicit identity reconciliation.
- **DoE:** the release fragment labels the documented/exported SensitivityPlan
  surface internal and omits structured change/compatibility metadata. Resolve
  the actual public classification and stricter Sobol input-law/seed migration.
  Reconcile the sensitivity bridge/adapter consumer writer with D before a
  default search rollout. The numeric interaction oracle for
  `Y=x+z+2xz`, independent `U[0,1]^2`, is
  `S1=(12/25,12/25)`, `S2=1/25`, `ST=(13/25,13/25)`.
  Isolate order from changed observations by permuting whole valid blocks or
  trajectories and their paired outputs identically; a samples-only mutation
  does not establish order-only custody. Final stability delta/removal evidence
  is separate from the earlier 117-PASS wave. B97–B105 remain limited/partial.
- **FRC:** the producer preserves the E/A writer boundary and does not establish
  an A trusted verifier or ordinary served route. A metric key is not a unit;
  source `data_schema_ref` is not resolved into an explicit unit on this path.
  Keep that limitation explicit until the canonical unit/source contract is
  consumed. A hit-count loop over the same BacktestReport comparisons is not
  an independent numerical oracle; compare fresh source rows and persisted
  interval values against a separate known-answer fixture. Scope/split/time/
  model-kwargs and false credibility controls remain consumer work. B32,
  LA-051 and FRC-01/02 remain limited/bridge-held; the labelled base run with
  candidate-worktree PYTHONPATH is not P41 inherited evidence.
