# GY-DEFC-1 diagnosis — N11 cold-worker boundary

Date: 2026-08-10

Base: `e18861d12` (`main`, merged GY-DEFC-1)

Scope: diagnosis only; no product source, validator, governed artifact, or expensive lane was
changed or run.

## Verdict

`not_established`

The evidence establishes the operand class and the control-flow difference, but it does not expose
the changed leaf needed to discriminate `GY-DEF10 incompletely closed` from a seventh class.

The failing comparison is an embedded-recording comparison. It compares a frozen admitted v2
recording, stripped of its authority admission and migration envelopes, with one freshly replayed
recording inside the N11 worker. It is therefore pair **(a), live-vs-frozen recording**, not a
parent-derived/worker-derived pair and not two worker-internal derivations
(`tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py:4692-5000`).

The direct Depth-N pass at `6782cb546` is not a receipt for that exact branch. Reading the artifact
on each side of that commit shows that all three input recordings were v1 with no admission before
the writer and v2 with `admission_kind=migrated` afterward. On v1 input,
`_domain_run_and_normalized_recording()` bypasses the `prior_admission` comparison and creates a
migration receipt (`:4733-4762`, `:5000-5038`). N11 then consumed the newly written v2 recordings;
only that route enters the comparison at `:4970-4989`. The whole-artifact writer reconciliation at
`:6910-6920` occurs later and cannot make an inner replay failure green.

This confirms the architect's embedded-recording reading but narrows it: the direct and N11 routes
do not use two different comparator functions. They use the same live builder with different
recording states. The direct green migrated v1 to v2; N11 was the first paid live replay of v2.

The canonical owner is not simply absent from the v2 site. The comparator calls
`reconcile_gy_operational_leaves()` when the two outer `recording_content_hash` values agree
(`:4974-4985`), and the owner recursively handles nested mappings and sequences
(`src/polisyos/pdc/_impl/gy_waist.py:126-172`). The focused v2 witness constructs nested
`generated_at` and `wall_time_ms` movement and requires exact replay equality
(`tests/unit/runtime/quality/test_depth_n_universality.py:2702-2725`); its semantic-marker negative
expects this same named error (`:2727-2737`). Therefore the observed error is compatible with two
materially different findings:

1. a real operational leaf or an operationally derived identity is still outside the canonical
   exclusion/projection, which would be `GY-DEF10 incompletely closed`; or
2. a semantic member changes only on the admitted-v2/cold-worker route, which would be a seventh
   class.

The exception contains only `authority_source_controlled_replay_recording_drift`. It records no
role, no two hash values, and no recursive changed path. The exact underlying field is consequently
`not_established`; `recording_content_hash` is a derived symptom, not the missing cause. Naming the
defect from that error string would repeat `P36`.

### Exact discriminating run not performed

The cheapest sufficient discriminator is one **instrumented, single-pass cold N11 owner
derivation**, not the full two-pass N11 writer and not a Depth writer:

- spawn a fresh interpreter through the same checker-module import/bootstrap shape and explicit
  repository/catalog/L5 arguments as the N11 worker;
- call `build_live_contract(repo_root, catalog_path=..., l5_path=...)`, which loads the registry and
  enters `load_owner_bundle()` with its pre-derivation fence and declared owner environment; and
- from an ignored scratch trace hook at the `:4986` comparison, capture `role`, both
  `recording_content_hash` values, and recursive raw and `strip_gy_volatile_fields()` diff paths for
  `expected_recording` and `normalized_recording`.

That one replay would settle whether every changed path is declared operational (incomplete
`GY-DEF10`) or whether any semantic path moves (seventh class), and would identify the exact field
and operand values. The prior cold N10 portion took about 1,537 seconds before failure, so this is an
expensive lane under the task's “few minutes” fence. It was not run. If it does not reproduce, the
next discriminator is the same trace in a paired direct-process and spawned-worker envelope; that
would isolate process-envelope causality rather than equality semantics.

## Operand analysis and P37 labels

