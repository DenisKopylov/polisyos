# Producers verification completion journal

Lane base: `a534024ee28dfd9ac4fd21be1ff769b253722d8e`.
Attached branch: `codex/producers-verification`.
Worktree: `/Users/deniskopylov/polisyos/.worktrees/producers-verification`.

## Execution contract

The exact requested names were checked before work; neither appeared in the worktree
list and the branch ref did not exist. Ordinary `git worktree add` succeeded at the
requested base. Root serializes commits and shared-file edits. No changes are permitted
to DEBT-REGISTER.md or LEDGER.md; they supply row requirements only and are never evidence
for tree claims. At most three workstreams run concurrently; Foundry research follows
the initial Claim Ledger, global-index and Atlas research. No push or history rewrite.

Stage 1 records one decision per row under docs/superpowers/specs and commits/readbacks
those decisions before source/test changes. Stage 2 verifies existing mechanisms before
repair, with exact named test nodes, production-path negatives and unchanged-negative
removal probes. No directory-wide, backend-wide or CI-parity suites. The shared browser
ports 8017/5177 and browser fixture root are serialized. Individual temporary CAS roots
are isolated. Complete gate output is retained under verification/raw, ignored by the
producers/.gitignore included in the first lane commit. Gate statuses and content hashes
are recorded below after execution; no successful historical handback is a fresh receipt.

## Research measurements

Independent AST census at the lane base: 2,654 tracked src/**/*.py files, identical Git
index and pinned-tree path sets, 2,654 parses, no parse errors. It counts 37,014 function
definitions including 879 AsyncFunctionDef nodes, and 367,214 Call nodes. Path-list SHA-256:
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
Output: `raw/independent-census.log` (hash recorded at closeout). Delivered vocabulary
was discovered by tracing actual persistence readers and callers before querying the
complete set. The source-derived production_invocation module at the base supplies the
separate complete caller audit. Static callback/receiver limitations will be reconciled
against real HTTP/lifecycle execution, never equated with runtime authority.

## Environment

Offline `uv sync --offline --frozen --extra lint --extra test --extra runtime` returned 1:
the pinned jaxlib wheel was absent from the cache. The online frozen invocation then
returned 0 and provisioned this worktree's own Python 3.14.3 environment; no dependency
or lockfile was changed. `corepack pnpm install --frozen-lockfile` returned 0 before any
TypeScript scanner/test. These are setup outcomes, not product gate verdicts. Complete
outputs remain in raw/environment-sync.log, raw/environment-online-sync.log and
raw/pnpm-install.log. The ordinary test command will be `uv run pytest` with named nodes.

## Row dispositions

**Lane status: complete-pending-an-architect-decision.** No new producer was built.
The three implemented mechanisms were already present at the lane base; the changes
strengthen production-route verification. This journal does not claim four debt rows
closed, default Claim root authority installed, or Foundry authority established.

| Row | Measured disposition | Remaining boundary / named destination |
| --- | --- | --- |
| `claim-ledger-supersession-owner-event-producer-missing` | **Already existed and verified with an explicit authority limit.** The real CAS candidate, verified append, replay and export are present; the strengthened named integration witness now traverses HTTP. | Default owner is unappointed. Positive HTTP verification uses explicit test-only root/issuance/appointment dependencies through the existing dev embedding seam. Team-scientist / Claim Ledger owner and architect must allocate real root-trust/admission composition and appointment. No matching successor task was established in the active plans; registration is owed, not discharged by an invented identifier. |
| `global-case-index-producer-missing` | **Already existed and verified.** Canonical persisted S2 bindings feed the default provider and real HTTP response. The exact closure-identity test passes, with an added content-mismatch negative and persisted refusal readback. | Tenant/cell-visible S2 inventory only; terminality and policy authority remain unestablished. Team-runtime and Atlas DS12 own producer scope/allocation disposition; DS13's browsing/history work is separate. No dependent row is closed here. |
| `atlas-public-verification-record-bridge` | **Already existed and verified against the stated bridge signal.** A server-issued persisted report reaches the real public route; signature corruption removes authentication and the visible document. | Report authentication is narrower than current policy authority. Promoted-record and PV-K01 authority slots remain typed-empty. Team-design / public-surface owner and architect own the protected row's disposition. |
| `foundry-runtime-authority-capabilities-absent` | **Honestly refused construction, with measured evidence and an actual scheduling proposal.** All four positive authority capabilities remain absent despite substantial candidate machinery. | `FR-AUTH-01` now exists as a proposed active-plan task. Architect acceptance, accountable allocation/order and the debt-row pointer remain outstanding. A proposed task is not an architect scheduling act. |

## Stage 1 commit boundary

