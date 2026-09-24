# PC-B2 execution record

The controlling Stage 1 findings are `PC-R04` and `PC-R05` in
`docs/superpowers/journals/promotion-conjunction/reduction-research.md@cc3f8ecce031a12a0b6041e6a2f54a53e4288655`.
Source work began only after that commit was read back on the attached lane.
The slice baseline is `28b8a1a42`; final source identities and selected verification
inputs are frozen in the root receipt `raw/source-freeze.json` (SHA-256
`0231e6629e71c28c4c7d3e85dad7d90107de1d77497a9d08ffe6b154400055ec`). Final gate and probe
results belong to the root execution receipt; the intermediate results below do
not claim final verification.

## Built chain and remaining deciding link

The non-test caller is `ControlPlaneService._admit_evaluation_safety_attempt`,
called by `_process_control_job` for both supported control-job branches. The
runnable workflow terminus is `POST /api/v1/control/runs` through
`launch_workflow_run`; the existing natural-language route uses the same admission
helper. The admission core is produced first, unchanged. Post-core source
selection now invokes the existing opaque near-miss classifier and both actual
canonical N9 readers, passing the same owner evidence repository.

The deployment constructor accepts `EvaluationSafetyPromotionSourceSlot`, whose
default is an empty tuple of source run IDs. Request payloads cannot fill it or
supply a classification verdict. Source selection resolves the actual completed
natural-language job, its persisted job payload, terminal core-run manifest, and
the selected compiled recursive run. It checks actor/run scope, exact CAS and
writer schema identity, and candidate/problem/world/mode binding. Each selected
run is visited; an unreadable selected run makes selection unresolved. A run that
has not been selected remains outside the stated population, even if present.

No new source DTO or dormant writer was introduced: the source producer is the
existing NL worker's `runtime.compiled_recursive_generation_cycle` output. Exact
child problems already have an owner source: `GenerationSourceRepository.load`
resolves retained source handoffs against the selected cycle and candidate tuple.
Historical child artifacts without that capsule remain named unresolved sources;
no root problem is silently substituted. Consequently no edit to the recursive
generation owner was needed.

Replay selects the candidate's actual canonical receipt and its owner projection,
including that candidate's value receipt. It does not borrow the cycle's single
selected value projection. The C4 resolver basis references are projected into
the existing PDC offer contract using registered profiles, and the opaque
classifier verifies that exact projection before invoking canonical replay.

The lifecycle repository shares the configured
`PromotionRuntime.promotion_evidence_source.measurement_catalog` and
`.measurement_providers`, plus immutable `.promotion_safety_source_trust`. It
does not rebuild a catalogue from declarations or substitute retrieval defaults
for the dependencies used by the actual N9 producer.

The service persists the source-resolution receipt whether a source is absent,
unreadable, refused, or classified. An existing diagnostic producer event points
to that receipt on both admission outcomes; blocked progress and the existing
artifact index also carry its reference. No API DTO or generated OpenAPI snapshot
was changed for this surface. The receipt identifies source-selection successful
reads and attempted reads separately and labels its scope `source_selection_only`.
Transitive classification-resolver reads, partial nested-owner failures, external
unselected source runs, historical missing child capsules, and the unappointed
promotion semantic decision remain named `unresolved_by_construction` boundaries.

The remaining link is selection of the promotion-purpose acceptance predicate
and its appointed authority, followed by a real candidate satisfying that
predicate together with the other promotion conjuncts. Source custody does not
answer that decision. A canonical negative receipt can produce a verified opaque
classification with `promotion_safe_facet=False`; neither that result nor an
unresolved source changes the frozen admission core or increments near-miss.

## Review disposition and pattern pass

`P01/P02/P12`: connected the existing writer, typed source slot, actual post-core
caller, canonical verifier, persisted classification offer, reducer, and existing
diagnostic surface. The original helper-only bridge omission was not treated as
an institutional stop.

`P31/P32/P37/P38/P40`: the first source-tuple review was the SAME completeness
class below source-run selection. The repair widened the selected quantity to
the exact persisted canonical candidate/problem/value tuple. The later core-vs-
PDC reference mismatch was another example of that SAME representation boundary:
the old mocked fixture admitted PDC references where production supplies core
references. The shared registered-profile projection now connects and checks
that boundary without inventing semantics or changing the offer DTO. Fixed
measurement-provider forwarding and source-trust forwarding belong to the SAME
replay dependency class.

The source-mode substitution was a NEW scope class: identical candidate/world
markers could previously bind a simulate-only value to a protected attempted
mode. The structural classifier now requires value mode to equal the produced
admission core's mode for every producer; source selection separately emits a
named mismatch. The adversarial witness changes only mode.

The compiled-source manifest escape was a NEW custody class: kind and blob hash
alone did not establish the actual writer contract. The single source reader
now checks artifact ID, blob digest, manifest integrity digest, byte size, media
type, and the exact producer schema. The witness varies manifest properties while
retaining valid bytes and kind; the content witness retains parsed semantics and
their self-markers while changing bytes.

