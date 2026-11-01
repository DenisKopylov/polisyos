# Независимый readback policy/search v2

**Итог: ACCEPT спецификации, не native PASS.** Все 12 предложенных файлов (5 packet MD/JSON pairs и LANE-01/02) рассмотрены вместе с baseline→v2 diff. Открытых блокирующих находок нет. Одна малая ошибка native seed fixture найдена, исправлена автором и перечитана; дополнительный PS-F08 также независимо проверен. **22 REQ / 22 TEST; все product tests NOT_RUN.**

Proposal, baseline и product peer-reviewer не редактировал. Точные hashes, JSON changed paths и source read ranges — в companion `review_policy_v2.json`.

## Содержательное заключение

### PS-F01 — ACCEPT

FOR=FN/(FN+TN) не ошибочен сам по себе, но не равен FNR=FN/(TP+FN). Старые FPR/TPR также действительно были FDR/precision. Новый DEC выбирает operational purpose, а не навязывает метрику. Counts, full/rolling window, missing labels, cohort и версия проходят всех consumers. Descriptive0 сохраняется; 0/5 не превращается в population acceptance. Burn-in rejected-label route реально существует и переиспользуется, но lessons/sentinels не объявляются representative traffic. Sampling/power/budget фиксируются до квалификации. Старые values/bytes не переименовываются задним числом.

Прочитанные подтверждения: `stages.py:398–408,502–545,682–714`; `calibration_report.py:112–171`; `cold_start.py:190–230,250–280`; `funnel/orchestrator.py:781–804,2096–2134`; `funnel/correlation.py:83–111`. Полные пути и хеши — в source scope ниже/JSON.

### PS-F07 — ACCEPT

В source подтверждены обе truthiness ветви. Explicit is-not-None selection — минимальный правильный ремонт. Раздельные predicted0/fallback3 и actual0/fallback3 controls отличают обе ошибки; None допускает только совместимый fallback. Новая проверка не расширяет concrete score domain и не убирает source/status admission. Невалидная пара не загрязняет corpus; extraction semantics переживают snapshot.

Прочитанные подтверждения: `stages.py:370–396`; `stage_contracts.py:23–61`; `test_fun_03.py:234–254`. Полные пути и хеши — в source scope ниже/JSON.

### PS-F03 — ACCEPT

Source guard действительно pending-only, cold/batch bypass остаются, после20 misses возвращается ещё один случайный candidate. V2 корректно связывает pending+completed с measurement basis и отделяет bounded proposal failure от полного finite census. Genuine measurement replicas сохраняются; cosmetic ID или optimizer RNG label не бесплатный обход. 99/100 seen и20 misses — сильнее binary-only fixture. Не требуется перебор произвольного continuous/mixed domain.

Прочитанные подтверждения: `bayesian.py:896–1006,1601–1649`; `test_bayesian.py:385–452`; `grid.py:89–126`. Полные пути и хеши — в source scope ниже/JSON.

### PS-F02 — ACCEPT_OPTIONAL_SCOPE

Source-fit guard намеренный: actual target test ожидает accepted1/rejected3, а current-run corpus имеет другой контракт. V2 не снимает этот guard и не меняет существующие TEST. Strategy-neutral reuse actual measurements — отдельная optional DEC/profile с source/unit/split/tenant/data/replica checks. Ни prediction mean/std, ни source surrogate state не становятся измерением. Отказ от нового профиля остаётся допустимым ограниченным решением.

Прочитанные подтверждения: `bayesian_generator.py:437–507`; `bayesian.py:249–312,1209–1266`; `test_v5_search_pipeline.py:2063–2104`. Полные пути и хеши — в source scope ниже/JSON.

### PS-F04 — ACCEPT_AFTER_SEED_FIX

Новый model y=u+(2+u)*a действительно может использовать sampled u через existing nonlinear expression owner; при empty evidence noise не фиксируется abduction. Независимая подстановка baseline=u, policy=2+2u, difference=2+u различает seed replay и нарушенное pairing. Counts/labels больше не единственный oracle; фикстура не подменяет draw заранее назначенным Gaussian числом. Exact integer comparator и positive-SE interaction restriction сохранены. Найденное несоответствие seed schedule исправлено на native request seed7/replications3→7,8,9.

Прочитанные подтверждения: `ncm_engine.py:101–147,691–755,862–890,1050–1097`; `joint_simulation_horizon.py:902–915,2880–2907`; `test_sim_03.py:201–257,286–327,618–689`. Полные пути и хеши — в source scope ниже/JSON.

### PS-F08 — ACCEPT