The Claim Ledger, global-index and Atlas decisions plus the raw ignore policy were
committed at `cc79d84fd70466c15d9c5b371a3d81a69397293e`. Root asserted attached branch
identity and compared every committed file's `git show HEAD:path` bytes to its worktree
bytes after commit. All matched. Source and tests remained at the lane base. Independent
Atlas spec review found no consequential gap; it confirmed the signature-corruption
negative reaches the live GET and drives the real route indicator.

The complete production_invocation audit returned 0, with equal base/current hashes
over 5,669 tracked src/tools/tests Python files and no regressions; receipt
`raw/base-invocation.json@sha256:d85dd870812f1655103135454c3bf1cbfdcc86602b182448664424801100b099`.
It reports target HTTP/callback methods as uninvoked under its documented static model.
This is not source absence and not wiring proof. The separate AST source census and
real HTTP gates resolve that distinction. The 7.7 MB recomputable view stays ignored.

Foundry is sequenced after the initial three research scopes. Its actual proposed task
is `FR-AUTH-01` in `docs/plans/active/foundry-runtime-authority.md`. This is an active-plan
proposal created under the scheduling option, not an architect appointment or row-link
receipt. Architect acceptance, allocation and linkage remain outstanding.


## Stage 2 boundary and reviewed delivery

The Foundry decision and actual proposed task were committed at
`07a01f44a8ae6f138424d44d4efa9cac75889113`. Root read all four decision documents
and the task back from the attached branch, compared bytes with the worktree, and
verified that source/tests still matched the lane base before Stage 2 started.
The first three source hypotheses therefore became verification tasks, not duplicate
producer construction.

Test/probe/runner delivery was committed at
`0c5ad474a8e77760686981d46350aa3bfaeb743d` and all nine files were read back from
that attached branch. Production `src/`, dependency files, governed registries,
DEBT-REGISTER and LEDGER are unchanged. No governed epoch was bumped. Claim and case
changes received independent review; the final probe/runner review found no blocking
finding. The known Foundry setup failure was classified as the same declared missing
verification precondition, not an ambient-authority escape.

### Decision sources and original delivery provenance

These decision documents carry the source-blob citations and independently traced
call/reader chains; their finding IDs are the warrant for the row dispositions:

- `docs/superpowers/specs/2026-09-10-producers-claim-ledger.md@8926c94ab67aa2ef5a85d814bb9649efcfccffea`, CL-01 through CL-05.
- `docs/superpowers/specs/2026-09-10-producers-global-index.md@214830a1979758b3835b9d64669e1f3dab565e0b`, GI-F01 through GI-F06.
- `docs/superpowers/specs/2026-09-10-producers-atlas-verification.md@d085e3221016c1ca847eb1e4b93eb6a7603148b6`, A1 through A6 (including the committed generated-example follow-through).
- `docs/superpowers/specs/2026-09-10-producers-foundry-authority.md@bfa78b3ff0c5b27d03ae3773a82af396a540b2dd`, FA-F01 through FA-F05.
- `docs/plans/active/foundry-runtime-authority.md@d9d8bc7cd2c3a9edaaa598d930ea0a67f50dd321`, proposed task FR-AUTH-01, not an appointment.

The September 7 missing-producers wave already supplied Claim supersession at
`37caf67c35a3a24db15f8e9263b32bd18ad8ee7b` and the global index at
`d207b82f5f231fc0ea8653027b2576b33d6a71b2`; both are ancestors of the lane base.
Their source changes and current execution establish delivery, not the older
handback's title. Atlas's report bridge was delivered separately at
`da73f861dbffc62db6a97a0013e4a0c99f59bede`, also an ancestor. The existing missing
labels are therefore not fresh source-absence facts.

### Caller, persisted artifact, exact reader and falsifier

**Claim Ledger.** Registered HTTP operation
`POST /api/v1/control/decision-validity/events` calls the real control service,
monitor bridge and `claim_owner.produce_owner_event_candidate`, then
`append_verified_owner_event`. This is a discoverable HTTP lifecycle operation;
a new polisyos-tools command would duplicate its admission surface. The positive
receiver still requires explicit embedding; the default factory returns
`UnappointedClaimLedgerOwner`, not the repository owner used by the test.

The producer persists `ClaimSupersessionOwnerEvent` with exact monitor, successor,
prior-ledger, purpose/rule and legal-evidence bindings. The owner persists a distinct
owner bridge and new immutable ledger/head. `load_lifecycle_bridge_result`,
`resolve_claim_supersession_owner_event`, closed-head replay and `export_current`
read back the exact persisted chain. The HTTP witness requires one head-generation
advance, unchanged predecessor bytes, idempotent retry and no automatic admission
of the separately referenced successor as published authority.

