# Stage 2 — recomputable candidate refusals reach DS15

This bounded bridge was selected by integrated review CV-IR01 and implemented
only after Stage 1 commit `9ccb4c148` was read back from the lane branch. The
research did not authorize any new positive domain meaning. The independent
engineering link consumes existing AQ1 candidate process results.

## What changed and why

The existing Runtime non-data bridge now has an operator CLI. It accepts explicit
request and planner-gap JSON, checks their claim/gap identities against a named
canonical census route, fingerprints its whole finite JSON object through the
existing `polisyos.pdc.gy_recorded_content_hash.v1` owner (including temporal fields),
calls the canonical planner and AQ1 producer, and persists
a content-bound route-to-receipt bundle in a dedicated source namespace. An empty
demand is an explicitly unknown candidate, not an invented target or domain fact.

The canonical source reader verifies the receipt through AQ1, verifies and
recomputes its planner report, checks exact route/claim/gap bindings, and records
every consulted CAS blob/manifest plus current census and bundle bytes. An unreadable
or missing consulted dependency cannot become a green absence. The fixed namespace
rejects symlink redirects, including redirects to another store inside the governed
root; read-side construction must not create missing CAS directories.

`GovernedProjectionService.get(ACQUISITION_GROWTH)` supplies those verified results
to the existing projection. Its independent child worker rereads the owner sources,
recomputes the same route payload, and checks the exact input denominator. Existing
`StructuralRouteProjection` fields carry all acquisition types, the resolution state
and all refusal reasons. Their gap class stays `not_established` and action stays
`blocked`. Existing `AcquisitionRouteDetail` renders these fields without an action.
No public DTO, OpenAPI snapshot or renderer implementation changed.

Absent optional bundle preserves the historical surface without claiming that
non-data capability is absent. A present invalid bundle yields `invalid_source`.
Such an invalid packet identifies only bytes actually observed before refusal;
its `non-data-source-unverified` address does not pretend to identify a complete
unreadable source family.

## Ownership and limits

This lane retains `ds15-int-r2-gap-acquisition-case-union` under CV-OWN-01. AQ1/Fabric
owns candidate intake/receipt verification; Runtime owns planner orchestration and
this operator bridge; DS15 owns presentation; VC1 and the relevant domain owners
retain semantic vocabulary registration and admission work. The current acquisition
commission did not include the row. This implementation closes only the ready
candidate-refusal bridge/surface obligation, not the whole row or its positive
semantic admission chain. No register or ledger status is edited. The runtime bundle root must be a dedicated
artifact snapshot outside the checked repository artifact tree; the actual lifecycle
audit includes new files under `architecture/policy_design_case` regardless of Git
ignore status. Repo-root runtime publication would need registration by the AQ1 /
generated-public-lifecycle owner, a named destination outside this no-register-edit
lane. The demonstration uses the dedicated copied snapshot described in evidence.

Receipts requiring positive/provisional reentry ports are outside this public
portless reader. It does not appoint owners, accept a source authority by its name,
turn ranking permission into consent, order incomparable estimands, or treat audit
integrity as assurance. The exact remaining questions are CV-Q1–5 in the
[decision package](README.md). No categorical create/do-not-create ruling follows
from lexical distribution; candidate vocabulary construction is deferred at its
precise unresolved semantic input.

Incidental destination CV-S2-TIME: aggregate packet `as_of` continues to follow the
existing census/composite timestamp policy. It is not the AQ1 receipt evaluation
time; `receipt.evaluated_at` remains in the bound CAS artifact. Any change to
aggregate temporal projection semantics belongs to the existing governed-projections
composite-time owner. CV-S2-IMPORT: the worker's broad heavy-import comment is narrower
than current HTTP code, which already imports Runtime quality owners; documentation
precision belongs to that worker owner. CV-S2-CLI: interrupting an obsolete
`tools.cli architecture guardrails check` invocation exposed `UnboundLocalError`
for its unassigned `exit_code`; destination is the tools CLI interruption/receipt
owner, and that interrupted attempt supplies no final gate verdict. CV-S2-TEST:
the existing worker-test helper discards a failed child's complete diagnostic and
uses a fixed 120-second timeout; destination is Runtime HTTP worker test harness.
This lane retains child output in its replay harness rather than excluding a red
by its exit alone. These observations do not change domain authority here.