ncm_engine.py действительно вызывает100000 global normal draws на quantile даже при n_samples1; world simulation использует отдельный seeded generator. Deterministic inverse-normal — адресная замена, без нового inference engine. Lower-tail форма избегает rounding верхней вероятности к1. Несколько confidence levels исключают hardcoded1.96; ambient-state/no-auxiliary-draw controls не отключают настоящую model RNG. n1/ddof0 и tiny positive confidence получают явную interval qualification/legacy boundary, сохраняя полезные mean/trajectory/n и paired endpoints. Deterministic z не объявляется доказательством CI coverage.

Прочитанные подтверждения: `ncm_engine.py:1050–1097,1099–1119`; `joint_simulation_horizon.py:2880–2907`; `test_ncm_engine.py:524–559`. Полные пути и хеши — в source scope ниже/JSON.

## Исправленная находка FA-PS-01

Первоначальный TEST-SIM-03-03 требовал `(7,11,19)`, но `_replication_seeds` в `joint_simulation_horizon.py:902–905` даёт `seed+index`. Arbitrary helper sequence не доказывала бы request-level schedule. Автор заменил fixture на `seed=7, replications=3 → (7,8,9)` без нового API; финальный текст и MD/JSON mirror проверены. Статус **RESOLVED**.

## Ограничения исполнения, не новые блокеры

- Existing grid.py uses points_per_dim and max_candidates truncation: its iterator being exhausted is not automatically a complete SearchSpace census. For the finite profile prove full feasible choices and no truncation; otherwise retain proposal_search_budget_exhausted. This follows the v2 rule, not a new blocker.

- BoTorch optimize_acqf_discrete accepts supplied choices/unique/X_avoid; it does not establish completeness of those choices or domain effective identity. Optional backend absence need not block bounded honest search.

- Noise-sensitive NCM fixture must declare the actual non-linear equation type/parent mapping and baseline a=0 intervention. Observe delegated draws; do not manufacture u from seed labels. The proposal already requires this actual producer path.

- Quantile residual near1 should use a lower-tail CDF/erfc reference and a predeclared error bound, not 1-CDF cancellation. Numerical CI comparison excludes the declared elapsed-time field, not changing interval fields.

- DEC-FUN-03-03 and DEC-SIM-03-02 remain bounded implementation/qualification decisions; native tests and population/inference coverage remain NOT_RUN. Optional DEC-OPT-03-02 is not a local repair prerequisite.

- Root owns shared03/aggregate04 integration; this readback covers authored local files and does not certify the eventual merged archive.


## Библиотечная перепроверка