| Claim | Evidence | P37 label |
| --- | --- | --- |
| The left operand is the frozen v2 recording minus admission/migration envelopes, rehashed as `expected_recording`. | `_authority_source_recording_base()` and `_without_authority_source_migration_receipt()` at Depth-N `:2765-2775`, `:4433-4440`, consumed at `:4970-4973`. | `recomputed` |
| The right operand is a fresh worker replay, `normalized_recording`. | `_domain_run_and_normalized_recording()` rebuilds compiler/N4/context/compiled state at `:4692-4969`. | `recomputed` |
| The pair is frozen-vs-live embedded recording, case (a). | Both operands are constructed and compared in the same worker call at `:4970-4989`; the parent supplies paths but no derived recording. | `recomputed` |
| The direct Depth pass migrated v1/no-admission recordings to v2/migrated-admission recordings. | Exact `git show 6782cb546^:...json` and `git show 6782cb546:...json` readback for all three roles. | `recomputed` |
| The direct green did not execute the admitted-v2 equality branch. | v1 takes the legacy/migration branch; only truthy `prior_admission` enters `:4970`. | `recomputed` |
| The later N11 run failed after milestone ordinal 5 at this named inner error and before `owner_bundle_loaded`. | Merged run journal at `docs/superpowers/journals/2026-08-09-gy-defc-1.md:518-556`; no replay was run here. | `institutionally_supplied` |
| Canonical reconciliation is recursively capable of preserving already-declared nested operational leaves. | Owner source at `gy_waist.py:126-172`; focused witness shape at `test_depth_n_universality.py:2702-2725`. | `recomputed` |
| The exact role, leaf path, old value, new value, and causal process input in the failed run. | The exception serializes none of them and no retained operand trace exists. | `not_established` |
| The changed leaf is operational and belongs to DEF10. | Requires the instrumented admitted-v2 replay above. | `not_established` |
| The changed leaf is semantic and constitutes a seventh class. | Requires the same discriminator. | `not_established` |

The candidate field denominator after the earlier guards is narrower than the whole recording:
`compiler_recording`, `schema_version`, `role`, and `design_problem_ref` are copied or checked before
the comparison. The unresolved movement can still be in normalized `n4_recording`, the context
binding, `compiled_run`, `compiled_run_content_hash`, or their derived `recording_content_hash`.
The run does not name which role or path.

## Alternate-projection set disposition

The current complete tracked-Python denominator is **5,560 `.py` paths**; the validator subset is
**184 `.py` paths**. These commands were rerun at `e18861d12` with cwd set to `policy-engine/`
(from the repository root, the validator pathspec is
`policy-engine/tools/quality/validation/*.py`):

```zsh
git ls-files -- '*.py'                                                    # 5,560
git ls-files -- 'tools/quality/validation/*.py'                           # 184
git grep -n -E 'exclude=\{"(content_hash|record_hash)"\}' -- '*.py'      # 0
git grep -n -E '\.pop\("(content_hash|record_hash)"' -- '*.py'           # 6 candidates
git grep -n -E \
  '(key|field|item)[[:space:]]*(not in|!=)[[:space:]]*(\{[^}]*"(content_hash|record_hash)"|"(content_hash|record_hash)")' \
  -- '*.py'                                                              # 42 candidates
git grep -n -E 'exclude=\{[^}]*"(content_hash|record_hash)"[^}]+\}' \
  -- '*.py'                                                              # 0
```

The three comparison scans now return **36 object**, **21 reference**, and **494 broad mapping**
candidates. There are **24** `gy_artifact_self_identity_projection` references and **23**
`reconcile_gy_operational_leaves` references. Candidate counts are search denominators, not claims
that every candidate is a comparator.

