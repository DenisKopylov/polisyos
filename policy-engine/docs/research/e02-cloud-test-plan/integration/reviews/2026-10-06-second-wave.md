# G: second continuation wave, 2026-10-06

Checkpoint source: `312e6d7c12e1d623f1ac9502c187e7cb92e48045`, tree
`11ffd482cf4324a25ca16e77d8b113c8bc9eebad`. Previous G record was
`0905081be26d115848d4f322aa9098210b5fc701`; main stays at the published
continuation base `198076863e143dea9f89f02734b13d50dae3eed5`.
G alone publishes integration. Original histories are preserved by sequential
merges. Acceptance below is per finished mechanism, separately from finding
closure. **No finding is newly closed by checkpoint-09.**

## Accepted code and exact verification

| Mechanism | Immutable source | G result | Scope |
| --- | --- | --- | --- |
| B strict budget / durable settlement | `2c52e1fe747627b227b5695e578b800cb7eade8b` | [95 PASS](../checks/2026-10-06-second-wave/b-durability.json) | Real local file/process/middleware and receipt retry/acknowledgment |
| B worker/callback capacity | `fd0a8b0044bb51539d812c2d0957381ed52ed3fd` | [31 PASS](../checks/2026-10-06-second-wave/b-executor.json) | Actual callback capacity plus async artifact-store and HTTP consumers |
| F Lex unique pass dispatch | `00a6eda114b903bc5abe86902cd8372426f739a1` | [24 PASS](../checks/2026-10-06-second-wave/f-lex.json), [fresh reader PASS](../checks/2026-10-06-second-wave/f-lex-fresh-reader.json) | Synthetic ExprAST, actual CLI, persisted report/diff, fresh CAS |

On the composed source312, one affected-consumer wave gave
[58 PASS / zero skips](../checks/2026-10-06-second-wave/checkpoint09-consumers.json).
This covers exactly the four recorded consumer files, not broad E02 replay.
All test source/import origins were isolated and content-pinned before/after;
no dependency installation or production-data read was needed. Complete
moderate outputs and JUnits accompany the receipts. Ruff check/format passed
for all nine changed Python source/test files from090→312
([complete output](../checks/2026-10-06-second-wave/ruff.txt)).

The prior B37 `99.0` admission failure is resolved in the accepted source:
[the unchanged G discriminator](../checks/2026-10-06-second-wave/b37-repaired.json)
now refuses unsupported version and foreign contract without rewriting bytes.
[Actual old-writer compatibility](../checks/2026-10-06-second-wave/actual-old-writer.json)
uses source80d to emit schema1.0 bytes, then source2c52 to read without mutation
and explicitly publish1.1 preserving spend. Original exact input remains in
ignored scratch by hash. `snapshot()` returns a current1.1 in-memory projection
while an untouched legacy disk file stays1.0; that is not evidence of an
on-disk migration. Caller payload digest, external billing, production factory,
power loss, multi-host semantics and complete B37/B38/B66/B78 closure remain
limited/unestablished. The current1.1 decoder's full removal discriminator is
still separate from the old historical wire-removal run.

F code was imported from its three-path implementation, excluding the later
5,984,903-byte compressed/170,873,422-byte expanded diagnostic. G corrected
only its release companion after independent review: actual
`public_stable: polisyos.lex`, completed inventory review, breaking duplicate-
input behavior, and effective version owner `team-architecture`. Basis is the
contract, inventory/reference and lazy-facade export at198/309; G did not
invent a new surface. The [single-fragment compatibility report](../checks/2026-10-06-second-wave/lex-compatibility-release.json)
has zero contract errors/findings. Unique plans and report schema1.0 retain
meaning; users treating repeat IDs as separate checks need distinct identities.
LA-017 stays limited: no current-law/corpus/authority input, and default
Markdown omits the pass plan/artifact refs. F should adopt this published
companion through an append-only integration merge.

B executor acceptance excludes the later Linux process/setup source3f445/fbc5
and aggregate head141. Their kernel-owned process/FD receipts support bounded
Linux review, but native platform/consumer acceptance, B40 absolute invocation
deadline, B39 provider classification, B95 and the full nested bridge remain
pending. A worker-count guard does not establish bounded external backlog.

## Returned owner actions and distinguishing cases

**B cache and CAS.** Head0ebb/source79b has a useful off-loop full-ArtifactRef
recovery path, but the actual225-case cohort is216PASS/9FAIL. Classify the nine
exact failures against the slice base and actual identity/readiness/process
contracts; P41 provenance is `not_established`, not inherited. The default
cache has no entry cap and the shared external queue is unbounded; document a
finite scope or implement its actual bounded quantity before a bounded-cache
claim. Head d6d aggregate is not an admissible all-B merge:309 cases are293PASS/
16FAIL. Four CAS-02 cases reach behavior and fail tenant/import/publication
refusal; twelve spawned children fail importing `core` before the property.
Repair the four runtime classes and child input closure separately, then retain
exact outputs. Neither a tokenizer hash nor adjacent PASS proves token quantity,
NET→C restart, complete source custody or full60-finding closure. Minimal
accepted2c52/fd0 do not import these failing aggregate source units. pool.py and
runner/serialization.py still need their own committed implementation receipts.

