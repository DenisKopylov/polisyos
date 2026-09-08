# GY-PR1a Data-Only First Governed Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Also use
> `superpowers:test-driven-development` for every Phase-2 source change and
> `superpowers:verification-before-completion` before every completion claim.

**Goal:** Produce the first real, canonical, production-lane
`consumer_promotable=True` receipt for a data-only (`simulate_only`) generation
cycle without constructing authority evidence in a test and without requiring
an institutional appointment.

**Architecture:** Keep the existing N7 unsatisfied gap immutable. Add a
separately versioned, CAS-backed positive admission for the
`certified_skg_identity_bridge` disjunct, verified by the Academic SKG owner and
CG2. CG2 consumes only a CAS-backed, behaviorally verified production corpus
derived from pre-existing independently adjudicated observations. Re-enter N8
through an isolated Foundry extension registry, dispatch the verified
certificate as the method's exact output contract, produce the already-
supported S10 `transported_limited` posture, persist the unchanged
`ValueGateReceipt`, and supply the existing N9 writers from an owner-derived
production context provider. S8 remains unranked; the appointment-dependent
pilot path remains PR1b.

**Tech Stack:** Python 3.14, Pydantic v2 strict/frozen DTOs, the existing core
`ArtifactStore`, Academic SKG/Data Forge, CG1/CG2, Foundry method selection and
dispatch, S10 forecast support, the N8 generation cycle, and canonical N9
promotion.

**Spec:** This document is the ratified contract design, INT-R9
pre-registration, and implementation plan. The N7 and CG2 additive families
are authorized; no other governed contract is.

## Global Constraints

- Phase 1 changes and commits only this document. No production source, test,
  governed artifact, schema, generated client, OpenAPI source, frozen receipt
  epoch, or active plan moves in Phase 1.
- The worktree is
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine`
  on `codex/gy-pr1a-data-only-promotion`. Every command below uses absolute
  paths. Before every commit, run `git status -sb` and require that exact
  branch attachment.
- No `checkout`, `switch`, `stash`, rebase, reset, force push, other worktree,
  or other lane is permitted.
- Phase 2 may add the explicitly ratified N7 contract family designed here.
  Every other governed contract remains read-only except the separately
  ratified CG2 family below. Existing predicates may be reused or made harder
  to bypass; none may be weakened.
- The architect ratified that N7 family and, separately, the additive CG2
  production-calibration family specified below. Those are the only two
  governed contract families this task may add or change. A third governed
  contract change is a stop.
- The first result-bearing row inspection is governed by `INT-R9` Option B.
  The pre-registration in Section 0 is immutable after its commit except by a
  new prospective amendment committed before any replacement case is opened.
  No sequence-level number or statistical-family claim is available.
- A direct `ValueGateReceipt(...)` or a caller-provided truth value for
  admissibility/effective independence is a stop, not a test technique.
- Targeted Phase-2 verification uses exact node IDs with `-x --lf`; each red follows a
  green positive control. Run the complete affected test file once at the end
  of its group. Do not run a directory-wide or repository-wide suite.
- Transport proof nodes run with `--extra solvers`. A skip naming the missing
  extra is a non-receipt and never a pass.

---

## 0. INT-R9 Option-B Pre-registration — Sealed Before Row Inspection

This section is the prospective record required before the first Academic SKG,
calibration, numeric-evidence, or production-data row is inspected in Phase 2.
The registration revision is the first branch commit whose plan blob contains
this section; its exact commit hash and commit time must be appended to the
task journal before the feasibility scan starts. The pre-registration base is
`3de7a3f26`.

### Claim boundary

`INT-R9` resolved to Option B: result-informed repair remains possible, so all
sequence-level probability was withdrawn. This run may preserve a falsifiable
custody record of prospectivity, firstness, substitutions, chronology,
adjudication, deviations, negative terminals, publication, correction, and
whether a prohibited substitution occurred. It may not be projected as
statistical family control, population performance, compliance, competence,
production readiness, or any other probabilistic claim.

The Git commit establishes repository-visible commit chronology. It does
**not** by itself establish prospectivity or firstness for a public `INT-K06`
claim, independently witnessed transaction
visibility, sealed holdout custody, or named-human adjudication that DS12 would
need to issue a public `INT-K06` claim. Those fields remain explicitly
`not_established` unless an independent owner receipt already exists; this task
does not create that third governance capability. The internal canonical
promotion receipt may be produced, but the journal is an input to later DS12
custody rather than a public custody attestation.

### Registered population and production-calibration source

The sole source universe is the Runtime-pinned production Academic SKG at:

```text
production_data/policyos_academic_runtime_slim_20260411T112032Z/
academic/graph/scholar_knowledge.duckdb
```

The scan pins `MAX(ac_skg_versions.version_id)`, the database byte hash, and the
owner snapshot reference returned by `SKGQuery.skg_snapshot_ref`. The sole
selector implementation is the content-bound source text recorded in the
pre-inspection journal before its first database query. It implements the
following query contract exactly; the one positional parameter is exactly the
UTF-8 string `duckdb://` followed by the resolved absolute database path.

<!-- GY_PR1A_SELECTOR_SQL_V1_BEGIN -->
```sql
WITH pinned_version AS (
    SELECT MAX(version_id) AS version_id
    FROM ac_skg_versions
)
SELECT
    CAST(? AS VARCHAR) || '#v' || CAST(v.version_id AS VARCHAR)
        AS skg_snapshot_ref,
    TRIM(p.numeric_id) AS numeric_id,
    TRIM(e.edge_id) AS edge_id,
    TRIM(p.openalex_id) AS openalex_id,
    TRIM(c.claim_id) AS claim_id,
    TRIM(e.src) AS edge_src,
    TRIM(e.dst) AS edge_dst,
    TRIM(t.target_context_id) AS target_context_id,
    TRIM(p.estimate_type) AS estimate_type
FROM pinned_version AS v
CROSS JOIN ac_skg_simulation_parameters AS p
CROSS JOIN LATERAL json_each(
    CASE
        WHEN json_valid(p.linked_claim_ids_json)
        THEN p.linked_claim_ids_json
        ELSE '[]'
    END
) AS claim_ref
JOIN ac_skg_span_grounded_claims AS c
  ON c.claim_id = json_extract_string(claim_ref.value, '$')
 AND c.openalex_id = p.openalex_id
JOIN ac_skg_edge_evidence AS ee
  ON ee.claim_id = c.claim_id
 AND ee.openalex_id = c.openalex_id
JOIN ac_skg_edges AS e
  ON e.edge_id = ee.edge_id
 AND e.src = ee.src
 AND e.dst = ee.dst
 AND e.direction = ee.direction
JOIN ac_skg_articles AS a
  ON a.openalex_id = p.openalex_id
JOIN ac_skg_transport_scores AS t
  ON t.edge_id = e.edge_id
WHERE v.version_id IS NOT NULL
  AND claim_ref.type = 'VARCHAR'
  AND TRIM(p.numeric_id) <> ''
  AND TRIM(p.openalex_id) <> ''
  AND TRIM(p.estimate_type) <> ''
  AND isfinite(p.point_estimate)
  AND TRIM(c.claim_id) <> ''
  AND TRIM(e.edge_id) <> ''
  AND TRIM(e.src) <> ''
  AND TRIM(e.dst) <> ''
  AND TRIM(t.target_context_id) <> ''
  AND a.retracted = FALSE
  AND a.skg_version <= v.version_id
  AND c.skg_version <= v.version_id
  AND ee.skg_version <= v.version_id
  AND t.skg_version <= v.version_id
  AND c.cause = ee.src
  AND c.effect = ee.dst
  AND c.direction = ee.direction
```
<!-- GY_PR1A_SELECTOR_SQL_V1_END -->

The selector-query SHA-256 is
`a69f142d098b4e6f3feb382f9ba0427a399415421bc918813eeb7300a2d770c6`;
it is the digest of the exact
UTF-8 SQL bytes after the fenced-code newline through and including the newline
immediately before the closing fence. The required tables are named above; a missing table,
column, version, or unreadable database is an empty structural population and
a terminal, not permission to use an ambient view or alternative join.

“Latest version” means the pinned `MAX(version_id)` plus the current
primary-key-materialized rows whose recorded versions are no later than that
pin. “Exact numeric” means the nonempty exact IDs and estimate type, finite
stored point estimate, exact JSON-string claim link, exact work identity, exact
claim/evidence/edge source-destination-direction identity, non-retracted work,
and nonempty exact transport-context identity expressed by the SQL. It does
not inspect interval adequacy, calibration labels, CG2, N7, N8, or promotion
success.

After the SQL returns, the selector permits only this deterministic
normalization: reject a row unless all nine projected fields are strings;
collapse duplicate rows by equality of the complete nine-field tuple; sort the
complete population by the concatenation of each field's UTF-8 bytes preceded
by its unsigned eight-byte big-endian length; and hash that ordered encoding as
the structural-population digest. No locale collation, database result order,
ambient view, interactive filter, alternate join, or later query is permitted.
That complete structural denominator is the selection frame; it is not
narrowed to rows already known to qualify.

The separate **calibration population** is the complete join from the selected
stratum to pre-existing independently adjudicated relation-outcome evidence. A
materialized adjudication counts only when its authority-bearing
`scientist.claim_adjudication.admitted_batch` CAS artifact, producer, raw input,
candidate, evaluation, and source lineage can all be read and content-bound.
An SKG assertion, CG1/CG2 decision, LLM label, code literal, test fixture, CG6
anchor, or contract seed can never supply the outcome label it is meant to
calibrate.

One distinct observation is keyed by:

```text
result_artifact_id | claim_id | openalex_id | numeric_id | edge_id |
target_context_id | reference_epoch
```

