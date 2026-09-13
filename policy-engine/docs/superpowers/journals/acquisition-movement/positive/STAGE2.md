# Stage 2 — native epoch qualification and activation composition

Stage 1 artifacts remain unchanged. This companion records implementation work;
final frozen runtime evidence is pending the root's shared verification wave.

## Pattern decision and authority boundary

The first gap was `implemented_but_not_orchestrated`: the production acquisition
wrapper selected an unallocated qualifier even when a captured deployment could
supply actual policy evidence. After wiring was proposed, the common qualifier's
unconditional `NativeProjectionCustodyGap` proved a second stop in the same
positive-composition class. The repair therefore widens once to the common
projection-custody quantity (P40/P31), shared by epoch and movement qualification.

The recorder is a projection of an already verified native result. It does not
appoint a policy owner, supply native predicates, replace a native head, accept
an anchor or grant retention. Policy selection, source verification, predicate
bijection, native limitations and full-prefix verification still precede it.
Its exact CAS bytes and manifest are reloaded before the existing private proof
persistence owner can emit `NativeChronologyQualified`. The qualified contract
requires the projection receipt, and the epoch production receipt now retains
its reference. This closes the P01/P02 bridge without admitting P05/P32 status
or reference-shaped substitutes.

## Concrete native owner

`semantic_epoch_qualification.SemanticEpochNativePolicyOwner` resolves the
configured signed `PredicatePolicyAdmissionStatement` using the captured
`EpochDeployment` trust snapshot. Its separately committed
`SemanticEpochChronologyOwnerRelation` binds the exact query, policy and native
history snapshot. The relation must map the complete policy rule denominator to
three native meanings: member manifest binding, ancestry denominator and query
binding. Names are supplied by the admitted policy; semantic operations are
implemented by this native owner. No mapping is inferred from arbitrary IDs.

The owner parses each real `SemanticEpochManifest`, recomputes its identities,
checks its scope/purpose and predecessor references, traverses exactly the
requested ancestry, and reconciles that ancestry with the canonical epoch
history repository. A prospective cutoff must extend the current native heads;
a replay must match the existing owner rows. It independently reconstructs
candidate bytes and predicates and persists the actual verifier evidence.
Predicate values are `recomputed`; the policy-owner signature reconciliation is
`independently_reconciled`. Missing signed admission, mapping, native store or
history owner fails closed. The default native slot stays empty.

`build_semantic_epoch_native_deployment(config)` supplies this concrete owner
only when configured policy selectors exist. `EpochDeployment` captures both
producer operations in its existing operation-attestation mechanism. The
production wrapper accepts this factory identity explicitly. The local
`python -m polisyos.runtime.quality.acquisition_epoch_admission` entry point can
consume a verified activation and returns zero only on that branch; absent
policy still returns the persisted negative with exit one.

## Positive read-back

`CatalogAcquisitionOverlay.read_activated_semantic_epoch_admission` reads CAS,
owner copies, active epoch references and the native member index. It resolves
every member to the physical overlay row, reconciles the member denominator,
and derives the observation count from `ds_observations` member rows. It cannot
activate a pending epoch.

`acquisition_executor.resolve_activated_semantic_epoch_admission` binds the
aggregate receipt to this owner read-back and its production/admitted evidence.
It requires a captured deployment, replays native qualification from the exact
persisted projection through that deployment's actual verifier, and requires
identical projection/bundle/verifier references. A stored positive declaration
alone cannot become fresh authority. Its `replayed=True` metadata denotes a
read-back, not a new-growth delta; the root bridge owns pre/post active membership
and target-variable delta.

## Fixtures and current evidence

`tests/_helpers/semantic_epoch_native.py` (outlier agent) creates separately signed
fixture policy evidence over an actual prepared manifest/history, uses the
concrete native owner, and can execute real finalization/overlay activation.
It does not construct a positive production receipt or install a test verifier.