Real negatives cover unsigned, revoked, wrong-scope, wrong-vocabulary and fake
successor evidence. Separate HTTP absent/wrong-vocabulary monitors return
422 `monitor_event_unresolvable` before any owner effect. The default HTTP request
returns the actual typed `claim_head_absent` outcome in its persisted bridge result.
Removing successor identity binding makes the unchanged fake-successor negative
admit the event; removing the bridge's producer call removes the required persisted
production outcome; removing supersession application leaves the authoritative
export's superseded list empty. All three isolated probes returned semantic red,
then the unchanged normal final wave passed. Test trust is synthetic and explicitly
labelled; it does not establish a real institutional appointment or default positive
production deployment.

**Global case index.** Registered HTTP operation
`POST /api/v1/control/capabilities/search` enters the default
`GlobalCaseIndexCapabilityDiscoveryProvider.search` and
`GlobalCaseIndexProducer.produce`. Its real source caller is the existing S2 design
search operation, which persists the canonical run-bound design record binding,
design record and search ledger. The producer enumerates the complete visible CAS
binding set, verifies each linked identity/provenance, and persists
`runtime.global_case_index` / `policyos.global_case_index.v1`. It verifies CAS content
and reads the exact bytes back through `GlobalCaseIndexSnapshot.model_validate_json`
before returning. Provider execution and HTTP response artifacts are also persisted.
This HTTP discovery flow needs no second command entry point.

The new negative creates a real, CAS-valid binding with the correct schema and
producer but a case identity inconsistent with its retained ledger. The live default
provider emits `case:case_index_binding_content_mismatch`, no results, and
`producer_unavailable`; the response is read back from CAS and equals the actual
HTTP response. Removing the real source-reader call makes this unchanged negative
return `recall_unmeasured` instead and fail. This is content verification, not a
keyword or missing-provider switch. The normal final wave passes after removal.

**Atlas.** The authenticated registered POST
`/api/v1/runs/{run_id}/public-verification-record` resolves/redacts the owned run
packet and calls `PublicDecisionVerificationService.issue`. It persists the exact
public document, signed report and immutable issuance index; its verifier reads
retained bytes through the signed-evidence repository and `_verify_entry`.
Anonymous GET `/api/v1/public-decisions/verification` supplies the browser's strict
response-bound authentication state. New service construction can read the retained
index; reads do not re-sign. This is a registered API/public-route workflow, not a
standalone operator producer needing a new polisyos-tools command.

A forbidden packet reaches the real publication refusal before record/link issuance.
The existing browser witness first displays the real authenticated report, zeros the
same retained signature, reloads and requires the server's signature-invalid reason
and absence of the authenticated document/indicator. It restores the original signature
in `finally`. Separately removing the server's signature rejection in memory makes the
unchanged HTTP corruption negative receive `verified` instead of `invalid`, a semantic
failure. The normal Python and browser gates pass. Neither report authentication nor
the test keys fill the promoted-record or current-authority slots.

**Foundry.** The public snapshot builders call the existing production authority
factory. Its no-cutoff implementation refuses before candidate machinery. A barriered
writer mutation after the second post-fstat walk preserves equal candidate manifests,
demonstrating why observation is not a writer-independent cutoff. Those two exact
witnesses and the HTTP worker's diagnostic-exception separation witness pass. No new
producer, command, signer, registry status or receipt shell was added.

### Verification results and limits

`run_checks.py@ae5069cd8f4486d34928d3c4d71e428725c5f938` (in this journal directory)
is the final runner. `--list` prints every file and parameterized node explicitly.
Each invocation launches exactly one gate and returns its actual exit code, preserving
complete stdout/stderr and elapsed time under a fresh raw tag. Removal expectation
metadata is not a verdict: the decisive assertion must actually be reached.

Run from `policy-engine`, for example:

```bash
python3 docs/superpowers/journals/producers/verification/run_checks.py claim
```

Gate names: `claim`, `case`, `atlas`, `atlas-browser`, `foundry`, `lint`, `openapi`, `guardrails`.
Probe names: `claim-binding-removal`, `claim-caller-removal`,
`claim-append-removal`, `case-removal`, `atlas-removal`, `foundry-removal`, plus `openapi-corruption` for deliberate generated-example drift.
There are no file-wide or directory-wide pytest selectors. Final Python result counts
come from all PASSED/FAILED node records in each complete final log: Claim 13/13,
case 15/15, Atlas 5/5. The browser gate selected exactly one named test and passed.
No tests are skipped in those deciding waves. Five Claim/case/Atlas source-removal
probes reached their intended failed assertions; normal fresh-process waves then passed.