Duplicates collapse to one observation. The stratum is derived, never filled:

```text
operator_family = the exact registered L6 operator resolved from edge.src
reference_region = the nonempty owner target_context_id
relation_type = exact
```

Missing context is disqualifying; it must not fall back to `global`. A genuine
production source is therefore a content-addressed Runtime projection over
this pinned, independently labelled population, with per-observation refs and
hashes plus derived stratum anchors. It is not an inline
`CalibrationStratumRecord(sample_count=20)`.

### Fixed case, stratum, and candidate/estimand binding rule

Selection is non-discretionary and fixed before the scan. The selection seed
is the literal `GY-PR1A-INT-R9-PRIMARY-2026-09-02-V1`:

1. Execute the content-bound selector once and enumerate the complete
   structural case population above. Do not require or inspect calibration,
   native interval adequacy, transport score, CG2, N7, N8, or promotion status
   while selecting; the exact nonempty transport-context identity is only a
   structural join key fixed by the query contract.
2. For every structural row compute
   `sha256(seed | skg_snapshot_ref | numeric_id | edge_id | openalex_id |
   claim_id)` and select the bytewise smallest `(digest, numeric_id, edge_id,
   openalex_id, claim_id, target_context_id)` using the length-prefixed UTF-8
   ordering above. An empty structural population is a zero result and stops
   the task. No second row is tried if the selected row later refuses.
3. Derive exactly one stratum from that row using the mapping above. Missing or
   ambiguous operator/context makes this selected case a negative terminal; it
   does not cause selection of the next digest.
4. Bind the candidate mechanically as follows:
   `candidate_id = "gy-pr1a-primary:" + sha256(snapshot_ref | stratum_key |
   selection_digest | numeric_id | edge_id | openalex_id | claim_id)`;
   treatment/operator is the exact registered edge source;
   outcome/target is the exact writable WMR edge destination; estimand is the
   row's nonempty normalized `estimate_type`; population/region is the exact
   `target_context_id`; point estimate, unit, native interval, confidence level,
   and standard error are copied from the same numeric row without synthesis.

5. Only after the selection receipt and resolved binding have been appended to
   the journal, enumerate the independent calibration population for **that
   exact stratum**. Require at least 20 distinct observations. Counts in every
   other stratum are reported for denominator completeness but can neither
   replace nor rescue the selected stratum.

This algorithm fixes which case, stratum, and binding are evaluated before any
result-bearing predicate is read. Its resolved identifiers are appended before
the calibration feasibility result and before any CG2 or N7 implementation.

### Prospective disqualifiers and chronology

The selected observation is disqualified by any missing/tampered CAS lineage,
wrong SKG version, non-exact join, non-native interval, missing registered
operator or writable target, missing/ambiguous context or transport row,
missing independent adjudicated outcome, duplicate-only sample inflation,
fewer than 20 observations in its stratum, stale reference epoch, or inability
to resolve genuine S5/S6/S8 inputs. A disqualification is a negative terminal.
It cannot be repaired by changing the case, row, stratum, estimand, criteria,
threshold, order, or exclusion after inspection.

Generic implementation repair after a failure is allowed and recorded as
adaptive continuation, but it neither re-runs nor re-scores the first attempt.
“Intrinsically unsuitable” means only a pre-registered disqualifier in this
section, evidenced in the append-only record; it never means a refusal, failure
to promote, adverse calibration count, inconvenient estimate, or an outcome
that would leave the acceptance predicate red. Such a terminal remains this
attempt's first result-bearing terminal. A replacement requires an explicitly
new prospective registration, new immutable selection receipt, affirmative
no-access proof for the replacement before its first row inspection, and an
append-only explanation of why the old terminal cannot be rescored or erased.
It is never a retry, rescue, or silent continuation of this selected case.

Before inspection, create the append-only journal with these fields:

- registration base/head/time and environment/`sys.prefix`;
- protocol, implementation, rule, schema, dependency, evaluator, and model
  versions (model is `not_applicable_no_llm` for this deterministic scan);
- population, source-root/version/hash, selection/order/stopping rules,
  disqualifiers, protected action, and no-substitution rule;
- first-inspection time, first result-bearing run, every terminal, repair,
  substitution request/disposition, deviation, incident, adjudication/dissent,
  publication, challenge, correction, and current head; and
- `prohibited_substitution_found`, initially `false` and changed only by an
  appended event—never by rewriting history.

---

## 1. N7 Verdict — Non-Institutional in Authority, Incomplete in Engineering

### Verdict

The certified SKG route is a real **non-institutional authority path**. Its
competent owners are PolicyOS engineering owners: Academic SKG/Data Forge can
assert exact source/numeric identity, and CG2 can recompute grounding,
applicability, calibration, and production promotability. Neither act assigns
a rollout owner, authorizes execution, or signs for an institution. Therefore
the architect's ruling that a data-only promotion needs no appointment
survives, and the new institutional stop rule does not fire.

The path is nevertheless **not presently buildable end to end on this base**.
There are two different gaps:

1. N7 has no positive representation. The only versioned record is an
   unsatisfied acquisition gap whose two alternatives are both statically
   `Literal["unsatisfied"]`.
2. CG2 has no production calibration population and no admitted production
   provenance. Its production store deliberately returns an empty typed
   ledger; its allow-list admits only the non-promotable contract-test seed.
   The nearby CG6 anchor set is explicitly typed `wired_into_cg2=False`, is too
   small, uses different strata, and has an unaccepted provenance.

The first is the additive N7 contract design ratified after Phase 1. The second
was an unowned engineering prerequisite at `3de7a3f26`; the architect has now
allocated it to GY-PR1a and ratified it as the task's second additive governed
family. Phase 2 begins with a feasibility census rather than construction: if
the pre-existing owner population contains no qualifying >=20-observation
stratum, engineering cannot manufacture one and the task stops.

Capability labels at entry are:

| Capability | Current label | Decisive observation |
| --- | --- | --- |
| N7 positive bridge representation | `artifact_missing` | Both represented alternatives are forced unsatisfied. |
| Academic SKG exact-identity certificate producer | `producer_missing` | No positive certificate/admission symbol exists in the complete Python census. |
| CG2 production calibration population | `producer_missing`, allocated here subject to Task-0 feasibility | Production-owned store returns `records=()`; no source may be synthesized. |
| CG6 to CG2 calibration path | `bridge_missing` + `implemented_but_not_orchestrated` | `wired_into_cg2` is `Literal[False]`; dimensions and provenance do not match CG2. |
| N7-to-N8 positive re-entry | `bridge_missing` | N8 stops at `treatment_assignment_not_owner_derived`. |
| N7/N8 to the existing CG2 production-promotability consumer | `bridge_missing` | The N9 consumer exists, but N7/N8 never supplies a positively admitted candidate to it. |

### Contract evidence: the missing positive representation

Recorded command:

```bash
/usr/bin/sed -n '286,342p' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/acquisition_planner.py
/usr/bin/sed -n '2184,2210p' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/generation_cycle.py
```

Decisive output:

```text
_VALUE_INPUT_WORLD_KNOWLEDGE_SCHEMA_VERSION =
    "policyos.runtime.value_input_world_knowledge_gap.v1"
class _ValueInputWorldKnowledgeAlternative(BaseModel):
    alternative_id: Literal[
        "owner_rollout_assignment",
        "certified_skg_identity_bridge",
    ]
    satisfaction_status: Literal["unsatisfied"]
...
return _blocked_value_observation(
    code="treatment_assignment_not_owner_derived",
    ...
    acquisition_requirement=value_input_world_knowledge_requirement_gap(...),
)
```

The existing record is therefore an honest gap, not a union that forgot to
exercise its positive member. Rewriting its literal in place would silently
reinterpret persisted v1 rows and is forbidden.