CV-S2-LIVENESS: the first replay on the final import/hash source reached the
ordinary service's 184-second owner-validation timeout. The unchanged constant
has no service constructor/environment override. Destination is the existing
Runtime governed-projections owner-worker liveness/budget owner, distinct from
the test helper's 120-second budget. Timeout causation and inherited status are
`not_established`; the evidence record retains subsequent actual results separately.
The subsequent ordinary service/worker replay passed with the same 184-second
limit (worker 46.34 seconds), and the unchanged acquisition worker selection
passed all its selected tests. That later result does not attribute the earlier red.

CV-S2-BUDGET-REF: the timing catalog's `manual_journal_excerpt:v1` source reference
no longer resolves to the claimed timing evidence at its stated register line.
Destination is the timing-catalog provenance owner. The catalog was used as
declared configuration, not independently established performance evidence.

CV-S2-ENV: offline frozen lane-environment provisioning could not obtain the
locked `jaxlib==0.8.2` wheel from the local cache. Destination is the workspace
dependency-cache/lock-environment owner. The incomplete environment was retained
under ignored `raw/`; shared-interpreter tests do not become lane-lock receipts.

CV-S2-LEDGER: the standalone ledger check returns 0 while retaining informational
unknown-host closure selections, an unsupported runner, shifted status columns
and standing supplied from ambiguous/prose sources. The collector/environment
and runner findings go to the debt-ledger collector owner; column parsing goes
to its parser owner; source standing goes to the named GY source owners. The
complete output identifies the affected rows. No register repair is implied.

CV-S2-GUARD: the first completed full guardrail invocation observed this lane's
documentation edit during its output probe. That race belongs to this lane's
verification harness and is corrected by freezing every tracked file throughout
the repeat. The same invocation also reported OpenAPI and trust-claim-posture
generated-output drift. Their provenance is `not_established`, not classified as
inherited; destinations are the runtime OpenAPI snapshot owner (the user's named
`openapi-snapshot-pins-environment-derived-digests` defect) and the trust-claim-posture
generated projection owner. No generator synchronization is authorized here.

CV-S2-STATIC: the complete invocation diagnostic returns 3 for dynamic receiver
resolution at `_ProjectionCAS.get_bytes`. AQ1 `_resolve` and the planner-report
loader call the actual store override, exercised by successful reads and the
removal traceback. This remains the invocation instrument's declared
`unresolved_by_construction` class; it does not require a fictitious caller task.

## Verification and pattern pass

Relevant patterns are P01/P02/P03, P05/P15, P27/P29/P32 and P35/P37/P38. The property
is a persisted refusal recomputed by its actual owner and consumed without granting
action. The gate measures content and canonical recomputation, not ref presence or
field spelling. Its decisive process predicates are `recomputed`; domain truth
remains `not_established` and cannot grant authority. A content-valid receipt with a
fabricated outcome is the divergent case rejected by the real reader.

Review classified independent defects before repair: S2-RV01 typed invalid-source
failure delivery, S2-RV02 namespace redirect, and S2-RV03 read-side constructor
mutation. S2-RV04 replaces the complete added deep-import edge set through existing public
facades and the full-record hash owner, without baseline synchronization. Each
repair preserves a single shared source reader and is checked by a
negative runtime case. The original mistaken stop at positive semantic decisions
was CV-IR01, addressed by building this independent link.

Complete commands, process exit codes, deciding outputs, source hashes, unmocked
production readback and removal probes are in the
[evidence record](../../../superpowers/journals/correspondence/vocabularies/evidence.md).
That record distinguishes isolated service tests from the actual child-process
verification, and distinguishes static invocation diagnostics from execution.
No unrun final gate is asserted by this implementation account.
