# DS11 public-signature population — successor-owner decision

Date: 2026-09-11. Row: `DS11-PUBLIC-SIGNATURE-POPULATION`.
Lane: `codex/owner-residuals`; merge base:
`cc74d65813d7bb1259a0f82f6c3cc8b131661a97`.
Stage 1: decision before execution; no source repair proposed.

## Owner and separate verdict

**OR-DS11-01 — routed-to-another-owner: team-design, DS12 — Public
Publication Foundation, record half.** This is the successor consumer the row
requires. It is not the closed DS11 trust-posture owner. The active
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md`,
**DS12 / Debt rows this slice must close**, explicitly allocates this exact row
and its record-half prerequisite. DS11's own slice, **Remaining debt rows**,
assigns it to DS12/team-design. The narrow DS11-TRUST-POSTURE-DEBT-CLOSURE plan
owns page conformance and explicitly excludes governed publication.

DS12 is already an active-plan destination; no new task ID is invented. Its
capability and actual-record gates are separate. Do not defer the whole signing
mechanism to an institutional appointment: that mechanism already exists.
Do not identify `GY-O0-NC-01` with the data-only first-promotion milestone:
the active DS12 section explicitly distinguishes its field-pilot protection
signal. This lane does not re-adjudicate GY's upstream promotion work.

## Complete starting-state census and independent proof

**OR-DS11-02 — delivered vocabulary first.** The actual producer is
`PublicDecisionVerificationService`; the population adapter is
`PublicVerificationRecordPopulationProvider`; the maintenance consumer is
`PublishedSignatureCustodyWatcher`. Read those source bodies and their callers,
not a predicted name family. The shared primary checker is the existing
`src/polisyos/runtime/quality/production_invocation.py` over all tracked
source/tools/tests. Its persisted receipt covers 2,654 source files, 5,670
current Python files versus 5,669 base files (the added exception test explains
the difference), and no invocation regressions. Its process exit is recorded
separately; the receipt does not establish runtime invocation.

The independent shared census reconciles all 2,654 tracked `src/**/*.py` with
the pinned tree plus recursive filesystem enumeration and AST-parses every
file: 36,135 sync plus 879 async function definitions, no parse errors.
Source-path SHA-256:
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
A separate row AST walk records all references to the delivered classes,
persistence function and `promoted_record` and checks exact test declarations,
including async functions, in `residuals/ds11/raw/census.json`.

**OR-DS11-03 — the property, not a global absence sentence.** The inspected
`public_decision_verification_contracts.py` constrains BOTH the stored
`PublicDecisionVerificationRecord.promoted_record` and the response field to
`Literal[None]`. `_verify_entry` returns authenticated report bytes with
`promoted_public_record_not_established`. The installed population provider's
`resolve` has a nonreceipt-only return type AND unconditionally constructs
`PublicSignaturePopulationNonReceipt`, even after it traverses and verifies
every issued report. Thus this exact production composition cannot supply
an admitted governed member. This is stronger and narrower than claiming no
class under any other name could exist elsewhere. An alternative producer
would still need to replace this admitted intake through its owning DS12 task.

Independent second trace starts at `RuntimeContainer.startup`: it constructs
that exact provider from `self.public_decision_verification_service` and passes
it to `ControlPlaneService`. The latter supplies it to the watcher and installs
`run_published_signature_custody_maintenance` as the embedded worker callback.
The public report service is also reached by the registered issuance and
verification HTTP operations. These traces refute a broad missing-signer or
missing-watcher claim while locating the specific governed record/admission gap.
The September 7 Atlas journal's exact **DS11-PUBLIC-SIGNATURE-POPULATION —
reachable portion and sized residual** records the same distinction; fresh
execution below supplies this lane's evidence rather than borrowing its green.

## Named production caller, receipt, exact reader

**OR-DS11-04 — callers recorded before code.**
`src/polisyos/runtime/http/routes/public_decisions.py` registers POST
`/api/v1/runs/{run_id}/public-verification-record` and public GET
`/api/v1/public-decisions/verification`. `app.py` includes that router and
`RuntimeContainer.startup` installs the population consumer described above.
`ControlPlaneService.run_published_signature_custody_maintenance` calls
`PublishedSignatureCustodyWatcher.scan_once`; `ControlWorker` owns the callback.

These operations are discoverable by HTTP/OpenAPI and the worker composition.
A new `polisyos-tools` command is inappropriate: it would not supply the
resource/tenant authorization and actual promoted-record authority. No new
loose `main()` or command is built. The source checker's registered framework,
callback and receiver blind spot (producers Atlas decision **A2**) applies:
its `uninvoked` classification for these methods is not absence evidence,
and its clean regression result is not a request witness.

The report owner persists signed canonical report/document CAS objects and
an immutable issuance locator. Its `issued_record_ids` is the exact local
inventory reader; `verify` reopens the locator, blob, manifest, signature and
document, checks cryptography and all bindings, and returns typed evidence.
The population provider consumes those results, and `scan_once` persists the
nonreceipt as `scientist.published_signature_custody_scan`. Tests reopen it
through canonical decoding and `PublishedSignatureCustodyScan.model_validate`.
No synthetic signature is installed as a governed population.

## Stage 2: exact existing nodes and unchanged-negative removal

Commit this document first. No tracked production source or existing test is
changed. Run only these exact existing nodes, with complete outputs retained
under the first-commit gitignore `docs/superpowers/journals/residuals/**/raw/`:

1. `tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_real_empty_issuance_slot_does_not_become_watched_empty`
2. `tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_real_signed_report_inventory_is_inspected_but_not_a_governed_population`
3. `tests/unit/scientist/governance/continuous/test_published_signature_custody.py::test_corrupt_actual_report_changes_population_nonreceipt_not_its_markers`
4. `tests/unit/runtime/http/test_public_decision_verification_routes.py::test_owned_run_packet_is_redacted_issued_and_publicly_verified`

The last node makes actual POST/GET requests through the installed app,
authenticates the report, verifies the slot is empty, corrupts the persisted
signature, and checks the same GET refuses for `record_signature_invalid`.
The unit boundary additionally proves that authenticated reports with no
promoted record create zero governed members and a durable nonreceipt.

Removal: AST-select only `_verify_entry`'s
`verification.status is not artifacts.SignatureVerificationStatus.VALID`
refusal and remove it **in memory**, preserving the source and test bytes.
The unchanged HTTP negative must become red at its invalid-authentication
assertion. Restore the exact function code and run that node unchanged again.
The initial decision used `--keep-duplicates`; execution showed pytest's
fixture ordering collapses repeated references to the same Function object.
That run proves the four baseline nodes only and is retained as such. The
corrected isolated raw plugin generates baseline/removal/restored control
phases through an unused fixture parameter on the unchanged HTTP test.
One literal pytest invocation runs that exact node; every phase outcome and
the expected overall exit 1 are retained. The plugin requires pass/fail/pass,
original method restoration and identical source/test hashes at exit.
If any other failure appears, it is unresolved until diagnosed, never a green.

## Pattern pass and acceptance boundary

P01/P02: existing report/adapter/watcher is a real chain; governed record
admission is a distinct producer obligation. P05/P15: report authentication
cannot grant policy authority. P29/P32: verify persisted bytes and corrupt
actual signatures; a field name is not evidence. P35: full tracked AST
census, delivered vocabulary and exact source composition. P37/P38:
`Literal[None]` plus the unconditional nonreceipt is the implementation,
not an inference from a stale missing-producer label. P27/P31: no duplicate
producer and no edits to closed Atlas/DS11 sources. P13: reuse the installed
consumer and route its missing admitted input to the appointed successor.

Acceptance here is the routing verdict and verified retained refusal boundary,
not closure of DS12's record half. That owner still owes governed decision
bytes, issuer/purpose/scope/rule/time admission, publication/withdrawal/
supersession history, a nonempty content-bound population, actual runtime
consumption and its own negative/removal proof. The original governed-signature
closure signal is not replaced by the report test. No governed epoch transition
is proposed from this lane's merge base.