Foundry's six-node gate returned **1: three passed and three failed**. The failed
public-builder and two N8 nodes stop at `DigestPredicateMismatch` before their target
assertions. The attempted Foundry removal also returns 1 at that precondition, so
**no successful Foundry removal receipt is claimed**. The three target assertions
remain unverified by this run. The genuine writer-race falsifier and cutoff refusal
still establish the reason to decline constructing an authority-looking shell.

### Incidental finding: inherited Foundry dependency-pin drift

The exact six-node command was replayed at the actual lane base in a self-contained
local Git clone, with its own frozen Python environment: the same three passes and
three `DigestPredicateMismatch` failures recur. The first shared-object replay was
rejected by N8's Git-semantics boundary; that output is retained but is not used to
claim those two failures reproduced. Root used ordinary `git repack` to make the
scratch clone self-contained, then reran the unchanged command. No primary worktree
or another lane's branch was moved.

The failing profile helper reads exactly its profile registry, pyproject and lock
bytes. The N8 precondition resolves the complete `_DEPENDENCY_SOURCE_PATHS` set:
**8 tracked files = 4 TOML + 1 lock + 3 Python**, all identical at base and delivered
HEAD. The broader authority source set is **12 = 4 TOML + 1 lock + 7 Python** and
is an additional conservative check, not a claim that positive authority ran.
At freeze `0c5ad474a8e77760686981d46350aa3bfaeb743d`, the complete 16-path lane delta intersects both sets at zero. The subsequent seventeenth path is the OpenAPI snapshot, outside both input sets. The source-bound
failure precedes package observation, legacy governing evaluation and supplied
pass/fail assertions. This supports inherited attribution for these digest failures,
not a blanket assertion that any future Foundry failure is inherited.

The profile registry
`architecture/production_quality/method_catalog_dependency_profiles.toml@bff19198751c6a296c4225e34996d763d64866f5`
still declares pyproject digest `sha256:a25bc559fb92ba39e357babc2961f4e8981b39bb51e599632a8224dcfed52484`;
the domain-framed digest of
`pyproject.toml@0deaec76d7df4f8a2537e539aa0de892aa36382c`
is `sha256:fef7f365eaab8bf145a8f93927a13887f7591414ac693dcb4551a8fea7d22b87`.
The lock pin also differs: declared
`sha256:ed542325c18b409047b5c81bfff3f242ca8ab6c22591b43a135d0e6caa1b4d68`,
observed `sha256:b72ae43724176606d0ec67bed40a29cde0529185be922fc60bd1add06bd6486d`
for `uv.lock@8ab2864e371a710f39f3a8f8b36b4d7fd4344cb2`.
The lock mismatch is a separately recomputed latent failure; all three observed
failures stop at pyproject first. No pin is changed in this verification lane.

**Destination:** Foundry dependency-profile registry owner, with the architect to
allocate the maintenance follow-up. The existing
`tools/devx/foundry/sync_dependency_profile.py` `regenerate-owner` operation owns
rebinding profile and purpose digests; then run its `--check` and
`--corrupt-field-drift-check` plus these exact failed nodes. This maintenance is
separate from FR-AUTH-01's four missing authority capabilities. It does not reopen
or modify either already-closed sibling lane.

### Other findings routed

- **Claim default positive composition:** team-scientist / Claim Ledger owner and
  architect. The requested follow-up is **Claim Ledger production root-trust and admission composition**. This named work is **not registered in an active plan** by this lane; the architect must register and allocate it. Its real root-policy, issuance-verifier and authority prerequisites remain explicit. Institutional
  appointment remains a distinct typed-empty prerequisite.
- **Global inventory coverage/allocation:** team-runtime with Atlas DS12; preserve
  `s2_bindings_only` and `terminality_not_established`. DS13 history/browse work is
  its own scope. Do not count tenant-visible S2 records as all possible policy cases.
- **Atlas authority residue:** public-surface owner / architect. Report authentication
  does not establish current policy authority; typed-empty slots are the intended
  boundary, not a reason to add a projection signer.
- **Static invocation model limits:** runtime quality / production_invocation owner.
  Its unresolved HTTP callbacks and receiver dispatch are documented bounded static
  limitations, reconciled here by real caller tests; no new checker or false static
  positive was built.
- **Worktree setup:** lane harness. Missing read-only catalog linkage caused initial
  HTTP/browser startup failures. The documented ignored symlink now targets the
  existing read-only production data; no data is written. Offline wheel-cache misses
  were resolved with frozen online provisioning without dependency changes.