The previously run positive control was:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_generation_cycle.py::test_typed_value_world_knowledge_gap_routes_without_renaming_blocker -q -x
```

It passed and returned the canonical
`treatment_assignment_not_owner_derived` routing result with no acquisition
receipt. That green proves the v1 negative route is live; it is not evidence
for a positive route.

### What a satisfied bridge must assert

The positive bridge is a two-stage epistemic certificate plus N7 admission,
not an appointment. The Data Forge producer asserts source-side identity; the
Runtime resolver independently recomputes it and adds live-cycle/CG2
admission. Together they must establish:

- the exact Academic SKG version/root and the source-work/OpenAlex identity;
- the numeric row ID and raw-row content hash;
- treatment variable, outcome variable, estimand, estimate kind, direction,
  unit, point estimate, native confidence interval, confidence level, and
  standard error when present;
- that the interval is native source evidence rather than synthesized;
- exact same-version numeric -> claim -> edge -> work joins and their hashes;
- a declared target binding for candidate ID/content hash, design-problem hash,
  WMR ID/content hash/reference epoch, target jurisdiction, and policy/data
  time, which the runtime N7 resolver—not Data Forge—must establish against the
  live cycle;
- replayed CG1 relation status, contradiction set, relation/atom identity, and
  certificate hash, while preserving CG1's shadow-only boundary;
- a production-promotable CG2 resolution against its owner store, including
  anchor ID/hash, reference epoch/hash, relation stratum, and verifier
  provenance;
- source and target transport context, covariate row hashes, selection-diagram
  hash, target-data requirements, uncertainty and limitation refs; and
- an exact Foundry value-uncertainty output declaration whose runtime output is
  this certificate type, not a caller-shaped lookalike.

Predicate provenance is frozen at admission:

| Predicate | Required provenance |
| --- | --- |
| SKG numeric identity and joins | `recomputed` by Academic SKG/Data Forge |
| CG1 replay | `recomputed`, shadow input only |
| CG2 grounding/applicability/calibration | `independently_reconciled` against the production owner store |
| Transport diagram and applicability | `recomputed` by the transport owner |
| Candidate/problem/WMR/epoch binding | `recomputed` from the live cycle |
| Source snapshot authenticity | `independently_reconciled` against a Data Forge owner root; `not_established` blocks |
| Owner rollout assignment | not used in PR1a; only that sibling is `institutionally_supplied` |

No `consumer_asserted` or `not_established` predicate may make the admission
positive.

### Who is competent, and why this is engineering

CG1 cannot fill the role. The closed-door command was:

```bash
/usr/bin/sed -n '245,290p' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/grounding_relation.py
```

Its certificate is fixed to `shadow_only=True` and
`no_bind_admit_promote=True`, with validators rejecting any other value. CG1
may be replayed as evidence by CG2; it can never mint N7 satisfaction.

CG2 is the competent production verifier because the canonical N9 consumer
already admits production promotability only after
`resolve_grounding_decision_promotability` resolves the certificate against a
production-owned calibration store. That verification is a deterministic
PolicyOS knowledge claim. It neither appoints an actor nor authorizes an
external act, so it is engineering under the identity boundary.

### The production calibration store is deliberate typed absence, but unowned

Recorded source command:

```bash
/Applications/ChatGPT.app/Contents/Resources/rg -n '_CALIBRATION_OWNER_ALLOWLIST|_DEFAULT_CALIBRATION_MIN_SAMPLES|cg2_production_calibration_empty|none_wired_production_freezes|owned_calibration_anchor_missing' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/grounding_bind.py
```

Decisive output:

```text
79:_DEFAULT_CALIBRATION_MIN_SAMPLES = 20
80:_CALIBRATION_OWNER_ALLOWLIST = frozenset({"cg2_contract_seed_anchor"})
1052:validation_reasons.append("owned_calibration_anchor_missing")
1381:ledger_id="cg2_production_calibration_empty"
1382:source_id="none_wired_production_freezes"
```

Direct readback at `grounding_bind.py:1370-1402` shows production returns
`GroundingCalibrationLedger(records=())`; the populated seed is explicitly
`authority_scope="contract_testing"`. A complete binding-key search over the
tracked planning/debt corpus found no named task or debt owner for a production
CG2 population or for changing the production provenance admission:

```bash
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine grep -n -e 'cg2_production_calibration_empty' -e 'none_wired_production_freezes' -e 'owned_calibration_anchor_missing' -e 'wired_into_cg2' -- docs/plans docs/superpowers/plans docs/superpowers/journals
```

The historical ownership result at the Phase-1 commit is therefore `unowned
engineering gap`; this revision records the architect's later allocation to
GY-PR1a. Allocation does not create observations. This plan cannot treat the
contract-test seed as an owner population: production resolution explicitly
returns `non_production_anchor_scope` for that store.

CG6 is also a closed door, not an implicit future owner. Recorded commands:

```bash
/usr/bin/sed -n '233,242p' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py
/usr/bin/sed -n '2437,2471p' /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src/polisyos/runtime/quality/grounding_benchmark.py
```

The type and producer both force `wired_into_cg2: Literal[False] = False`.
The committed scoreboard has five strata, 10 anchors total, exactly two per
stratum, provenance `cg6_benchmark_calibration_v1`, and dimensions
`operator|target|exact_or_specialization`. CG2 requires at least 20 observations
per `operator_family|reference_region|relation_type` stratum and currently
accepts only `cg2_contract_seed_anchor`. CG6 is neither large enough nor
schema/provenance-compatible.

Recorded checker/readback commands:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tools/quality/validation/check_grounding_benchmark_contract.py --check --output-format json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py --check
```

Recorded decisive readback:

```text
CG6: 5 strata; 10 anchors; 2 per stratum; wired_into_cg2=false;
     headline false binds 0/6 across two growth epochs.
CG1/Fork B: 5,124 numeric identities; 3,579 numeric-edge bindings;
     13,092 relation rows; SAT:false-analog=1,076;
     UNKNOWN:unknown=12,016; Fork-A positive candidates=0.
```

The existing CG6 liveness test exercises bypass mutations, not a production
CG6-to-CG2 bridge. Phase-2 gate G0 therefore also requires a semantic test that
`wired_into_cg2=false` cannot make a production certificate promotable; there
is no such direct node now.

Phase-2 gate G0 is now the pre-registered feasibility census in Section 0. A
nonzero qualifying source authorizes Task 1 to implement its Runtime-owned
producer and behavioral verifier under the architect's second explicit
authorization. Zero is a completed capability finding and stops all source
work.

## 2. Versioned Positive N7 Admission Contract Design

### Additive family; no v1 reinterpretation

The architect has ratified this three-artifact family as one N7 design:

| Artifact | Proposed schema | Role |
| --- | --- | --- |
| Existing negative gap, unchanged | `policyos.runtime.value_input_world_knowledge_gap.v1` | Historical and current statement that neither alternative has yet been admitted. Both alternative rows remain `Literal["unsatisfied"]`. |
| Academic SKG bridge certificate | `policyos.data_forge.academic_skg_identity_bridge_certificate.v1` | Owner-produced exact identity, grounding, transport-input, uncertainty, and output-contract evidence. |
| Positive N7 admission | `policyos.runtime.value_input_world_knowledge_admission.v2` | A separately persisted decision that the `certified_skg_identity_bridge` disjunct satisfies the named v1 requirement for one exact candidate/problem/WMR epoch. |
| Admission resolution | `policyos.runtime.value_input_world_knowledge_admission_resolution.v1` | Runtime replay result: `admitted`, `refused`, or `not_established`, with recomputed reason and verifier provenance. |

The v2 admission contains a discriminated positive variant, proposed as
`CertifiedSKGIdentityBridgeSatisfiedV2`, with these load-bearing fields:

```text
schema_version = "policyos.runtime.value_input_world_knowledge_admission.v2"
requirement_gap_id = "requirement-gap:data_requirement:value-input-world-knowledge"
prior_gap_schema_version = "policyos.runtime.value_input_world_knowledge_gap.v1"
compiled_requirement_ref = "runtime-requirement:value-input-world-knowledge:v1"
alternative_id = "certified_skg_identity_bridge"
satisfaction_status = "satisfied"
candidate_id + candidate_content_hash + design_problem_ref
world_model_record_id + world_model_record_content_hash + reference_epoch
certificate_ref + certificate_content_hash
owner_root_refs + verifier_provenance_ref
predicate_provenance = "independently_reconciled"
authority_purpose = "value_input_world_knowledge_admission_only"
rule_version + valid_time + content_hash
```

`satisfaction_status="satisfied"` is a projection of the owner decision, not
the predicate that turns the gate on. N8 ignores the field until the repository
has resolved the CAS bytes and recomputed every decisive predicate. A
self-consistent caller-made v2 object is therefore still not admitted.

The certificate is strict/frozen and self-hashed. It carries the source-side
identity, native uncertainty, transport-input, and declared target-request
assertions in Section 1 plus:

- `contract_id` and a `value_uncertainty_output_contract(...)` declaration;
- `to_value_uncertainty(*, estimand, projection_binding)`, with the native
  interval and transport limitations preserved;
- no rollout, execution, publication, recommendation, or institutional
  authority; and
- a `may_not_use_for` envelope naming those denials.

The v2 Runtime admission, not the Data Forge certificate, carries the
live candidate/problem/WMR comparison and the resolved CG1/CG2 outcome. This
keeps the import direction legal: Runtime may consume Data Forge; Data Forge
does not import Runtime.

The Foundry adapter must declare the exact certificate class as its `report`
output contract and return the resolved instance. A declaration-only object,
an `EconometricResult` relabelled as an imported study, or
`MethodValueEvidence`'s non-production placeholder would be authority
laundering.

### Persistence and resolution

1. `AcademicSKGIdentityBridgeProducer` reads the owner Academic SKG snapshot,
   recomputes all source/numeric identities and joins, binds the opaque target
   request it was given, creates the certificate, canonicalizes it, and
   persists its exact bytes in the existing `ArtifactStore`. Data Forge does
   not import Runtime or decide candidate/WMR admissibility.
2. `ValueInputWorldKnowledgeAdmissionRepository` accepts only an
   `ArtifactRef` to those bytes. It reads them back, verifies the CAS hash,
   validates the strict type, recomputes the self hash, reruns the Academic SKG
   joins, compares the declared target request to the live
   candidate/problem/WMR, runs CG1 replay and CG2 production resolution, and
   only then persists the v2 admission and its verifier provenance root.
3. Resolution always begins from CAS. A caller-provided model instance or a
   matching string ID is insufficient. Candidate, problem, WMR, epoch,
   certificate, owner roots, and rule version are compared to the live cycle.
4. Any missing bytes, hash mismatch, stale epoch, cross-candidate/cross-problem
   substitution, synthesized interval, inexact join, CG1-only claim, failed
   CG2 production resolution, or unavailable source root returns `refused` or
   `not_established`; it never falls back to a Boolean.

### Receipt-to-N8 re-entry

The default N8 branch currently calls `load_value_data_profile` and then stops
at `treatment_assignment_not_owner_derived`. The positive bridge re-enters
*before* that rollout-panel call:

1. The N8 owner receives an admission `ArtifactRef` through its owner
   configuration, not through candidate-declared fields.
2. The resolver replays the v2 admission against the exact live candidate,
   problem, WMR, and existing v1 requirement identity.
3. If admitted, N8 selects the Academic SKG adapter using an isolated Foundry
   registry, dispatches it through `MethodDispatcher`, and requires the runtime
   `report` to be the exact resolved certificate type.
4. N8 independently reconstructs and solves transport. It does not treat the
   N7 certificate's status string as a transport result.
