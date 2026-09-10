# Atlas public verification bridge: measure and retain the existing owner path

## Decision and scope

Base: `a534024ee28dfd9ac4fd21be1ff769b253722d8e`, attached branch
`codex/producers-verification`. This workstream verifies
`atlas-public-verification-record-bridge`; it does not reopen the closed browser-badge
repair or mint PUBLIC decision authority. The row supplies the acceptance requirement,
not evidence of implementation. Findings below derive from tracked source at this base.

**A1 — The producer and bridge already exist.** Select verify-existing. Do not create a
second issuer, browser verifier, signed-record store, or API. The implementation entered
in `da73f861dbffc62db6a97a0013e4a0c99f59bede`; its relation to this lane base is checked
with ordinary Git ancestry, and current source must pass fresh behavioral verification.
The merged September 7 missing-producers wave is not the author of this Atlas path:
its historical journal covers Claim Ledger and global case discovery; the Atlas delivery
is a separate source commit, so neither that handback nor adjacency establishes this row.

Alternatives rejected: rebuilding duplicates the retained CAS and Ed25519 owner;
expanding a verification-report signature into policy issuance substitutes authority
and violates the very boundary this row requires. A verification report may authenticate
retained candidate bytes while all promoted-record and current-authority slots remain
unestablished. That limitation is an acceptance condition, not a missing bridge.

## Measurement and independent cross-check