- **Harness selection/fixture issues:** lane harness, corrected locally. A misspelled
  initial Claim path, invalid test tenant UUID, and browser grep anchored before the
  full Playwright title produced collection/setup failures, not product negatives.
  The corrected selector's listing reports one file/one browser node. A baseline run
  overlapping a briefly applied/restored fixture edit was invalidated and rerun with
  immutable inputs; both outputs are retained.
- **Metrics bind warning:** runtime observability owner. Concurrent HTTP startup can
  report an occupied Prometheus port and disable that exporter; API assertions still
  execute. No existing process was killed or reconfigured to manufacture green.
- **Standalone Atlas status-retirement gate:** Atlas architecture owner. Guardrails
  explicitly says it is a separate gate. It is outside this producer-verification
  scope and is not claimed to have run.

Closeout pattern pass reopened the failure/repair register. P01/P02/P27 are addressed
by reuse and real HTTP callers; P29/P32 by exact readback and source-property removal;
P35/P38 by complete AST source counts and explicit static-vs-runtime limits; P37 by
refusing authority from synthetic or candidate evidence; P40 by retaining the declared
Foundry capability boundary; P41 by exact slice-base replay and complete input
intersection before attributing the digest red. No new failure-pattern class was
found, so no pattern/register edit was made.


### Guardrail finding and mandatory generated-example refresh

The initial complete `uv run polisyos-tools architecture guardrails check` returned
**1 (FAILED)** in 235.590 seconds, with exactly one finding: the generated Runtime
OpenAPI snapshot differs. Required freshness environments ran successfully; this was
not exit 2 / UNRUN. Runtime API client, dashboard types and trust-claim posture outputs
were clean. No deep-import creep was reported, and guardrails sync was not run.
The exact command also returned 1 at the lane base with the same family finding.

That replay alone does not justify carrying the finding. The canonical OpenAPI
producer includes a live confidence-ledger example whose real worker reads a complete
6,416-binding denominator: **5,675 files (5,669 Python + 3 JSON + 2 TOML + 1 lock),
739 directories and 2 missing paths**. All four edited test files are in the actual
worker receipt. The five journal Python scripts are excluded. The normal generator
and independently instrumented generator emitted identical bytes, binding the trace
to the real output. The trace's own raw-output directory observations are not used
as the worker's dependency denominator.

All 5,675 bound file paths exist at the base. Complete directory identities match
Git's immediate-child listings; the only base-to-lane file-identity differences in
that bound set are our four test edits. Replacing only those exact four hashes with
base values changes the aggregate from
`sha256:48562e9e664421d3aa372b3a1e6f579c6aef8af133b51c9553a7b0a0ae7696a1`
to the controlled base prediction
`sha256:82e6c7d13492f810d07ae0104d6f252faf5825555ca8b1f6df2bc4beda5bf802`.
This substitution is a controlled recomputation, not a generated base receipt. The
count change from the committed example's 6,410 to 6,416 predates this lane; our
contribution is the test-byte identity change. Therefore this lane owns its generated
example refresh even though the base was also stale.

A6 was committed and read back at `6c0ae40ef` before the snapshot changed. The
`runtime-openapi-snapshot` family's declared freshness rule explicitly covers changes
to owner-validator consulted dependencies. The canonical generator output was adopted
with **exactly ten scalar changes in that one existing example**: dependency/count and
derived receipt, projection and replay identities. There are no route, request/response
schema or other payload changes, and no JSON reformat. Compatibility is unchanged;
no generated-client type or governed epoch/rule version is changed from the lane base.

Source ownership: team-polisyos (artifact family), team-runtime (API version).
The actual test-byte reader is `acquisition_strangle_receipt` in
`src/polisyos/runtime/quality/acquisition_planner.py@83a3c5a07070f1140c142a92dd2fc654779737d7`,
called while assembling the acquisition receipt. The generator and governing family
are pinned in A6. This closes the lane-owned companion finding through the existing
owner path; it does not repair unrelated Foundry dependency pins or add any authority
capability. Final focused API contract, deliberate corrupt-field and guardrail verdicts
are recorded below after execution.


The focused OpenAPI contract check returned **0** in 52.252 seconds. Its deliberate
single-field corruption returned **1** in 51.575 seconds, specifically detecting
`bound_dependency_count` 6,417 instead of the recomputed 6,416 while the retained
hashes were unchanged. The production snapshot remained intact. Delta-only review
of A6 and the runner found no blocking issue. Source/tests remain frozen; the final
post-refresh guardrail wave follows this generated-companion commit.


## Final verdict and retained receipts

