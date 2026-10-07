# F E02 — итоговая передача, 2026-10-06

35 IDs / 17 bundles / 36 source-card bindings, 35 различных исходных карточек (LA-016 связан дважды). Решения F — технические рекомендации по исходному критерию; G ещё должен принять код и formal ledger. Закрытых: 17, limited: 16, held: 2.

PASS ниже означает измеренное свойство в указанном профиле. Для limited/held оставшийся критерий UNRUN либо имеет отдельный FAIL/ERROR/SKIP в полном receipt; PASS не означает production closure.

| ID | Исходный критерий / измеренное свойство | Actual consumer | Code SHA | Check | Outcome | Ограничение / следующий owner |
|---|---|---|---|---|---|---|
| B204 | Идентифицированный DiD; ATT=3; preperiod invalid/not_testable | StandardDifferenceInDifferences.pure_step | cebe94d8134a | PASS | closed | Реальные parallel trends остаются предпосылкой. |
| B205 | Фактические HC1 iid и unit-cluster CR0 | StandardDifferenceInDifferences.pure_step | cebe94d8134a | PASS | closed | Small-cluster coverage не установлена. |
| B206 | Confidence level изменяет DiD/RDD границы | StandardDifferenceInDifferences / RegressionDiscontinuity → CAS | cebe94d8134a / fb022aa12599 | PASS | closed | RDD RBC: отдельный clean-room fixed profile. |
| B207 | θsel, cohort-share ratio IF, общий unit multiplier | StaggeredDifferenceInDifferences → MethodJob → CAS → Scientist reconciler | cebe94d8134a | PASS | limited | G: полный admitted run_causal_evaluation и fresh consumer. |
| B208 | Centered studentized null и CI inversion той же проверки | StaggeredDifferenceInDifferences → CAS → Scientist reconciler | cebe94d8134a | PASS | limited | G: полный admitted consumer; synthetic coverage не real-data вывод. |
| B209 | Anticipation-safe controls; без cell drops/renormalization | StaggeredDifferenceInDifferences → CAS → Scientist reconciler | cebe94d8134a | PASS | limited | G: production admission/authority и точные refs. |
| B210 | Sharp RDD CCT RBC tau_bc/se.rb/CI | RegressionDiscontinuity → MethodJob → CAS → fresh reader | fb022aa12599 | PASS | closed | Fixed p/q/kernel/HC0 profile; fuzzy до typed treatment limited. |
| B211 | RDD O(np) weighted design; без n×n diagonal | RegressionDiscontinuity → MethodJob → CAS | fb022aa12599 | PASS | closed | Row permutation и resource oracle — finite native profile. |
| B212 | Point-only DoWhy не создаёт estimator CI | DoWhyIdentifyEstimate → genuine 3.12 worker → CAS → 3.14 reader | 423165322e50 | PASS | limited | G: полный admitted Node; getter None остаётся nongating point-only. |
| B213 | Реальный identified estimand/contrast/target binding | DoWhyIdentifyEstimate → worker → CAS → canonical report factory | 423165322e50 | PASS | limited | G: полный admitted Node; ATE/backdoor linear profile. |
| B214 | Известные marks/direction; cycle/unresolved refusal | ReconcileCausalGraph → CAS → ReconcileCausalGraphNode / static GCM | 6dcb792b6f8c | PASS | limited | Широкий policy-gate intake/PAG identification UNRUN; G/A/C. |
| B215 | Gaussian abduction mean/cov, singular evidence, row IDs | GCMQuery → source-bound model → fresh CAS reader | 6dcb792b6f8c | PASS | closed | Declared linear Gaussian profile; unknown law typed limited. |
| B216 | m-separation: fork/collider независимый exhaustive oracle | Actual m-separation / Rule 1 → graph consumer | 6dcb792b6f8c | PASS | closed | Конечный small-graph oracle, без общего identification обещания. |
| B217 | Perfect do удаляет latent incoming relation | Actual Rule 3 / do surgery → graph consumer | 6dcb792b6f8c | PASS | closed | Конечный latent-DAG surgery oracle. |
| B218 | Lag export сохраняется; static GCM отказывает | CausalGraphModel export → fresh reader / static GCM intake | 6dcb792b6f8c | PASS | limited | Временная identification/readiness не установлена; G/A/C. |
| B219 | NetworkX 3.6.1 mixed MultiDiGraph parallel readback | CausalGraphModel.to_networkx → MultiDiGraph → fresh CAS reader | 6dcb792b6f8c | PASS | closed | Actual backend witness снимает прежний held только для этого свойства. |
| B220 | Deep immutability, cold/warm/copy cache и weakref cleanup | CausalGraphModel → cached node/edge rows → real export/readback | 2137961b0d3a | PASS | closed | Первичный mutation FAIL сохранён; окончательное решение связано с narrow fix и независимым consumer/control receipt. |
| B221 | Real GCM assignment/fit, persisted source/row-bound model | HybridSCMFit → DoWhy gcm.fit → CAS model → fresh GCM reader | 6dcb792b6f8c | PASS | closed | Fully observed static linear DAG; не NumPy fallback witness. |
| B222 | Сохранённый polynomial исполняется точно | GCMQuery / TwinNetworkQuery → CAS → fresh reader | 6dcb792b6f8c | PASS | closed | Declared mechanism profile; unknown law typed limited. |
| B223 | Same-arm=0, do(2)-do(0)=6; interval kind/refit | GCMQuery → RunCausalQueriesNode → CAS → fresh reader | 6dcb792b6f8c | PASS | closed | Distribution/posterior interval не estimator CI; iid full-refit bootstrap. |
| B224 | Exact do surgery; replaced/irrelevant mechanism не исполняется | GCMQuery → actual surgical sampler → CAS reader | 6dcb792b6f8c | PASS | closed | Static declared graph/law; lagged query typed refusal. |
| B225 | Normal/Uniform/TruncatedNormal support/CDF, tails | GCMQuery → declared stochastic intervention → CAS reader | 6dcb792b6f8c | PASS | closed | Unknown law и unsupported profile — typed limited/refusal. |
| B54 | Recompute cache identity; caller key не bypass | fit_crossfit_nuisance_bundle → fit_tmle_ate | 55d2e14755bd | PASS | closed | Binary [0,1]; EIF CI только regular iid profile. |
| B56 | Все folds исполняются в existing worker budget | LocalWorkerPool → MethodJob → TMLE folds → CAS reader | 55d2e14755bd | PASS | limited | G: общий production budget/admission consumer UNRUN. |
| LA-001 | Seed → persisted Treasury salts → actual RNG | compile.api.compile → compile_trinity → TreasuryPlan → execute.api.execute → execute_program_graph → adaptive_agent | 63425f734946 | PASS | closed | Selected versioned salt profile; legacy default сохранён. |
| LA-002 | Family certificate → actual state mechanism consumer | Family catalog / native certificate → state verifier | 63425f734946 | PASS | limited | 4 реальных catalog families без runtime state mapping; owner C/G. |
| LA-003 | Equivalent fiscal/labor/plugin real patch fixtures | Registered fiscal/labor kernels → apply_patch_map → GlobalState | 532ca1f5ff78 | PASS | limited | Units/laws различия сохранены; полная migration/admission — G/C. |
| LA-004 | Independent Gini pairwise/scale/dtype; economic meaning | foundry.agent_sim.executor.PureExecutor / EconomicsPlugin → compute_aggregates | 532ca1f5ff78 | PASS | held | G/экономический owner: исходная welfare norm не задана; held. |
| LA-007 | Удаление id_engine.py с полным importer census | Installed package preserved; external dynamic loaders UNRUN | 6dcb792b6f8c | UNRUN | limited | G/C: full computed/external import denominator; не importability closure. |
| LA-016 | Legacy DiD umbrella → dedicated causal methods/callers | DifferenceInDifferences dispatcher → public method facades | cebe94d8134a | PASS | limited | Два maintained callers; full migration/admitted inputs — G/C. |
| LA-017 | Duplicate pass refs; actual legal plan blockers/topics | LegalPass → frozen plan → blockers/CAS/CLI render | 00a6eda114b9 | PASS | limited | G/legal owner: current-law corpus/source authority local-only UNRUN. |
| LA-019 | Две retired causal shadows и реальные loader consumers | Installed preserved causal packages; external loaders UNRUN | 6dcb792b6f8c | UNRUN | limited | G/C: полный external/computed consumer denominator. |
| LA-020 | Public FQN/docs/monkeypatch/default identity и installs | Canonical public facade → wheel/sdist → neutral-cwd consumer | 729d137279b7 | PASS | limited | 182 computed expressions/external clients unresolved; G/C. |
| LA-035 | Historical normalized-income score и optimizer owner | normalized_income_budget_loss → legacy aliases → GlobalState/JIT/grad | 532ca1f5ff78 | PASS | held | income≥1 score=−1 сохранён; actual production optimizer/norm — G, held. |
| LA-037 | IR slot layout → consumer → installed layout | Native IR slot layout / installed public package consumers | 63425f734946 | PASS | limited | Полный compatibility-wrapper retirement/caller census — G/C. |

