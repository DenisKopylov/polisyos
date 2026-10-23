# R4 — persisted conditional transport diagnostics

Status: G selects implementation with the revisions below to the author's R4 proposal at `f12fb9895a4009ce77828554f4c5c18d83e6ec15`. Historical `7 PASS / 1 FAIL` is author-reported, source-qualified evidence over manually supplied SCMs, not this document's runtime verification. No finding closure or code acceptance.

## Selection and outer invariant

Extend the existing `TransportabilityResult` with optional strict/frozen `candidate_diagnostics: TransportabilityCandidateDiagnosticV1 | None`, reused within `CausalEffectReport`. No independent candidate artifact family, duplicated scheduler or new authority status lattice. The nested execution outcome describes a candidate attempt, never protected eligibility.

When the operative legal relation is unverified, explicitly construct and preserve outer `status=UNSUPPORTED`, `transport_mode=NONE`, `feasible=false`, the exact existing legal refusal and `requires_expert_review=true` with its reasons. Never rely on today's model defaults (`IDENTIFIED`, `DIRECT`, confidence 1, feasible true). A candidate formula/score must not populate outer authoritative formula/estimand/confidence/identification-bound fields. Existing outer unresolved fields retain their documented refusal semantics.

**Change from the author's proposal:** new refused results do not mirror a candidate scalar into top-level `id_confidence_under_pag`, `pag_dag_sample_size`, or `pag_transportable_count`. Keep them absent/null for this route. Their presence is too easy for an old consumer to treat as evidential confidence. Historical values remain readable under their own source representation, with no new meaning imputed to them. An export needing old shape may show only the refusal and an explicit omission notice; it cannot silently strip a diagnostic and claim a lossless full-result round trip.

## Minimum nested contract

Reuse existing enums/ref/attempt/resource types where they carry these meanings; do not create a second transport result inside the result. New closed discriminator values describe execution, not a new authority lattice.

| Logical field group | Required semantics |
|---|---|
| Identity | `schema_version=1.0`; stable diagnostic semantics/profile revision; actual attempt reference and implementation/backend version |
| Execution disposition | Completed, partial, unsupported, error, or not-run with typed reason; mutually consistent value/payload requirements. Missing computation cannot be encoded as a numeric zero |
| Input binding | Exact graph artifact and selected manifest profile, graph type/content digest, selection-diagram or named model/plan relation, canonical query/intervention, source/target contexts and their content identities; actual solver inputs, not earlier requested inputs |
| Assumptions | Manual/fitted/generated graph provenance, supported graph profile, unresolved scientific/legal predicates, transformation/orientation policy and interpretation limit |
| Computation | Registered solver/algorithm revision, actual parameters, seed where used, resource budget and termination reason; distinguish requested from effective profile |
| Result | Typed conditional formula, diagnostic statistic or sample sensitivity output that the actual algorithm produced; value cannot be invented by projection/defaults |
| Accounting | Separate generation and solver partitions, linked by admitted member identity: proposals/duplicates/invalid/validated and evaluated/completed/failed/not-run; actual budgets and termination per phase; retain existing attempt receipts |
| Scope and time | Candidate-only allowed uses and forbidden promotion uses using existing authority boundary; evaluation time, graph/context valid/observation time where known, unknown currentness explicitly retained |

No universal mandatory legal-evidence envelope is introduced: bind the refusal and any actually present relevant refs, never fabricate legal source IDs. Inline bounded inputs or their exact refs are acceptable through existing serializers; large traces remain referenced. Validation verifies cross-field invariants and relation to outer result and report, not just object shape.

## What the PAG statistic may say

