# Post-E02 R9 + GY + Atlas/debt program: assurance design

**State:** planning instrument only. It does not accept E02, change any task standing, authorize a data read, or claim runtime acceptance. This review read repository instructions and the cited plans; it ran no tests, builds, imports, installs, or production reads and made no Git changes.

## Entry fence: establish E02 before implementation

The post-E02 portfolio is a research proposal, not an implementation authorization. Its own README says it does not change official task status or authorize implementation, data acquisition, expenditure, or protected findings. The opening status of R9 lifecycle and acquisition also says their probes/runtime acceptance are unrun and that these documents are not E02 acceptance. Therefore “E02 fully accepted” may appear in the roadmap only as a **conditional planning scenario** until an actual acceptance receipt is resolved and reconciled.

Before implementation, resolve the actual existing G acceptance decision and its accepted source/tree, criterion scope, inputs/backend profile, deciding evidence and residuals. [The entry charter](../execution/01-charter-and-entry.md) is controlling. The checks below are a reconciliation checklist over that existing decision, not a new receipt service, signing requirement or universal all-backend gate. G must actually accept E02; an assumption or receipt-shaped document cannot substitute. Preserve code acceptance and finding closure separately. The illustrative receipt later in this document is project logistics only, not a product schema or mandatory replacement for native receipts.

This fence is about E02’s internal acceptance evidence. After it passes, do not make every program increment wait for unrelated external facts. Gate an external issuer, grant, source row, deployment, or human decision only where the selected claim needs it. Candidate analysis may proceed with a declared unknown and a narrower result; a protected action or published authority claim that needs the missing fact remains limited or blocked. This follows the custody boundary: institutional absence binds the claim, not every capability (GY §8.5; S0-K03/K06; acquisition §2 and §5).

## Evidence algebra and claim standing

Represent each accepted evidence item as a tuple:

`E = (claim/scope, owner, source+input hashes, rule/schema/runtime versions, event/time roles, persisted artifact, bridge, consumer, verifier, audience/surface, outcome, residuals)`.

A capability is accepted only by conjunction, never by a score or count:

`contract ∧ producer ∧ persisted artifact/event ∧ orchestration bridge ∧ consumer ∧ property verification ∧ audience surface (or explicit out_of_scope) ∧ semantic positive ∧ distinguishing negative ∧ residual reconciliation`.

