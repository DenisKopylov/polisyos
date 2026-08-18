---
title: PAO-R36 - Orientation Error Ledger
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_pass_i_orientation_audit
  - pao_r36_count_reconciliation
  - pao_r36_repository_claim_dispositions
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 orientation error ledger

## 1. Scope and method

This ledger audits every orientation entry in
`policy-engine/docs/research/policy-operations/pao-r36/orientation-ledger.md` at the audited head.
Repository-source claims are pinned to `main@1a7a2d05ebba22fae80e9934329e4b880806588e`.
The audited research branch is read only.

The environment could not resolve ordinary GitHub egress and supplied no recursive read-tree action.
The connected GitHub interface did supply exact-ref code search and exact file reads. The audit used
that interface as follows:

1. request up to 100 path-bounded candidates for each exact token under `policy-engine/src`;
2. when candidates existed, read every returned candidate at the pin and count the exact,
   case-sensitive substring in every source line;
3. report separately: token-containing files, matching lines, and literal occurrences; and
4. where the search returned zero candidates, report `not_established` rather than converting an
   index miss into a P35-complete universal absence.

For `supersede`, the case-insensitive candidate search returned 49 files. All 49 were read. Two were
uppercase-only false positives for the lowercase token:

- `policy-engine/src/polisyos/foundry/methods/lifecycle/deprecation.py` contains
  `SupersededBy...`; and
- `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/validation.py`
  contains `DATASET_SUPERSEDED`.

The remaining 47 files form the exact lowercase `supersede` set in the returned denominator. The
same 49-file read supplied the exact lowercase `superseded` subset.

## 2. Count vocabulary

- **Source lines:** physical newline-delimited lines in one exact file.
- **Matching lines:** source lines containing at least one exact, case-sensitive token.
- **Literal occurrences:** non-overlapping exact substring occurrences.
- **Token-containing files:** distinct files containing at least one literal occurrence.
- **Candidate files:** files returned by the connector's path-bounded search before exact-case
  reconciliation.

One source line can contain more than one occurrence. These units are never substituted for one
another.

## 3. Reconciled token census

Search denominator for the non-zero rows: every connector candidate returned for the exact-ref query
under `policy-engine/src`, followed by an exact read of every candidate at the pin.

| Exact lowercase token | Commission file count | Audited research disposition | Re-derived files | Matching lines | Literal occurrences | Audit verdict |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `supersede` | 48 | Refused a census; reported 49 candidates | **47** | **203** | **246** | **Commission count wrong by one.** The research's refusal avoided a false claim, but it left a count that could be settled from its own finite candidate set unresolved. `PAO-R36-I-001`. |
| `superseded` | 34 | Refused a census; reported 37 candidates | **34** | **152** | **180** | **Commission count correct.** Candidate count was inflated by case-insensitive and broader-stem hits. |
| `retraction` | 6 | 7 all-file candidates; six Python plus one README | **7 all files** / **6 Python** | **40 all files** / **39 Python** | **44 all files** / **43 Python** | The research correctly exposed the unstated file-type denominator. It should also have supplied line and occurrence counts. `PAO-R36-I-002`. |
| `cache_invalidat` | 3 | Three candidate files | **3** | **5** | **5** | Agrees and now has all three units. |
| `subscriber` | 3 | Three candidate files | **3** | **18** | **21** | Agrees and now has all three units. |
| `correction_notice` | 0 | Zero indexed candidates, explicitly not a complete walk | `not_established` | `not_established` | `not_established` | The research was right not to promote an index miss. A recursive pinned tree/archive walk would settle the zero. |
| `notify_subscribers` | 0 | Zero indexed candidates, explicitly not a complete walk | `not_established` | `not_established` | `not_established` | Same disposition. |
| `correction_feed` | 0 | Zero indexed candidates, explicitly not a complete walk | `not_established` | `not_established` | `not_established` | Same disposition. |

### 3.1 `retraction` denominator

The seven all-file members are:

1. `policy-engine/src/polisyos/runtime/quality/policy_design_case.py`;
2. `policy-engine/src/polisyos/runtime/quality/policy_benchmarking.py`;
3. `policy-engine/src/polisyos/runtime/quality/calibration_ledger.py`;
4. `policy-engine/src/polisyos/runtime/quality/tenant_cas_approval_governance.py`;
5. `policy-engine/src/polisyos/scientist/nodes/builtins/decide/decision_packet/enrichment.py`;
6. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/skg_versioning.py`; and
7. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/README.md`.

The first six are Python files. The commission's “6” is not a substantive source-tree contradiction;
it is an unstated-denominator defect. The research was right to expose it.

### 3.2 `cache_invalidat` denominator

The three members are:

1. `policy-engine/src/polisyos/foundry/methods/compiler/hot_reload.py` — 3 matching lines / 3
   occurrences;
2. `policy-engine/src/polisyos/fabric/_adapters/observability.py` — 1 / 1; and
3. `policy-engine/src/polisyos/fabric/connectors/cache/_store_core.py` — 1 / 1.

Total: 3 files / 5 matching lines / 5 occurrences. None is a correction-scoped public-cache
inventory.

### 3.3 `subscriber` denominator

The three members are:

1. `policy-engine/src/polisyos/scholar/search/security.py` — 2 matching lines / 2 occurrences;
2. `policy-engine/src/polisyos/runtime/http/services/review_collaboration.py` — 15 / 18; and
3. `policy-engine/src/polisyos/data_forge/domains/academic/knowledge/runtime_canonical_registry.py`
   — 1 / 1.