The post-refresh architecture gate returned **0 (PASSED)** in **202.378 seconds**.
All four default generated-artifact families, including the refreshed OpenAPI
snapshot, were fresh. There was no incomplete freshness environment, no exit 2
UNRUN verdict, no deep-import baseline registration and no guardrails sync.
The final focused contract check is 0; its corrupt-field counterexample is 1 for
actual drift. The unchanged producer verification waves total **33 passed Python
nodes plus one passed browser node**. Foundry contributes **3 passed / 3 failed**
from its six explicitly selected nodes; the three inherited digest failures and
unreached removal assertion are retained, not relabelled as passed or skipped.

The refreshed governed companion is
`schemas/runtime_api_v1.openapi.json@f6291aec65b661ef12c125ea828849696487e362`,
compared with base blob `56229017e932a241a79b3b249959f6bab2e60bd9`:
10 added / 10 removed lines, exactly the ten computed example scalars described
in A6. The identical normal and traced generated JSON copies and derived diff views
are represented by these two Git blobs; full generator/trace logs and measured
binding receipts remain under raw. The lane-created clean exact-base clone was
removed after its outputs were retained; no stale worktree registration was added
for that replay.

All paths below are relative to this journal directory unless they begin with
`tests/` or `schemas/` (product-root paths). `sha256:` identifies retained local
output bytes; unprefixed 40-character values identify tracked Git blobs. Complete
stdout/stderr is retained, including failed setup attempts; the table labels the
verdict rather than counting every exit 1 as a successful negative. Runner JSON
sidecars preserve exact argv, cwd, elapsed time and actual exit codes for its gates.

### Deciding gates and removal probes