`tests/_helpers/acquisition_epoch_production.py` prepares the full production
wrapper's L5/Lex/catalog/facet basis. `production_admission_inputs` performs no
fetch or admission, so the root can run the actual production port. The separate
`build_production_admission_case` convenience helper first obtains the actual
unallocated wrapper's prepared basis, signs that exact basis, and leaves it
pending for the caller to activate. Its default transport is the existing WDI
executor/Fabric observer-sink fixture; independently executed live evidence can
be supplied instead. No native producer, qualifier or activation path is patched.

Runtime diagnostics retained under `positive/raw/`:

- `stage2-projection-red.txt` @
  `ed9d2a2f2456ddcac741482e3a6cd658790ebb735a33dec34c554a92494d740b`:
  actual initial consumer refuses positive candidates at projection custody;
  both positive cases failed and both custody-absence cases passed (exit 1).
- `stage2-projection-diagnostic.txt` @
  `009e150d7fdd39019013ae2b926f0efc5d17ea8ad8a0e61d823e8e9667d6f053`:
  direct real consumer reaches `NativeChronologyQualified` (exit 0).
- `stage2-qualification-focused-v1.txt` @
  `d41dfe4da23499ce4440c97f4419278364c27d0f17caf60c6819e8ba4b1a44bb`:
  127 passed, one failed in 340.24 seconds. The failure is the promotion fixture's
  incomplete deployment attestation components during concurrent assembly edits.
  This is diagnostic, not a frozen closeout receipt.
- `stage2-projection-green-initial.txt` @
  `2607b4e3886cc9ee5111de1bb8d6469d4817a7ebc0ecc7fdc9b79ad4f9edb39d`:
  consumer produced qualified, but a test loaded its older JSON decoder before
  the canonical-byte decoder correction. Diagnostic only.
- `stage2-activation-readback-red.txt` @
  `a460e7e1a175f633ce7e151a2593a7c5b691f6fa27c3a5a5574e23518a48943a`:
  mixed-source import encountered the old epoch DTO and new overlay field;
  **not a receipt for the intended read-back refusal**.

No diagnostic red above is claimed inherited or excluded from closure. Frozen
baseline/removal/restored evidence for new native/activation branches, the root
port-positive/deeper-movement run, and architecture/public-contract checks remain
required. The outlier agent's bounded source review found no demonstrated blocker
in the native owner/read-back; its exact-query sibling concern was incorporated
in the existing signed-context conjunction before freeze. No register/ledger,
canonical OpenAPI, commit, push or sync operation was performed by this agent.

## First frozen integration wave and bounded repair

The root's `docs/superpowers/journals/acquisition-movement/raw/stage2/first-wave.txt` @
`7c714359828f31f52c1699402ed0f79f1517cf4b82bd7fe509ba42dba685a622`
is a real frozen red, not an inherited failure. Within the nine selected cases
owned here, the four generic projection cases passed; the four native epoch
cases and the active read-back case failed. Root owns the complete wave's
selector denominator and process receipt.

The native owner used the generic security statement codec to read history
written by the epoch owner's JSON-mode codec. Typed scope bytes therefore
reserialized differently despite the actual source being valid. The repair
extracts the existing producer's `_history_view_bytes` and uses it both for
history persistence and strict reader reserialization. Native bytes still have
to match the producer byte for byte; parsing alone is insufficient. This is the
same native composition class deeper (P40), not a new authority source.

The production retry then exposed the owner-state replay gap: after a first
unallocated attempt admitted pending rows, preparing again included those rows
in the candidate basis and caused `epoch_content_conflict`. The overlay now
selects the original prepared reference from its exact epoch/candidate pending
receipt, checks CAS plus owner copy and native member denominator, and returns
that reference as a custody read. The runtime resolves and content-binds the
actual `PreparedSemanticEpoch`, requires the exact request and candidate, then
recomputes the passport against current source/authority and invokes the existing
admission and finalization checks. No caller-supplied prepared object or weaker
conflict rule was introduced. The full wrapper test binds the activation to the
first negative's actual prepared reference. Already-active recovery continues
to require the original production and activation receipts; root owns that
read-back bridge.