5. N8 builds and persists existing S10 `ForecastSupport` with
   `s5_base_origin="transported_scholar_estimate"`,
   `s5_support_label="transported_with_heavy_limitation"`, visible interval
   and limitation refs, real S5/S6/S8 inputs, and no target-panel
   `ForecastCalibrationRecord`. The existing S10 envelope must return pass and
   the N8 calibration receipt must return `forecast_tier="transported_limited"`.
6. N8 derives the real `ValueOuterSet`, persists the unchanged
   `ValueGateReceipt`, reads it back, and emits the valid `value_ready`
   observation. Only that observation reaches N9.

The existing S10 contract already supports step 5: transported support needs
uncertainty plus explicit limitations and treats calibration as
`not_applicable_non_observable`. What is missing is the N8 owner producer and
CAS resolver. `_build_s10_forecast_inputs` must not be reused unchanged: it
currently maps every non-simulation tier to `validated_local_model`, which
derives `observable_calibrated` and demands panel calibration. The new branch
must use the existing transported origin and label rather than fabricating
`n_treated`, `n_control`, `pre_periods`, or `post_periods` from a source study.

The S10 bridge still requires genuine S5 system-effect support, S6 firewall
refs, S8 provenance, design graph/context, method validity, equilibrium
handling, and limitation refs. If the live candidate cannot resolve those
existing inputs, Phase 2 stops; N7 transport evidence cannot be substituted
for them.

### Foundry isolation and selector binding

The global N8 governed catalog is frozen at 55 value methods. PR1a must not add
the adapter to global `_registry_boot.py` or regenerate that artifact. Use
`registry_scope()` plus the existing extension registration API. Add a
controlled catalog-snapshot path to both `select_value_method_for_problem` and
`method_selection_context_hash`, because both currently call
`ensure_all_methods_registered` and would otherwise admit ambient entry points
or a development scan. Selection, context hash, registry lookup, and dispatch
must use the same scoped registry instance and exact snapshot.

The selection manifest binds the typed contract target
`policyos.data_forge.academic_skg_identity_bridge_certificate.v1`; it does not
encode a certificate ID/hash as a fake `contract_target`. Artifact-instance
identity is admitted by the N7 CAS resolver and bound into the dispatched
certificate and `ValueOuterSet` provenance. Changing certificate ID/hash must
change the N7 admission/value output even if the compatible method class stays
the same.

### Why an old row stays unsatisfied

No migration, union widening, default, coercion, or validator fallback is
added to `_ValueInputWorldKnowledgeAlternative` or
`_ValueInputWorldKnowledgeGapMetadata`. Deserializing the exact old v1 bytes
still yields two unsatisfied alternatives and an unsatisfied aggregate.

The v2 admission references the v1 `requirement_gap_id`; it does not overwrite
the v1 artifact. N8 asks the v2 resolver whether the exact live requirement is
resolved. Absence or invalidity of v2 leaves the v1 gap and blocker byte-for-
byte equivalent. A regression test must round-trip pre-change v1 bytes after
the positive path passes and prove they still route to
`treatment_assignment_not_owner_derived`.

### Second ratified family: production CG2 calibration

The architect has separately authorized one additive CG2 family. It does not
widen `CalibrationStratumRecord`, reinterpret the contract seed, or accept a
caller ledger. It adds:

| Artifact | Proposed schema | Role |
| --- | --- | --- |
| Production observation | `policyos.runtime.cg2.production_calibration_observation.v1` | One independently adjudicated, source/claim/edge/numeric/context-bound outcome, with owner CAS lineage and reference epoch. |
| Production corpus | `policyos.runtime.cg2.production_calibration_corpus.v1` | Complete eligible calibration population for the frozen selected stratum, with the complete structural/grouped denominators retained as audit metadata, plus exclusions, owner-root hash, and observation refs. |
| Production resolution | `policyos.runtime.cg2.production_calibration_resolution.v1` | CAS replay result for one exact stratum: `calibrated`, `cold_start`, `drift`, or `refused`, with recomputed reasons and verifier provenance. |

`ProductionCG2CalibrationSource` belongs in
`src/polisyos/runtime/quality/production_grounding_calibration.py`. It opens the
Runtime-pinned Academic SKG through the public Data Forge read API, validates
the database/version and every admitted adjudication artifact, preserves the
complete structural/grouped census as audit metadata, projects every eligible
calibration observation for the one frozen selected stratum, persists those
observation and corpus bytes to CAS, reads them back, and only then derives the
existing aggregate `CalibrationStratumRecord` consumed by CG2. It does not
attempt to infer labels for every SKG row. Data Forge exports evidence; it does
not import Runtime or decide calibration.

The only new production provenance admitted is
`cg2_production_academic_skg_adjudication_v1`. Adding that string to the owner
allow-list is insufficient by itself: the CG2 production resolver must also
resolve the corpus, match the exact stratum/epoch/anchor/content/evidence
hashes, re-count distinct observation refs, verify every source lineage, and
require at least 20. The old `cg2_contract_seed_anchor` remains
`authority_scope="contract_testing"`, retains its current bytes, and still
resolves non-promotable. CG6 remains `wired_into_cg2=False`.

The behavioral verifier extends `check_grounding_bind_contract.py` and its
owned `grounding_bind_contract.json` artifact under this second authorization.
Its remove-the-property controls delete or duplicate an observation, forge an
adjudication/source hash, swap epoch/stratum, lower the distinct count, replace
the production corpus with the contract seed or CG6, and assert production
promotability turns red. Existing artifacts must continue to verify.

The five currently misdirected CG2 controls are repaired without changing
alias semantics: their shared setup uses a canonical exact-relation
certificate and first asserts it reached the intended stratum before checking
the calibration terminal. The `tax_credit_rate` synonym remains covered by a
separate alias test. A calibration negative that terminates at relation
canonicalization is not accepted as CG2 evidence.

## 3. Re-Derived Chain Census

These are the measurements already taken on the pinned branch; this section
records rather than reruns them.

### Complete tracked Python AST census

Recorded command shape (the script walked the complete tracked set returned by
`git ls-files`, parsed every file with `ast.parse`, and printed every positive
location):

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python - <<'PY'
import ast
import subprocess
from pathlib import Path

root = Path("/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine")

def files(pattern: str) -> list[Path]:
    raw = subprocess.check_output([
        "/opt/homebrew/bin/git", "-C", str(root), "ls-files", "-z", "--", pattern
    ])
    return [root / item.decode() for item in raw.split(b"\0") if item]

def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""

for label, pattern in (("src", "src/**/*.py"), ("tests", "tests/**/*.py")):
    paths = files(pattern)
    hits = {key: [] for key in (
        "class_definitions", "direct_constructors", "model_validate_calls",
        "literal_value_ready_calls", "context_provider_calls",
        "literal_value_ready_tokens",
    )}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(root)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ValueGateReceipt":
                hits["class_definitions"].append(f"{rel}:{node.lineno}")
            if isinstance(node, ast.Constant) and node.value == "value_ready":
                hits["literal_value_ready_tokens"].append(f"{rel}:{node.lineno}")
            if not isinstance(node, ast.Call):
                continue
            callee = dotted(node.func)
            leaf = callee.rsplit(".", 1)[-1]
            if leaf == "ValueGateReceipt":
                hits["direct_constructors"].append(f"{rel}:{node.lineno}")
            if callee.endswith("ValueGateReceipt.model_validate"):
                hits["model_validate_calls"].append(f"{rel}:{node.lineno}")
            if leaf == "ValuePortObservation" and any(
                kw.arg == "status"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value == "value_ready"
                for kw in node.keywords
            ):
                hits["literal_value_ready_calls"].append(f"{rel}:{node.lineno}")
            if leaf == "CanonicalN9PromotionPort" and any(
                kw.arg == "context_provider" for kw in node.keywords
            ):
                hits["context_provider_calls"].append(f"{rel}:{node.lineno}")
    print(label, "tracked_python_files", len(paths))
    for key, values in hits.items():
        print(key, len(values), values)
