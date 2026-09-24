# N18 implementation map

## Scope and evidence status

This is a read-only implementation plan for the 18 N findings: B09, B27, B28, B19, B21, B23, B25, B26, B108, B109, B111, B57–B59, B72, B73, B88, and LA-021. No tests or validators were run for this map. Every listed test identity is a candidate witness and remains **UNRUN** here. The baseline broker may later supply four-base outcomes; this document does not replace them.

The original B cards are pinned at `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@d800082eebfc12eaf647b0c0257c4f06e135d25a`. The LA card is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@4bdf76e99f0c26e40bc2a71e76d4940c23712260`. Existing source/test identities below are from the Phase0 review tree and are cited by path and blob. The current integration head has only advanced its baseline harness; no source/test change affected this map.

Status labels describe source-level coverage only. They do not imply a finding-level closure. A repair to a source owner is conditional on a distinguishing behavioral witness failing at the assigned base.

## Cycle and occurrence identity

### B09 — data progress versus name-only retry

**Exact card criterion:** “тот же кандидат с новыми реальными данными переоценивается; тот же кандидат на тех же входах под новым именем не запускается бесконечно. Обновляются и переход, и последующий валидатор. Проверяется идентичность occurrence и привязка к исходной/пересмотренной задаче.”

**Production caller and current witnesses:** the served WDI path admits a delta and re-enters the same case through the AcquisitionWorldGrowth bridge. Candidate witnesses are `policy-engine/tests/integration/core_runtime/test_acquisition_world_growth_chain.py@c101c5d2a2f25da0bce6cf6a265eff4a99a2bdc2::test_actual_wdi_admits_delta_and_reenters_same_case`, and `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a::test_controller_runs_counterexample_driven_revision_over_two_real_cycles`, `::test_uuid_and_timestamp_only_revision_is_blocked_as_no_progress`, `::test_acquisition_required_invokes_n7_and_records_same_cycle_reentry`.

**Smallest behavioral addition:** negative control: the same admitted basis under a new name/UUID/timestamp remains no-progress. Preserving control: for the same candidate, a genuinely changed data basis admitted through overlay, passport, and epoch qualification creates the next occurrence, triggers re-evaluation, and updates the subsequent validator. A direct fabricated world-model write is not a preserving control.

**Conditional owner and lease:** `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`, only if the served witness is red. This file and its unit test overlap R1, R2, R5, R6, R11, R12, and R13; the integration witness overlaps R2/R13. Sequence behind those leases. A production claim needs a genuinely admitted changed-data record; an in-memory substitute only tests the selector. No principal decision is identified.

### B27 — revised request and owner context

**Exact card check:** “Допустимая вторая итерация получает согласованный context и проходит; изменение предмета, популяции либо модели не переиспользует старые доказательные привязки. Проверить исходный и пересмотренный запрос в общей сохранённой истории.”

**Production caller and current witnesses:** `GenerationCycleController` through the HTTP owner composition. Candidate tests are `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a::test_same_candidate_new_basis_preserves_history_and_current_front` and the R1-owned request path `policy-engine/tests/unit/runtime/http/test_control_service_di.py@4c100bb6d2c17cac8e3e61bee34519c338c075ec::test_process_nl_job_enters_persisted_tenant_scope`.

**Smallest behavioral addition:** negative control: a change to subject, population, or model cannot reuse the prior evidence/context binding. Preserving control: a permitted revised basis with matching current owner context completes a second iteration and preserves both source and revised request history.

**Conditional owner and lease:** `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a` only if this witness is red; do not bypass the context owner. The runtime/test paths overlap R1, R2, R5, R6, R11, R12, and R13; `policy-engine/tests/unit/runtime/http/test_control_service_di.py` is R1-owned. No principal decision is identified.

### B28 — occurrence-specific current front

**Exact card check:** “Один кандидат на двух версиях данных представлен без потери истории и без дубликатов текущего фронта. Итог второй попытки не присваивается первой. Проверить, что downstream получает нужную occurrence.”

**Production caller and current witness:** cycle current-front derivation flows to downstream promotion. Candidate witness: `policy-engine/tests/unit/runtime/quality/test_generation_cycle.py@4f851cb207267a13877647ef82a2b73f3a24360a::test_same_candidate_new_basis_preserves_history_and_current_front`.

**Smallest behavioral addition:** negative: a second result cannot attach to occurrence one, and duplicate candidate IDs cannot stand in for occurrence binding. Preserving control: both attempts remain in history while current-front/promotion selects the intended newer occurrence once.

**Conditional owner and lease:** `_current_candidate_summaries` / `_derive_fronts` in `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`, only if the downstream occurrence witness is red; shared R1/R2/R5/R6/R11/R12/R13 lease. No separate production seam is established before the consumer witness.

## Joint simulation and SMM

### B19 — baseline and factual evidence remain distinct

**Exact card criterion:** “no-op не создаёт ненулевого эффекта лишь из-за отсутствующего baseline; отсутствие comparator не подменяется нулём. Фактическое evidence не меняется незаметно при выборе базы сравнения. Совместное взаимодействие использует согласованный baseline.”

**Production caller and current witnesses:** `JointSimulationPort` → `JointSimulationHorizonController.run`, consumed by the cycle. Candidate tests in `policy-engine/tests/unit/remediation/test_sim_03.py@3462c32268dd9cc35427680d97e5e6e037043d56`: `test_ncm_evidence_none_and_explicit_empty_are_distinct`, `test_joint_simulation_requires_explicit_selected_outcome_baseline`, `test_explicit_comparator_makes_equal_scenarios_zero_effect`.

**Smallest behavioral addition:** negative: absent comparator must not become zero or invent a no-op effect. Preserving control: an explicit comparator makes equal scenarios yield zero while factual evidence remains a separate bound input. Exercise the production caller if current tests stop at the helper.

**Conditional owner and lease:** `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c` only on red. No known R-source overlap; no data/principal dependency for a deterministic contrast.

### B21 — requested replications and measured error

**Exact card criterion:** “изменение допустимого числа повторений меняет фактическую работу или выдаёт явное ограничение. Count, seeds и оценка численной ошибки согласованы. Один стохастический draw не выдаётся за точную оценку. Численная Monte Carlo-ошибка не заменяет неопределённость модели мира.”

**Production caller and current witnesses:** the same joint-simulation horizon caller. Candidate tests in `policy-engine/tests/unit/remediation/test_sim_03.py@3462c32268dd9cc35427680d97e5e6e037043d56`: `test_single_paired_draw_has_unestimated_standard_error`, `test_paired_replicates_require_distinct_seeds`, `test_joint_request_runs_each_requested_replication_with_distinct_seeds`.

**Smallest behavioral addition:** negative: requested count is not executed, seeds repeat, or one draw claims a precise SE. Preserving control: N requested draws use distinct seeds and report numerical error; a one-draw result states that error is unestimated.

**Conditional owner and lease:** `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c` only on red; no known R overlap. Deterministic small inputs suffice.

### B23 — reuse physical run but preserve role references

**Exact card criterion:** “в детерминированном одно-/двухатомном примере дубликат не вызывает второе вычисление, но обе роли сохраняют свои references. Изменённый seed или параметр не даёт ложный cache hit. Если независимость экспериментов требует отдельных runs, выполняются отдельные runs.”

**Production caller and current witnesses:** the same horizon/cache caller. Candidate tests in `policy-engine/tests/unit/remediation/test_sim_03.py@3462c32268dd9cc35427680d97e5e6e037043d56`: `test_physical_run_ref_binds_effective_evidence_and_source_mode`, `test_joint_simulation_reuses_physical_spec_across_roles`.

**Smallest behavioral addition:** negative: changed seed/effective parameter forces a distinct run. Preserving control: exact duplicate physical specifications reuse one run, while each role keeps its own reference.

**Conditional owner and lease:** `policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py@e74fa941d673b98b51e3b90934db666ecfa6467c`, only on red; no known R overlap.

### B25 — metric removal cannot improve calibration eligibility

**Exact card criterion:** “удаление метрики не улучшает пригодность кандидата на прежней задаче. Разные наборы данных/метрик явно несопоставимы или сравниваются по объявленному правилу. Настоящее улучшение всех требуемых выходов сохраняется.”

**Production caller and current witnesses:** `CoupledSMMEstimator.estimate` / `calibrate_coupled_smm`; current candidates in `policy-engine/tests/unit/remediation/test_sim_03.py@3462c32268dd9cc35427680d97e5e6e037043d56`: `test_summary_distance_requires_one_declared_metric_set`, `test_smm_missing_required_moment_cannot_win_calibration`, `test_smm_all_incomparable_candidates_are_explicitly_blocked`. The review did not establish a real accepted production-selection caller.

**Smallest behavioral addition:** negative: removing a required moment cannot improve eligibility; differing metric/data sets are typed incomparable or compared only by a declared rule. Preserving control: a complete required set with genuine improvement remains eligible. Do not add a production bridge solely to make the test look end-to-end; first establish its real caller.

**Conditional owner and lease:** `policy-engine/src/polisyos/foundry/coupling/estimation.py@5f574d9aa735d843722b429bb8c00c3721ca6911` only on red. Production caller is `not_established`; no data/principal decision identified for helper behavior.

### B26 — interaction order is not global additivity

**Exact card criterion:** “трёхатомный multiplicative пример не выдаётся за глобально аддитивный. Настоящая сумма независимых эффектов сохраняет соответствующий результат в проверенной области. Составные labels и читатели показывают, что именно проверено, не требуют экспоненциального перебора ради первого примера.”

**Production caller and current witnesses:** cycle joint-simulation result and board consumer. Candidate tests in `policy-engine/tests/unit/remediation/test_sim_03.py@3462c32268dd9cc35427680d97e5e6e037043d56`: `test_three_atom_controller_reports_real_higher_order_residual_and_order`, `test_joint_residual_keeps_higher_order_interaction_visible`, `test_checked_interaction_orders_include_pairwise_two_atom_run`.

**Smallest behavioral addition:** negative: three-atom multiplicative interaction keeps a visible higher-order residual and is not labeled globally additive. Preserving control: true independent additive effects sum in the declared checked region. Assert the consumer names the checked interaction order.

**Conditional owner and lease:** horizon/consumer only if the behavior is red. If implementation changes `policy-engine/src/polisyos/runtime/quality/generation_cycle.py@65d830f71dccd9c3b1e943e5e132678f7221ed8a`, coordinate with R1/R2/R5/R6/R11/R12/R13; otherwise `test_sim_03.py` is not known to overlap R leases.

## Search and registry admission

### B108 — score aliases, absence, units, and invalid values

**Exact card acceptance:** “Эквивалентные кодировки balance/deficit дают одинаковый score; ноль не считается отсутствием; полностью отсутствующее, конфликтующее, non-finite и несовместимые единицы различены.”

**Production caller and current witnesses:** `BudgetDeficitObjective` via `ObjectivePresets` and `SearchLoopRunner._evaluate_candidate`; it is configurable and not established as the default live objective. Candidate tests in `policy-engine/tests/unit/scientist/methods/search/test_objective.py@5dd6e5b66ca2c5c95752e524d4f43185e17bade7`: `test_budget_deficit_normalizes_missing_null_alias_and_sign`, `test_budget_deficit_marks_missing_metric_unusable`, `test_budget_deficit_keeps_non_finite_metric_unusable`, `test_budget_deficit_rejects_conflicting_balance_aliases`.

**Smallest behavioral addition:** add incompatible-unit negative and compatible-unit positive controls; preserve a real zero and equivalent alias parity. Verify the search consumer retains missing/incomparable as unusable instead of scoring a favorable zero.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/methods/search/objective.py@d27c9e2570a5b3c02f8cc4433b4c24f71aa167d3` only if the consumer witness is red. No known R overlap or principal/data dependency.