| Original census site or set | Current disposition | Exact evidence |
| --- | --- | --- |
| The literal ten singleton exclusions across value evidence, advisor, uncertainty, confidence ledger, generation cycle, grounding bind, and intervention substrate | **Absorbed** | Zero exact singleton exclusions remain; each former site now calls the generic or GY artifact self-identity owner (`value_evidence.py:110`, `advisor.py:464`, `uncertainty.py:115`, `confidence_ledger.py:4099`, `generation_cycle.py:367`, `grounding_bind.py:141,150`, `intervention_substrate.py:279,364,406`). |
| `acquisition_planner.py:2641` | **Absorbed** | Uses the generic artifact self-identity projection; GY volatile stripping remains downstream. |
| `grounding_admission.py:1112,1122,1132` | **Absorbed** | All three projections use the generic self-identity owner. |
| `grounding_benchmark.py:526-528,3132-3141` | **Partly absorbed; unresolved duplicate** | Scoreboard self-identity is generic, but `_without_volatile_latency()` remains a private latency projection overlapping the GY `*_ms` owner. It is outside this cold comparison and has no post-merge explicit classification. |
| `grounding_bind.py:1361` | **Absorbed** | Uses the GY artifact projection. |
| `intervention_atom_binding.py:560-575` | **Absorbed base; classified out remainder** | Generic self-identity removal is shared; atom ID, producer, provenance, status, and nullable normalization are this artifact's declared content projection. |
| `intervention_substrate.py:364,406` | **Absorbed** | Both mapping paths use the GY artifact projection. |
| `recursive_generation_cycle.py:265-266` | **Absorbed base; classified out remainder** | GY self-identity is shared; computed `leaf_nodes` is an artifact-specific omission. |
| `world_model_record.py:1182-1208` | **Absorbed base; classified out remainder** | GY self-identity is shared; WMR identity, authority, producer, and non-content location fields remain a distinct WMR projection. |
| `grounding_active_controller.py:1515-1522`; `grounding_phrasing_defense.py:884-895` | **Absorbed base; classified out remainder** | Both former duplicate helpers now start with the generic owner and remove their artifact ID field. |
| `promotion_sequence.py:1871-1874` | **Unresolved classification** | The trace still computes a local hash excluding `trace_content_hash`; the prior census required explicit artifact-owner classification, and no post-merge classification records it. |
| `scientist/methods/autotune/reflexion.py:205-210` | **Absorbed base; classified out remainder** | Generic self-identity is shared; `can_retry` remains reflexion-card-specific. |
| `runtime/http/services/control/generation_cycle.py:70-73` | **Absorbed base; classified out remainder** | GY self-identity is shared; `leaf_nodes` is an API surface-shape omission. |
| N10a whole-artifact writer/comparator | **Absorbed** | Calls `reconcile_gy_operational_leaves()` at `check_layer3_gy_second_domain_pack.py:6439-6449`. |
| Depth-N whole-artifact writer/audit | **Absorbed at artifact boundary** | Writer and audit call the owner at Depth-N `:6910-6920`, `:7833-7842`. |
| Depth-N admitted-v2 embedded-recording comparator — the failing site | **Unresolved, not classified out** | The owner is called at `:4977`, but only after outer hash equality at `:4974`; the failed run exposes no changed path. This was the targeted whole-recording row, not one of the exclusions. |
| Twenty artifact-reference, lifecycle, verifier, and self-integrity comparison rows in the original census | **Classified out** | They compare owner-issued identities/references rather than choose operational equality; complete table at the merged journal `:317-336`. |

The alternate set therefore does not establish that the failure was intentionally outside the
owner. The failing comparator was meant to be absorbed and is recursively supported, but its live
v2 disposition remains unresolved because path classification happens implicitly through the outer
hash gate rather than being reported at the failure.

## Worker-process boundary

Assessment: **partly sealed**. The derivation's declared consumed set is sealed inside the spawned
worker; parent-to-worker execution equivalence is not itself sealed.