PY
```

Recorded output:

```text
src tracked_python_files 2617
class_definitions 1 ['src/polisyos/runtime/quality/generation_cycle.py:445']
direct_constructors 0 []
model_validate_calls 2 ['src/polisyos/runtime/quality/promotion_sequence.py:1530', 'src/polisyos/runtime/quality/promotion_sequence.py:1590']
literal_value_ready_calls 0 []
context_provider_calls 0 []
literal_value_ready_tokens 4 ['src/polisyos/runtime/quality/generation_cycle.py:170', 'src/polisyos/runtime/quality/generation_cycle.py:527', 'src/polisyos/runtime/quality/generation_cycle.py:3715', 'src/polisyos/runtime/quality/generation_cycle.py:5688']
tests tracked_python_files 2489
class_definitions 0 []
direct_constructors 2 ['tests/unit/runtime/quality/test_promotion_sequence.py:3909', 'tests/unit/runtime/quality/test_value_gate.py:2362']
model_validate_calls 4 ['tests/unit/runtime/quality/test_value_gate.py:3237', 'tests/unit/runtime/quality/test_value_gate.py:3284', 'tests/unit/runtime/quality/test_value_gate.py:3297', 'tests/unit/runtime/quality/test_value_gate.py:3328']
literal_value_ready_calls 1 ['tests/unit/runtime/quality/test_value_gate.py:3302']
context_provider_calls 5 ['tests/unit/runtime/quality/test_promotion_sequence.py:2044', 'tests/unit/runtime/quality/test_promotion_sequence.py:2114', 'tests/unit/runtime/quality/test_promotion_sequence.py:2173', 'tests/unit/runtime/quality/test_promotion_sequence.py:2722', 'tests/unit/runtime/quality/test_promotion_sequence.py:2759']
literal_value_ready_tokens 6 ['tests/unit/runtime/quality/test_open_world_risk.py:579', 'tests/unit/runtime/quality/test_value_gate.py:1899', 'tests/unit/runtime/quality/test_value_gate.py:2456', 'tests/unit/runtime/quality/test_value_gate.py:3303', 'tests/unit/runtime/quality/test_promotion_sequence.py:3826', 'tests/unit/runtime/quality/test_generation_cycle.py:841']
```

The source `model_validate` calls parse persisted owner/history projections and
mint nothing. The sole test `value_ready` call deliberately omits an owner
receipt and proves the `value_ready_requires_owner_receipts` guard. Thus it is
a negative positive-control, not a hidden producer.

### Complete bridge-vocabulary census

Recorded command shape:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python - <<'PY'
import re
import subprocess
from pathlib import Path

root = Path("/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine")
raw = subprocess.check_output([
    "/opt/homebrew/bin/git", "-C", str(root), "ls-files", "-z", "--",
    "src/**/*.py", "tests/**/*.py", "tools/**/*.py",
])
paths = [root / item.decode() for item in raw.split(b"\0") if item]
needle = "certified_skg_identity_bridge"
positive = re.compile(
    r"CertifiedSKGIdentityBridge|certified_skg_identity_bridge.{0,80}satisfied|"
    r"satisfied.{0,80}certified_skg_identity_bridge",
    re.IGNORECASE | re.DOTALL,
)
locations = []
positive_locations = []
for path in paths:
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), 1):
        locations.extend(
            f"{path.relative_to(root)}:{lineno}" for _ in range(line.count(needle))
        )
        if positive.search(line):
            positive_locations.append(f"{path.relative_to(root)}:{lineno}")
print("tracked_python_files", len(paths))
print("token_occurrences", len(locations), "files", len(set(x.rsplit(':', 1)[0] for x in locations)))
print("locations", locations)
print("positive_contract_symbols", len(positive_locations), positive_locations)
PY
```

Recorded output:

```text
tracked_python_files 5540
token_occurrences 8 files 3
locations [
  'src/polisyos/runtime/quality/acquisition_planner.py:292',
  'src/polisyos/runtime/quality/acquisition_planner.py:319',
  'src/polisyos/runtime/quality/acquisition_planner.py:3335',
  'tests/unit/runtime/quality/test_acquisition_planner.py:288',
  'tests/unit/runtime/quality/test_acquisition_planner.py:303',
  'tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py:561',
  'tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py:594',
  'tools/quality/validation/check_layer3_gy_n10_cg1_l2_relation_census.py:850',
]
positive_contract_symbols 0 []
```

The committed Fork-A census also remains empty. Its complete reported
denominators are 13,092 relation rows, 3,579 exact numeric-edge candidates,
2,967 numeric identities without an exact bound edge, 6,932 unresolved edge
tokens, and zero Fork-A evidence-candidate rows. The current checker is green
only for that negative census; it does not prove the proposed positive route.

## 4. N8 Ownership, Persistence, and a Valid `value_ready`

N8, not N7, Task K, or PA1, owns the value receipt. The existing contract at
`generation_cycle.py:445-501` already carries candidate, evaluation mode,
selected method, identification status, `ValueOuterSet`, transport and
calibration receipts, WMR identity/hash, value hash, WMR-cache posture, and
K-world before/after refs. Its validators recompute the two decisive WMR
consistency predicates.

The missing implementation must:

- consume only a CAS-resolved N7 admission;
- select and dispatch the actual Foundry adapter;
- derive a non-empty real `ValueOuterSet` whose provenance binds the N7
  certificate, S10 support, WMR, transport, and DataTrust;
- persist the S10 support and the unchanged `ValueGateReceipt` as canonical
  bytes in the owner store;
- read both artifacts back and validate them before emission; and
- make `value_ref` the owner-derived content identity, not an arbitrary label.

A valid observation is not a status flag. The guard at
`generation_cycle.py:529` requires both a `ValueGateReceipt` and the
`MethodSelectionReceipt`; `generation_cycle.py:532` rejects any still-open
acquisition requirement; and the selected FQN must equal the selection
receipt's FQN. Blocked or pending observations cannot carry a value receipt.

For this data-only route, `evaluation_mode="simulate_only"`, K-world must not
shrink, transport must be `direct` or `transported_limited`, S10 calibration
must pass honestly as `transported_limited`, and DataTrust must satisfy the
existing floor. `_eval_safety_obligation` must see this non-attempted mode and
return `not_applicable_data_only`.

## 5. Production N9 Writer Surface

The consumers are real and already centralized in
`_bind_production_promotion_evidence`:

| Existing key | Required owner input | Persisted consumer |
| --- | --- | --- |
| `effective_independence_writer_input` (`promotion_sequence.py:1435`) | `evidence_lines`, `portfolio_designs`, non-empty `graph_id`, optional producer start, feature flags, graded config, rare-domain context | `N9PromotionEvidenceBridgeRepository.persist_effective_independence` |
| `measurement_root_writer_input` (`:1455`) | one real `ArtifactEnvelope` from `MeasurementRootProducer.produce_from_catalog` | `persist_measurement_root` |
| `effect_obligation_writer_input` (`:1467`) | `InterventionAtomBinding`, `InterventionSubstrateBundle`, `WorldModelRecord`, operator kind, parameter value, proposal and proposal ID, optional declared estimand and mechanism ref | `persist_effect_obligation` |

The strict DTOs are at `promotion_sequence.py:457-486`. Each writer persists a
candidate/problem-bound CAS artifact; the consumer resolves and recomputes the
bridge rather than trusting the context payload. Malformed inputs are
currently swallowed and become missing-evidence refusals, which is safe but
diagnostically ambiguous. PR1a must prove such input cannot promote; it need
not change the diagnostic contract.

`CanonicalN9PromotionPort` accepts a provider at
`promotion_sequence.py:2439-2468`; the batch calls it at `:2717`, creates the
canonical input at `:2734`, and binds the writers at `:2769`. The production
`GenerationCycleController` creates the port without a provider at
`generation_cycle.py:2448-2459`. The source census's zero production
`context_provider=` calls is therefore a real missing bridge.

The provider must also supply owner-derived WMR/CG2 inputs and S6/S7/S8
postures. It may not supply `admissibility`, `effective_independence`, or an
`open_world_gate`; those are resolved by their existing owners.

### The four conditional `scope_insufficient` branches

These four branches define the remaining “complete evidence” relevant to the
carried refusal table. The first three have real owners and pass only on real
evidence; the fourth is mode-dependent by design.

| Branch and source | What the current evaluator checks | What a data-only candidate must carry |
| --- | --- | --- |
| Effective independence, `promotion_sequence.py:4562-4595` | `_effective_independence_obligation` satisfies only when the CAS resolver returns `status="established"`; `refused` is a full failure and absence is `scope_insufficient`. Owner: `polisyos.evidence.portfolio.effective_independence_graph.build_effective_independence_graph`. | A persisted graph bridge whose candidate ID/hash and design-problem binding replay, whose source semantic hash and verifier provenance match, and whose independently recomputed disposition is established. It is a decisive predicate, not a class-gate exemption. |
| G4 PARAM, `promotion_sequence.py:4903-4929` | A falsy `g4_governed_promotion_ref` is `scope_insufficient`; a nonempty ref that does not resolve in `architecture/policy_design_case/layer3_g4_promotion_records.json` is a full failure; a found record satisfies. | The production provider must choose the record whose existing `case_id`/`candidate_ref` match the live case and must supply its exact `promotion_record_id`. The evaluator's lookup is by ID, so the provider mutation test must prove a substituted record is withheld/refused rather than relying on the current default string. |
| Measurement root, `promotion_sequence.py:5090-5119` | `_measurement_obligation` satisfies only on an `established` CAS resolution; an owner refusal is a full failure and no resolved bridge is `scope_insufficient`. Owner: `polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer.produce_from_catalog`. | A real `ArtifactEnvelope` produced from the catalog, persisted through the existing writer, then replayed with exact candidate/problem binding, source semantic hash, and verifier provenance. |
| EvalSafety, `promotion_sequence.py:5194-5217` | Modes `sandbox_pilot`, `field_pilot`, and `deployment` return `scope_insufficient` with owner `absent/unallocated`; every other current mode returns `NOT_APPLICABLE_DATA_ONLY`. | The PR1a receipt must carry `evaluation_mode="simulate_only"` from the N5-bound execution context. It must **not** carry a certificate intended to satisfy EvalSafety. The required result is `not_applicable_data_only`. |

The ordinary full-failure checks still matter to final acceptance: the effect
writer must establish its RACE evidence, the N8 calibration receipt must pass,
and `ValueOuterSet.data_trust` must meet its resolved promotion floor. Task K's
three full refusals were those real evaluators seeing incomplete fixture
evidence, not unimplemented obligations.

## 6. S8 / GY-PA1 Split

The exact binding rows are `GY-PA1` and `GY-PR1a` in the active GY task table:
the former is a completed `not_executable` result whose live engineering was
carried to the latter. Carrying every named S8 object is too broad for an
unranked data-only promotion.

PR1a genuinely needs an authority-grade **unranked** posture:

- build a real nondominated frontier from the N8 `ValueOuterSet` and candidate
  set;
- persist the existing `ParetoArchive` and audit refs;
- resolve it from CAS and recompute candidate/value/frontier identity; and
- only then construct the existing `Layer2S8ValuePostureInput` showing that no
  scalar weighting, ranking, or choice was attempted.

`ParetoArchive` and `build_pareto_archive` already support that state and
already reject ranking without a schedule. The missing work is the
producer/persistence/resolver and the N9 bridge, not a new S8 public contract.