### B109 — fast Pareto agrees with a direct oracle

**Exact card acceptance:** “Согласовать быстрый и прямой фронт для 1–4 измерений, перестановок входа, равенств одной/всех координат и обоих направлений после нормализации.”

**Production caller and current witnesses:** `_find_non_dominated_2d`, its 3D use, and `ParetoRegistry._recompute_front`; current equality tests in `policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py@678a78222cedf1f41e8f9cdb910904deec3dc91a` cover 2D/3D cases.

**Smallest behavioral addition:** deterministic bounded corpus for 1–4 dimensions and both normalized directions compared with the independent slow dominance oracle; include input permutations, equal-one/equal-all coordinates, and preserve distinct records with identical vectors. State the corpus denominator in the receipt.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/methods/autotune/pareto.py@947ce5b43c2098ced7552b05d2fa0c8931b98b23` only if oracle comparison is red. Production caller exists; no known R overlap.

### B111 — champion genesis/replacement cannot publish non-finite metrics

**Exact card acceptance:** “Перестановки не меняют конечный фронт; invalid сохраняет причину; reference point и hypervolume конечны или явно недоступны; генезис и смена чемпиона не публикуют неопределённое число.”

**Production caller and current witnesses:** `ChampionRegistry.consider_promotion`, called by `SearchLoopRunner._evaluate_candidate`. Pareto candidates in `policy-engine/tests/unit/scientist/methods/autotune/test_pareto.py@678a78222cedf1f41e8f9cdb910904deec3dc91a` cover non-finite front/reference behavior. `policy-engine/tests/unit/scientist/methods/autotune/test_registry_and_runner.py@89004b621244fe76b0d389b50c01a89195bc9018` has no exact registry genesis/replacement non-finite witness in the reviewed source.

**Smallest behavioral addition:** through the native store, negative NaN and ±infinity at genesis and replacement cannot publish a champion; finite genesis/replacement remains accepted. Reopen persisted evaluation and retain a typed invalid/missing reason through the registry reader.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/methods/autotune/registry.py@596ce03c9dd59972e5754b4f3a9ff9be960c2470` checks `None` but not finiteness in the reviewed genesis path; add the guard only if production-path test is red. No known R overlap.

