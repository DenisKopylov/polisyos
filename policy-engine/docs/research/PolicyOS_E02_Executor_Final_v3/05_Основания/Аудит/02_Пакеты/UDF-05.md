# UDF-05 — единый demographic snapshot и границы его использования

## 1. Решение

**Ограниченно оценён, не закрыт.** Исходный per-file old/new fallback устранён: сначала выбирается один целый layout либо explicit inventory request, затем читаются его members. Поддержка старых данных, optional donor, public read API, typed arrays и pure static aging сохранена.

Свежий результат: **5 MATCH; 31 неизменённое тело существующих тестов / 77 cases PASS** в изолированном запуске. Найдены два отдельных bounded residual: **C88-R01** — конфликтующие поля priors заменяют target-owned values при aggregate merge; **C88-R02** — fractional donor indices молча усекаются. Ни один из них не доказывает production-смешение или ошибку фактической демографической оценки.

Whole historical readers и pure consumer исполнены. Candidate проверки ограничены post-resolution fixtures; native producer/CAS/Foundry chain **UNRUN**. Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.

[Исходная карточка](../05_Источники/UDF-05_исходные_строки.txt) · [Pinned sources](../05_Источники/C88_источники.json).

## 2. Матрица исходного ID

| ID | Подтверждённая часть | Остаток |
|---|---|---|
| LA-032 | Whole old/new selection; ambiguous/mixed refusal; explicit former snapshot; scalar compatibility; optional donor; captured historical bytes; read API и pure aging | R01 role-owned fields, R02 discrete indices; G01 native receipt/blob qualification; G02 пригодность конкретных source facts |

LK12 сохранён: verified read API не заменён прямым open для inventory route; historical filesystem adapter отдельно и явно ограничен. LK20 сохранён: generation identity не означает completeness, authority или разрешение reuse. Одинаковая shape не считается общим происхождением.

## 3. Реальная цепь owner → source → consumer

`demography/__init__.py` выбирает full new/legacy layout до composition. Два complete layouts требуют explicit selection; partial/mixed layout и present invalid member отказываются. Optional donor берётся только из выбранного снимка. Scalar reader сохраняет изолированный single-member compatibility только там, где не объявлен complete selected layout (`S01`).

Historical resolver захватывает bytes всех выбранных members, формирует identity и передаёт `legacy_limited` с `not_established` provenance. Изменение файлов после resolver не меняет его captured snapshot. Legacy omission `entrant_state_totals` получает только нулевую shape-проекцию с явным not-measured статусом; malformed present field отказывает. Candidate omission не превращается в нулевое наблюдение (`S01`, `S02`, `S08`).

Existing opt-in builder читает explicit producer request, вызывает candidate inventory producer и возвращает selected upstream ArtifactRecord inputs. Resolver проверяет inventory-stage identity, source receipt/manifest, exact input membership, повторно читает selected content, сравнивает basis и отдельные declared cross-member равенства. Candidate wrapper использует verified-stage read API; D5 receipt не переименован в универсальный demographic certificate (`S02`, `S03`, `S06`). Эта цепь прослежена по коду, но не полностью исполнена.

Role projections отделяют payload от typed evidence, копируют вложенные структуры и отвергают nonfinite JSON values. Candidate остаётся `candidate_only`, source claims — `consumer_asserted` или `not_established`. Actual pure aging переносит arrays и evidence в state; scientific authority из этого не возникает. Contract v2 требует evidence, Mapping projection намеренно не mutable dict (`S02`, `S04`, `S10`).

## 4. Свежие проверки