| Boundary member | Evidence and assessment | P37 label |
| --- | --- | --- |
| Explicit roots | `repo_root`, catalog, and L5 paths are passed as `multiprocessing.Process` kwargs (`check_layer3_gy_confidence_ledger.py:3841-3914`) and resolved inside `load_owner_bundle()`. | `recomputed` |
| Declared source/artifact/filesystem set | The worker constructs the source closure and content fence before derivation and reconstructs them after it (`layer3_gy_confidence_ledger_contract.py:230-268`, `:909-1029`, `:1049-1121`). | `recomputed` |
| Recorded set size | The merged journal reports a pre-freeze set of 2,088 members: 2,084 `recomputed`, four `independently_reconciled`, none in a rejected P37 class (`2026-08-09-gy-defc-1.md:398-415`). The failed N11 path minted no receipt. | `institutionally_supplied` |
| Controlled environment | `_declared_owner_environment()` constructs 19 keys: JAX CPU, sixteen N4 keys, and two N7 keys; the worker applies them around the whole owner derivation and seals their actual values (`layer3_gy_confidence_ledger_contract.py:828-870`, `:945-960`). | `recomputed` |
| PolicyOS/tool root-file identity and declared import membership | The owner closure includes both N11 tool entry modules and dynamic producers with `include_tools=True`, resolves them under the explicit root, and hashes those files (`layer3_gy_confidence_ledger_contract.py:51-54`, `:1049-1121`). | `recomputed` |
| Actual loaded-module origin/code | The ledger binds origin/code for its `polisyos` authority closure, whose normal runtime call excludes tools (`confidence_ledger.py:4272-4288`, `:4930-4966`, `:5388-5404`). Actual tool-module import origin and precedence are not equivalently bound. | `recomputed` for the `polisyos` closure; `not_established` for tool origin |
| Python ABI and repository dependency declaration | The runtime manifest plus `pyproject.toml`, `uv.lock`, and all `src/polisyos/**/*.py` bytes enter deployment identity (`confidence_ledger.py:4198-4269`, `:5268-5289`). | `recomputed` |
| N8 runtime packages/backends | N8 independently re-derives its governed package/backend projection (`check_layer3_gy_value_gate_contract.py:3486-3507`). That is evidence for N8's artifact, not a complete parent-to-worker distribution/native-library seal. | `recomputed` for N8; `not_established` for complete worker state |
| Post-derivation same-input reuse in the failed run | The worker failed before `owner_post_derivation_fence_started`, so the second fence and `assert_consumed_input_reuse()` did not execute. | `not_established` |
| Raw inherited environment outside the 19-key map | `multiprocessing` spawn receives no sanitized `env`; only declared keys are overwritten later. Whether any unenumerated inherited key affected this replay is not shown by the failure. | `not_established` |
| Child working directory | The closeout worker does not `chdir`; it inherits cwd. The audited cold owner calls use explicit roots, but cwd equivalence is neither bound nor rejected. | `not_established` |
| Raw `sys.path` order/import chronology | Resolved repository file membership is bound and loaded `polisyos` origin/code is checked; raw path order and actual tool-module origin are not. Opposite-order focused evidence is recorded, but no end-to-end cold receipt exists. | `not_established` for process-equivalence; `institutionally_supplied` for the focused witness |
| Installed third-party state beyond governed runtime-package/backend evidence | Lock bytes and N8's relevant package/backend identities are bound, but the complete installed distribution set and native-library state are not one sealed parent/worker member. | `not_established` |

The semantic source-flip subprocess is now explicitly sanitized rather than inheriting
`os.environ` (`check_layer3_gy_confidence_ledger.py:3368-3392`), but the failing closeout worker is a
different `multiprocessing` path and still inherits its process envelope. None of the unsealed rows
is established as causal. The failure occurs after the pre-derivation seal and inside N10 replay;
that proves location, not cause.

## Orchestration

Three `gpt-5.6-terra` workers ran read-only in parallel:

| Worker | Lane | Returned evidence |
| --- | --- | --- |
| `operand_trace` | Frozen/live operand and control-flow trace | Pair (a), common builder, v2 branch, missing path discriminator. |
| `projection_census` | Full alternate-projection disposition | Failing site unresolved/not classified out; current P35 counts and two residual non-cold classifications. |
| `worker_seal` | Parent/child boundary audit | Within-worker seal is real; full process-envelope equivalence is not established. |

All governed/source reads ran concurrently; no contended artifact existed. The root serialized the
only write, this journal. No `sol` worker was used or considered necessary, and no tier escalation
was attempted. No worker edited a file or ran an expensive lane.

## Closure state

No new defect ID is proposed because the evidence does not yet discriminate the two permitted
classes. No smallest repair is prescribed before that discrimination. The next action is the one
instrumented single-pass cold N11 owner derivation above; its raw/canonical path diff is the
acceptance signal for the architect's classification decision.