## Workflow cache, mutation, and checkpoint

### B57 — cache replay applies actual writes, not stale whole state

**Card acceptance:** “Warm/cold совпадают на текущих релевантных входах; независимые обновления не откатываются; удалённое не воскресает без настоящей операции; явная запись прежнего значения не теряется.” Distinguishing setup: old state `x=2, unrelated='old'`, node writes only `y=4`, independent step changes `unrelated` to `new` before cache replay.

**Production caller and current witnesses:** `WorkflowExecutor` node cache. Candidate identities in `policy-engine/tests/unit/scientist/orchestration/engine/test_engine_executor_idempotency.py@604ac837cd4eecf3c51296bc4fb24533db732535`: `test_executor_cache_hit_preserves_unrelated_current_state`, `test_executor_cache_hit_replays_top_level_ref_write`.

**Smallest behavioral addition:** negative: warm replay cannot revert independent update or resurrect a deleted field. Controls: exact declared `params.y` write preserves unrelated updates; explicit same-value write is still replayed as an operation.

**Conditional owner and lease:** `executor.py@ebf136b63e23578eaf05a7048ae1ddd6f039269b` / `idempotency.py@ecf55fda4e1ff0a0d94d5554f8c9b76f4db8105d`, only if executor witness is red. No known R overlap.