1. **P01 — 77 cases PASS.** 21 UDF-05 body, 5 artifact bodies и 5 выбранных pure inventory bodies. Проверены чистые old/new, mixed targets/priors, ambiguity, explicit old, removal без смены snapshot, corrupt selected JSON, shapes, optional donor, scalar controls, directories, dangling и readable symlinks, readonly projections, finite JSON, captured bytes и legacy omitted entrants. Это actual historical filesystem execution, но не native pytest/CAS.
2. **P02 — evidence/basis.** Actual generation primitive различает current, changed content и malformed digest; duplicate member names отказали. Caller задаёт denominator. Historical donor absence остаётся unknown, а declared facts не приобретают independent provenance. Content binding и scientific validity не смешаны.
3. **P03 / R01 — role overwrite.** В одном coherent new layout targets содержат `[100,250]` и исходные state IDs. Priors дополнены конфликтующими `target_state_totals=[900,800]` и другими `state_ids`. Scalar target reader возвращает исходные values, aggregate и actual pure aging — подменённые. Причина: `{**targets, **priors}`, затем donor update (`S01:298–315`). Отдельный candidate post-resolution control проходит actual declared state-order check, но subsequent composition меняет axis. Это **не** исполненный обход native CAS admission.
4. **P04 / R02 — fractional indices.** Public historical reader сохраняет donor_state_index `[0.9,1.9]` и `[-0.9,1]`; pure consumer получает `[0,1]`. Record indices `[1001.9,1002.9]` становятся `[1001,1002]`. Validator сначала приводит к int64 для проверки и не отвергает дробную исходную identity (`S01:251–270`); consumer повторяет cast (`S04:36–39`). Integer out-of-range `[0,2]` отказал. Full Foundry impact не измерялся.
5. **P05 — ограниченные candidate controls.** На явно constructed ResolvedDemographySource full bundle отказывает при unknown absent donor; limited target/prior projection сохраняет unknown. Missing candidate entrant не получает legacy zeros, утраченный resolved member не переключается на filesystem. Это post-resolution checks, а не native lost/corrupt CAS blob qualification.

`MATCH` у P03/P04 означает успешное воспроизведение остатка, не product PASS. Синтетические числа используются только как различающий witness.

## 5. Сохранить и доработать

**Сохранить:** единый selection, explicit old snapshot, полезные historical arrays/readers, optional donor, captured bytes, narrow layout errors, immutable projections, typed evidence, candidate-only distinction, verified read API и generation primitives. Не требовать rebuild пригодных данных и не расширять D5 authority по названию receipt.

**C88-R01, medium/high confidence.** У существующего aggregate owner нужно согласовать владение полями roles: конфликтующие чужие поля должны явно отвергаться либо не участвовать в projection. Нужна проверка scalar/aggregate/consumer consistency на one-layout conflict и native candidate route. Это небольшая доработка существующей composition, не новая data-platform. Правомерная явная композиция источников и metadata compatibility должны остаться возможными.

**C88-R02, medium/high confidence.** Дискретные donor indices должны проверяться до cast: fractional, negative fractional и непредставимые integer values не должны молча менять identity. Сохранить допустимые integer arrays и shape/range checks. Пока доказана только reader→pure consumer boundary; не заявлено искажение production population.

**C88-G01 — native chain.** Поддержанная Python/dependency среда, реальный inventory builder, profile-aware CAS, prior receipt, version conflict, lost/corrupt blob, exact record metadata и full consumer требуют отдельного существующего native corpus и одного сквозного исполнения. Native import здесь блокируется Python3.14 syntax в Core store на Python3.12; pytest отсутствует. Это limitation среды, не самостоятельный product defect.

**C88-G02 — конкретная научная пригодность.** Source-owner identity, полнота state/measure mapping, currentness и допустимость reuse должны оцениваться для конкретного применения. Их отсутствие не делает candidate inventory ложным сертификатом: он прямо ограничивает authority. Отсутствие универсального детерминированного model inventor само по себе не баг; synthetic fixtures не эмпирические наблюдения.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C88_UDF05/commands.json) · [Diagnostics](../04_Проверки/C88_UDF05/bounded_diagnostics.json) · [Native status](../04_Проверки/C88_UDF05/native_verification.json) · [Fixture limits](../04_Проверки/C88_UDF05/fixture_authority_limits.json) · [Архивное представление negative fixtures](../04_Проверки/C88_UDF05/archival_fixture_transformations.json) · [Остатки](../01_Реестры/C88_остатки.json).

Run01 exit0: 5 MATCH, 77 bounded cases PASS. Actual NumPy/Pydantic и whole reader modules; Core initializer shell, forbidden CAS и pytest compatibility helper обозначены. Native integration и scientific validity не установлены. 12 fixture symlinks и 4 malformed JSON проверены до безопасного archival преобразования; их исходные значения/bytes/hashes сохранены. Это не новая успешная проверка после преобразования.

Checkout чист; source/tests/config/dependencies не изменялись, installs, servers, external data и production paths не использовались.

**88/127 рассмотрены ограниченно. LANE-07 пройден по порядку; следующий — FED-01. Фаза 2 не начата.**