`P29/P33`: the source-chain test uses an actual generated tree and an actual
negative `CanonicalN9PromotionPort` output, with the existing explicitly test-only
epoch appointment and a value fixture. The existing NL worker persists that
compiled source and its terminal manifest. The attempted-evaluation path then
selects it, persists the real offer, and invokes the actual classifier and N9
readers. N9 validators and promotion outcomes are not mocked. This is a negative
integration witness, not an empirical protected-promotion success.

The legacy helpers in `tests/unit/runtime/http/services/test_evaluation_safety.py`
and `tests/unit/runtime/quality/test_evaluation_safety.py` required mandatory
fixture companions: its value stub now includes the actual
core mode and its resolver references use the core artifact type plus the exact
C4 profile projection. Its admission assertions were not weakened. Independent
review of PC-B3 found no further authority escape: current source attribution
replay cannot fill the typed-empty acceptance slot, and protected-mode EVAL_SAFETY
still returns scope refusal when request custody is verified.

## Retained intermediate evidence

All paths in this table are relative to this journal. Each JSON retains the exact
subprocess command, process return code, stdout, and stderr. The initial run did
not record monotonic duration; that omission is explicit in its receipt.

| Receipt | Actual process result | SHA-256 |
| --- | --- | --- |
| `raw/bridge-initial-regression.json` | `0`; explicitly selected legacy admission/injection tests | `9e6e7e3f43d30a32df48a24e7e1a136f81dbafcc03798e6fbac4353d5802ca8b` |
| `raw/bridge-targeted.json` | `1`; 288.6197 seconds; runtime trust dependency had not yet landed, failing before the new source property | `4cd09c1a76cd72d4e3d0f5e6964bd526ff9a0b56835e4fc862449d5918c29afc` |
| `raw/bridge-targeted-v2.json` | `1`; 104.062494 seconds; reused identical intake across distinct test jobs hit the existing authority identity refusal before the content-mutation property | `4e4930f7c3f0489effdd3549989b8c0ad6049877df6012c02fc485da2b091742` |
| `raw/final-targeted.txt` | `1`; root wrapper 774.023 seconds; complete first frozen combined wave | `99ce0467e9648264117a2a86c8caf57d45b83347d832a0a4d34028dd3e66431a` |

The first frozen combined wave also supplied deciding correction evidence. CAS
already rejected the artifact-ID/integrity/size manifest corruptions with its
original `ArtifactIntegrityError`; the new test incorrectly demanded the later
adapter marker. Its media/schema variants reached the adapter and passed. The
real-negative fixture used raw JSON parsing instead of the actual canonical
float decoder and failed before classification. A separate legacy injection
fixture still supplied PDC-shaped resolver mocks. These are in-slice failures,
not exclusions. The correction batch uses the original CAS-owner refusal in those witnesses,
uses `canon.from_canonical_bytes` for the real source fixture, and brings the
separate legacy fixture to the actual core-reference/mode contract. Static review
also found that the offer writer used the broader GY comparison hash over live
models and time, while the admission owner checks an exact canonical hash. The
writer now calls `EvalSafetyNearMissClassificationOffer.build`, which owns the
existing exact `_content_hash` operation. This is the SAME content-projection
class, closed by the existing owner constructor rather than another hash recipe.
The parent owns the final rerun receipt.

The first red was resolved by the agreed runtime dependency landing. The second
was resolved by giving independent test attempts independent IDs; the explicit
same-job retry witness retains its original ID. Neither red is excluded as
inherited product debt. Final source and tests were then frozen for the root's
single combined verification interpreter; the root retains its complete output.

`bridge_removal_probe.py` is the tracked removal instrument. Its `main()` runs the
source-custody, resolver-forwarding, and mode-binding witnesses, checks the exact
selected call-phase failure and actual pytest return code, and restores the
original function bytecode in `finally`, including every previously imported
alias. It retains the original marker in bytecode. The compatibility entrypoint
`raw/pc_bridge_remove.py` calls that tracked instrument. Probe success means the
expected original behavioral assertion failed under removal; an unrelated setup
failure is not a witness.

## Routing

The architect's register update for the two NC01 closure rows should distinguish
the now-built classification bridge from its protected-promotion semantic
decision. The default empty source selection is a deployment-owned typed slot,
not an unimplemented source writer. The unavailable empirical complete-evidence
candidate remains with `first-promotion-candidate-with-complete-evidence`.
Historic child sources without handoffs and nested owner-read coverage remain
explicit named runtime limitations; they make no claim of complete absence.
The interim fixture identity collision and missing dependency landing go nowhere
outside this receipt because the final batch resolves them without weakening a
product refusal. No register, ledger, or generated OpenAPI file was edited by
PC-B2. The failure/repair register and measurement-instrument rule were reread
before this closeout note.