### B58 — allowed deletion survives direct, parallel, and cached merge

**Exact card acceptance:** “Разрешённое удаление временного параметра одинаково работает при прямом, параллельном и кэшированном пути; запрещённое удаление индекса отвергается. Удаление отсутствующего поля и конфликтующие операции имеют объявленную семантику.”

**Production caller and current witnesses:** `merge_parallel_outcomes` used by workflow execution. Candidate identities in `policy-engine/tests/unit/scientist/orchestration/engine/test_state_merge.py@645e30fa190a9f66b77b468adb6ceb5826213ce7`: `test_replay_distinguishes_delete_null_and_no_write`, `test_replay_rejects_deletion_from_protected_index`.

**Smallest behavioral addition:** negative: permitted `params.stale` deletion cannot disappear through parallel/cache caller; add absent-field and conflicting-operation cases. Controls: `null` remains distinct from deletion and protected `inputs`/`artifacts_index`/`reports_index` deletion stays refused.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py@638cfce7e4c0e35bac651975c8839f31b8cc574f` only if caller witness is red. No known R overlap.

### B59 — nested declared branch state is isolated before commit

**Exact card acceptance:** “Изменения внутри объявленного поддерева не видны основе и соседу до commit; отказ ветви не оставляет следов; неиспользуемая крупная область остаётся общей, если она неизменяема.”

**Production caller and current witness:** `branch_state` consumed by `AsyncWorkflowExecutor`. Candidate: `policy-engine/tests/unit/scientist/orchestration/engine/test_state_branching.py@22d3c75e16d39c7eb1bbf7d8f7d845980341b094::test_branch_state_deeply_isolates_nested_elements_of_declared_leaf`.

**Smallest behavioral addition:** negative: mutate nested history under declared `params.config`, then fail/cancel; base and sibling must remain unchanged before commit. Controls: exact scalar-leaf/top-level edit works and unrelated unchanged subtree remains shared.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/orchestration/engine/state_branching.py@957047c7085d1cdb615bd11995e03476fa64b779`, only if the canonical caller witness is red. No known R overlap.

