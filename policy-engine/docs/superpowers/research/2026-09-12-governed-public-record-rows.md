# Governed public record — Stage 1 row predicates

Read-only R1/R2 research at `034f30c64a79eb2020c04c6f0b0f07c90a74a1ee`,
branch `codex/governed-public-record`. No source, tests, register, or ledger was
changed in this research. Runtime replays by the coordinator are recorded separately. This file is research input to the original
Stage 1 decision; it does not grant execution authority or close a debt.

## Evidence and denominator

**GPR-R01 — exact current rows and unwritten nodes.** The complete census is
`docs/superpowers/journals/governed-public-record/raw/rows-stage1-final.json`
@sha256:`a37445813544aa5f44864e55b968f1dd6b460018fd4d395283246ab16d0f5c62`.
Replay from the repository root:

```sh
policy-engine/.venv/bin/python policy-engine/docs/superpowers/research/2026-09-12-governed-public-record-rows.py
```

Replay script SHA-256:
`afa5ad5807cfd41ba9bf42c63a1e0afd5e74a0e58e61d2002956523ad73f09a4`.
The raw directory is ignored by `policy-engine/.gitignore:149`.

The test denominator is **all 2,587 tracked `.py` files under
`policy-engine/tests/**` at the pinned base**, obtained from `git ls-tree`, independently reconciled against `git ls-files`;
each filesystem blob was checked against its base Git object and AST parsed,
including synchronous and asynchronous definitions and case-insensitive names. There were no blob
mismatches or parse errors. Neither of the two named test paths exists in that
denominator, and none of the three function names has a definition anywhere in
it. This is static identity absence, not a pytest collection/run receipt or an
absence claim about dynamically generated tests or external files. Every
Markdown table row in the two owner files was traversed and exact first-cell
identity selected; each of the commissioned five has one register and one
ledger row. The retained output includes those exact rows without truncation.

The deciding source bodies cited below are tracked at the same base; they are
not duplicated as evidence dumps.

## What each row actually asks

| Row | Pinned register / ledger state | Predicate and decision |
| --- | --- | --- |
| `ds8-public-case-publication` | `blocked`; owner cell still candidate | Original signal: **DS12 acquires a scope and this row moves into it**. The DS12 master-plan dated ownership act explicitly names this row. Later register prose changes the subject to a positive published governed case and explicitly denies scope-only closure. This is an architect reconciliation of scope and implementation predicates, not a code task that can silently close the scope row. |
| `ds8-signed-public-decision-surface` | `blocked`; `absent/unallocated` | Original signal: **a named slice with a scope claims it**. DS12's dated debt-row act explicitly names it. Later prose appends server record/certificate, signing, citizen projection, client strangle, and DS10's semantic node. Again architect scope adjudication is needed; implementation does not decide which signal governs. |
| `ds10-public-decision-rendering` | `blocked`; `team-design` | Its exact HTTP pytest node must pass for a public decision projection bound to governed custody. Internal REVIEWER/EXPERT discovery and MACHINE/compiler candidates cannot supply the authority. An authenticated verification report is also insufficient. |
| `DS11-PUBLIC-SIGNATURE-POPULATION` | `open`; `surface_missing` | Its exact HTTP pytest node must pass **after DS12's independent promotion gate**. Routing to DS12 does not close it: the Sept 11 architect correction explicitly reversed that attempted closure. A real governed public-signature member must be admitted and consumed under custody. |
| `DS11-GROUNDED-PERFORMANCE` | `blocked`; runtime/GY evidence owner and separate publication consumer | Its exact integration node must show a promoted design supplying content-bound **performance** evidence, with DS12 still separately deciding publication. Firstness/custody is not performance support. |

The two scope acts are
`docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1771`
(“Debt rows this slice must close”, dated 2026-09-01), its named rows at
`:1776` and `:1777`, and the inherited-obligation explanation at `:1915`.
The same plan explicitly says the scope act is not closure. Preserve the
contradiction in the decision; do not resolve it by relabeling an implementation
witness. Prior finding **OR-DS11-01** in
`docs/superpowers/specs/2026-09-11-owner-residuals-ds11.md` establishes the
already-appointed DS12 destination without claiming the original signal.