Полные SHA/tree, source-card bytes/hash, oracle/negative controls и output refs по каждой строке: [index.json](index.json). Неизменённые полные deciding audit bytes: [artifact-transports.json](artifact-transports.json).

База: `198076863e143dea9f89f02734b13d50dae3eed5` / tree `2b754a92c27959e2e747738d47ed0b419f3b6dd8`; anchor ancestor проверен. G97 — только audit base. Все 12 topic refs и PR перечислены в index; main не опубликован.

Whole architecture/strict gates UNRUN при отсутствующих prerequisites; docs/static/EMP FAIL и ERROR сохранены в receipts. P41 `not_established`, ни один SKIP/UNRUN не принят за PASS.

Текущие deciding refs: PASS. Полная историческая custody: UNRUN — один Git blob `175c1ed4db37589e8adaf14af6700ad639edb2c8` отсутствует локально и возвращает GitHub HTTP404 (4 provenance-only ссылки); ни одно решение по 35 IDs не использует его как доказательство. Полные результаты и read-only probe сохранены.

Синтетические analytic/DGP/graph результаты доказывают объявленные generic properties. Необходимые реальные law/history/authority inputs и read-only rerun переданы G отдельным committed recipe. Корзины нет; cleanup candidates перечислены, ничего не удалено.
