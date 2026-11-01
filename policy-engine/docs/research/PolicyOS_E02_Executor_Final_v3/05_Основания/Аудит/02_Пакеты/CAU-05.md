# CAU-05 — dedicated DiD и граница исторического replay
## C56 · 1 ноября 2026 года

**Порядок:** 56/127, LANE-05. **Исходный ID:** LA-016, этап2/2, accountable closure. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; свежий проход после внешнего сохранения C55.

## Решение

Metadata больше не принадлежит deprecated umbrella: independent constants и отдельные MethodMetadata используются dedicated methods и общими numerical helpers. Default built-in list, public exports, maintained synthetic request и просмотренные benchmark callers ориентированы на `did.standard` / `did.staggered`. Старый direct-import adapter остаётся полезным: он явно переводит slots и boolean mode, не выбирая estimator по truthiness.

**8 bounded MATCH, 8 unchanged test bodies /9 cases PASS изолированно. Нового R не подтверждено.** Full corrected reports и warnings совпадают для проверенных old/dedicated standard/staggered requests. Но **direct-import compatibility не доказывает чтение frozen plans по сохранённому FQN/version**. Default registry намеренно не предлагает старый FQN, exact lookup не имеет alias fallback, existing native tests ожидают отказ. Нужны declared historical scope и native replay evidence; LA-016 целиком не закрыта.

## 1. Матрица исходного ID

| ID/фаза | Что требовалось | Что подтверждено | Остаток |
|---|---|---|---|
| LA-016 M, accountable CAU-05 | Metadata-detachment, dedicated planning, однозначные old slots/mode, finite caller scan и supported frozen replay | Общие definitions независимы; dedicated default inventory/request/callers; direct adapter эквивалентен по whole report/warnings; ambiguity refused; finite tracked-Python census | G01 native chain; G02 versioned frozen plans; G03 numerical/scientific остатки CAU-01/02 |

Полная карточка 6783–6871 прочитана. CAU-01/C52 уже частично оценил LA-016; новый этап сохраняет прежнюю assessment и **не увеличивает unique-ID count**. Удалять did.py/helpers или useful partial adapter оснований нет.

## 2. Metadata и numerical owner действительно отвязаны

Citations/equations/assumptions находятся в `_DID_*` constants. Dedicated metadata получает собственные mappings; shared algorithms не читают `DifferenceInDifferences.metadata`. **P02** исполняет исходный poison-metadata test. **P05** дополнительно удаляет legacy class binding из actual extracted module globals: оба dedicated numerical paths всё равно работают. [S01:44–57](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L44-L57) [S01:1124–1279](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L1124-L1279)