## Three test identities and the properties they must witness

These are owed future artifacts, not green receipts. Commands below are the
registered replay identities, **not commands executed during this research**.

1. `uv run pytest tests/unit/runtime/http/test_public_export.py::test_public_decision_projection_is_custody_bound -q`

   Must traverse the real public decision producer and persisted bytes to a
   public HTTP projection that resolves its governed source, authority purpose,
   scope, rule/time and currentness evidence. It must preserve the actual
   limitations, denied uses and constitutive history, and refuse forged,
   mismatched, unsupported, stale-currentness and projection-only authority.
   It cannot pass solely because an API report has a valid signature.
   **PV-K01/PV-K02/PV-K03/PV-K04/PV-K05** supply the controlling semantic
   constraints; a future exact witness should exercise the owning runtime and
   its actual public consumer rather than assert the presence of these fields.

2. `uv run pytest tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound -q`

   Must consume DS12's independently admitted governed record and persisted
   signature/decision bytes, produce a nonempty content-bound governed
   population, feed the installed custody maintenance path, and show a durable
   scan/lifecycle consequence. Arbitrary unsigned CAS content, a synthetic
   population, and an authenticated report with an empty promoted slot must not
   admit a governed member. The old report-authentication HTTP test is a useful
   existing negative, not this node under another name. The population must
   remain accountable for staleness and supersession without erasing historical
   issuance (**PV-K02**).

3. `uv run pytest tests/integration/runtime_quality/test_first_governed_promotion.py::test_promoted_design_supplies_content_bound_public_performance_evidence -q`

   Must start from the actual production promotion chain and independently
   verified evidence that supports the specific performance claim, content-bind
   the evidence to that design and declared use, persist it, and exercise the
   publication consumer's separate decision. The row does **not** require
   `compose_effective_state == "supported"`, an authorized public performance
   claim, or publication success; its wording explicitly reserves DS12's
   decision. Evidence supply and supported publication are separate predicates.
   Contract-testing receipts,
   verification-only confidence evidence, constructed/forged receipts, generic
   admitted identity/accessibility evidence and a custody-first claim cannot
   satisfy it. **INT-K06** expressly forbids promoting firstness/custody into
   population performance, compliance, competence or readiness. This node's
   positive assertion is not discharged merely by building a governed record
   container or rendering a true no-number custody claim.

These descriptions interpret the existing signals under binding invariants;
they are research requirements, not new contracts or permission to change a
closed owner's basis.

## Current executable boundaries and actual blockers

**GPR-R02 — report authentication is implemented; governed admission is not
available through this composition.** Prior finding **OR-DS11-03** identifies
this exact boundary, independently reread here:

- `runtime/http/services/public_decision_verification_contracts.py:97` and
  `:126` constrain stored/response `promoted_record` to `Literal[None]`;
  `public_decisions.py:56` does likewise for issuance. The report is
  `verification_report_only`; every `PublicDecisionVerificationDimensions`
  coordinate is constrained to `not_established`.
- `PublicVerificationRecordPopulationProvider.resolve` in
  `scientist/governance/continuous/published_signature_custody.py:131` returns
  only `PublicSignaturePopulationNonReceipt`. It verifies the issued inventory
  but even a nonempty promoted object is refused as `promoted_record_not_admitted`;
  an authenticated report with the normal empty slot yields
  `governed_public_record_producer_missing`.
- `persist_public_signature_population` and
  `resolve_public_signature_population` validate CAS hashes, kinds, schemas,
  manifests and input identities. Their `_assert_exact_artifact` helper checks
  artifact integrity, not a governed signature's admission semantics. Installing
  a static or institutionally supplied snapshot cannot turn that advisory
  custody substrate into a governed public issuance verifier.