The read-back fixture assertion expected one observation while its real input
and owner activation contained two. That assertion and the native finalization
assertion now use the actual two-row fixture denominator. The first red never
reached the pending-state removal assertion, so it is not cited as that removal
receipt. Targeted Ruff passed on the repaired source and tests. The next frozen
runtime wave and the prepared in-memory removal witness remain pending.

The next frozen wave passed the native owner and read-back cases but retained a
full-wrapper refusal. A bounded real-wrapper exception trace,
`positive/raw/stage2-wrapper-diagnostic-v2.txt` @
`2c39881dd328cb0bbbbac3339e8fc4b9349937621cdeda2f9a5714ff8fc7ce57`,
identified `chronology_proof._payload_fingerprint`: JSON-mode serialization tried
to decode a binary native manifest frame as UTF-8 and rejected byte `0x87` at
position 7. Projection custody had already succeeded. The small catalog fixture
had merely happened to have UTF-8-compatible frame bytes.

This is the same binary-native codec class deeper. The private continuation now
fingerprints every typed input through the existing byte-aware raw canonical
mapping. Its process-local fingerprint changes; persisted native/proof wire
formats do not. The regression supplies actual non-UTF-8 opaque member bytes to
the fixture producer, then runs the real common qualifier and proof persistence.
It constructs no qualified result. The production-wrapper assertion now retains
the entire returned receipt when it fails.

The complete nine-module filename scope (`chronology`, `semantic_epoch`, and
`epoch_deployment.py`, Python files under `src/`) and all inspected serialization
calls are retained in `positive/raw/stage2-native-serialization-census.json` @
`8d17d653dc1e284d6df4e354e73bea4abb78c049a3a39b7be0677f86f99529e8`;
independent `rg` output is `positive/raw/stage2-native-serialization-rg.txt` @
`c184c61215126ab6dd88061d25119b94df9465594bad321f032c069a2062b1cb`.
The repaired fingerprint was the JSON-mode consumer of reconciliation/member
`native_bytes` in that scope. Other calls serialize metadata, strict signature
or verifier-result DTOs, deployment selectors, or the separate established epoch
scope/owner wire grammar. The finding is bounded to arbitrary chronology member
bytes; it does not establish arbitrary binary support for every epoch identity
field. Targeted Ruff passed; the new runtime regression awaits the root wave.

## Identical-input enforcement witness

`positive/raw/stage2_property_probe_v3.py` @
`ad1163b9d2c8771b9b39dbcfd805bfc2cb4487e34722bcf634211e579b69b3c1`
ran in one process (session 44993, actual exit 0). Complete deciding output:
`positive/raw/stage2-property-identical-v3.txt` @
`113c1ea0f47ab08d5632c31c86b2fe4f18ab68a43c2a984e0c12846e97900a32`.
Each of five cases built its external/native fixture once, then exercised the
actual caller in baseline, in-memory removal and restored phases. All baseline
and restored assertions passed; each removal failed its real property assertion.
The phase gate codes are **0 / 1 / 0**, not separate subprocess exit claims.

| Property removed | Actual removed behavior |
| --- | --- |
| Projection custody, absent store write | `NativeChronologyQualified`, two members |
| Projection custody, corrupt stored projection | `NativeChronologyQualified`, two members |
| Native denominator reconciliation | False empty denominator became `NativeChronologyQualified`, zero members |
| Active owner state read-back | Exact valid pending owner bytes passed through cached active markers |
| Binary-aware continuation fingerprint | Actual consumer raised `UnicodeDecodeError` on native byte `0xff` |

