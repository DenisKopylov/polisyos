# GY builders C journal

Lane base `07c89304d`, attached branch `codex/gy-builders`, 2026-09-10.
Decision: `../specs/2026-09-10-gy-builders-c-decision.md`.
Source changes remain prohibited until the parent freezes all workstream decisions.

## Stage 1 — research and owner execution

Read GY-CB1/GY-ML1 task definitions and §3.5.5/3.5.6; ratified W5-K02/W5-K06;
WP-09/WP-11/WP-12; INT-R3 benchmark, operational addendum and controlling amendment;
INT-R6 protocol, FX-001–003 and W5 routing map; CONTRIBUTING and failure register.
No institutional owner has been appointed; no withheld proposition is decided.

`gy-builders/c/owner_research.py` executed the complete tracked `src/` census at the lane base:
2,851 tracked source files, of which 2,640 are Python. A second method, an OS tree walk,
reconciled the complete Python identity set against `git ls-files`. The AST census parsed
172 Python files under `src/polisyos/runtime/quality/`, 43 under `src/polisyos/lex/`, and
28 under `src/polisyos/scholar/`; no unreadable member was omitted. Exact text searches
across all 2,851 tracked `src/` files found no `human_comprehension_established`, `MAEP`,
`operator comprehension`, `behavioural_contract` or `behavioral_contract`. These are bounded
text observations, not proof that no differently named owner exists. Owner placement comes from
the complete topical definition census plus inspected canonical implementations.

Full output is preserved at
`gy-builders/c/raw/stage1-owner-census.txt@d0676d0fff58ef388cb97b08cdb67a791b526a0e087030beacfd30f04e4cdc97`.
It is gitignored because it contains a large source-derived definition inventory. Read owner bytes
are bound inside that receipt; their tracked source is cited instead of embedded.

C-OWNER-01: CB1 composes `RuntimeDiagnosticEventLog` and `DiagnosticEvent` through the existing
producer-execution event and diagnostic CAS payload family. No new event storage/authority owner.
C-OWNER-02: ML1 extends Lex semantic evaluation, adjacent to `knowledge/benchmark.py` and
`normpack/legal_authority.py`. Scholar source acquisition stays upstream; imported source bytes
remain candidate evidence. No second status lattice or legal competence owner.
C-OWNER-03: root and C are independently allocated census parsers; only domain and output interface
were shared before implementation. Reconciliation compares full maps and byte identities, never
counts alone. Corrupt-field negative is required after allocation.

Existing-owner gate: only
`tests/unit/runtime/quality/test_runtime_event_log.py` and
`tests/unit/runtime/quality/test_diagnostic_event_contract.py`.
Complete output: `gy-builders/c/stage1-existing-owners.txt`.
Command uses venv first in PATH and `python -m pytest`; first invocation failed during collection
with `AcquisitionActionHeadRecord` circular import when ControlPlaneStore is imported before the
runtime control API. No product path was changed. The failure is a measured collection result, not
an inherited-debt claim; a canonical-startup-order replay will be recorded separately.

No predecessor is replaced/subordinated; no StrangleReceipt is currently applicable.
No governed epoch transition is planned. A later need would declare the transition from the immutable
merge base `07c89304d` before changing governed bytes.

Default architecture gate: `not_completed` because its compiler chain invokes prohibited
`check_debt_ledger.py`. Neither debt/ledger file was edited. No full/directory-wide suite was run.

## Claims that stay refused

GY-CB1's claim that humans comprehend PolicyOS stays refused: the emitted result has a non-settable
false property and all trial/conformance evidence in this lane remains candidate-only; WP-09
per-cell numerical claims stay typed empty.

GY-ML1's claim of legal equivalence stays refused: no signer, qualified holder or trust root can be
filled by this lane, and every candidate result reader enforces the complete declared
proposition/purpose/holder/context denominator before returning a bounded diagnostic.

## Routed findings outside this owner

- W5-R3-Q06 retains item adjudication and governance-loss appointment; no appointed study authority.
- W5-R6-Q05 retains per-jurisdiction co-authentic reconciliation.
- W5-R6-Q07 retains institutional security owner, trust roots and key-custody appointment for any
  future signed certificate; this lane builds a form with those slots empty.
- WP-09, WP-11 and WP-12 retain their withheld statements; no local constant closes them.
- Arbitrary natural-language semantic extraction/verification is not established by candidate frame
  equality. Its authority-grade producer is explicitly nowhere in this new mechanism; qualified
  adjudication remains the prerequisite, and the refusal is structural.

Design review amendment: internal per-cell exact-binomial estimator requires explicit candidate alpha,
while public bounds remain withheld; MAEP implements resolved-byte integrity and append-only
revocation/use-time checking now even though signer/trust roots remain empty.

Stage-1 startup-order replay completed RC0: all 22 cases in the two named files pass after importing
`polisyos.runtime.http.services.control.api` before the direct store import. Full deciding output is
`gy-builders/c/stage1-existing-owners-startup-order.txt`; executable replay is
`gy-builders/c/owner_test_replay.py`. B independently confirmed the facade-first startup order and a
real SQLite reopen/duplicate/checkpoint execution. The earlier collection error remains recorded and
unrepaired. This establishes the existing event/CAS bridge under the supported startup order.

C-OWNER-04: readback located the existing detached-signature/Ed25519 verifier owner under
`core/artifacts/store.py` and `core/artifacts/signing.py`. MAEP will call its unsigned strict
verification with empty trust roots; no second crypto engine and no signing call.