**A2 — Complete Python denominator.** A separately executed AST walk reconciles
`git ls-files -z -- src` with `git ls-tree -rz --name-only a534024ee -- src`:
2,654 tracked `src/**/*.py` files, 2,654 parses, no parse errors, 37,014 synchronous-plus-
asynchronous function definitions including 879 async definitions. Sorted source paths
SHA-256: `b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
The exact receipt is under `docs/superpowers/journals/producers/verification/raw/`.
This census uses the delivered vocabulary discovered by tracing readers; it is not an
absence claim from predicted symbol names. The existing
`src/polisyos/runtime/quality/production_invocation.py@a534024ee` is the primary complete
source-derived caller audit, including tracked tools/tests and script entry points.
The completed audit returned 0 with no regressions over 5,669 tracked Python files
(src/tools/tests); its source denominator is 2,654. It marks these HTTP handlers and
service methods uninvoked because it does not resolve their FastAPI callbacks or
service-return receivers. This result is not evidence of absence or successful wiring.
Its callback/receiver limitations are retained: a static diagnostic never proves an HTTP
request, persisted artifact, or authority. The independent cross-check starts at the
actual reader/route, inspects its AST calls and exact source bodies, and checks Git history.

**A3 — Exact production caller before any change.**
`src/polisyos/runtime/http/routes/public_decisions.py@a534024ee` registers
`issue_public_decision_record` as POST
`/api/v1/runs/{run_id}/public-verification-record`, with resource-bound PLATFORM_ADMIN
authorization and tenant-owned run resolution. It resolves the persisted decision packet,
calls `build_public_export_bundle` and `assert_public_export_official_use_limits`, then
`PublicDecisionVerificationService.issue`. The source packet is selected from the run;
a caller-authored document is not accepted. The corresponding public GET
`/api/v1/public-decisions/verification` calls `PublicDecisionVerificationService.verify`.
`src/polisyos/runtime/http/app.py@a534024ee` imports and includes this router;
`src/polisyos/runtime/http/container.py@a534024ee` builds its service from explicit
configuration. These are discoverable HTTP/OpenAPI operations, not loose module entry
points. A new polisyos-tools command is inappropriate: issuance already has the HTTP
resource/tenant authorization boundary and creating a parallel command could bypass it.
The production app factory is the deployment terminus; fixture-server main is only the
browser test harness, not claimed as the production caller.

**A4 — Persistence and exact readback.**
`src/polisyos/runtime/http/services/public_decision_verification.py@a534024ee` writes the
canonical JSON public document and strict report into FileSystemCAS, signs the report
through the existing Ed25519 signer, verifies the captured bytes before publishing the
index, and atomically links/fsyncs the immutable issuance locator. A subsequent `verify`
resolves the index, captures blob/manifest/signature, verifies cryptography, trusted issuer
and purpose, validates every signed binding, resolves/digests the public document, and
returns only that captured document. Reads do not issue new signatures. Missing/forged
signatures refuse with their own reason; arbitrary CAS presence is not an issued URL.
`public_decision_verification_configuration.py@a534024ee` loads deployment trust from
`POLISYOS_PUBLIC_VERIFICATION_CONFIG`; absent trust cannot issue, malformed trust fails
startup. It never generates a deployment identity.

**A5 — Surface consumption.**
`apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx@a534024ee`
is the real public route. It calls
`apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts@a534024ee`,
which requests the anonymous verifier, strict-parses the response and binds the requested
record identity. The rendered indicator requires that server response's authenticated
report, valid signature and trusted key; a late response for a different route is withheld.
`src/polisyos/runtime/http/services/public_decision_verification_contracts.py@a534024ee`
type-constrains the promoted record to null and every PV-K01 dimension to not_established.
No new mechanism, public schema, governed artifact, or epoch change is planned.

## Pattern pass and decisive predicates

P01/P02: retain the measured producer -> signed CAS artifact -> registered HTTP caller ->
reader -> Atlas route. P03: verify the actual public route, not only a component stub.
P05/P15/P37: signature verification is independently reconciled against configured trust;
issuer appointment is institutionally supplied and does not establish policy authority.
P29/P32/P33/P38: a green positive alone is insufficient; corrupt a real signature while
keeping its ID, report bytes and positive markers, then require the cryptographic reason.
P35: AST includes async definitions over the entire tracked Python set; TypeScript UI
observations are explicitly separate from that denominator. P40: a trust-boundary escape
is bucketed before repair; repeated same-class findings are bounded or structurally fixed.
P41: no inherited-failure attribution without the exact base replay and disjoint input set.
Missing labels: none for the bounded verification-report bridge, pending fresh tests;
PUBLIC promoted record/current authority remain explicitly not_established, not supplied
by this verification workstream. No institutional appointment is inferred from test keys.

## Stage 2 acceptance and removal plan

Commit this decision before source/test mutation and read it back from the attached
branch. Run only the explicit files/nodes listed in the final runner, with full output
retained and measured durations. Existing tests are sufficient unless fresh execution
exposes an untested closure condition; there is no reason to rewrite a passing mechanism.

1. `tests/unit/runtime/http/test_public_decision_verification_routes.py::test_owned_run_packet_is_redacted_issued_and_publicly_verified` exercises real HTTP issuance, persisted signature corruption and refusal.
2. `tests/unit/runtime/http/test_public_decision_verification_routes.py::test_public_export_refusal_prevents_record_and_link_issuance` proves a stored blocked packet reaches the real export refusal.
3. `tests/unit/runtime/http/test_public_decision_verification_routes.py::test_legacy_browser_token_receives_public_verifier_refusal` proves client forgery reaches a specific verifier reason.
4. `tests/unit/runtime/http/test_public_decision_verification.py::test_persisted_index_survives_new_service_and_reads_never_resign` proves exact replay under a new reader.
5. `tests/unit/runtime/http/test_public_decision_verification_configuration.py::test_configured_keys_issue_and_reverify_persisted_report` verifies the deployment configuration route.
6. `apps/runtime-dashboard/e2e/public-decision-verification.browser.ts`: `real verification service authenticates a report and rejects the same record after signature removal`. Run only this node with `e2e/playwright.public-verification.config.ts`. The existing test mutates the issued signature on disk, verifies the same record receives `record_signature_invalid`, and requires the real public route to remove the authenticated indicator and document while report bytes stay unchanged.

For a source removal probe, temporarily replace only the cryptographic rejection predicate
inside `_verify_entry` with a false predicate; keep report/key/schema/digest markers and the
unchanged HTTP negative node. It must fail on the expected invalid-signature assertion,
not collection, fixture setup or disabled feature. Restore exact original bytes in a
finally path, and rerun the same node green. A separate signature-artifact corruption in
the browser is the surface witness. No source mutation from a probe is committed.
Serialize the fixed ports 8017/5177 and browser scratch. Root owns git and shared records.

If gates expose incidental issues outside this bridge, route them to team-design/public-
surface corridor in the single completion journal; do not edit DEBT-REGISTER or LEDGER.
The lane handback records fresh evidence and recommends row disposition, leaving those
architect-owned surfaces untouched.
