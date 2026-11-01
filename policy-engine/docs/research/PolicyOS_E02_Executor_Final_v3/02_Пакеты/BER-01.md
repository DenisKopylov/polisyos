# BER-01 — Один persisted wire intake и честная alias-only display policy

**LANE-11 · LA-034, LA-036 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить объяснения и исторические method names без принятия construction-only payload как persisted record.

**Тип:** C120-R01 narrow intake fix; C120-G01 native qualification; C120-G02 bounded policy decision.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/BER-01.md), [исходные карточки](../05_Основания/Аудит/05_Источники/BER-01_исходные_строки.txt), [трассировка](../04_Трассировка/BER-01.json).

## 2. Уже работает — сохранить

- LK13: рабочие BERL kernels/benchmarks и раскрытый empirical fallback сохраняются.
- Generated strict nested schema, construction defaults отдельно от persisted required/version/strict JSON.
- Requested/effective identities, request-local typed cache, conditional refusal и claim confidence budget.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-034 | fix | REQ-BER-01-01, REQ-BER-01-02, REQ-BER-01-05 | Profile generated repaired; persisted helper permissive ещё. |
| LA-036 | lifecycle | REQ-BER-01-03, REQ-BER-01-04, REQ-BER-01-05 | Identity repaired; native tree-first и alias-only display decision открыты. |
| C120-R01 | fix | REQ-BER-01-01 | model_validate construction не persisted strict JSON. |
| C120-G01 | qualify | REQ-BER-01-02, REQ-BER-01-03, REQ-BER-01-05 | Supported3.14 native, actual selected store/readers; unsupported3.12 failure не product fix. |
| C120-G02 | lifecycle | REQ-BER-01-04 | Conservative display boundary требует решения existing policy owner, не fake disagreement. |

## 4. Нормативные требования результата

**REQ-BER-01-01.** Public persisted validator должен применять тот же known-version/required-fields/strict JSON intake до semantic eligibility, что selected loader; construction convenience остаётся отдельным API.

**REQ-BER-01-02.** Generated persisted schema должна совпадать по полному content и deterministic bytes с canonical DTO profile; semantic reliability не выводится из schema pass.

**REQ-BER-01-03.** Compatible aliases одного effective request должны вычисляться один раз, сохраняя requested IDs/fallback и exact cache identity; unsupported conditional law не возникает из label.

**REQ-BER-01-04.** Alias-only display policy должна явно отличать отсутствие independent disagreement от missing required evidence, не выдумывая comparison и не меняя confidence budget из dedup.

**REQ-BER-01-05.** Native selected persistence/Phase5/display и historical readers должны сохранять wire refusal и requested/effective meaning, включая tree-first fallback.

## 5. Конкретное техническое решение — рекомендуемый способ

- Выделить существующую strict payload parsing последовательность из persistence.load_explanation_bundle в neutral BERL contracts wire helper: required list из generated schema, exact version, model_validate_json(strict=True) с JSON-native datetime. Public validation_rules и selected loader вызывают его; loader сохраняет manifest/ref checks. Избежать contracts→persistence→service cycle; не создавать третью schema.
- Public helper returns typed refused validation при wire parse failure; отдельный construction parser остаётся permissive там, где поддержан. Phase5 wrapper должен видеть refusal, а не silently repaired defaults.
- G02 finite call-site policy census: existing owner решает, является ли disagreement обязанностью distinct effective estimators или всех requested claims. Рекомендуется explicit N/A alias-only diagnostic при неизменных confidence claims; если policy intentionally требует evidence, оставить limited. Выбор documented, не поменять bound law автоматически.

