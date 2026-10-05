# G: disposition of recovered workspace drafts

Workspace retirement preserves source history and moves disposable checkouts
to Finder Trash. Earlier permanent removals of rebuildable environments,
private caches and a verified archived output tree are recorded separately
in the local cleanup report; later retirement waves use Trash only. Recovery is not
code acceptance or finding closure. These source reviews compare immutable
drafts with integration `08918047feac94acffb19eccba6d6f9d7e564adc`, tree
`a447dee6f176dbc8e767fb79fb48726b0780b4be`; no recovery tests were run.

## Useful inputs for canonical owners

The refs below are published archival branches. Fetch them for a small
adaptation against the current owner; do not restore their older whole files.

| Input and exact preserved commit | Canonical owner and disposition | Required discriminator |
| --- | --- | --- |
| `codex/e02-retired-r1-l4-period-coverage-20261005` @ `75a095b0752db290b0fa7f8a1ee676c89233880e` | A/data-state producer: `runtime/quality/data_state_substrate.py::_project_real_l4_payload`. Adapt observation-window filtering before latest-row selection, aggregation and truncation. Keep identity snapshots distinct from period-bearing observations. | A newer out-of-window row must not displace the in-window row. Bind coverage to actual source inputs; decide whether gaps are informational candidate limitations or affect WMR/simulation admission, and test the persisted consumer effect. Current simulation consumption drops status/limitations, so temporal metadata alone does not close the bridge. |
| `codex/e02-retired-e02-b26-served-consumer-bridge-20260929-draft` @ `60e86a29c70332c0d5caac5d96bccbf4a4653424` | A/N5 producer and HTTP consumer: adapt the tenant/cell/job-bound read-time diagnostic surface to current persisted N5 APIs. B26/SIM-03 remains partial; diagnostics confer no N9 authority. | Persist a multi-step request with only step 0 observed, then exercise the served readback. It must expose incomplete coverage and evidenced checked orders; foreign tenant/job denial precedes artifact reads. Removing owner recomputation while retaining response markers must fail. |
| `codex/e02-retired-e02-r1-positive-bridge-code-20260927-draft` @ `25ce5321896e4825b7465bd1872e420f01bdef37` | A/current direct-ref context owner: adapt only the same-kind, different-lineage negative fixture. Selector propagation is already covered. | Preserve kind while changing lineage/job/selected manifest identity; require rejection at the real consumer. Do not reinstate a tenant-wide scan that drops selected profiles. |
| `codex/e02-retired-e02-r11-owr-projection-20260926-draft` @ `ad28258e29350ca09da46b488059a35622d60d36` | A/N6-to-N9 public-export owner: adapt the test that transplants a genuine pre-N9 gate-bearing port onto a blocked run. Current owner validation already rejects the combination. | Require `blocked_generation_cycle_n9_admission_mismatch` before resolver/projector calls. The served gate-only post-construction mutation is a bounded internal-corruption residual; external reachability is not established. |
| `codex/e02-retired-mig02-readback-tests-20261005` @ `0ec18c55ce3abdebe198987374e803c7f9b45912` | C/MIG-02: recover the two migration CLI→persisted RunManifest→Runtime resolver tests against the current candidate. Their 65-line addition is absent from G; production code is already present. LA-048 remains partial. | Inject replace failure, preserve the old destination and source bytes, clean the sibling temp, then retry and reopen through the real Runtime resolver. Tiny local fixtures suffice; this does not establish power-loss durability. |

## Superseded or unsafe drafts

Old R1 job binding, R2 admission currentness, R5 worker, R9 approval/CAS/view
propagation, R13 projection hashing, two R11 implementations, B72 status
safeguards and B88 bounded replay behavior are covered or evolved in current
owners. Do not replay those patches. In particular, the old N3/raw `get_paths`
capability escapes tenant custody, and the R5 worker can promote a
`candidate_only` result into normative publication. Preserve their recovery
history without restoring those paths.

