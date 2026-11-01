# HYG-04 — Canonical bootstrap/benchmarks и один CP6 build window

**LANE-12 · LA-011, LA-012, LA-013 · SHA `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

**Статус:** исполнительская спецификация на последующую работу; требования и будущие тесты здесь не исполнены.

## 1. Практическая цель и тип работы

Сохранить ранний JAX setup, рабочие benchmark commands и настоящие apps при retirement точных старых адресов.

**Тип:** C126-G01 lifecycle; G02 supported bootstrap qualification; G03 docs/build qualification.

Основания: [полный отчёт](../05_Основания/Аудит/02_Пакеты/HYG-04.md), [исходные карточки](../05_Основания/Аудит/05_Источники/HYG-04_исходные_строки.txt), [трассировка](../04_Трассировка/HYG-04.json).

## 2. Уже работает — сохранить

- Common early JAX defaults/setdefault и explicit overrides.
- Canonical bootstrap4profiles и root benchmark suite IDs/CLI.
- Independent research tools, LK16 shell/dashboard/client и LK23 styleguide не удаляются.

## 3. Полная disposition исходных обязанностей и остатков

| ID | Действие | Требования | Почему |
|---|---|---|
| LA-011 | qualify | REQ-HYG-04-02, REQ-HYG-04-03, REQ-HYG-04-04 | Wrappers removed; early timing/public native/external setup validate. |
| LA-012 | lifecycle | REQ-HYG-04-01, REQ-HYG-04-04 | Three wrappers still forwarding, exact migration needed. |
| LA-013 | qualify | REQ-HYG-04-03, REQ-HYG-04-04 | Redirect absent; actual docs/build links qualify. |
| C126-G01 | lifecycle | REQ-HYG-04-01 | Actual census existing owners, no blanket directory deletion. |
| C126-G02 | qualify | REQ-HYG-04-02, REQ-HYG-04-03, REQ-HYG-04-04 | Recording no installs; late demo retired import is explicit follow-through risk. |
| C126-G03 | qualify | REQ-HYG-04-03, REQ-HYG-04-04 | Full links/build and protected apps, not new frontend. |

## 4. Нормативные требования результата

**REQ-HYG-04-01.** Три benchmark aliases должны получить finite caller/config/job/package migration и отдельный retirement/temporary support outcome, сохраняя canonical algorithms и CLI contract.

**REQ-HYG-04-02.** Canonical bootstrap и JAX preparation должны сохранять profile commands и применять defaults до numerical imports, не перезаписывая explicit environment.

**REQ-HYG-04-03.** Удалённые install.sh/jax_bootstrap/frontend redirect должны оставаться retired при проверенной навигации/lifecycle obligations; дата сама по себе не evidence миграции всех пользователей.

**REQ-HYG-04-04.** Shared CP6 build/distribution qualification должна сохранять actual apps/packages/research tools и declared roles; early import guard не выдаётся за full demo/production UI proof.

## 5. Конкретное техническое решение — рекомендуемый способ

- Finite census точных3benchmark addresses, migrate actual jobs/imports to root benchmarks and remove only after supported exit. Existing advanced census mechanism preferred lexical-only scan. Preserve independent jax/lex/data tools.
- Common jax_env now package, not old jax_env.py. Keep apply_jax_env_defaults before actual heavy imports. Bootstrap tests record CommandSpec/run_command, не запускать real system bootstrap. Late demo reference inspect/reproduce in supported selected smoke; do not reconstruct removed domain.state to satisfy stale path blindly.
- Root CP6 orchestration reuses existing workspace build/docs/Q2 results for all four lane packets. Build artifact evidence passes CYC-05 bridge owner; no separate readiness issuer here.

**Существующие code/test owners:**
- [`src/polisyos/common/jax_env/__init__.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/jax_env/__init__.py).
- [`tools/devx/workspace/bootstrap.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/devx/workspace/bootstrap.py).
- [`tools/research/benchmarks/metrics.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/research/benchmarks/metrics.py).
- [`tools/research/benchmarks/harness.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/research/benchmarks/harness.py).
- [`tools/research/benchmarks/suite_registry.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/research/benchmarks/suite_registry.py).
- [`tools/quality/validation/check_docs_lifecycle.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/quality/validation/check_docs_lifecycle.py).
- [`tests/unit/common/jax_env/test__policy.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/common/jax_env/test__policy.py).
- [`tests/unit/remediation/test_hyg_04.py`](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_hyg_04.py).

## 6. Локальные проверки — все NOT_RUN

### TEST-HYG-04-01 → REQ-HYG-04-01

**Уровень:** wrapper/canonical CLI. **Ожидается:** positive + negative + boundary.

**Setup:** metrics/harness/suite_registry actual imports, canonical and legacy CLI good/bad arguments; jobs/config census.

**Действие:** Compare object identity/stdout/stderr/exit before migration, run canonical after chosen retirement.

**Oracle:** Identity exact, suite IDs and exit semantics stable. All found jobs updated; unresolved external surface explicitly retained narrow; no inherited DEFAULT_SHIM_SUNSET invented.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-04-02 → REQ-HYG-04-02