### B72 — skip semantics do not depend on concurrency width

**Exact card acceptance:** “Метаморфный тест: добавить независимый соседний узел, не меняя входов исследуемого узла. Его skip и дальнейший resume сохраняют один смысл в обеих ширинах. Ok добавляется в завершённые в обеих ветках; fail не добавляется.”

**Production caller and missing witness:** `AsyncWorkflowExecutor` plus checkpoint/resume. No exact width-1 versus width-2 persisted skip test found in `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py@3c05cf6adaae5b9495f84ca15d046757972927fd`, `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor.py@4a8e95fa735cc0c8329478f1b3aaa752844c0890`, or `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py@f8c97053f81f67cd21b67ddbdcfd1128b9897172`.

**Smallest behavioral addition:** proposed `test_skip_completion_alias_is_width_invariant_across_checkpoint_resume`: same target inputs at widths 1/2 with an independent neighbor, persist/resume, compare meaning/completed set. Negative is width-dependent skip completion; controls prove `ok` counts complete in both and `fail` does not. Use native skip status, not a substitute `ok` result.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py@c12f3bd3ec67ff61e9707d615729d82003b0a767` / `policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py@15391d5fbd56bb37bd83c5015a34b2130f11844a` only if red. Current source appears to include a local `ok`-only alias fix; test before changing it. No known R overlap.

### B73 — parallel-level durable head agrees with completed set and compensation

**Exact card discriminator:** crash after first level-A/B publication; reopened state and complete set agree semantically; B's increment is applied once; separately verify A=`ok`/B=`fail` with `fail_fast` and `continue`. The card also requires compensation, output-cache, and seed references to match the committed level.

**Production caller and missing witness:** `_run_parallel_tier` / `_execute_tiers` / `CASCheckpointHook` in `AsyncWorkflowExecutor`; no fault-after-first-publication/reopen witness found in `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor_hardening.py@3c05cf6adaae5b9495f84ca15d046757972927fd`, `policy-engine/tests/unit/scientist/orchestration/engine/test_async_executor.py@4a8e95fa735cc0c8329478f1b3aaa752844c0890`, or `policy-engine/tests/unit/scientist/orchestration/engine/test_checkpoint.py@f8c97053f81f67cd21b67ddbdcfd1128b9897172`.

**Smallest behavioral addition:** inject failure after first possible legacy per-alias publication, reopen the actual checkpoint, and assert complete occurrence set, exactly one B increment, and compensation/output-cache/seed refs all agree. Parameterize `fail_fast`/`continue`. Preserve the intended partial-commit/rollback contract.

**Conditional owner and lease:** `policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py@c12f3bd3ec67ff61e9707d615729d82003b0a767` / `policy-engine/src/polisyos/scientist/orchestration/engine/checkpoint.py@15391d5fbd56bb37bd83c5015a34b2130f11844a`; route or retire the legacy hook only if this witness fails. No known R overlap.

## Replay egress and canonicalization

### B88 — a failed replay does not call an unauthorized live source

**Exact card check:** “На настоящем missing/corrupt fixture сетевой egress и ordinary delegate не запускаются без отдельного допуска; режим и provenance правдивы.” Supported fallback replay preserves the same bytes and request binding.

**Production caller and current witnesses:** `ControlService.run_data_ingestion` → `run_replay_mode` in `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py@a3827ed1677df17f09827d479db7510ffdb70e6e`. Helper candidates in `policy-engine/tests/unit/fabric/data_plane/test_modes.py@4f9d353c83429ce92ddeaf445f793731c0215af8`: `test_run_replay_mode_does_not_fallback_to_live_after_fixture_failure`, `test_run_replay_mode_uses_shared_blocking_bridge`. No service-level replay call is present in `policy-engine/tests/unit/runtime/http/test_control_service_di.py@4c100bb6d2c17cac8e3e61bee34519c338c075ec`.

**Smallest behavioral addition:** service-level negative in the existing control-service test file: corrupt/missing fixture with intercepted transport yields no unauthorized request/delegate and no replay-success/provenance label. Control: valid fixture replays the bound bytes/request without unrelated egress.

**Conditional owner and lease:** `policy-engine/src/polisyos/fabric/data_plane/modes.py@7932cd8b5884239b8bbcc7567076edc5797845b0` only if the real caller egresses or mislabels. `policy-engine/tests/unit/runtime/http/test_control_service_di.py` overlaps R1. `policy-engine/tests/unit/runtime/quality/test_live_acquisition_executor.py@21a741caf97a9982864f8817f354749c9d006b41` is an alternate intercepted-transport seam but overlaps R7; prefer the direct ControlService test unless needed. No production data or principal ruling; use fixture bytes and intercepted transport.

### LA-021 — shared Core/IR canonicalization profiles

**Exact card acceptance:** “Проверить двустороннее чтение поддержанных старых payloads, byte/hash identity, типы исключений, numeric/date/null/typed-tag cases, depth errors и imports.” The same card preserves the deliberately narrower IR tag profile; Core/IR must not silently adopt one another's vocabulary.

**Production caller and current witnesses:** shared `common/canonical.py` behind separate Core and IR facades. Candidate semantic identities in `policy-engine/tests/unit/remediation/test_can_01.py@d4cb77099597b0888b4a68c065ff2ca74dc9a222` include byte/golden round-trip and hash parity, malformed/unknown/depth behavior, exception identity, Core-only tag acceptance versus IR refusal, facade imports, and legacy SHA-1 profile. Dynamic caller census is not established as executed.

**Bounded corpus recheck and 418 limit:** the existing pinned instrument is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/tools/check_la021_canonicalization.py@40bfe270c844a227ee697b305696936986aa7bed`; report `.../LA021_CANONICALIZATION_RECHECK.md@617ed7ff6560d5d2c67fb57a68150ca36960ae2b`. It pins historical/current source and fixed-vector blobs, selects all regular tracked `.json` blobs at integration commit `73c656744f051d9f40667da7f8bc91c61d8b4ebf` (2,867 paths / 2,833 unique blobs), and includes 27 fixed vectors. The recorded instrument result is PASS within Core and IR's separate profiles. This is a stronger measured corpus for that selector, **not a reproduction of the architect's exact 418 inputs**. The exact 418 selector has no immutable path/blob manifest in the reviewed package; do not invent a similar-looking 418 sample and call it a replay. To reproduce the architect's selector, recover that manifest first. Four-base unit replay stays UNRUN in this map.