Total: 3 files / 18 matching lines / 21 occurrences. None establishes a public-correction
subscriber registry or notification cohort.

## 4. Structural orientation reconciliation

| Audited proposition | Re-derived result | Evidence at the pin | Verdict |
| --- | --- | --- | --- |
| INT-R7/R8 ratification record is 439 lines | **439 source lines** | Exact endpoint read returned lines 436-439 and no line 440 in `policy-engine/docs/system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md`. | Agrees. |
| `rule_evolution.py` has 30 top-level declarations | **28 column-zero functions + 2 column-zero classes = 30** over **839/839 source lines** | `policy-engine/src/polisyos/core/contracts/rule_evolution.py:1-839`; no line 840. | Agrees. The protocol method is nested and excluded. |
| `public_export.py` is 2,103 lines | **2,103 source lines** | `policy-engine/src/polisyos/runtime/quality/public_export.py:2098-2103`; no line 2104. | Agrees. |
| `projection_semantics.py` is 3,763 lines | **3,763 source lines** | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:3758-3763`; no line 3764. | Agrees. |
| Four canonical audiences | PUBLIC, REVIEWER, EXPERT, MACHINE | `policy-engine/src/polisyos/runtime/quality/projection_semantics.py:648-655`. | Agrees. |
| `rule_evolution.py` is the owner to extend | Registry, replay, persistence, public annotation, producer/reader ownership, and silent-upgrade prohibition are co-located | `policy-engine/src/polisyos/core/contracts/rule_evolution.py:1-38, 177-189, 302-330`. | Agrees under P27/P28. |
| `public_export.py` producer-to-HTTP relation is `bridge_missing` | Producer function exists; a live HTTP control-response consumer reads `progress.public_export` / `public_export_ref`; the control-plane store invokes that response shaper; production orchestration does not call the builder | `policy-engine/src/polisyos/runtime/quality/public_export.py:102-120`; `policy-engine/src/polisyos/runtime/http/services/control/response_shapes.py` function `_policy_design_projection`; `policy-engine/src/polisyos/runtime/http/services/control_plane_store.py` call to `build_control_job_projection_shape`; complete invocation census in `policy-engine/docs/research/policy-operations/int-r8/orientation-ledger.md:145-166`. | **Agrees.** Both endpoints exist; their production connection does not. `PAO-R36-IX-001`. |
| Existing public export is a signed correction | No exact `signature`/`signing` path or signing bridge was established in the producer | `policy-engine/src/polisyos/runtime/quality/public_export.py:1-2103`. | Not established; research correctly refuses the capability claim. |
| GY-N12 is the currentness owner | Plan owns epoch/current-head/stale/reissue chronology and forbids a parallel owner | `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2052-2138`. | Agrees; undelivered/contract-only. |
| Atlas D4 fixes language posture | `uk` primary, `en` baseline/fallback, `ru` frozen legacy | `policy-engine/docs/brand/ATLAS_SOURCE_OF_TRUTH.md:262-338`. | Agrees. |
| INT-R7 supplies key-lifecycle distinctions | Issuance-time authorization, revocation/compromise intervals, original-signature preservation, and separate currentness are defined | `policy-engine/docs/research/policy-operations/int-r7/public-verification-profile.md:250-405`; terminal controlling amendment at `:620-760`. | Agrees; composite outcomes must read through terminal section 18. |

## 5. Pass I findings

### `PAO-R36-I-001` — material — the unresolved `supersede` census is wrong

The audited orientation leaves the commission's 48-file claim unresolved at
`policy-engine/docs/research/policy-operations/pao-r36/orientation-ledger.md:49-57`. Exact-case
reconciliation over all 49 returned candidates gives 47 files, 203 matching lines, and 246 literal
occurrences. The refusal was better than inventing certainty, but it became avoidance once every
candidate was finite and readable.

### `PAO-R36-I-002` — minor — the `retraction` correction stops at files

The research correctly identifies seven all-file members and six Python members at
`pao-r36/orientation-ledger.md:58-78`, but it does not supply matching-line and occurrence counts.
The completed figures are 7/40/44 for all files and 6/39/43 for Python files.

### `PAO-R36-I-003` — commendation — structural counts reproduce

The 439-, 839-, 2,103-, and 3,763-line claims, and the 28+2 declaration arithmetic, reproduce exactly.
The research separates source lines from declarations rather than treating one as evidence of the
other.

### `PAO-R36-I-004` — commendation — generic token hits are not laundered into capability

The research correctly says the cache and subscriber hits are generic technical occurrences, not a
correction cache registry or notification chain (`pao-r36/orientation-ledger.md:80-101`). Exact
counts strengthen rather than alter that conclusion.

### `PAO-R36-I-005` — commendation — zero indexed results are not overstated

The orientation explicitly refuses to call the three zero-result queries a complete whole-tree
absence (`pao-r36/orientation-ledger.md:30-64`). That is correct P35 discipline. This audit also
cannot promote the zeros: the connector exposes no recursive read-tree action and exact-commit archive
egress failed. A recursive exact-pin tree walk is the settling evidence.

## 6. Pass I conclusion

The orientation is mostly trustworthy. Its structural anchors and capability interpretation hold.
Its main numerical defect is the unresolved `supersede` row: the lowercase exact count is 47 files,
not 48. The `retraction` dispute is a denominator-documentation issue, not an architectural reversal.
The three named outward-correction zeros remain `not_established` as complete-walk propositions, even
though every available exact-ref search returned zero.