The following are **not required** for this acceptance predicate:

- authority-grade `AuthorizedValueSchedule` production/persistence/resolution;
- `NormativeAuthorizationRecord`;
- `NormativeDecisionRequest`; and
- a ranked-consumer bridge.

Those four objects belong to a later ranked-value PA1 successor. They do not
belong to PR1b either. PR1b is solely the appointment-dependent EvalSafety
promotion-authority path for `sandbox_pilot`, `field_pilot`, and `deployment`.
If PR1a attempts any ranking or scalar recommendation, the absence of those
objects must block and the task stops rather than silently expanding scope.

## 7. Acceptance Predicate

A receipt satisfies GY-PR1a only when **all** of the following hold in one
production run:

The run is also the first result-bearing execution under the immutable Section
0 selection record. Its complete Option-B chronology is append-only and
nonnumeric. This custody condition governs which run may satisfy the predicate;
it does not add a caller field to the receipt or authorize a DS12 public claim.

1. A canonical `GenerationCycleController` run starts from a content-bound
   `DesignProblem`, produces its candidate and N5/WMR observations, and reaches
   N7/N8/N9. The test does not directly construct a `ValueGateReceipt`, N7
   certificate/admission, CG2 certificate, N9 evidence receipt, or promotion
   receipt.
2. The unchanged v1 gap remains unsatisfied. A separately persisted v2 N7
   admission resolves the certified-SKG disjunct for the exact candidate,
   problem, WMR, and epoch.
3. Academic SKG identity and joins are owner-recomputed; source authenticity is
   established; the interval is native; CG1 remains shadow-only; CG2 resolves
   against a genuine production-owned, >=20-sample matching stratum and returns
   production-promotable. No caller/test seed participates.
4. One isolated Foundry registry contains governed builtins plus the explicit
   adapter and no ambient methods. Selection, selection-context replay,
   registry lookup, and `MethodDispatcher` all use that same registry. The
   global frozen 55-method catalog is byte/count unchanged.
5. The exact resolved N7 certificate is the adapter's actual report output.
   N8 independently solves transport, persists/replays S10
   `transported_limited` support with real S5/S6/S8 inputs and limitations,
   produces a non-empty `ValueOuterSet`, and passes the existing DataTrust and
   calibration predicates without invented panel counts.
6. N8 persists and reads back the existing `ValueGateReceipt`; the observation
   is `value_ready`, carries both owner receipts, carries no acquisition gap,
   has matching selected-method FQNs, consistent WMR hashes, and unchanged
   K-world for `simulate_only`.
7. S8 is a CAS-resolved, owner-recomputed unranked Pareto posture. No schedule,
   scalar rank, or normative authorization is asserted.
8. The production N9 provider supplies all three writer inputs from their real
   owners. CAS replay establishes effective independence, measurement root,
   and effect evidence for the exact candidate/problem. A real candidate-bound
   G4 governed-promotion record resolves. Open-world and epoch projections are
   established by `PromotionRuntime`, never by context.
9. Every applicable N9 obligation is satisfied, the confidence/risk ledger is
   within budget, and `EVAL_SAFETY` is exactly
   `NOT_APPLICABLE_DATA_ONLY`—not satisfied, omitted, contract-exempted, or
   `scope_insufficient`.
10. The persisted canonical N9 receipt reads back with
    `promotion_lane="production"`, `promoted=True`,
    `consumer_promotable=True`, an authority derivation trace, no refusal
    reasons, and CG2 reason `owned_production_anchor_resolved`.
11. Mutation controls for v1-only, forged/stale/cross-bound N7 evidence,
    absent/contract-test CG2, ambient Foundry registry drift, missing S5/S6/S8,
    invalid `value_ready`, any missing/malformed writer, substituted G4, ranked
    S8 without authorization, and pilot mode all remain non-promotable.

This distinguishes a governed promotion from a fixture: the truth-bearing
objects are produced, persisted, replayed, recomputed, consumed, and exposed in
one production chain; the test merely supplies the initial problem and storage
boundary and observes the resulting artifacts.

## 8. Ordered Phase-2 Build Sequence

### Task 0 — Hard preconditions; no source edits

**Files:** create, then append only,
`docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md`.
The census implementation lives only in this plan's ignored SDD workspace:
`/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/task-0-feasibility.py`.

- [ ] Verify that the first commit containing Section 0 is attached to
      `codex/gy-pr1a-data-only-promotion`; append its hash/time and the already
      confirmed bound `sys.prefix` to the journal before any row read.
- [ ] Append the complete initial `INT-K06` custody record: population,
      selection/firstness/order/stopping/no-substitution rules, disqualifiers,
      versions, claim boundary, and every currently `not_established` external
      custody field.
- [ ] Before its first owner-data query, append the selector source text,
      SHA-256, interpreter version, exact command, declared output schema, and
      the committed selector-query SHA-256 to the journal. The selector is
      single-invocation for selection; a changed script/hash, rerun after any
      selected-row result, or interactive row filtering is a deviation and
      stops this registered attempt.
- [ ] Execute the fixed hash selector over the complete structural denominator,
      append its database hash/version, denominator, selection digest, exact
      row identity, derived stratum, and candidate/estimand binding, and freeze
      that receipt before reading calibration or promotion outcomes. Do not
      print or choose rows interactively.
- [ ] As the **first result-bearing Phase-2 act**, run the read-only complete
      calibration census for that exact selected stratum. Capture the command,
      table/file denominators, exclusion counts and reasons, grouped distinct-
      observation counts, selected-stratum count, and every other stratum count
      as nonselecting context.
- [ ] If the structural denominator is empty, the selected case is disqualified,
      or its independently adjudicated calibration count is below 20, append
      the negative terminal `producer_missing: pre-registered CG2 stratum lacks
      >=20 distinct independently adjudicated production observations`, record
      `prohibited_substitution_found=false`, commit the journal, and stop. Do
      not create a calibration population or any source/test file.
- [ ] If the selected count is >=20, record the global N8 method count/hash and
      require the frozen value 55 before Task 1.

The feasibility census is measurement, not a fixture or producer. It may read
the owner data and CAS but may not create, label, duplicate, repair, or persist
an observation. Zero is a valid governed result.

Commit group: prospective custody record + feasibility result. If zero, this
is the terminal implementation commit for the task.

### Task 1 — Production CG2 calibration and repaired controls

**Files:**

- Create
  `src/polisyos/runtime/quality/production_grounding_calibration.py`.
- Modify `src/polisyos/runtime/quality/grounding_bind.py`.
- Modify
  `tools/quality/validation/check_grounding_bind_contract.py` and its owned
  `architecture/policy_design_case/grounding_bind_contract.json` artifact.
- Create
  `tests/unit/runtime/quality/test_production_grounding_calibration.py`.
- Modify `tests/unit/runtime/quality/test_grounding_bind.py`.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_grounding_bind.py::test_contract_testing_bind_resolves_non_promotable -q -x --lf
```

- [ ] Add
      `test_production_calibration_source_rejects_rows_without_independent_adjudication`.
      **Expected red:** production source/resolver type is absent.
- [ ] Add
      `test_production_calibration_corpus_persists_and_resolves_exact_stratum`.
      **Expected red:** `_owned_calibration_store` still returns the typed empty
      production ledger.
- [ ] Add missing/tampered source root, duplicate observation, under-20,
      wrong-epoch/stratum, unapproved provenance, self-labelled CG2 outcome,
      seed, and CG6 negatives. **Expected red:** no behavioral corpus verifier
      exists.
- [ ] Repair the five existing CG2 controls so their canonical exact-relation
      setup first proves the intended stratum, then reaches its calibration
      boundary. Preserve a separate `tax_credit_rate` alias behavior test; do
      not change alias semantics.
- [ ] Implement the second ratified artifact family, CAS persistence/replay,
      production source loading, exact owner resolution, and additive
      provenance. Leave the contract-testing source and scope unchanged.
- [ ] Make the generic checker recompute the corpus and add corrupt-field
      mutations; regenerate only its owned CG2 artifact.
- [ ] Run exact red/green nodes, then both affected whole test files and the
      checker/corruption probe once for this group.

Commit group: production CG2 source + artifact/resolver + five repaired
calibration controls + behavioral verifier.

### Task 2 — Academic SKG certificate producer

**Files:**

- Create
  `src/polisyos/data_forge/domains/academic/knowledge/skg_identity_bridge.py`.
- Modify
  `src/polisyos/data_forge/domains/academic/knowledge/__init__.py` only for the
  canonical typed export.
- Create
  `tests/unit/data_forge/domains/academic/knowledge/test_skg_identity_bridge.py`.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/data_forge/domains/academic/knowledge/test_skg_query.py::test_skg_query_resolves_existing_version_ids -q -x --lf
```

- [ ] Add the positive producer test
      `test_production_skg_rows_emit_content_bound_identity_certificate`.
      **Expected red:** module/type does not exist.
- [ ] Add
      `test_identity_bridge_refuses_synthesized_interval_or_cross_epoch_join`.
      **Expected red:** no resolver performs those discriminations.
- [ ] Implement only the ratified strict certificate and deterministic producer.
- [ ] Persist/read exact CAS bytes and rerun both nodes green.
- [ ] Run the whole new test file once.

Commit group: certificate contract + producer + tests.

### Task 3 — Additive N7 admission, persistence, and replay

**Files:**

- Create
  `src/polisyos/runtime/quality/value_input_world_knowledge_bridge.py`.
- Modify
  `src/polisyos/runtime/quality/generation_cycle.py` only to accept/resolve the
  owner admission ref and branch before rollout-panel loading.