**Существующие code/test owners:**
- [`src/polisyos/berl/contracts/validation_rules.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/contracts/validation_rules.py).
- [`src/polisyos/berl/contracts/schema.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/contracts/schema.py).
- [`src/polisyos/berl/persistence.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/persistence.py).
- [`src/polisyos/berl/service/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/service/__init__.py).
- [`src/polisyos/berl/service/cache_identity.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/berl/service/cache_identity.py).
- [`src/polisyos/scientist/validation/phase5_preflight.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/validation/phase5_preflight.py).
- [`tests/unit/remediation/test_ber_01.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_ber_01.py).
- [`tests/unit/berl/test_persisted_wire_profile.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/berl/test_persisted_wire_profile.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-BER-01-01 → REQ-BER-01-01, REQ-BER-01-02

**Уровень:** wire corpus + public helper. **Ожидается:** positive + negative + boundary.

**Setup:** Full1.0.0; empty nested; extra;9.9.9; omitted version/defaults; numeric string raw_score="8.0".

**Действие:** Generated schema, construction parser, persisted helper и strict wire reader; writer twice.

**Oracle:** Persisted APIs одинаково reject unknown/omitted/coercion; valid passes structural intake, then independent semantics. Construction defaults supported unchanged. Generated full content equal, bytes deterministic.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-BER-01-02 → REQ-BER-01-01, REQ-BER-01-02, REQ-BER-01-05

**Уровень:** E02-I11-A selected storage/Phase5. **Ожидается:** positive + negative + boundary.

**Setup:** Actual tmp CAS manifest/profile и valid persisted bundle; mismatched version/profile/raw bytes.

**Действие:** Persist→fresh loader→public helper/Phase5/display; legacy accepted records.

**Oracle:** Invalid wire не passed/analyst_display; selected admission remains strict; historical records read under explicit profile без rewrite. Inline candidate не становится selected authority.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-BER-01-03 → REQ-BER-01-03, REQ-BER-01-05

**Уровень:** native actual orchestrator. **Ожидается:** positive + negative + boundary.

**Setup:** 2-feature actual model/background; kernel/marginal/tree aliases в kernel-first и tree-first order; changed input/model/background/typed params; custom adapter.

**Действие:** Count real model calls and compare effective identities on supported3.14.

**Oracle:** Aliases same effective request one raw calculation; changed identity recomputes. Requested names/fallback preserved; conditional refused before calculation. Guards11features/empty background retained; no fabricated TreeSHAP exactness.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-BER-01-04 → REQ-BER-01-04, REQ-BER-01-05

**Уровень:** policy truth table. **Ожидается:** positive + negative + boundary.

**Setup:** One estimator under2aliases versus2 distinct estimators; bounds below/above existing threshold; requested claims same.

**Действие:** Run existing display/reliability owner before/after selected DEC policy.

**Oracle:** Alias-only outcome explicit not_applicable_disagreement or existing conservative limited with rationale; never invented independent agreement. Existing Bonferroni/claim budget unchanged; distinct estimators still require actual disagreement where policy says so.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I11-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-11.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

BERL contracts owns shared wire parser; runtime quality и Phase5 только consumers. Не переносить kernels в другой subsystem.

## 8. Совместимость и восстановление

Historical requested IDs/bytes immutable. New persisted-helper strictness intentional; construction API не ужесточать. Сохранённые known-version readers до конца migration; no backend rewrite ради Python3.12.

## 9. Free-grow и design decisions

- [Stage-0 §4.3](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md#43-k06--fail-closed-binds-the-protected-action-not-the-computation) и [синтез §4](../05_Основания/Исследование/design_direction.md): защищённый claim ограничивается своим основанием; useful diagnostic computation не блокируется целиком.

## 10. Решения, которые нельзя подменить догадкой

- DEC-BER-01-01: existing display/confidence owner выбирает alias-only N/A либо conservative limited policy; выход truth table с неизменным claim budget и distinction effective estimator count. Не создавать synthetic disagreement.

## 11. Что предъявить и что не является готовностью

R01 before/after through actual helper/Phase5; native tree-first/selected persistence separately. Schema validity не infidelity eligibility и linear fixture не scientific explanation quality.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0433` → REQ-BER-01-01; model_validate construction не persisted strict JSON.
- `remaining:0434` → REQ-BER-01-02, REQ-BER-01-03, REQ-BER-01-05; Supported3.14 native, actual selected store/readers; unsupported3.12 failure не product fix.
- `remaining:0435` → REQ-BER-01-04; Conservative display boundary требует решения existing policy owner, не fake disagreement.
- `preserve:0692` → REQ-BER-01-02; Generated strict nested schema — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0693` → REQ-BER-01-01, REQ-BER-01-02; Construction defaults distinct from persisted wire — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0694` → REQ-BER-01-03, REQ-BER-01-05; Historical requested IDs and explicit fallback — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0695` → REQ-BER-01-03; Conditional-law refusal — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0696` → REQ-BER-01-03; Request-local typed cache — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0697` → REQ-BER-01-04; Claim confidence budget — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0698` → REQ-BER-01-01, REQ-BER-01-05; Selected CAS strict reader — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