The old binary-orientation path is not admissible for this diagnostic: some PAG endpoint/confounding semantics are lost, and at the question pin the real scalar solver refuses PAG/CPDAG before reaching it. Do not remove that gate or relabel the old ratio. Implement [06's registered validated-family profile](06-validated-partial-graph-profile.md) at the candidate method boundary; call the existing resolved DAG/ADMG solver only for validated members within its actual supported domain.

Use **selected validated-family sensitivity**. The primary result is a count/vector of the actual existing transport statuses and modes, with one source-bound outcome per member; do not call every non-unsupported outcome success. For this profile an optional `identified_member_fraction` is exactly:

`count(valid completed member outcomes with status IDENTIFIED) / count(all valid completed member outcomes)`.

The denominator includes completed `PARTIALLY_IDENTIFIED`, `BOUNDED_NON_IDENTIFIED` and `UNSUPPORTED` outcomes; these statuses are displayed separately. Errors, interrupted and unstarted evaluations are outside that denominator and visible beside it, along with total admitted members. Inconsistent status/mode/feasibility or missing method-required proof is an invalid result/error, not a completed outcome. This uses the existing solver's conditional identification contract for the pinned graph/query; it is not verification of the graph's real-world truth. Zero denominator has no fraction. Never emit `id_confidence_under_pag` in the new nested schema.

The fraction is descriptive of a selected family and actual completed calls, not the probability of transportability, posterior confidence, an identification bound or a result for the entire PAG class. A fraction of one with errors or truncated coverage remains visibly incomplete. All-completed identification in a selected family still does not establish whole-class identification.

Generation and evaluation are distinct partitions in the existing attempt record, not new ledger services. Generation records total proposals, duplicate proposals, rejected/invalid proposals, validation-incomplete proposals, and unique admitted members; each proposal has exactly one final disposition. Evaluation records admitted unique members, not started, interrupted, completed outcomes partitioned by existing status/mode, and errors; their totals reconcile. An early stopped generator cannot know the number of all ungenerated completions: record unused declared attempt budget and `coverage=not_established`, not a fabricated universe count. Persist seed/tie-breaker, effective budgets, validator/solver revisions and stopping reason. A selection diagram's transport-domain S-nodes are not PAG sample-selection variables; preserve both roles distinctly.

A genuine whole-class or probabilistic method may later supply a separately registered result profile and its domain/proof/sampling law. The shared envelope admits versioned result profiles through the same owner mechanism, not a central enum for each algorithm. Extend result payloads through the existing owned artifact/ref and profile-resolution mechanism, not arbitrary dictionaries or artifact-supplied executable types. Consumers lacking a result profile must refuse that typed interpretation; generic authorized inspection may retain it opaque. An independently registered outer-refusal-only projection may remain readable with a declared diagnostic omission, but may not replace an unknown diagnostic with `None` and claim a full compatible read. No flag, sample threshold or larger sample count substitutes for a soundness/coverage proof. Search prioritization may use a descriptive fraction only as candidate information; it never clears an authority gate.

## Execution and storage path

1. Resolve requested operation and resource/access eligibility; freeze graph/query/context/profile/solver selection in the existing attempt. The graph resolver must return the actual selected profile alongside the model. Reject identity ambiguity; do not fetch a fresh default manifest after computation.
2. Evaluate the protected relation using the existing Lex route. If unknown at policy-authority scope, create the explicit refused outer result. If access to compute is itself prohibited/unestablished under its applicable policy, do not run that operation.
3. Extend the owned transport input resolver and node metadata with an optional **explicit candidate request**: a strict request binds registered profile identity/revision and a resource-budget selection resolved by the existing compute permit/policy (not a new human approval or caller-defined cap). Absent means no new attempt; explicit null/malformed/unknown profile is a typed refusal, not absence. A trusted search planner may create this request as candidate intent through the same entry point. Existing injected `pag_identification_policy=probabilistic`, `pag_max_dag_samples=100`, or an omitted/default seed does not constitute this intent. Persist the request and resolved effective values; expose it through the existing workflow DTO/intake/generated clients where that route is public. No new endpoint is required.
4. In `TransportabilityResolutionLoop.resolve`, split the current early Lex-refusal return: retain its exact outer refused result and independently invoke the requested candidate branch only after input/access/resource admission. For resolved DAG/ADMG inputs invoke the existing solver; for PAG invoke profile 06 first, then the existing solver per admitted member. CPDAG is unsupported by that PAG profile; retain direct CPDAG refusal until a separately registered DAG-equivalence profile exists. Do not reinterpret CPDAG as PAG. That future extension does not block this PAG or resolved-DAG/ADMG work. This branch belongs to the existing transport-method/node owner, not a second transport service. The direct scalar PAG/CPDAG gate stays unchanged. Do not reconstruct “no legal S-nodes” as verified absence of legal mechanisms: the candidate explicitly says that policy-level legal effects are unverified/excluded from this conditional graph calculation. Catch typed unsupported/resource/solver failures into the nested disposition without replacing the legal refusal. Reuse existing compute permits; no unbounded sampling or automatic retry storm.
5. Bind result lineage to graph, contexts/query inputs and relevant source report via existing selected `InputRef`s. Persist the immutable result, then the report containing the same result/identity. Publish the existing state/current-head update only after both succeed, using its normal concurrency control. A crash/partial dual write must not expose a mixed report/result generation; retry is idempotent for the exact attempt.
6. Fresh readers validate owner representation, content/profile and nested/outer agreement. A fresh GET reads the persisted verified projection; it does not invoke a solver, migrate an entire corpus or reinterpret old results on demand.

Candidate computation is optional for unrelated operations. Once explicitly requested under a supported bounded profile, “always unavailable” is not success: the real conditional positive and removal test are required. Budget/cancellation/error statuses remain truthful and do not weaken outer authority refusal.

## Versions and history

Select new result payload/manifest `ir.transportability_result@2.2`, stable DTO contract ID `ir.transportability_result.v2`; nested diagnostic `1.0`; report payload/manifest `ir.causal_effect_report@1.1`, stable contract ID `ir.causal_effect_report.v1`. These are selected new writer contracts, not claims that historical versions were sound or aligned. These identifiers are allocated relative to the question source, not reserved forever against concurrent work: at implementation rebind, reuse an already delivered identical contract or choose the next unused owner version if the number is occupied by different semantics, with an explicit handoff mapping and regenerated consumers. Never overwrite an occupied meaning. Such collision resolution preserves this architecture and does not require another abstract choice from G.

Apply IR-Q1/Q2, not a standalone migration policy. At the question pin the result DTO defaults to 2.1, writer manifest to 1.0, and migration declarations cover 1.0/2.0. Build an explicit source-tuple compatibility matrix before writer enablement. Only after owner establishment, historical 1.0/2.0/2.1 payloads and report 1.0 may be read through their exact validated historical tuples and explicit transformations, with `candidate_diagnostics=None` for genuinely old forms. A version label alone does not qualify an arbitrary payload or mismatched manifest. Preserve original schema/version/bytes in read context and lineage. Do not globally restamp history as 2.2.

Unknown future result/report versions, unregistered tuples and old readers without 2.2/1.1 support refuse typed consumption. A historical source claiming the new field under an old incompatible schema is a conflict, not an absent default. Upgrade all required consumers before new emission; keep an explicit no-new-diagnostic old writer mode only if that older representation is genuinely supported and the omitted capability is reported as unavailable. No hidden JSON-field dropping.

## Required consumer migration

Carry forward the complete author's 33-path seed inventory: 22 adoption paths, three documentation companions, eight test modules. Reconcile its exact paths against implementation source and add newly discovered direct/indirect readers; the seed count is not a permanent scope cap. The source path sets are pinned in the input receipt, not copied source bodies.

| Owner/route | Required behavior |
|---|---|
| `scientist/nodes/builtins/causal/resolve_transport.py` and result helpers | Actual candidate production, selected input lineage, coherent result/report/state generation; outer state remains unsupported |
| `ir/analytics/transportability.py`, `causal.py`, `privacy_transportability.py`, `transport_resolution_results.py` | Strict nested/outer semantics, load/persist/transform preservation, versioned migration; no candidate-to-proof conversion |
| Readiness, `transportability_required_pass.py`, `governance_gate_requests.py` | Decide from protected outer result/proof basis, never candidate success or field presence; report 1.1 consumed only by upgraded reader |
| `scientist/cross_graph/compiler.py`, calibration leaderboard, `runtime/quality/status_deficits.py` | No improvement in protected assessment/confidence/rank/readiness from nested candidate; unsupported remains blocked |
| Decision-packet causal sections, HTTP debug/API, browser/audit/export | Separate conditional diagnostic with assumptions, actual scope, truncation/error and unchanged refusal; filter by audience/access; no unexplained confidence badge |
| IR root/analytics facades, ABI/catalog/snapshots/migration registry | Same defining DTO object on supported facades; explicit schema versions and generated companions from one source |

PUBLIC may receive an authorized refusal/explanation or a permitted clearly conditional projection under existing audience policy. Raw graphs/data and expert diagnostic detail are not automatically PUBLIC. REVIEWER/EXPERT and machine clients receive typed limitations appropriate to their access. A new machine route must consume the same semantics, not scrape display prose.

## Acceptance and adversarial signals

- Full actual solver → result CAS → report CAS → fresh consumer/GET positive over authorized manual inputs: substantive diagnostic survives, exact graph/query/context/profile bind, all outer refusal fields unchanged. Manual fixtures prove only that conditional route.
- Remove solver/property while retaining fields/labels: positive fails. Swap graph topology, selected profile, query or contexts: provenance/semantic check fails; same variable names cannot satisfy B33.
- Populate an attractive candidate score/formula, including a ratio of one, while legal evidence is missing: every protected consumer, proof projection, rank and readiness still refuses. New refused output has no legacy scalar mirror.
- Zero attempted/zero completed, only duplicates, all invalid, validation-incomplete, partially failed, budget exhaustion, cancellation and unsupported graph profile have truthful two-phase accounting. An arbitrary DAG orientation is not certified as a PAG completion. Preserve bidirected and compelled marks; removing membership validation while retaining labels must fail. Direct scalar PAG/CPDAG still refuses.
- Explicit request triggers the real candidate bridge; omission does not silently launch sampling. Null/malformed request is not defaulted. A removal of the branch, planner-intent propagation or resource admission fails its corresponding positive/negative. A caller permission Boolean never substitutes for the actual access owner.
- Wrong nested version, outer/nested conflict, original/new version tuple mismatch, conflicting aliases and unknown future versions refuse; read/write/rollback matrix preserves old bytes and known semantics.
- Crash between result/report/state persistence cannot produce a current mixed generation. Cached candidate reuse under changed graph, profile, purpose, solver or access epoch is rejected/re-evaluated as appropriate. Late legal evidence cannot mutate historical refusal.

Pattern pass: P01/P02/P03/P04/P05/P07/P08/P10/P14/P27/P29/P31/P32/P35/P37/P38/P40. The defining property is useful conditional computation without authority promotion; both unconditional refusal and scalar laundering fail it. Formal original findings remain separately adjudicated.