**Conditional owner and lease:** no source change proposed. Current owners are `policy-engine/src/polisyos/common/canonical.py@25fa43311ba8a04a25845a1863898399a7eed958`, Core facade `.../core/canon/canon_json.py@ca14a6bf9cec51292cf457243f38191892c5828a`, and IR facade `.../ir/model_layer/canon.py@02167bbe1c34c7b6501c37a122186a5aa0ea9d90`. No R overlap or principal ruling; exact selector manifest is the named missing record.

## Lease boundary and unresolved inputs

- Cycle implementation/tests are shared with R1/R2/R5/R6/R11/R12/R13. The WDI production test overlaps R2/R13; the HTTP owner test overlaps R1. Do not add an N patch to those files until the owning R fixes are complete and the lease is released.
- B88's proposed service-level test also touches the R1 test file. The alternative live-executor test file is leased to R7.
- Other N18 test groups have no known R source/test overlap from the current R assignments; still confirm the written lease map before any edit.
- No N18 item is marked as requiring a principal ruling. B09 needs an actually admitted changed-data record for a production claim. B25's real accepted SMM caller remains `not_established`. LA-021's exact 418-input manifest is missing. These are the explicit data/owner limits; do not turn them into new code paths or overclaim closure.
- Candidate test files are existing files only; no new test module is necessary. Conditional source files, if behavioral tests go red, are limited to the named current owners: `generation_cycle.py`, `joint_simulation_horizon.py`, `estimation.py`, `objective.py`, `pareto.py`, `registry.py`, workflow `executor.py`/`idempotency.py`/`state_merge.py`/`state_branching.py`/`async_executor.py`/`checkpoint.py`, and `fabric/data_plane/modes.py`. LA-021 has no proposed source write.