The deciding witness hash is
`afd8d6bbab3092df38dfc4b7063cd4d8cd4a76e1629631f51f40abc5edf8a576`
before and after every case in every phase. This is distinct from the script
hash. The driver hashes actual query/candidate/policy/receipt bytes, every file
initially present in the five fixture CAS roots, native history-owner file sets,
configured trust files, the baseline, and exact active/pending owner snapshots.
The actual DuckDB bytes are also checked immediately before each read-back call.
The complete input denominator is
`positive/raw/stage2-property-identical-cases/1789322146220456000-3550/immutable-input-denominator.json`
@ `dbc8168f15de20ec1cd8a92a9723b1f746aed87e08ca74f3f3c68a6ea02ccaa5`.
Derived proof/output artifacts are not misclassified as immutable inputs. Named
source bytes stayed unchanged; root owns the complete imported-source freeze.

The superseded v2 attempt ended before any phase because the mixed witness
envelope used chronology's float-forbidden codec for an activation authority
score. Its full output remains `positive/raw/stage2-property-identical-v2.txt`
@ `bc04dacf4078a81aae970ccb2a7bea5b4f25767e61053ee33878721dd6604476`.
That is a harness `UNRUN`, not a product red. V3 uses the existing general
canonical codec for the measurement envelope; no production behavior changed.
The root's third aggregate wave remains the separate integrated runtime receipt.

The third aggregate output is
`docs/superpowers/journals/acquisition-movement/raw/stage2/third-wave.txt` @
`6fc86b857b320cbee5f23a9b8b195e47093fc9f78f83c394e8ae8c8a93aa153f`.
The native full wrapper, binary-member qualifier, root's actual WDI/N6 growth,
and separate GY positive tests passed in that wave. This agent's remaining
importer failure was the mandatory contract census companion: the independent
AST/runtime enumeration found 120 models while its old constant expected 118.
The two added projection models already belonged to its explicit complete
partition; the constant and matching docstring now say 120. Both independent
enumerations, complete partition reconciliation and injected-model falsifiers
remain intact. This is a P39 companion correction, not a new mechanism or a
register change. Targeted Ruff passed; root owns the final targeted replay and
the other wave failures. Native production source stayed unchanged after the
completed identical-input witness.

## Stored receipt grammar compatibility

The parent delta review found a **NEW** P07/P40 class: adding the optional
`chronology_projection_ref` changed reconstruction of old exact production
statements, although those stored bytes never contained that field. The core
verified loader already retains the actual decoded mapping. The persisted DTO,
negative CLI consumer, and overlay activation comparison now retain the known
legacy omission; every original required field remains required. The persisted
DTO preserves omission when serialized and still recomputes both raw CAS and
domain-separated semantic hashes. Explicit null and a non-null ref cannot borrow
an omitted-field receipt's identity. New production receipts retain their current
grammar, and native admission still requires actual projection custody.

The complete deciding red is
`positive/raw/stage2-receipt-compatibility-red-v3.txt` @
`382b611476c1424c02d6386c7a254c6d358074ff75a036cd9763f026531ffd49`
(own process exit 1): both old negative and old positive CAS statements failed
the persisted ref/profile binding after successful raw readback. Earlier outputs
were fixture `UNRUN` results, preserved separately:
`positive/raw/stage2-receipt-compatibility-red.txt` @
`5a7f7ad9f53bbc3120333e13c9a64d14316ecc67261e75811402a1639566f852`
(missing test artifact media type), and
`positive/raw/stage2-receipt-compatibility-red-v2.txt` @
`71a612bc88756f4156f19e4ef781999b940fd6d776706fa109570bcc5757c961`
(test hash helper called positionally instead of with keyword arguments).

Targeted Ruff passed on the three mechanism files and three companion test
files. The new regression additionally exercises the negative CLI and old
positive overlay activation/readback while requiring native resolver refusal.
These companion tests and the existing actual native positive selectors await
the parent's next frozen aggregate wave; no green runtime receipt is claimed
for this compatibility delta yet. Native predicate enforcement was unchanged.