[BoTorch0.16.1 optim](https://botorch.readthedocs.io/en/v0.16.1/optim.html) действительно предоставляет discrete choices, unique и X_avoid; это не сертификат полноты domain. Lock отдельно прочитан: BoTorch0.16.1, Torch2.10.0, NumPy2.3.5.

[CPython3.14.0 statistics source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/statistics.py) подтверждает inverse-normal и строгий диапазон p. [SciPy1.16 norm](https://docs.scipy.org/doc/scipy-1.16.0/reference/generated/scipy.stats.norm.html) документирует isf как inverse survival; обе альтернативы позволяют избежать случайной quantile simulation. Native numeric qualification остаётся отдельной.

## Независимая арифметика — не product execution

Host Python3.12 stdlib: one-sided illustrative95% upper для0/5 ≈0.4507197283; 0.99^20≈0.8179069376; FOR1% и FNR100% для FN10/TN990/TP0. Правильная paired SE для[1,2,3] —1/√3; mispair[-1,2,5] —√3.

При confidence=nextafter(1,0), lower tail=5.551115123125783e−17, а `1-tail` уже равно1. Stable lower-tail z≈8.2923610758; независимый erfc roundtrip возвращает5.551115123125807e−17. Это объясняет различающий test, но не target-runtime PASS. Числа сохранены в `policy_quantile_arithmetic.json`.

## Точные файлы и hashes

Полный readback покрывает нижеуказанную финальную редакцию. Старый baseline текст рассмотрен через полный diff; неизменённые normative sections полностью прочитаны в proposed MD. Companion JSON parsed целиком, а повторяющийся текст проверен exact against MD.

| Proposed файл | Baseline SHA256 | Final SHA256 |
|---|---|---|

| `e02_final_technical_review/policy_search/proposed_v2/02_Пакеты/FUN-03.md` | `6833f5a3c6360320c4a5d7816d0f1fd6790e35486491da177f9e9fe2d3f318e6` | `992b3355f65e78a3e95358bc9626b10a81ffccadec341c9802bd482cecc8433f` |

| `e02_final_technical_review/policy_search/proposed_v2/04_Трассировка/FUN-03.json` | `b57cacfe7087b248336a5f571bb39dcd7f0ddbb0eb363e6ff67561bed4573310` | `ac82c1f8596a70b77c206d16b0e223d95e82917e7040ea174569378ceb3eafbd` |

| `e02_final_technical_review/policy_search/proposed_v2/02_Пакеты/OPT-02.md` | `b3057778bfdca3e4a3d76b44ff2426d3fc6a9c7194a2541f8c6d443885e529fe` | `dc961a4c49cf01cdcbf6a7dad1726e4ff43b9dc2715d8804c534e851526db8f0` |

| `e02_final_technical_review/policy_search/proposed_v2/04_Трассировка/OPT-02.json` | `587b1172356c6d6df12070cf70840b25524cf5dd1b914193c56143ad6fa85c13` | `239697d9f421eaf0a1b0cb90ed04efde3858499d7133525d3ebd1274e3fd6f5c` |

| `e02_final_technical_review/policy_search/proposed_v2/02_Пакеты/SIM-03.md` | `d7f0dbaa314c11ec906bfe3e5c6d8420b6c291da39fc4d0c6eb23c17abcd4ce4` | `aa14bc4c7dd580eb9c50f093616aebce060449afca42b4bec141aff9b0cf0a5e` |

| `e02_final_technical_review/policy_search/proposed_v2/04_Трассировка/SIM-03.json` | `5397b780ec111b0417696365a8dea17e3cc1a3ea9a498727dfd2b56d6fb5fc91` | `00a5dcab73db7c1f62a2e05416a0b7df50307d1f99cd3e6db08bd53f6a0e710a` |

| `e02_final_technical_review/policy_search/proposed_v2/02_Пакеты/OPT-03.md` | `3e35e027ab532d71189096e7063f624e0b6cbd6ffa79d89630791c78e5a12c1b` | `ac39c763c00a38184ea26a2184b3eca6af77d3db283077810c02ba789e67320e` |

| `e02_final_technical_review/policy_search/proposed_v2/04_Трассировка/OPT-03.json` | `9c0e63efed7a71642fe37784e6cddcb2af7efc585e28df5a04dabea97bf20e25` | `b0311bca091c8d8a9bdaac805549bb7d2943b50062cb730eaec4c9106d1e4cae` |

| `e02_final_technical_review/policy_search/proposed_v2/02_Пакеты/TRN-01.md` | `5d20bedd7e1011b64d09cf3c9c756651bbfb314fd9aa6b66fd875e5e190a1c2b` | `acb63f3f975fb5c24f8da00b67b1673a232ec256c761f03fd9b820fb58efed8e` |

| `e02_final_technical_review/policy_search/proposed_v2/04_Трассировка/TRN-01.json` | `53468e110aa9e2ecc770bc25c64de7ae8418634f7405239a244959fe8fa355b1` | `cf3748957343529fed819e191e82ac590c7cff2e641bb9d14e205e7bb2508397` |

| `e02_final_technical_review/policy_search/proposed_v2/01_Лейны/LANE-01.md` | `60e37988d181aaaf1054089498b34d851ea7d7fb8a97eeefc07f2f4b37367ecd` | `8c4a9ffa024a39d88eb10f940882e653a315e8817505a5616e3c47f2122b062c` |

| `e02_final_technical_review/policy_search/proposed_v2/01_Лейны/LANE-02.md` | `ca33cbf6b608d6f1398c9e46287c92d31bfa42c984826e56a6f7b727aa93f47e` | `f32af01898b24a89803e9812697273403813e692c45c1601b33bb717a92e27b3` |


## Source/test read scope

Это выбранные содержательные ranges, не full-repository audit. Тестовые тела читались, не исполнялись.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/stages.py`: 335–415, 480–545, 675–720; SHA256 `13a5d9b19e4966b7b18b5aa3ac74e0c7ad155b726d46a09f96268601a4ab83c2`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/stage_contracts.py`: 20–90; SHA256 `00a45aa0010e6a85812602ff52a7489610da7098ceef33258b8ed6a2ad950701`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/calibration_report.py`: 105–175; SHA256 `62c26dc393bf89d093b05be18bda03cb1ba04a9483715ab55a6866a0883d6f2f`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py`: 770–812, 2088–2140; SHA256 `b01a4e6277e45b17379a75734586d16383271f8e7e41bbfe926a3dea96577502`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/cold_start.py`: 190–230, 250–280; SHA256 `c0324ccd02b7de154b53b2836c772e1263c7a370ce34698925acdfaeefd810f0`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/funnel/correlation.py`: 75–115; SHA256 `9687fc07425ebfe49f936ca225765a62288942337df6cd46e6e7724a72d86e12`.

- `e02_repository/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py`: 70–155, 820–910; SHA256 `6db900ee270a88ef20f9b5c000eb5b612417ce96be2781aab109ea279eb2a948`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py`: 880–1010, 1595–1655; SHA256 `51635c530d94f185049a559016fa92c3e98da2cae4452ccc342162228b195c15`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/strategies/grid.py`: 75–126; SHA256 `d2533274a274f4418f2d65dc1a820270676ca96749bd966d45ceeabac5ba6ad9`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py`: 230–320, 1190–1275; SHA256 `51635c530d94f185049a559016fa92c3e98da2cae4452ccc342162228b195c15`.

- `e02_repository/policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py`: 420–515; SHA256 `f933be68848e16cc3cc1b7757d5434d89a68a158b6cb3633c8d33e5576203bd1`.

- `e02_repository/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py`: 691–758, 1025–1110; SHA256 `6db900ee270a88ef20f9b5c000eb5b612417ce96be2781aab109ea279eb2a948`.

- `e02_repository/policy-engine/tests/unit/remediation/test_sim_03.py`: 201–257, 286–327, 618–689; SHA256 `ba76c16a27f6c8dd3839115a0dbb8233a0b9a27dd36bf7ba792a70a95cd592c7`.

- `e02_repository/policy-engine/tests/unit/remediation/test_fun_03.py`: 190–258; SHA256 `4ed5107d633a1346e528a53535c99e6fb7c5c655132ad6bd26f14fcf8d3be73c`.

- `e02_repository/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py`: 890–945, 960–1005; SHA256 `333deedcd2d85bf4a75f58d698a0d487a8a163256609d0825f2063fb087a2454`.

- `e02_repository/policy-engine/src/polisyos/foundry/methods/catalog/simulation/coupled.py`: 543–640; SHA256 `f607a9e1d78157fb9e53475280b129a04c8d7400a76ad24771b0c70268038e60`.

- `e02_repository/policy-engine/tests/unit/scientist/search/strategies/test_bayesian.py`: 385–453; SHA256 `d55b032ab57826363a53548e8635821c967b0a7923215bdeb3385d679757df6b`.

- `e02_repository/policy-engine/tests/unit/scientist/methods/autotune/test_v5_search_pipeline.py`: 2060–2110; SHA256 `717294efd13f9a6570875c133b2a5dce0e0e0691e504d5c8b3a318b15ec834b7`.

- `e02_repository/policy-engine/uv.lock`: Full stdlib TOML parse; inspected package name/version only for BoTorch/GPyTorch/Torch/NumPy; SHA256 `ccfdca0e741dc77795f5af61871af5d62e73feebf55c7ffb28cd16e55fe207e9`.

- `e02_repository/policy-engine/src/polisyos/foundry/methods/catalog/causal/ncm_engine.py`: 1097–1134; SHA256 `6db900ee270a88ef20f9b5c000eb5b612417ce96be2781aab109ea279eb2a948`.

- `e02_repository/policy-engine/src/polisyos/runtime/quality/joint_simulation_horizon.py`: 2880–2910; SHA256 `333deedcd2d85bf4a75f58d698a0d487a8a163256609d0825f2063fb087a2454`.

- `e02_repository/policy-engine/tests/unit/foundry/methods/catalog/causal/test_ncm_engine.py`: 524–560; SHA256 `c82c3b48447157d6f635cdf167a1e92ba9bd81e91942dfcc21b06d5f92e2a902`.


## Центральная сборка после root application

Содержательный readback выполнен против author staging `policy_search/proposed_v2`, а не против прежнего central состояния. После сообщения root независимо проверено точное byte-for-byte равенство всех12 central файлов под `proposed_v2/PolicyOS_E02_Executor_Specifications_v2` рассмотренным staging bytes. Хеши также совпадают с `cross_lane/policy_staging_application.json`. Статус **PASS_EXACT_BYTE_EQUALITY**; это не приёмка shared03 или всего архива. Полные пары paths/hashes и ledger hash сохранены в JSON.


## Document validation

PASS: все12 manifest hashes согласованы; original REQ/TEST IDs и obligation/residual/preservation maps сохранены; решения и tests MD↔JSON зеркальны; все22 tests NOT_RUN. Три добавленных DEC: DEC-FUN-03-03, DEC-SIM-03-02, DEC-OPT-03-02. Общий shared03/aggregate04 merge проверяется coordinator отдельно.