- Modify
  `tests/unit/runtime/quality/test_acquisition_planner.py`.
- Modify `tests/unit/runtime/quality/test_generation_cycle.py`.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_generation_cycle.py::test_typed_value_world_knowledge_gap_routes_without_renaming_blocker -q -x --lf
```

- [ ] Add
      `test_satisfied_skg_admission_is_additive_and_v1_gap_stays_unsatisfied`.
      **Expected red:** no positive v2 type exists.
- [ ] Add
      `test_resolved_skg_admission_reenters_n8_before_owner_rollout_gap`.
      **Expected red:** current path returns
      `treatment_assignment_not_owner_derived`.
- [ ] Add hash, epoch, cross-candidate, cross-problem, WMR, source-root, CG1-only,
      and CG2-nonproduction mutations. **Expected red:** no CAS resolver exists.
- [ ] Implement the ratified v2 admission/repository/resolver; leave all v1
      source and serialized behavior unchanged.
- [ ] Prove v1-only input still emits the exact old blocker and gap bytes.
- [ ] Run both affected whole files once.

Commit group: N7 positive admission family + CAS resolver + re-entry tests.

### Task 4 — Isolated Foundry adapter and exact selection/dispatch

**Files:**

- Create
  `src/polisyos/foundry/extensions/academic_skg_native_estimate.py`.
- Modify
  `src/polisyos/foundry/methods/selection/advisor.py` to accept a controlled
  catalog snapshot for selection and context hashing.
- Modify `src/polisyos/runtime/quality/generation_cycle.py` to thread one scoped
  registry through selection, verification, lookup, and dispatch.
- Create
  `tests/unit/foundry/extensions/test_academic_skg_native_estimate.py`.
- Modify `tests/unit/foundry/methods/test_selection_advisor.py`.
- Modify `tests/unit/runtime/quality/test_value_gate.py`.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/foundry/methods/test_value_evidence.py::test_native_declaration_without_slot_witness_is_not_projection_authority -q -x --lf
```

- [ ] Add
      `test_academic_skg_adapter_returns_exact_resolved_certificate_contract`.
      **Expected red:** adapter absent.
- [ ] Add
      `test_scoped_registry_snapshot_excludes_ambient_discovery_and_global_catalog`.
      **Expected red:** selector re-bootstraps ambient methods.
- [ ] Add
      `test_selection_hash_lookup_and_dispatch_share_one_scoped_registry`.
      **Expected red:** current N8 uses global defaults.
- [ ] Add manifest controls proving a typed contract target affects selection,
      bare certificate ID/hash keys do not establish admission, and a substituted
      certificate is refused by N8.
- [ ] Register the adapter only in a scoped registry via the existing extension
      API. Do not modify global registry boot.
- [ ] Dispatch via `MethodDispatcher`; reject direct adapter calls in the N8
      path.
- [ ] Re-run the frozen 55-method count/hash and require no change.
- [ ] Run each affected whole test file once.

Commit group: scoped adapter + controlled selection + real dispatch.

### Task 5 — S10 transported owner bridge and persisted N8 receipt

**Files:**

- Create `src/polisyos/runtime/quality/value_gate_store.py`.
- Modify `src/polisyos/runtime/quality/generation_cycle.py`.
- Modify `tests/unit/runtime/quality/test_value_gate.py`.
- Modify
  `tests/unit/runtime/quality/test_design_axes_outcome_prediction.py` only for
  the existing transported contract's owner-path witness.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_design_axes_outcome_prediction.py::test_transport_without_limitation_is_rejected -q -x --lf
```

- [ ] Add
      `test_owner_resolved_skg_bridge_persists_transport_support_and_value_receipt`.
      **Expected red:** current N8 has no transported producer and no receipt
      persistence.
- [ ] Add
      `test_transport_limited_support_without_target_panel_calibration_is_valid`.
      **Expected red:** current helper derives the wrong S5 origin/tier.
- [ ] Add negative nodes for missing real S5/S6/S8, interval, limitation,
      source/method lineage, equilibrium input, false-clear count, policy-context
      mismatch, and observable tier without calibration.
- [ ] Implement the owner S10 transported branch with existing contracts and
      persist/replay support before `_value_calibration_receipt`.
- [ ] Derive/persist/read the existing `ValueGateReceipt`; emit `value_ready`
      only after both owner receipts resolve.
- [ ] Run transport nodes with `uv run --extra solvers`; treat an extra-naming
      skip as not executed.
- [ ] Use the exact solver-enabled form for each transport node:

```bash
/opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test --extra solvers pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_value_gate.py::test_owner_resolved_skg_bridge_persists_transport_support_and_value_receipt -q -x --lf
```

- [ ] Run both whole affected files once.

Commit group: transported S10 producer + N8 persistence + valid observation.

### Task 6 — Owner-derived unranked S8 and production N9 context

**Files:**

- Modify
  `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` to add
  persistence and exact replay around the existing unranked archive.
- Create
  `src/polisyos/runtime/quality/data_only_promotion_context.py`.
- Modify `src/polisyos/runtime/quality/generation_cycle.py` to instantiate the
  production provider.
- Modify
  `tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py`.
- Modify `tests/unit/runtime/quality/test_promotion_sequence.py`.
- Modify `tests/unit/runtime/quality/test_generation_cycle.py`.

**Positive controls first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_design_axes_value_choice_provenance.py::test_pareto_archive_cannot_rank_without_authorized_value_schedule /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py::test_scope_insufficient_obligation_does_not_vacuously_pass -q -x --lf
```

- [ ] Add
      `test_unranked_posture_requires_owner_derived_frontier_proof`.
      **Expected red:** current posture trusts a caller DTO and has no resolver.
- [ ] Add
      `test_production_generation_cycle_context_provider_persists_independence_measurement_and_effect_bridges`.
      **Expected red:** production constructs no context provider.
- [ ] Add malformed/missing writer mutations, substituted G4, and cross-
      candidate archive mutations. **Expected red:** no production provider or
      S8 resolver exists.
- [ ] Persist/recompute the unranked Pareto archive and construct the existing S8
      posture only after replay.
- [ ] Build all three writer inputs from the actual cycle artifacts. Do not add
      caller Boolean gates.
- [ ] Resolve the exact candidate-bound G4 record and thread the provider into
      the controller's canonical N9 port.
- [ ] Preserve the existing
      `test_eval_safety_names_the_missing_promotion_authority_without_reusing_o0`
      and add `test_data_only_promotion_marks_eval_safety_not_applicable_without_appointment`
      plus a pilot mutation that remains
      `eval_safety:scope_insufficient` for PR1b.
- [ ] Run each affected whole file once.

Commit group: unranked S8 producer/replay + production N9 context bridge.

### Task 7 — New production capstone, journal completion, and focused closeout

**Files:**

- Create
  `tests/integration/runtime_quality/test_first_governed_promotion.py`.
- Append only to
  `docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md`.

**Positive control first:**

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python -m pytest /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_generation_cycle.py::test_typed_value_world_knowledge_gap_routes_without_renaming_blocker /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tests/unit/runtime/quality/test_promotion_sequence.py::test_eval_safety_names_the_missing_promotion_authority_without_reusing_o0 -q -x --lf
```

- [ ] Add
      `test_production_data_only_cycle_emits_real_consumer_promotable_receipt`.
      **Expected red before Tasks 2-6:** the cycle terminates at the owner N7 gap
      and no receipt exists.
- [ ] Start at the canonical problem/cycle boundary and assert every acceptance
      conjunct in Section 7 by reading persisted artifacts back. Never call a
      receipt/certificate constructor from the test.
- [ ] Add one mutation table covering every negative in Acceptance item 11.
- [ ] Run the exact capstone node with `-x --lf`, then the integration file once.
- [ ] Append the journal's red-first commands/output, actual source-file delta,
      artifact refs/hashes, final acceptance readback, and exact append-only prose
      for `first-promotion-candidate-with-complete-evidence`,
      `gy-promotion-obligations-scope-insufficient`, and the GY plan's
      `GY-PR1a` row. Do not edit `docs/plans/active/`.

Commit group: capstone + append-only journal. If a source/test fix is required
after this group starts, commit that coherent delta before the journal's final
evidence append; do not rewrite prior journal prose.

- [ ] Freeze source before final review.
- [ ] Run ruff only over changed Python files.
- [ ] Run architecture guardrails and the directly affected checkers, including
      the CG2 checker/corruption probe, CG1 census, frozen N8 catalog, and docs
      checks.
- [ ] Run each affected whole test file once per group; no wider suite.
- [ ] Run the bound debt checker once, on a quiescent tree, with both streams
      captured at
      `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/bound-check.txt`;
      append `EXIT=$?` to that same file, then read the file instead of trusting
      terminal transport.
- [ ] Verify the tracked `src/**/*.py` delta. The ratified design adds exactly
      six source files:
      `production_grounding_calibration.py`,
      `skg_identity_bridge.py`,
      `value_input_world_knowledge_bridge.py`,
      `academic_skg_native_estimate.py`, `value_gate_store.py`, and
      `data_only_promotion_context.py`. Against this Phase-1 base the forecast is
      **2,617 -> 2,623 (+6)**. Modifications do not change the count.
- [ ] Execute the bound checker exactly once using:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tools/quality/validation/check_debt_ledger.py --check > /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/bound-check.txt 2>&1; /bin/echo "EXIT=$?" >> /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/bound-check.txt
```
- [ ] Before each commit, require:

```bash
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine status -sb
```

- [ ] After the final commit, read the commit back from the attached branch with
      `git show`/`git diff-tree`; staged or working-tree presence is not delivery.

## 9. What This Task Will Not Build

