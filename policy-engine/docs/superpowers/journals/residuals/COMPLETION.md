# Owner residuals — five separate verdicts

Lane: `codex/owner-residuals`; merge base:
`cc74d65813d7bb1259a0f82f6c3cc8b131661a97`.
Status: execution in progress; this record is not a complete architecture verdict.
No push. Root alone serializes git and shared-file edits.

The first three row decisions and `**/raw/` ignore were committed in `97803baae`
before the verification-only test addition in `5c31a37da`. Both commits were
read back from this branch after writing. The two owner-dependent rows follow
the initial three workstreams; each will have its own committed decision.

## 1. Structure exceptions

Decision: **routed-to-another-owner**, team-lex/team-scholar with architect
allocation. The historical denominator is all thirteen TOML entries. At the
lane base seven were already deleted and six already renewed. The independent
current census reconciles every condition; the decision document contains every
ID and dated disposition. No renewal is fabricated here.

The two new exact negatives in
`tests/repo_quality/architecture/test_owner_residual_exceptions.py` and the exact
existing Phase7 time-bound metadata node passed (exit 0). Removing the expiry
time predicate in an isolated process turned the unchanged negative red (exit 1,
17.03 seconds): an expired exception suppressed the real Lex finding. Fresh-process
restoration passed (exit 0, 17.50 seconds). Closed gate source stayed at SHA-256
`fe4139a9edbadfa98dabea7d670a0a918a30dda0c5623f8f6f1ea63aed72ed83`.
Targeted Ruff passed. Raw outputs: `exceptions/raw/verification.txt`,
`exceptions/raw/removal.txt`, `exceptions/raw/restored.txt`, `exceptions/raw/ruff.txt`.
Caller/registration: existing `polisyos-tools validation repository-structure-phase0`.

## 2. Ukraine method-contract consumer residual

Decision: **routed-to-another-owner**, team-scientist workflow consumers;
team-foundry retains its real contract producer. All thirteen CAS readbacks,
corrupted-output refusal, mismatched-FQN refusal and valid roundtrip passed
in four exact nodes (exit 0; 404.73 seconds on borrowed Python 3.14.0).
The single FQN negative passed on Python 3.14.3 (330.98 seconds); removal and
restoration receipts are pending. Twelve selected-contract execution routes are
not closed by the existing panel-only consumer.

## 3. N13b production execution handshake

Decision: **routed-to-another-owner**, team-runtime's `DS15-MANDATE-INTAKE`.
The concrete execution producer exists. That previously named intake task is
not registered in the allowed active-plan denominator; architect registration
remains required. Verification receipts are pending; no full production
handshake is claimed from a fixture worker or a scoped GET refusal.

## 4. DS11 public-signature population

Owner investigation and separate decision pending.

## 5. GY-DEF22

Split correctness/execution owner investigation and separate decision pending.

## Shared measurement and limitations

Independent AST census: all 2,654 tracked `src/**/*.py`, 36,135 synchronous and
879 asynchronous definitions, zero parse errors. Index path set reconciles
with the pinned Git tree and recursive filesystem walk. Path-set SHA-256:
`b91000ce91548fa9c18caf7dcb943b861307d61eb84477bf47dfd330680243d8`.
Existing `production_invocation.py` is reused; receipt pending. HTTP/callback
reachability remains outside its static proof. There is no new invocation checker.

Python offline frozen provisioning could not retrieve uncached jaxlib 0.8.2;
this is a tooling non-receipt, not a product failure. Borrowed installed dependency
versions and local source import paths are recorded in raw verification receipts.
`corepack pnpm install --frozen-lockfile` completed before trusting TS scanners
and enabled the checkout-local commit hook. No frozen Python-environment claim.

The first Python 3.14.0 module invocation of the checker was interrupted before
any verdict (process exit 143) after a measured GC bottleneck. Its diagnostic is
retained in `census/raw/invocation-original-nonreceipt.json`; the identical checker
is running directly under local Python 3.14.3. Required guardrail verdict pending.

Incidental routing so far: Common's scope-only root-cleanup carrier needs
team-core-runtime clarification; release/release-fragments gate versus taxonomy
belongs to team-ops/team-release; Lex/Scholar carrier allocation belongs to the
architect and their own teams; Ukraine execution allocation belongs to
team-scientist; N13b governed intake allocation belongs to team-runtime.
No DEBT-REGISTER.md/LEDGER.md edit or evidence citation. No governed epoch
transition is proposed from this lane's merge base.