Independent lifecycle inspection also confirmed a separate missing served link:
the existing admission CLI and wrapper can activate durable pending evidence
after policy arrival, but the WDI served path made its quarantine terminal
immutable and only exposed recovery of already-active admission. The exact
native policy selection binds a manifest/denominator derived after fetching;
the in-call fixture signature was therefore insufficient proof of an operational
later-appointment flow. Parent and movement agent own the distinct new action
over the saved attempt, reusing the existing native wrapper and preserving the
original terminal and consumed live lease. This is a bridge/consumer repair,
not authority granted by changing the native predicate meaning.

## Production replay verification precondition

The bounded delta review found the production authority intake class one level
deeper: a restarted acquisition provider with no decision-verification appointment
passed `None` to the generic gateway, selecting its optional unsigned legacy
mode. The current mandate, signed admission and separate DS9 source could remain
valid. The production provider now requires its factory-attested decision
verification identity before opening any worker decision. The generic gateway's
legacy behavior remains outside this acquisition execution boundary; missing
institutional slots can still produce a request-side refusal. No new mandate,
policy meaning or signer is synthesized.

`test_real_worker_replay_refuses_absent_decision_verification_appointment` in
`tests/integration/core_runtime/test_acquisition_authority_provider.py` reuses the
actual two-action served fixture, including committed human custody. Within each
ready job it creates one missing-verifier provider and reuses that same object
and the same retained CAS/DS9/mandate bytes for baseline, in-memory removal, and
restoration. Only `_require_worker_decision_verification` is removed. The probe
requires gate codes 0/1/0; the removed phase must load the exact allowed decision,
and all phases must call no effect. The original worker proceeds afterward with
its unchanged reservation. This avoids consuming the authority idempotency state
while measuring the intake.

The test writes full deciding records to its retained pytest temporary directory
as `provider-verifier-removal.json`: actual CAS read receipts, blob/manifest/
signature file hashes, exact deployment/request inputs, source hash, fixed
evaluation time, and the measured limitation that diagnostic-event/exposure-audit
backing files are not part of the CAS-byte hash claim. Runtime results are pending
the parent's frozen wave. Targeted Ruff passed. Frozen provider source hash:
`2c3eaf495bb5f228ffaeaafebe07b5f23dd26029d9f51a4e6dd3b17e97b5d3ad`;
test hash:
`0e3fa3fc45fedfaec543e02f348e713258c77a373f3ad1a4f1415c637394c8da`.

The deferred-action source review also found that a new job still selected
`action_generation=1`, colliding with the immutable quarantine head because the
durable head key excludes job ID. This is the deferred bridge class deeper; the
parent owns the distinct generation/sink repair. No additional blocking native
receipt join was demonstrated in the frozen deferred bridge. Its negative
reader preserves the original production mapping and re-binds prepared query,
admitted evidence, passport, selected variable and original live evidence; its
started fence preserves the declared no-retry boundary for unknown outcomes.

## Runtime artifact custody composition

The real served worker exposed the producer-composition class one level deeper
(P31/P40): Fabric reconstructed a default CAS for ingestion and again for its
snapshot, discarding the supplied guarded tenant/cell writer. Ambient context
already crossed the coroutine/thread bridge; reconstructing an unowned writer
was the deciding difference. The native epoch factory had the same conflation
between its captured external-policy reader and runtime native artifacts. The
repair widens to those runtime writer/readback boundaries, without adopting
unowned artifacts or changing any ownership or native proof predicate.

The executor now supplies the existing ingestion dependency store factory
(`acquisition_executor.py:977`); the orchestrator uses it for the snapshot as
well (`fabric/data_plane/orchestrator.py:558`). The actual object, including its
guard and ownership enforcement, remains the writer. The cache's existing
filesystem root requirement is checked against the supplied backing root.