- It will not build or appoint EvalSafety promotion authority for
  `sandbox_pilot`, `field_pilot`, or `deployment`. That is PR1b. Those modes
  must continue to return `eval_safety:scope_insufficient` and
  `consumer_promotable=False`.
- It will not reuse the attempted-evaluation certificate for promotion; that
  certificate expressly denies the authority.
- It will not build `AuthorizedValueSchedule` production,
  `NormativeAuthorizationRecord`, `NormativeDecisionRequest`, or a ranked
  consumer. Those belong to the later ranked-value PA1 successor, not PR1b.
- It will not rank an unranked frontier, synthesize social weights, infer
  preferences, or turn absence of a schedule into equal weights.
- It will not rewrite or widen the v1 unsatisfied N7 gap.
- It will not alter `ValueGateReceipt`, S10, N9 promotion/obligation epochs,
  OpenAPI, generated clients, the frozen global N8 catalog, or any schema
  outside the separately ratified N7 and CG2 additive families.
- It will not treat CG1, CG6, caller calibration, a contract-test seed, a
  fixture certificate, or a caller truth value as production evidence.
- It will not repair
  `test_real_measurement_root_resolves_and_binds_into_n9` in place and call that
  a promotion. That test remains a bridge witness with an incomplete fixture.
- It will not edit `docs/plans/active/`; the architect transcribes journal prose.
- It will not issue the DS12 public `INT-K06` claim, claim independent sealing
  or named-human adjudication that was not observed, or attach any probability
  or readiness meaning to this first run.

## 10. Known Risks and Firing Observations

| Risk | Observation that it fired | Required response |
| --- | --- | --- |
| Pre-registered stratum lacks a genuine production calibration population | Complete Section-0 census finds fewer than 20 distinct independently adjudicated observations in the selected exact stratum, regardless of other strata | Commit the negative INT-R9 terminal and stop before Task 1; allocation cannot manufacture or substitute evidence. |
| INT-R9 selection drift | A different stratum/row/case/estimand is used after first inspection, or a deviation is discovered without an earlier append | Stop; retain the first terminal and require a new prospective committed registration before any replacement inspection. |
| CG2 calibration self-labels | A count is derived from CG1/CG2 decisions, LLM output, code literals, CG6, seed, duplicate rows, or materialized rows without CAS adjudication lineage | Refuse the observation; it is not production calibration evidence. |
| CG2 controls are red for the wrong reason | Negative node terminates at `relation_not_bind_eligible` or fails to reach calibration resolution | Mark control `not_established`; repair it in Task 1 before PR1a red/green claims. |
| No real SKG row satisfies the certificate | Complete producer run yields zero native-interval, exact-join, transportable, production-CG2 rows | Stop; do not manufacture an example. |
| Source authenticity remains unknown | Owner snapshot/root cannot be resolved or provenance is `not_established` | Refuse N7 admission and stop acceptance. |
| v1 weakening | Old serialized gap parses as satisfied or no longer yields the exact blocker | Revert the design delta; do not commit. |
| Ambient Foundry discovery leaks into scope | Scoped registry denominator changes after `ensure_all_methods_registered`, entry-point install, or dev scan | Stop; selection is not reproducible. |
| Frozen catalog moves | Global value-method count !=55 or governed artifact/hash changes | Stop under the frozen-contract rule. |
| Selection context is used as artifact admission | Bare cert ID/hash in manifest makes selection/admission pass | Refuse; artifact identity belongs to CAS resolution. |
| Adapter is declared but not dispatched | Test can bypass `MethodDispatcher` or runtime report is not the exact certificate type | Keep red; no N8 receipt. |
| Source-study counts are laundered as target calibration | Passing S10 support contains invented treated/control/pre/post values or derives `observable_calibrated` | Stop and use only the existing transported-limited semantics. |
| Required S5/S6/S8 context is absent | Transported S10 construction lacks real prerequisite refs | Stop; N7 evidence cannot substitute for another owner. |
| Receipt is an in-memory fixture | `value_ready` appears without CAS readback, or a test calls `ValueGateReceipt(...)` | Stop under fixture-minting rule. |
| S8 remains caller asserted | Archive/posture mutation does not change replay outcome | Keep red; require persisted/recomputed frontier. |
| A writer input is missing/malformed | Corresponding resolution is `not_established` or refusal reason includes data/measurement/effect | Do not promote; improve diagnostics only if no contract change is required. |
| G4 default masks substitution | A nonempty but wrong ref passes, or provider relies on the current default string | Keep red; require exact candidate-bound owner resolution. |
| EvalSafety enters data-only | Data-only obligation is satisfied, omitted, or scope-insufficient instead of `not_applicable_data_only` | Stop under task rule 4. |
| Ranked behavior enters PR1a | Scalar recommendation/rank appears without authorization chain | Stop and route to the ranked PA1 successor. |
| Source count differs from +6 | New mechanism file is added or one of the six is omitted without an explicit reason | Reconcile against mechanism boundaries before commit; revise plan if scope changed. |
| Bound-check transport truncates | Terminal output is absent from the captured file or the appended `EXIT=` line is missing | Treat closeout as `not_established`; do not rerun the one permitted invocation. |

## 11. Pattern Pass

Relevant register patterns are `P01`/`P02` (contract/producer/bridge reality),
`P04`/`P05` (status and authority boundaries), `P07`/`P08` (replay, epoch, and
time roles), `P10` (semantic adequacy), `P13` (governance gravity), `P14`
(independence inflation), `P15` (candidate evidence laundering), `P27`/`P28`
(canonical owner and no parallel legacy positive path), `P29` (behavioral
proof), `P31`/`P32` (class repair and resolve/content-bind/provenance), `P33`
(no teaching to the test), `P35`/`P36` (complete denominators and cited
authority), `P37`/`P38` (predicate provenance and proxy divergence), and `P41`
(red provenance).

The existing anti-pattern is a chain of real downstream contracts and guards
whose positive upstream representation and production orchestration do not
exist. A fixture can satisfy the shapes and still skip the property. The
smallest correct pattern is one behaviorally derived production CG2 corpus,
one additive versioned N7 admission, one owner CAS intake, one isolated real
method dispatch, reuse of existing transported S10 and value/N9 contracts, and
one end-to-end production readback.

The target capability state is:

```text
pre-existing independently adjudicated calibration observations
+ persisted production CG2 corpus/resolution
typed N7 certificate/admission
+ owner producer
+ persisted artifact
+ CAS resolver/replay
+ N8 method/transport/S10/value producer
+ persisted ValueGateReceipt/value_ready
+ unranked S8 bridge
+ production N9 three-writer context
+ canonical consumer_promotable receipt
+ adversarial semantic test
```

Any missing term keeps the capability labelled precisely (`producer_missing`,
`artifact_missing`, `bridge_missing`, `consumer_missing`,
`verification_missing`, `implemented_but_not_orchestrated`, or
`semantic_test_missing`) rather than being summarized as “promotion works.”

## 12. Phase-1 Historical Verification and Commit Boundary

Before the Phase-1 plan commit:

- [ ] Confirm only this plan is changed.
- [ ] Stage only this plan, then run `git diff --cached --check` so the new
      untracked file is included in the whitespace check.
- [ ] Recount tracked `src/**/*.py` and require 2,617; Phase 1 adds no source.
- [ ] Run `check_docs_lifecycle.py` and require the carried baseline: exit 1,
      exactly six findings, with no seventh caused by this plan.
- [ ] Run `check_debt_ledger.py --check` exactly once on the quiescent tree and
      require exit 0 with zero blocking findings.
- [ ] Re-open the failure/repair register and self-review this plan against the
      pattern pass.
- [ ] Verify branch attachment, commit only this plan, then read the plan back
      from the branch commit.

Commands:

```bash
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine ls-files 'src/**/*.py' | /usr/bin/wc -l
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tools/quality/validation/check_docs_lifecycle.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /opt/homebrew/bin/uv run --directory /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine --frozen --extra test python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/tools/quality/validation/check_debt_ledger.py --check
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine add /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/docs/superpowers/plans/2026-09-02-gy-pr1a-data-only-promotion.md
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine diff --cached --check
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine diff --cached --name-only
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine status -sb
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine commit -m 'docs(gy): plan data-only first governed promotion'
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine show HEAD:docs/superpowers/plans/2026-09-02-gy-pr1a-data-only-promotion.md
```

That boundary was delivered at `3de7a3f26`; its Section-2 N7 family and Section
7 acceptance predicate are now ratified.

## 13. Ratified Revision and Pre-inspection Commit Boundary

Before any Phase-2 source-data row is inspected:

- [ ] Confirm the working tree changed only this plan; ignored SDD bookkeeping
      is permitted but carries no product authority.
- [ ] Confirm tracked `src/**/*.py` remains 2,617.
- [ ] Confirm this revision names the CG2 production source, the full
      feasibility denominator, deterministic case/stratum/estimand binding,
      disqualifiers, no-substitution rule, Option-B claim boundary, and
      captured bound-check path.
- [ ] Run the docs lifecycle checker and require exactly the six carried
      findings with no finding caused by this plan.
- [ ] Do **not** rerun the debt-ledger checker here; its one closeout execution
      belongs to Task 7 and will be captured to a file.
- [ ] Stage only this plan, run `git diff --cached --check`, verify attachment
      to `codex/gy-pr1a-data-only-promotion`, and commit the revision alone.
- [ ] Read the committed plan back from the branch, then create the append-only
      journal registration event before running Task 0's census.

Commit message:

```bash
/opt/homebrew/bin/git -C /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine commit -m 'docs(gy): preregister first-promotion execution'
```

After this revision commit, execute Tasks 0 through 7 continuously. Stop only
on the explicit feasibility/contract/predicate/substitution rules in this plan
and the task authorization.