The corresponding **OR-DS11-04** production trace is already installed:
tenant-bound POST `/api/v1/runs/{run_id}/public-verification-record` creates a
redacted bundle from a persisted run packet, public GET
`/api/v1/public-decisions/verification` authenticates report bytes, and the
runtime container supplies that service to the population adapter and custody
worker. `runtime/quality/public_export.py:596` emits
`public_redacted_projection`, `redacted_derived`, `projection_only` and
non-authoritative approval/scorecard roles. Reuse these owners; do not infer a
missing signer or missing entire watcher from the missing governed record.
Capability labels for the additional positive chain are `producer_missing`
(governed record/admission), `bridge_missing` (positive admission to population)
and `semantic_test_missing` (the required end-to-end signals).

**GPR-R03 — NC-01 is the wrong blanket first-record blocker.** DS12's gate
amendment at master-plan `:1761` and register §J.3 explicitly separate a
**data-only first governed promotion** (`GY-PR1a`) from the field-pilot
protection/near-miss property of **`GY-O0-NC-01`** (`GY-PR1b`). An institutional
pilot appointment does not gate building public custody mechanics or the
permitted data-only route. This is also finding **OR-DS11-01**. The three target
implementation rows retain older NC-01 pointers; the Stage 1 decision must not
silently turn them into a demand for pilot authority.

The current code is stronger than a bare `promoted` flag:
`promotion_sequence.py:3617` computes promotion from the empty refusal set;
`:3618` additionally requires the resolved CG2 certificate and store to be
production-promotable (`_cg2_resolution_is_production_promotable`, `:4742`);
verification confidence provenance forces `consumer_promotable=False` at
`:3620`. Non-contract production also requires open-world and epoch-validity
projections. `CanonicalPromotionReceipt` validates the production lane,
promoted status and trace and disallows verification-only evidence. A public
consumer must resolve and verify the actual owner evidence, not copy these
asserted DTO fields into a new authority record.

The newest amendments to `first-promotion-candidate-with-complete-evidence`
explicitly supersede the old N7/zero-constructor narrative: the certified SKG
engineering path was found, PR1 source/measurement wiring was built, and the
remaining candidate inputs include authentic N4/confidence and protected
admission evidence. Those amendments are pointers for the upstream research
lane, not a fresh proof that a qualifying candidate now exists. This row census
has not run a promotion and establishes no positive candidate.

**GPR-R04 — performance has an additional intentional boundary.**
`scientist/evidence/claims/posture.py:1186`, `compose_effective_state`,
unconditionally returns `BLOCKED` for `family == "grounded_performance"` even
when a `governed_performance_prerequisite` is supplied. Its
`derive_admitted_verifiers` only derives typed identity/accessibility/page-a11y
bases, explicitly denying performance. Existing
`tests/unit/scientist/evidence/claims/test_posture.py:293` exercises refusal of
relabeled non-performance evidence. A new public record does not discharge
this basis. Independent performance evidence and its owner admission would be
separate work; deleting the guard or repurposing an identity verifier would
launder authority. Preserve **INT-K06**'s narrower publishable custody claim.

The unresolved semantic choice is which actual performance proposition the
future node will test and which existing promoted-design evidence legitimately
supports it. The node name does not specify an estimand, metric, population,
measurement or validity envelope. If the original Stage 1 decision selects only
a governed custody record, leave performance support outside that mechanism; if
it selects performance-evidence supply, identify the substantive owner basis
before writing a positive assertion. Neither this uncertainty nor a later
institutional signature prevents building the authorized record machinery.

## Stage 1 stop and acceptance

No implementation closure can be claimed from a scope allocation, a valid
report signature, or an unwritten-test alias. The two DS8 rows need an architect
scope verdict, while each other row keeps its own semantic predicate. If no
actual qualifying governed production candidate can be resolved, the positive
record/signature/performance witness is blocked on that absent input; building
and verifying the typed mechanism with honest nonreceipts remains separable.
A no-number custody publication does not close the performance row.

Pattern pass: **P01/P02/P03** distinguish existing report chain from missing
positive governed producer/bridge/surface; **P05/P15/P32** protect authority;
**P29/P33** require behavioral negatives rather than new green names;
**P35/P36** pin complete denominators and finding IDs; **P37/P38** distinguish
scope, report authentication, production promotion, custody and performance
predicates. The failure/repair register was read before research and reopened
before this handoff. Acceptance of this research is a committed original
Stage 1 decision that carries these distinctions, not a register status change.