This is the repository capability bar, applied to the exact claim. Classify every gate predicate as `recomputed`, `independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, or `not_established`, freeze that classification at admission, and let only the first two authorize an authority-grade positive. The latter three must cap/block that claim or remain a declared candidate assumption (P37; S0-K06). A test that checks a field, marker, exit code, status label, or declared denominator without exercising the deciding property is not evidence (P29, P32, P38).

Keep three distinct views (within existing records, not three new product ledgers):

- `planning_snapshot`: what the portfolio/source records reported at a named cutoff. It supports navigation and conditional estimates, not acceptance or implementation standing.
- `scenario_assumed(E02=fully_accepted)`: a counterfactual used to compare portfolio paths and remove repeated repair budget. It never upgrades the planning snapshot.
- `accepted_at(receipt_sha, source_tree, inputs, backend_matrix)`: the only state that permits program implementation and E02-output reuse. Its standing is limited to reconciled criteria and surfaces.

`partial` is not aggregate acceptance: it admits only the named reconciled subclaim. `warn`, `near_binding`, `contested`, `review_required`, unknown, and stale retain their distinct existing meanings and compose through the canonical status lattice; no new enum or implicit “green enough” reduction (P04/P09). A historic valid receipt stays valid as historical evidence; current use can become stale and trigger revalidation/reissue (P07/P08).

## Slice assurance: test the property through the real chain

Each pilot slice names one concrete decision/use and one native owner. Its acceptance packet must demonstrate input condition → existing or extended producer → durable artifact/event → lifecycle/orchestration effect → fresh consumer → intended audience projection. Reuse the native owner first; extend, consolidate, or build only after a caller/consumer census. Keep one canonical writer for shared semantics, schemas, generated outputs, and governed artifacts.

For every load-bearing property, write a behavioral contract with (a) the positive that should be admitted, (b) a distinguishing negative that must refuse or limit, and (c) a harmless/allowed control that must still work. Cover relevant mixed outcomes (`warn`, `partial`, `near_binding`, `contested`, `review_required`) rather than only all-pass/all-fail. Include semantic adequacy, authority purpose, status, time roles, rule/schema version, provenance, and audience where the artifact crosses a workflow boundary.

Required falsifiers, selected by the property and claim rather than copied as a universal checklist:

- **Adversarial variants:** synonym, malformed, missing, present-but-fake, wrong content/hash, cross-bound identifier, stale source, sibling producer/consumer, wrong audience/purpose, and contradictory evidence. The probe is a witness, never the spec (P33).
- **Removal probe:** delete the real property while retaining markers/field names/declared premises; the gate must turn red or downgrade the result. Complement it by preserving behavior while perturbing a non-decisive marker. This catches both authorial and proxy proof (P29/P37/P38).
- **Independent oracle:** pin a small exact hand calculation, source-defined result, or separately implemented reference before the producer is finalized. The oracle must not call the producer/generator or share its decision helper. Record oracle provenance and scope. A fixture made by the same pipeline proves consistency only, not truth or independence (P14/P32).
- **Differential base:** replay the same property and exact inputs against the slice base and candidate using one environment/profile. For inherited reds, replay the exact command from a base predating all slice work and prove the changed-path set intersects the gate’s complete input denominator at zero; for handoff/closure use the slice base. Otherwise classify `not_established`, not inherited (P41).
- **Failure/chaos:** inject crash, retry, duplicate/reordered event, stale worker, partial write, backend outage, and ambiguous external effect at named durability/fencing boundaries. Assert persisted state and consumer behavior after recovery; use controlled fakes for external effects unless a real permitted source is specifically in scope.
- **Persistence/new process:** close and reopen the store, start a clean process, resolve the committed artifact by identity, and exercise a fresh consumer. Assert authority, time, version, and status survive serialization and migration; in-memory caches are not persistence.
- **Schema/generator/migration:** run the canonical generator from the pinned schema and compare all generated outputs; test old/new readers and writers across the declared migration window, unknown fields/versions, and round-trip of limitations. A generated artifact that is merely present or diff-clean is not proof of the schema behavior.
- **Machine/API/browser:** for claimed machine surfaces, exercise the actual typed export/API and parity with the governing surface. For claimed UI or audience behavior, use browser evidence for the real route plus server-side authorization negatives; hiding a control in UI does not prove denial. Test stale/offline projections and fail-closed error rendering when in scope. Follow Atlas Execution Doctrine for public/reviewer/expert/MACHINE audience boundaries and proportional accessibility evidence.

### Independent roles and exception provenance

The slice owner builds the native producer/consumer contract and records decisions. One integrator binds owner seams, calculates the affected closure, and reconciles the receipt; the integrator does not sign their own acceptance. An independent reviewer gets the exact frozen source and inputs, runs the decisive property and adversarial probes, checks the oracle and residual ledger, and records their own outputs. Domain or institutional owners supply facts only within their authority; their evidence is labeled `institutionally_supplied`, never silently upgraded to `recomputed`. If the fact is decisive for an authority claim, the gate still needs independent reconciliation or the claim remains limited.

Every exception, exclusion, skip, unsupported backend, test quarantine, or bounded residual gets a record with: ID; property and affected claim; exact file/backend/input denominator; origin (`new`, `inherited`, or `accepted limitation`); evidence and base; owner; authority for the disposition; scope and user-visible limitation; expiry/re-entry trigger; and smallest closure capability. Complete isolation before declaring a failure unrelated (P34). A known red is neither an automatic stop nor automatically somebody else’s debt (P41). On the second finding of one class, bucket it as same class deeper or new class; widen the mechanism or declare a falsifiable bounded residual instead of starting an endless repair ladder (P40).

## Pilot admission and rejection

Admit one pilot only if the reviewer can answer yes to all authority/custody questions below. This decides whether the proposed *claim* is safe to exercise; it is not a feature checklist.

- Is the exact decision/use, target population, time horizon, audience, and authority band explicit? Is a candidate result clearly separated from anything publishable or action-triggering?
- Is each institutional act, external grant, source permission, or issuer competence either resolved from its competent source and bound to the exact operation, or carried as an explicit unknown that limits the claim? No parser, model, fixture, or UI may mint that authority.
- Can a reader resolve the evidence, verify content and producer/verifier provenance, reconstruct the rule/schema/input versions, and distinguish observed fact from transformation, inference, assumption, and refusal?
- Does a real consumer use the produced artifact, and does the lifecycle preserve correction, expiry, staleness, invalidation, reissue, and historical replay where the claim promises them?
- Does the test suite prove an admissible positive, a laundering negative, and a harmless control through the same authority boundary and each claimed surface?
- Does the frozen backend/input matrix support the promised claim, with every unsupported mode explicitly bounded? Is the independent oracle fit for this exact question?
- Is the existing owner path reusable without a parallel authority owner or duplicate ledger? Is the complete acceptance denominator and every residual named?

Reject protected/publishable pilot admission when authority, custody, audience, basis, or temporal validity depends on a consumer assertion, self-attestation, marker, unexplained default, unverified external act, or unresolved residual. A useful candidate investigation may still proceed with a typed limitation. Reject a claim of completeness, parity, causality, independence, or successful recovery when only a fixture, one backend, setup success, or a receipt-shaped artifact supports it. Do not reject unrelated work solely because data access, external appointments, production deployment, or legal evidence is unavailable; split the scope and preserve the limited result.

## Gate selection by blast radius and replay economics

Compute the affected closure from owners and semantic dependencies, not the count of changed files: changed runtime modules and transitive importers; all producers/readers of the artifact; persisted formats and recovery paths; schemas and generator outputs; public/API/client/MACHINE/UI surfaces; rule/status/authority consumers; and relevant architecture/import boundaries. Record the closure and why each gate is inside or outside it (P35/P36/P38).

1. **Slice gates:** targeted logic and semantic tests for each changed property, importer/consumer tests, adversarial/removal probes, and validator `--check` plus a corrupt-field drift where a recomputing validator owns the artifact.
2. **Boundary gates:** add integration/workflow/persistence/new-process checks when the producer-to-consumer, transaction, lifecycle, backend, or status composition is touched; add schema/generator/migration checks when ABI or generated outputs are in closure; add API/browser/accessibility checks only for surfaces whose claims are in scope.
3. **Architecture/repository gates:** run guardrails for owner/import/public-surface changes. Broaden to backend verification or CI parity at program closeout, or sooner only when the closure actually reaches those boundaries. Existing red is classified by P41 before disposition.
4. **Expensive replay:** name shared resources (e.g. governed artifact writer, schema/generated-client family, database/DuckDB scratch, browser/Storybook/fixed port). Parallelize non-contending checks. Freeze source and inputs, get every independent review against that exact source, apply accepted blocking repairs, then pay the content-bound full receipt/replay chain once. After freeze, cosmetic findings become debt; batch blocking findings. A changed source after the replay creates a new bounded rebind/replay obligation for the affected closure, not permission to omit verification. Never weaken a correctness gate to meet the compute budget (GY §3.5.7 E1–E14; Atlas Execution Doctrine; R9 lifecycle §3/§6).

Measure each expensive suite once to set explicit timeouts; slow progress with a recorded heartbeat is not a reason to kill it. Keep durable raw evidence journal-first where a live task needs it. Do not serialize unrelated lint/type/logic work behind a contended resource. The plan/journal/register and tests required by a moved constant are mandatory records, excluded from mechanism path caps (P39).

## Optional handoff checklist over native receipts

```yaml
kind: optional_project_handoff_checklist_not_product_schema
receipt_id: <stable ID>
acceptance_index_ref: <path/hash; index records SHA-256 of exact receipt bytes>
standing: accepted | partial | limited | blocked | not_established
program_slice: <stable ID>
claim_scope: <decision, population, period, audience, authority band>
accepted_source:
  commit: <full object ID>
  tree: <full tree object ID>
  worktree_state: clean | included_changes_listed