Это содержательная независимость, не просто новый class name. MethodMetadata dataclass исполнен из реального AST. Registration decorator, runtime wrappers и signature ABI не исполнялись; их source прочитан отдельно. Наличие `@foundry_method` у legacy class само по себе не значит default registry admission: decorator обновляет/проверяет class contract и возвращает class, а built-in family берёт явно возвращаемые owners. [S20:1047–1228](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/base.py#L1047-L1228)

## 3. Old slots/mode: сохранять equivalent move отдельно от статистики

Legacy materializer переводит `outcome_panel→outcome`, `treatment_indicator→treatment`; конфликт двух identities отказывает. `staggered` принимает только bool/np.bool_, затем вызывает actual dedicated pure_step. Unknown DTO field не превращается в другой режим. [S01:106–153](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L106-L153) [S01:1074–1120](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py#L1074-L1120)

**P01/P03/P04:** четыре исходных CAU-05 tests пройдены. Дополнительно standard cluster request на80% и staggered not-yet-treated request на95%,399 draws при одном seed сравниваются по **всему report**, method_params, diagnostics и warnings, не только point. Actual JSON roundtrip сохраняет объект. Шесть ambiguous flags, оба alias conflicts и unknown input field отвергнуты. Useful report/result и envelope/uncertainty_envelope aliases остаются.

Это equivalence текущих corrected requests, не воспроизведение исторического flawed estimator и не повторная общая аттестация CI. C52-R01 с NaN cluster identity и C52/C53 native/coverage ограничения остаются открытыми.

## 4. Dedicated planning: фактические producers и consumers

`register_causal_methods` явно возвращает Standard/Staggered, не umbrella. Canonical extension loader вызывает эту family factory, оборачивает методы в components и использует существующий registry bridge. Catalog/public facade expose dedicated classes; retired class доступен в узком did module для direct import. [S05:266–299](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/catalog/causal/_registry_boot.py#L266-L299) [S06:33–68](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/extensions/_builtin_loader.py#L33-L68) [S07:194–218](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/extensions/registry.py#L194-L218)

**P06** исполняет actual maintained `_default_g2_runtime_method_candidate`: FQN=`causal.inference.did.standard@1.0.0`, specification=`standard_2x2_did`. Producer сам помечает request `synthetic_fixture`; его canned refs/pass labels не empirical authority. Source-derived standard signature не содержит staggered flag. [S09:5746–5804](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py#L5746-L5804)

**P08:** два standard benchmark runner bodies и один staggered body исполнены при poisoned legacy pure_step. Они доходят до dedicated numerical owners; standard known ATT≈3. CLI bootstrap и native benchmark imports не исполнялись. [S10:131–140](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/benchmarks/interference/policy_did_interference.py#L131-L140) [S11:103–117](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/benchmarks/natural_experiments/policy_natural_experiments.py#L103-L117)

Scientist selected consumer отдельно обрабатывает dedicated FQNs и повторно проверяет target/diagnostics. Этот outer route прочитан, numerical consumer controls уже ограниченно проверялись в C53; C56 не выдаёт его за новый native job. [S23:539–558](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py#L539-L558)

## 5. Finite census и граница frozen replay

Свежий [literal census](../04_Проверки/C56_CAU05/python_literal_census.json) прочитал **8231/8231 Git-tracked .py**, сверил каждый blob и SHA256, без read failures. По четырём named patterns — 101 line hit в40 files. В `src` exact old class встречается только как declaration и did-module export; old full FQN/исторический short FQN не найдены. Maintained dedicated FQN найден в synthetic request и Scientist consumers. Другие hits в tests/history сохранены, не скрыты.

Это complete **названный literal-Python denominator**, не все deployment clients или saved plans. Computed FQN, non-Python serialized artifacts и внешние caller repositories не покрыты; короткий semantic method_ref не автоматически executable registry identity.

**P07** исполняет exact `MethodRegistry.get` FQN branch с explicit two-entry fixture: dedicated разрешается; старый full/short FQN отказывает, alias migration там нет. Fixture не объявлен real booted registry. Source native tests прямо требуют old-name refusal и выполняют direct adapter отдельно через class, а не через frozen-plan reader. [S08:685–733](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/foundry/methods/selection/registry.py#L685-L733) [S13:108–152](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/foundry/methods/catalog/causal/test_did_diagnostics_ownership.py#L108-L152) [S14:37–94](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/runtime/quality/test_did_request_route.py#L37-L94)

**C56-G02:** original plan требует supported historical replay. Сохранённый class adapter полезен, но пока не предъявлены finite supported plan/schema versions и actual versioned reader, нельзя заявить это условие исполненным. Следует проверить существующий replay/migration owner на сохранённых fixtures либо честно определить более узкий retirement contract. **Не требуется** возвращать generic method в новое planning или поддерживать любые неопределённые старые планы. Доказанного production outage здесь нет.

## 6. Остаток и сохранение

- **Сохранить:** dedicated cutover, detached metadata, shared numerical helpers, strict bool/alias handling, direct compatibility, output aliases и declared non-gating result.
- **C56-G01:** actual built-in component bootstrap, registry/dispatcher, native slots/output contract, CAS/fresh reader и supported runtime. Existing tests есть и прочитаны; pytest отсутствует, native import блокируется Python3.14 syntax under3.12, no installs.
- **C56-G02:** declared versioned frozen-plan compatibility и его actual test. Direct callable equivalence — не whole persisted replay.
- **C56-G03:** interface consolidation не устраняет C52/C53 numerical/inferential limits и не даёт causal authority. Не переизобретать deterministic model inventor вместо LLM semantic proposer и независимой проверки assumptions.

Восемь unchanged bodies/девять cases состоят из adapter4/4 и metadata/diagnostics4/5. Нативные retirement/Statsmodels/CAS tests не заменены mock store и не названы PASS. Финальный bounded probe/census exit0, checkout clean; исходники не менялись.

[Диагностика](../04_Проверки/C56_CAU05/bounded_diagnostics.json) · [Команды](../04_Проверки/C56_CAU05/commands.json) · [Границы](../04_Проверки/C56_CAU05/native_verification.json) · [Источники](../05_Источники/C56_источники.json) · [Остатки](../01_Реестры/C56_остатки.json).

**56/127 пакетов рассмотрены ограниченно; 132 уникальных B/LA частично оценены. Следующий — SCM-01. Полного закрытия нет.**