The debt-survey and group-A research documents have newer canonical findings;
their old denominators and whole-file context must not overwrite current
registers. SCM's three schema snapshots match current source bytes, while its
other generated companions are stale: regenerate from the frozen source and
run the generator's check instead of merging the retired draft.

A preserved pre-commit patch also suggests durable claim-adjudication resume
at `scientist/methods/autotune/claim_adjudication_runtime.py`, coordinated with
the Data Forge frozen-input producer and existing verifier. Its old
claim-ID-only JSONL checkpoint is unsafe. Reuse the existing input-bound
campaign mechanism: interrupt after one committed provider response, resume
without redispatching it, and reject reuse after source/model/prompt changes
that preserve the claim ID. This is an adaptation input outside the accepted
E02 slices. Keep the archived mixed patch local; its shell component contains
credential-like literals and must not be republished or reapplied.

The current A topic's engine/trajectory and receipt-hash checks, and the current
B CAS topic's manifest-tenant owner check, are separate incoming deltas. They
need current committed handoffs and distinguishing tests; recovery review is
not their acceptance. B72 required-output/reopen, B88 tenant replay custody,
and finding-specific P41 verification remain held at their recorded scope.

## Focused follow-ups from historical reviews

All 23 otherwise-unreachable historical commits and all 32 archived
pre-commit patch entries were reviewed. Most behavior is covered by evolved
current owners. The following are scoped adaptation inputs or verification
gaps, not accepted changes or new closure requirements for every slice.

| Current owner | Smallest useful follow-up and scope |
| --- | --- |
| `generation_cycle.py::JointSimulationPort` and its HTTP consumer | Capture exact durable outcome/horizon/budget/resource hints at the persisted owner-NCM→N5 request boundary; missing required budget must refuse before N5. Existing HTTP missing-NCM evidence proves a typed block, not served N5 success. |
| Scientist executor and `ResolveParametersNode` | Run two otherwise-identical cached invocations around an SKG byte change at the same path; require a cache miss and newly source-bound output. Retain a same-bytes reuse control. Source binding and executor wiring already exist; their combined witness was not found. |
| Fabric resilience `_bounded_registry.py` | With capacity one and a protected state already present, a second protected key must raise `BoundedResourceRegistryCapacityError` without inserting the denied key or resetting the first. Current code implements refusal; the direct boundary witness was not found. |
| CAS inventory and signature batch owners | The initial authenticated member-name census is explicitly not cancellable. Preserve that bounded limitation; a repair would require cancellation during the real first traversal, with a typed incomplete result and no subsequent traversal. Later worker cancellation does not establish this property. |
| Legal AST backend and real `LegalPass` consumer | Adapt a malicious backend `must`/`when` expression negative requiring `BLOCKER` / `SECURITY_VIOLATION` at the actual consumer. The backend rejects unsafe AST; the archived patch is not a safe replacement for current IR owners. |
| Scientist workflow and compatibility-shim owners | Search-phase enums have tests but no workflow bridge: `implemented_but_not_orchestrated`. Decide the bridge at its existing owner. The unreferenced evidence `_shim.py` also needs an explicit retirement decision before adding an assertion that it is absent. |

The retained causal Rule 3 confounding fixture is valid and already covered.
An independent primary-source review found no implementation defect there;
do not restore an earlier false alarm as a code task.

## Evidence and limits

Local full reports, source-to-Trash paths, retained output hashes and recovery
refs are under `policy-engine/_build/e02-g-disk-cleanup-20261005/` in G's active
checkout. Original source objects and refs are kept in the main repository's
shared Git store. The original `production_data` directory stays local and
read-only. The old already-missing checkouts' working bytes and dirty state
cannot be reconstructed from an index or reflog alone.

Pattern pass: P27/P31 keep adaptation on canonical writers; P29/P32/P37/P38
separate real consumer evidence from source retention and status markers;
P35 requires complete inventory denominators; P40 keeps declared residuals
bounded; P41 does not assign inherited-red provenance without exact replay.
Broad replay and data-dependent closeout remain UNRUN until source freeze.