**Уровень:** native bootstrap recording + early subprocess. **Ожидается:** positive + negative + boundary.

**Setup:** Supported3.14; four actual profiles; invalid profile; Darwin/Linux with explicit JAX overrides and Metal opt-in.

**Действие:** Replace only run_command with recorder; guard immediately before JAX/Equinox/Foundry import in actual entrypoints.

**Oracle:** Exact frozen sync/profile commands, invalid exit2; no installation executed. Defaults established before import, overrides untouched. Early guard does not attest subsequent workload.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-04-03 → REQ-HYG-04-03, REQ-HYG-04-04

**Уровень:** docs/lifecycle/workspace. **Ожидается:** positive + negative + boundary.

**Setup:** Actual links and notices, removed paths, protected apps/packages.

**Действие:** Existing full docs lifecycle/link commands and shared package inventory; negative120day no-ADR fixture.

**Oracle:** No dangling active navigation to retired path; justified external redirect if needed. Lifetime/date policy tested as implemented, not assumed today>sunset. Protected shell/dashboard/styleguide present.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

### TEST-HYG-04-04 → REQ-HYG-04-04

**Уровень:** E02-I12-A CP6 capability smoke. **Ожидается:** positive + negative + boundary.

**Setup:** Existing actual Q2/package build, selected benchmark/demo consumers; run_mechanism_design late foundry.domain.state reference explicitly inspected.

**Действие:** One shared build and bounded supported canonical benchmark smoke; diagnose actual demo path before claiming complete.

**Oracle:** Artifacts/imports/command exit valid within declared profile; reachable retired import fixed via actual current owner or explicit demo unsupported decision, not hidden behind early-order PASS. Shell diagnostics call generated client; formatter not authority issuer.

**Seams:** Реальные owner/DTO/численная функция и принимаемый consumer; только фиксированные входы, isolated tmp store и управляемое время.

## 7. Совместная приёмка, зависимости и владение

Общие сценарии: **E02-I12-A** из [канонического lane integration-контракта](../03_Интеграция/LANE-12.md). Они переиспользуются; отдельный тяжёлый harness этого пакета не создавать.

Исходные предшественники: нет. Доказанный существующий контракт может удовлетворить зависимость; lane не глобальный барьер.

LANE-12 производит actual build/distribution/census evidence с artifact binding. CYC-05 владеет positive build/deployment→N6 readiness bridge в existing confidence_ledger и runtime currentness; здесь не создавать второй issuer/registry. CP6 — одно общее окно Q2/package qualification, не build на каждый alias. CLI-01 owns generated client family; reuse its Node22 results, no parallel install/build.

## 8. Совместимость и восстановление

Retired wrappers не восстановить ради obsolete selector. External setup/URL obligations receive explicit decision; no automatic sunset. Canonical suite output remains stable; actual apps retain separate roles.

## 9. Free-grow и design decisions

- [North Star §2](../05_Основания/Архитектура/policy-design-causal-operating-system-north-star.md#2-everything-reduces-to-data--but-the-causal-structure-is-not-data) и [синтез §4](../05_Основания/Исследование/design_direction.md): общий действующий owner сохраняется, удаление исторического адреса не заменяет способность; новые compatible resources подключаются через существующий механизм.

## 10. Решения, которые нельзя подменить догадкой

- DEC-HYG-04-01: benchmark3aliases finite migration/exit table; DEC-HYG-04-02: exact external setup/URL obligations and late-demo consumer scope. Each has source evidence, selected action, acceptance; not all delayed by one unknown external caller.

## 11. Что предъявить и что не является готовностью

Native recording/import-order, full links and actual build separately. No installer execution for test. Metadata suite listing не scientific benchmark validation.

**Команды:** из `policy-engine/` использовать существующее поддержанное Python 3.14 окружение и точные существующие test paths выше. Шаблон: `<existing-python> -m pytest <selected-existing-path> <new-selector-after-authoring>`; это не выполненная команда и не утверждение, что будущий selector уже существует. Native job — один по общему ресурсу. Никаких install/full-suite по умолчанию.

## 12. Lossless inventory bindings

- `remaining:0375` → REQ-HYG-04-01; Actual census existing owners, no blanket directory deletion.
- `remaining:0376` → REQ-HYG-04-02, REQ-HYG-04-03, REQ-HYG-04-04; Recording no installs; late demo retired import is explicit follow-through risk.
- `remaining:0377` → REQ-HYG-04-03, REQ-HYG-04-04; Full links/build and protected apps, not new frontend.
- `preserve:0607` → REQ-HYG-04-02; Common early JAX defaults/overrides — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0608` → REQ-HYG-04-02; Canonical bootstrap profiles — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0609` → REQ-HYG-04-01; Root benchmark owners/suite IDs — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0610` → REQ-HYG-04-01, REQ-HYG-04-04; Independent research tools — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0611` → REQ-HYG-04-03, REQ-HYG-04-04; Runtime shell/dashboard/client — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
- `preserve:0612` → REQ-HYG-04-03, REQ-HYG-04-04; CLI styleguide — конкретный contract/oracle в указанных REQ/TEST; исходное поведение не снимается.