**D accounting/provider inlet — HOLD, head653ba2.** Full owner TSV/cards assign
DUR-01 to B-W05 and LLM-01 to B-W09. D changes B's ledger/middleware to a distinct
resource-event/reservation API and schema1.0 while B publishes durable ack/
resolver semantics and schema1.1. There is no shared-path lease or compatible
reconciliation in D's provider-only receipt. B must own one append-only successor
contract; reuse its durable receipt/unknown-ACK semantics for an additive lease
layer, then D rewires producers. G does not resolve these files or rewrite history.
The239-pass receipt targets earlier dcb, not final653. A real gateway divergence
also remains: `_as_float` changes raw present negative cost to0 before typed
response admission; preserved `.raw` is not read by the new extractor. The
actual gateway parser/producer inlet must preserve/reject invalid-present cost
before normalization; test HTTP raw payload→typed response→settlement, including
negative/bool/malformed, finite zero and absence. Do not patch only the later
helper again. Cache billing also trusts class/module/name/cache-hit flags, and
stage attribution trusts caller evaluation IDs: require owner-bound cache/stage
identity or retain explicit non-authoritative limitations.

**D search/transfer — HOLD, heads987/c86 and composed root8eb.** The real
independent NumPy/Cholesky GP oracle supports23PASS on exact87f source; it is a
bounded synthetic fixed-parameter posterior/append result, not full search
closure. The final CAS→WarmStartBridge→SearchLoopRunner→GP test exists but has
no deciding run on the composed tree. Component receipts cannot prove that
composition; run it once after the corrected source freezes. Pareto supplier
has two actual A dependency failures; agree the supplier contract with A and
apply the canonical successor. Neural executed-input tests need a behavioral
prediction/acquisition discriminator rather than markers. Reconcile stale
D-M1/B111 and old state/migration companions. Transfer tests still import
optional hnswlib unconditionally in minimal profile: add explicit selection/
skip, retaining native backend proof where installed. Lesson transfer ages
against target time while local retrieval ages against wall time and clamps
future evidence to age0; fix the common evidence-time quantity or record/test
its exact supported scope. A historical target must not silently admit post-
target evidence as fresh. B129/B133 history/custody and B134 issuer decisions
remain separate. G's ML backend replay is UNRUN, not PASS.

**D stress/champion — HOLD for downstream semantics, head529.** Bounded producer
mechanics have source-bound evidence. B106 still maps optional/no threshold to
score1 without a violation rule; Level5 drops partial/conditional status and
blueprint merge recomputes score from issue counts. Preserve the typed semantic
basis through those actual consumers; falsify the missing-rule/partial cases.
This is the known score-semantics class, not another isolated score patch.
Champion b328 is absent from stress head529; its ten reviewed production blobs
match composed D-root8eb, so its receipt applies there only. Do not claim it
from the stress head. Source/root/per-component receipts need separate identities.

**E joint law — HOLD for general admission, headd2a/source4e7.** Two independent
reviews find accepted weighted laws altered: absolute weight tolerance1e-12
substitutes the first carrier law for another, and clipping uniforms to
[1e-10,1-1e-10] erases admitted positive endpoint atoms of mass5e-11. Establish
one exact canonical row-weight law and a transform preserving every admitted
positive mass, or typed-refuse unrepresentable/ambiguous laws. Generate first/
last/interior tiny atoms, near-equal unequal weights and collapsed CDF variants;
no one-off clipping patch. Independent dyadic paired-row witness: masses1:1:2
for outcomes0,3,9 give E=5.25 and variance15.1875; a256-point complete net should
produce64/64/128 rows. Non-Gaussian Uniform marginals with valid covariance
currently call nominal evaluator before a later uncaught unsupported-law error.
Preflight the actual joint-law family before any callback; counter stays zero
on typed UNKNOWN, with Gaussian/paired-empirical positive controls. No copula
implementation is required merely to refuse this unsupported input. These are
existing B188/B192 law/admission classes deeper under P40. Gaussian/null-space
and canonical bounded-indicator evidence remain useful within their declared
profiles. Draw ledger structure is not generic evaluator/source replay; keep
B194 limited and B201/B202 held. G ran no new numeric E wave. The cited independent
mc.json is unavailable in this head; bring the exact artifact if relying on it.

**E DDM — companion HOLD, head299/source052.** Receipt command/source opacity is
resolved; runtime source did not change after the earlier bounded review.
The same closed schema$id adds four fields: new-reader/old-record works, old
strict-reader/new-record does not. Record that directional migration boundary
and actual internal inventory classification; version identity if old/new
readers must coexist. Current producer validating current schema does not prove
legacy-reader compatibility. Complete feed/now/trigger provenance and R2 signoff
remain not established; LA-054/055 stay partial/limited. Earlier unchanged DoE
and FRC holds remain in [first-wave actions](2026-10-06-first-wave.md).

## Remaining verification and custody

Result importer `--check` passed before pack use; verification.json was read,
then failures-only query and exact sources/cards used. Raw baseline archives,
organization DOCX, actual production law/history and some institutional inputs
remain unavailable to the relevant proof, not invented. Production data stays
local read-only; no blanket dataset requirement or cloud transfer. Linux-only,
Torch/GPyTorch/BoTorch, Ray/Temporal and external-store limitations are explicit.
Common expensive replay/data-dependent closeout remains UNRUN until shared
source freeze and all independent reviews; this checkpoint is not that freeze.
Current architecture/full CI acceptance is not established by these focused
results. No main push is authorized by this checkpoint.

Pattern pass: P27/P31 return shared writers to canonical owners; P29/P32/P37/P38
check real runtime quantities, not receipt labels/markers/hashes of tools;
P35 counts complete diff/output/test sets; P40 groups deeper law/identity/time/
score escapes before repair; P41 preserves unknown red provenance. Archive
cleanup is only after deciding receipts are retained and users/handles checked,
only to local Trash. Trash is never emptied by G.