`EpochDeployment.composition_scope` (`epoch_deployment.py:197`) binds the exact
factory identity and immutable affiliated owner states to that same supplied
runtime store, with every configured backing root checked. It restores nested
scopes and does not alter captured policy trust. The qualifier captures this
store when constructed and re-enters its owner scope for each operation
(`chronology_qualification.py:230,258`), including invocation after construction
scope exit. Genuinely empty deployment state retains the original unallocated
consumer. The native epoch service, activation readback and movement consumer
supply their current runtime store; native sources, challenge/projection/proof
outputs and their readback use it. Signed policy, owner relation, admission and
provenance inputs remain on their captured external reader. No root-only global
store lookup or new public facade/deep-import edge was introduced.

The actual tenant-scoped lifecycle regression first failed on the produced
Fabric snapshot with `artifact_ownership_error`: complete deciding output
`positive/raw/stage2-tenant-red-v2.txt` @
`bd72cba92e3e9edade53f82e5e570c1a1a868a5ba1519555ea6a3be61d611782`
(own exit 1). The earlier `stage2-tenant-red.txt` is an `UNRUN` receipt because
pytest plugin autoload was disabled while its default benchmark argument
remained enabled. The deciding rerun explicitly used `-o addopts='' -p asyncio`.

The parent's eighth frozen wave passed the new actual tenant lifecycle,
construction-scope lifetime/nested/reset/wrong-root test, native qualification,
served two-action admission, provider, movement and refusal selections. Its
complete output is `raw/stage2/eighth-wave.txt` @
`8cfc5eb713716e3958a97e1a38f302b0a2b1b53eeecdc41708d6f543de0d8cce`.
That aggregate itself exited 1 on a separately selected empty-health fixture's
missing catalog input, before its assertion; its repair and replay belong to
the parent. This is not a claim that the entire aggregate passed. Targeted
Ruff check and format check passed for this custody delta before freeze.

The ignored driver `positive/raw/stage2_custody_removal.py` @
`55bd23bd42a86e5ef3d8e19ec227c23e94666d978984e7e2d129a8ed74a13395`
then ran both actual producer probes with natural process exit 0. Each measured
baseline/removal/restoration assertion codes **0/1/0**. Fabric removes only the
supplied dependency factory dispatch; native qualification removes only scoped
runtime-store dispatch. Both removed phases produced an actual
`ArtifactOwnershipError`, with `current owners: unowned`, on the unchanged
reader. Baseline and restoration verify the emitted output, reject a different
tenant or cell, and reopen it under the original scope.

Each fixture was built once. Native signed policy, query, key, source/history
bytes, tenant/cell, deployment and guard objects remain the same; the complete
pre-output CAS snapshot is restored at the same path between phases. Every
measured guard future is drained before restoration, using one private executor
per probe; the shared async executor is untouched. The input receipt explicitly
bounds runtime wall-clock observations outside the fixed business/query inputs.
The scripted source denominator selects the complete Python set under `src/`
and `tests/` minus one named exclusion (5,291 selected files): the parent's concurrent
`tests/unit/runtime/http/test_runtime_service_container.py` fixture repair; that
excluded module was independently confirmed not imported by this process. No
included source bytes changed.

Complete output: `positive/raw/stage2-custody-removal.txt` @
`f2f06941b7e83c6df678dc16bf15dbc9f838460fa8bdfeb13e4f708447e7df06`.
The retained directory
`positive/raw/stage2-custody-removal-state/1789329329813337000-14218/` contains:

- `receipt.json` @ `e035da611057a8aa860bf6e6216da078a218270bba8bd805d659e0abc098a9e4`;
- `input-denominator.json` @ `4ce846b41382eadf1d11594458d4caeac2fe76974ff5aad365140e744a639c58`;
- `actual-read-receipts.json` @ `e5f2126eefa3f791d64fb267302f2eb785f288444735ca39574ad807d2cfec5c`.

Those records retain successful and failed CAS reads plus scratch `Path.read_bytes`
reads, exact fixture/input hashes, phase codes and explicit read-boundary limits.
No product source was mutated by the probes, and no Stage 1 artifact was changed.