inputs_manifest_sha256: <hash>
rule_schema_runtime_versions: <exact versions>
backend_matrix_ref: <content-bound path/hash; every declared backend has an outcome>
criterion_evidence_map_ref: <content-bound path/hash>
  # criterion -> producer -> persisted artifact/event -> bridge -> consumer
  # -> semantic positive/negative -> verifier -> API/audit/dashboard/MACHINE surface
residual_reconciliation_ref: <content-bound path/hash, including explicit out_of_scope>
gate_predicates:
  - predicate: <load-bearing predicate>
    classification: recomputed | independently_reconciled | consumer_asserted | institutionally_supplied | not_established
independent_oracle_ref: <hash, provenance, scope, or explicit not_applicable>
exceptions_ref: <hash, empty only when the complete denominator was reconciled>
independent_review: <reviewer identity/role, exact source+input hashes, result>
replay_command_receipts: <commands, environment, outputs/hashes, duration, outcome>
rebind_from_prior_plan: <prior plan hash and mapping ref, or initial>
accepted_claims: <exact claims and surfaces this packet supports>
not_claimed: <explicit limits: untested backends, external acts, causal scope, etc.>
reentry_triggers: <events/versions/changes that invalidate or require reissue>
```

A receipt-shaped YAML file is not the receipt: resolve each reference, content-bind it to the accepted tree and claim, verify reviewer provenance, and reproduce the deciding gates. If a supplemental project checklist is useful, content-bind it alongside the existing native G records; creating this optional file or a detached index is not an entry or acceptance requirement. Store complete deciding output and removal-probe evidence; cite tracked evidence as `path@sha` instead of copying derived inventories into the packet.

## Post-acceptance plan rebind without reopening history

Once the E02 packet passes, create a new append-only `plan_rebind` record. Do not rewrite old acceptance receipts, historical closure rows, or the planning bundle’s source standing. The rebind contains: prior plan/snapshot identity; accepted E02 receipt hash; accepted tree and frozen inputs; exact E02 output IDs consumed; prior criterion/closure ID → current accepted artifact and evidence; affected program increments; and the mapped result (`retained`, `reused`, `superseded`, `limited`, or `reopened`) with reason and verifier.

Carry a historical closure forward as historical. Mark a downstream requirement `reused` only when its exact accepted artifact has the needed producer/consumer semantics and version. Reopen only a requirement whose current expected property materially diverges, whose accepted output fails the new consumer, or whose residual intersects the new claim; record that as a new delta with its own baseline and acceptance. Do not open adjacent historical rows to make the newer plan look uniform. Update only affected dependencies, effort, sources, and assumptions, then re-read the reconciled plan from its exact written bytes. This is the portfolio’s version of the post-E02 scenarios in roadmap.md (“Three E02 scenarios”) and maintenance.md (“Units of update” and “Completeness control”).

## Pattern pass and source map

Relevant IDs: **P01/P02/P03, P04/P05, P07/P08/P09/P10, P13/P14/P15, P27/P28, P29, P31–P41**, with P16–P26 only when the slice touches their named universal-design axis. Risks directly addressed here: document/contract mistaken for a capability (P01/P02); hidden or false surface (P03); authority/status/time laundering (P04/P05/P07–P09/P15); semantic or independence overclaim (P10/P14); parallel owner or instance patch (P27/P28/P31); marker-only and reviewer-trained proof (P29/P32–P34); denominator/citation drift (P35/P36); declared predicates and proxy gates (P37/P38); mandatory-record budget errors (P39); endless ladder repair (P40); unknown red provenance (P41). Target pattern: the smallest reused native owner chain, closed by property-exercising, independently reviewed, scope-bound evidence. Missing labels are assigned per slice using the repo’s capability states (`absent/unallocated`, `contract_only`, `producer_missing`, `artifact_missing`, `bridge_missing`, `consumer_missing`, `verification_missing`, `implemented_but_not_orchestrated`, `surface_missing`, `surface_out_of_scope`, `semantic_test_missing`); no planning artifact upgrades one of these.

Primary local references:

- `AGENTS.md`; `policy-engine/CONTRIBUTING.md`; `policy-engine/docs/reference/policy-design-case-failure-patterns.md` (especially P29, P31–P41).
- `policy-engine/docs/research/universal-policy-design/external-foundations/lifecycle/06-delivery-and-review.md` (R01–R12; W0–W6; T01–T20; source freeze, surfaces, migration, and UNRUN limit).
- `policy-engine/docs/research/universal-policy-design/external-foundations/acquisition/05-implementation-and-review.md` (A0–A7; AP01–AP19; exact source reconciliation, scoped deployment dossier, and conditional gates).
- `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md` (§3.5.7 E1–E14; §3.5.13; §3.5.14/P38; §8.5 authoritative task standing; §8.6 predicates; §§11–12 acceptance/closeout).
- `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` (“Execution Doctrine”; vertical closure, server-side audience auth, MACHINE twin, seeded negatives, verification economics).
- `policy-engine/docs/research/development-programs/2026-09-30-post-e02/README.md`, `roadmap.md`, `maintenance.md`, and `validation.json` (proposal status, E02 scenarios, exact-scope rebinding, and the validation artifact’s explicit non-acceptance limits).