| Complete output | Result / role |
| --- | --- |
| `raw/claim-final.log@sha256:91ec3187542dd11ffb9d7b77bdcbb20e4acc6781f8fca35ae02b7e46ed1f5954` | 0; 13 passed, restored normal HTTP/owner/importer wave |
| `raw/case-final.log@sha256:4f0aa783711153de17c20402c4e6b9cc729bde8174b3d62ed17ce3fea502be37` | 0; 15 passed, restored normal HTTP/index wave |
| `raw/atlas-final.log@sha256:b91ed3245d91821b54866555153c31c1644c2713249932036838f29a7b2457aa` | 0; 5 passed, restored normal HTTP/service/configuration wave |
| `raw/atlas-browser-final.log@sha256:754b13b28b8a0afe90d7800cc327fcbb81e0cf98f370a06b4494d15fc5b3ec3a` | 0; exactly one live browser witness passed |
| `raw/claim-probe-binding.log@sha256:f565d44738b4a2a7e77d96b97e35593f9cc878ef90925239a14498255177ac08` | 1 expected; unchanged fake-successor negative admitted the forged identity |
| `raw/claim-probe-caller.log@sha256:7ff575a6c003e88a31584ac0513720c8862ccf871be3d88fe67bcc3469e104e2` | 1 expected; unchanged HTTP negative lost the persisted producer outcome |
| `raw/claim-probe-append.log@sha256:5d3cf998eb5ca16cf68dd8fe2d6e918584d53597c7ba87273c46f83f024aef53` | 1 expected; unchanged HTTP positive exported no superseded predecessor |
| `raw/case-source-reader-removal.log@sha256:b448c2b4ebc42c9e7db27f00ea920bfb549fdfa14e5d7c5976c38a4cf2616b80` | 1 expected; unchanged HTTP negative returned recall_unmeasured instead of producer_unavailable |
| `raw/atlas-removal-ready.log@sha256:045beda6539a29c00f777ac8951f9e4c2b2fce1c70b45d7f02ceafc90e93fd16` | 1 expected; unchanged signature-corruption negative received verified instead of invalid |
| `raw/foundry-before-removal.log@sha256:b7fe254d02d781996e4bb70ffe04284db126994a7aeca3059e60be3a6adb0987` | 1; 3 passed / 3 digest-precondition failures, not six verified properties |
| `raw/foundry-base-replay-self-contained.log@sha256:a021e8688a8c0fdad695a8c3616498ac1d56006a91badc98d7cfc4c1d8864122` | 1; exact-base replay, same 3 passed / 3 digest-precondition failures |
| `raw/foundry-removal-attempt.log@sha256:82cd350754b694efbd90481cb795704424af16b8ab7bb6dbb6955263b71952c5` | 1; digest precondition failed before target assertion; NO removal receipt |
| `raw/openapi-final.log@sha256:ed841e011969c1e9b9b94b1f99fd566e9c4390620d6c33622c0ff5656de17407` | 0; focused canonical Runtime API contract check |
| `raw/openapi-corruption-final.log@sha256:2b1effdbddc554f1ce3184cdcfcbd9a9e6c7e7f7ff72b8c6f5be6173ceb8859c` | 1 expected; exact recomputation rejects the single count corruption |
| `raw/guardrails-final.log@sha256:4ef9405820e578245b72346c34cee15a03c4afe56aa915f397129be55d5a1362` | 1 FAILED; initial complete verdict, sole OpenAPI freshness finding |
| `raw/guardrails-base-replay.log@sha256:957cb4379ef35cbe9871f0de948a0b5f4761cc01879ce629672cfed5a96f519a` | 1 FAILED; same family at base, but current input intersection was nonzero |
| `raw/guardrails-after-refresh.log@sha256:9fa49e2a57ea7578043fb7d62548f19b0e0f0734b1ace31d1943d46686829e18` | 0 PASSED; final complete post-refresh verdict |
| `raw/final-runner-lint.log@sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | 0; exact changed tests and probe/runner files |
| `raw/claim-baseline.log@sha256:8b309528db02b578b0986512dccdfa1d4404a68831fb0cd03030868b61572065` | 0 immutable baseline rerun; preceding overlapping run explicitly invalidated |
| `raw/claim-http-positive-2.log@sha256:617278cc36024ef81cc5e22304caf68bdc8ee1c49225f31f0ddfcb663ee8905a` | 0; first successful strengthened HTTP positive |
| `raw/claim-owner-negatives.log@sha256:91afb267eb693ba4f084d786b4e1ab827724f32dd41b867b1ffdf474733d015e` | 0; eight exact owner negatives |
| `raw/claim-http-negatives-1.log@sha256:423d5c0708d5f755bb7f4481eca22cc787cf550662ef2c66ff42f998eb4a9b6d` | 0; default + two fake HTTP negatives and exact existing importer |
| `raw/case-readonly-data-wave.log@sha256:04c97bf860b8230219f5c4e953b2a18a91b9d27dc466edd2f5f90cea6e8d3e37` | 0; five exact HTTP/index nodes after setup correction |
| `raw/case-restored-negative.log@sha256:ef69f005c26f40d9516d2d9c0928867cfbf5f8abd9bb2d8e243302047dcb1853` | 0; fresh unchanged negative after case source-reader removal |
| `raw/atlas-python-ready.log@sha256:4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5` | 0; five exact Python nodes after setup correction |
| `raw/base-invocation.log@sha256:6f2ca72784441d6fa8820f9bd477bbf5bc200ba4bf94c53106bb719a58d1bc2b` | 0; source-derived audit, static diagnostic only |
| `raw/independent-census.log@sha256:bbb3918773b5b13111e22831ee2fdb53f6410df1d6663a172533daa074b39d76` | complete independent AST source denominator and delivered-vocabulary cross-check |
| `raw/foundry-input-reconciliation.log@sha256:dafd2b971c1b6a39e57d487f944b4f7d4cbf489899d8126bd1850d0afc0a0ade` | complete 8/12 source-input sets, exact-base identities and empty lane intersections |


### Setup and intermediate outputs retained without promoting their verdicts

These are complete supporting outputs. Missing-catalog startup, the first browser
selector, the first invalid Claim fixture, pre-fix lint and the shared-object base
replay are explicitly not deciding product/removal evidence. Their corrected deciding
runs are above. Offline cache failures and online/frozen setup successes are described
in the environment section; they are not product verdicts.

- `raw/atlas-browser-ready.log@sha256:7a66eb790506474d2759f134cfe2b7416aa990fccfe9d0def6d13faeffe9eea4`
- `raw/atlas-browser.log@sha256:748484230d43e25887d81cc65d63c13716094b1f101c43830e226583dbc4ee8f`
- `raw/atlas-python.log@sha256:5fc42d5664332a19212a6ab6bf90ae67d3b0e8fe93b842ff13d638bd87bdc76b`
- `raw/atlas-removal.log@sha256:179700beb9015b989ffdfdb7cbfa2e909393516b53d9fc1ae95e88416d106439`
- `raw/base-replay-cleanup.log@sha256:1f0a222963ff0558d93953f64c6594126869a42821728e64605a3236677bff08`
- `raw/base-replay-environment.log@sha256:1a8d8ac37e7d78a1f4ce2890ada52e0381641c548c01153a7d245857878b6db8`
- `raw/base-replay-online-environment.log@sha256:233fe8eaeb1b6098d7caf6490b91b711aa0a39b8a2f099b31357c55694b64c92`
- `raw/base-replay-pnpm.log@sha256:7c4a6f4d24f2e9ae2edcb6b39c9c0dc8a29a7c0d488b48893e360969d3d42185`
- `raw/case-baseline.log@sha256:2580165d1c4d10d4d6091185c0cf94ab3c0b2193356d31282c3c14270f7fb4f2`
- `raw/case-lint.log@sha256:f3241888b679ef4374e4e7e5e1d2a53b7304c8fc82055b1ab1f73e832c14a3e9`
- `raw/claim-http-positive-1.log@sha256:125819b7776f3ad204c40123ecb82292a4f6df3077856e1ea29b7b5e5eab0e5a`
- `raw/claim-lint-before.log@sha256:912229a1730da2768ed537af46c796a41460c7bb7e9d4fc7851be6f8523520d9`
- `raw/claim-lint.log@sha256:7e37d6a1b5cab8dea6339bf87acb17a473ad26cefa2e4e642b5e4bf735e36d51`
- `raw/environment-online-sync.log@sha256:15bca0d8e16d204810d74900cd9ba7af53c5b7c6a9650a1416a60d587bf7f705`
- `raw/environment-sync.log@sha256:1a8d8ac37e7d78a1f4ce2890ada52e0381641c548c01153a7d245857878b6db8`
- `raw/final-collection.log@sha256:0de9eb9e06ab36c824eb70ebf9bf9181c1fb4c067d2005e3ab97841466c36622`
- `raw/final-lint-1.log@sha256:76764dc684396726aa76e81fd4d4229009a1c6545d916ac00ebf1662da5893f0`
- `raw/final-lint-2.log@sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`
- `raw/foundry-base-replay.log@sha256:37632027af1207381572ead938893c727f06d8f1a534d895701af11ee820eecd`
- `raw/pnpm-install.log@sha256:9eda181b24d2893214d08625e9fb28b708ef57ca6bf3f8fdde5d69addc2065cd`


### Bound OpenAPI diagnosis and execution artifacts

- `raw/openapi-diagnostic/generator.log@sha256:75da777a2fb53956f4afbee5cb833bcadb49a9dacbaa7261e4382c1b4d84afd5`
- `raw/openapi-diagnostic/traced-generator.log@sha256:4a14c000f67d1a8127d928f76f151ba04c44749a236618ae231780e7ec993404`
- `raw/openapi-diagnostic/worker-receipts.json@sha256:898fee2a3c245adeb53dd22fa02250e20a02c043d166d3ba2f2f3694d5e598a2`
- `raw/openapi-diagnostic/generator-observed-bindings.json@sha256:078e6c52eda33aa9fb704973caf01e242490e51566aaea5c0de17c1f0b706fc2`
- `raw/openapi-diagnostic/intersection-report.json@sha256:2a503bd576be6c6f0bec8bbdfe4fd71998a4e5b3219b5dd93c4094b4ec279871`
- `raw/openapi-diagnostic/base-substitution-report.json@sha256:0acf29d7a458c0b12fba65e6c1bde6108fb75150b87e644e6b59ac3467b1e831`
- `raw/openapi-corruption-final-corrupted-openapi.json@sha256:e78a81ed9690a080c7a7ffdf8333a2609e09e759c1a24ab12fe6cf3f1063134b`


### Tracked verification delivery

The exact-node runner and probes are execution receipts' reproducible selectors and
mutations, not new production callers. Test authority fixtures remain explicitly
synthetic. These files were read from their committed branch blobs after writing:

- `docs/superpowers/journals/producers/.gitignore@9f7bba6df15ac9189b69ca71737c9453fab73670`
- `docs/superpowers/journals/producers/verification/run_checks.py@ae5069cd8f4486d34928d3c4d71e428725c5f938`
- `docs/superpowers/journals/producers/verification/claim_probes.py@5369a97426d5c48132d3a6d806e522ca0f2e4a12`
- `docs/superpowers/journals/producers/verification/case_probe.py@13d7b7c23d194f9b6a9dfcd784e7ef8423626594`
- `docs/superpowers/journals/producers/verification/atlas_probe.py@2f4fd0986568ed1675b645e6642e1b8b9e7b472b`
- `docs/superpowers/journals/producers/verification/foundry_probe.py@c350957c047e7fd2745b997172eb5dea3bfab99e`
- `tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py@a0ce5ba4d674b580d2809047496caff85ebc8008`
- `tests/unit/scientist/governance/continuous/test_owner_event_producer.py@805e12edcdef7987cb87cb6868f2c9df384ab4d7`
- `tests/unit/runtime/http/test_capability_discovery_api.py@ad843625970cdc6f8bd81337688970d18c925e6a`
- `tests/unit/runtime/http/test_runtime_api_authz.py@8684faf80bb3ff389a6496c3e5b4783c57848a60`


Final branch readback checks the complete 17-path lane delta, attached branch and
base ancestry, exact committed bytes, and the unchanged production-source/protected
file sets. The final record-only commit adds no input to the measured owner basis,
so the completed source/test/generated-artifact wave is not repeated for journal
text. Local branch and worktree are retained for the architect; nothing is pushed.
