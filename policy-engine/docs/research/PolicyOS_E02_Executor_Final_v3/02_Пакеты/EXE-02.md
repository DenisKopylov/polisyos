# EXE-02 — Готовность зависимостей вместо лишнего tier-ожидания

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: B77. Тип: container-aware admission fix + test maintenance/qualification.

C(A) получает committed A до независимого B только когда независимость действительно доказана; alias spelling list index не снимает tier boundary.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/EXE-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C64_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/EXE-02_исходные_строки.txt), исходный объединённый план §EXE-02 (исторические строки 7597–7665).

## 2. Уже работает — сохранить

- Narrow readiness admission и fallback для checkpoint/provenance/compensation/conditions/fail_fast/unknown effects.
- Merge commit перед successor release; separate immutable launch baseline и declared delta.
- Stable report invocation order, explicit dependency join, exact seeds/counts.
- Не новый scheduler; S направления не включаются.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C64-R01 | fix: Container-aware identity либо conservative refusal неоднозначных list paths. | REQ-EXE-02-01 |
| C64-G01 | qualify: Native runner/state/custody и completeness declarations, не только tiny schedule. | REQ-EXE-02-02, REQ-EXE-02-03 |
| C64-G02 | fix: Исправить test persistence fixture ABI, не product ownership contract. | REQ-EXE-02-03 |

### Исходные обязанности, не только новые R

- B77 → REQ-EXE-02-01…-03: уже реализованное раннее scheduling сохранить; исправить admission alias, квалифицировать lifecycle и measured first useful result без обещания speedup17→10.

## 4. Нормативный контракт

### REQ-EXE-02-01
Для unordered nodes readiness разрешается только если declared target identities disjoint в текущем admitted state. List .0/.00/.+0/.-1, разрешающиеся в один элемент, считаются overlap либо неоднозначный путь отказывает readiness. Dict keys '0'/'00' сохраняют разные identities; unresolved container/type/alias не считается доказанно disjoint.

Источник: B77; аудит: C64-R01; проверки: TEST-EXE-02-01.

### REQ-EXE-02-02
A→C с независимым B начинает C после committed A до release B; добавление B→C возвращает join. Failed A блокирует C, independent B сохраняется. Semantic tier hooks сохраняют прежний маршрут; методы, inputs/seeds/repeats и порядок records не меняются.

Источник: B77; аудит: C64-G01; проверки: TEST-EXE-02-02.

### REQ-EXE-02-03
Existing remediation fixtures принимают current return_selected_profile и возвращают действительную форму selected profile. Native runner должен сохранить selected artifacts/report/finalization, rollback/cancel и fresh readback; измерение first-useful-result и стоимости launch snapshots не выдаёт synthetic schedule за workload speedup.

Источник: B77; аудит: C64-G01, C64-G02; проверки: TEST-EXE-02-03.

## 5. Техническое решение и producer → consumer

_can_use_readiness_schedule сейчас получает workflow/invocations без state и сравнивает textual paths. Передать admitted launch state в predicate (единственный внутренний caller проверить) и через общий path helper разрешить сегменты с типом container: dict сохраняет string; list нормализует int с учётом length; prefix/parent mutations и aliases контейнеров консервативно overlap. Если структура неизвестна или parent может сменить shape, оставить tier schedule. Простой безопасный первый вариант: на выявленном list пути разрешать лишь канонический неотрицательный spelling, иначе readiness=false; это не отказ всего workflow. Shared resolver согласовать со STA-01 merge/read boundaries; не обещать расширение grammar RES-01, пока consumer не установлен.

Unjournaled completion synthetic journal и tracked journal проверяются одинаковой admission границей. Обновить только tests helper signature/return tuple по актуальному API; product selected-profile keyword не удалять.

### Проверенные owners на срезе
- policy-engine/src/polisyos/scientist/orchestration/engine/async_executor.py: _can_use_readiness_schedule, _readiness_paths_overlap, _readiness_get_path, _readiness_launch_pair
- policy-engine/src/polisyos/scientist/orchestration/engine/state_merge.py: _get_path/_set_path
- policy-engine/tests/unit/remediation/test_exe_02.py: _executor persistence helpers

Глобальное int() для всех paths неверно для dict keys. Увеличение workers или новый scheduler не исправляет independence proof. Conservative fallback сохраняет полезный ordinary workflow.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-EXE-02-01
- Уровень: unit + targeted native integration.
- Setup: One-element list и unordered writers .0 vs .00,+0,-1; dict {'0':0,'00':0}; journaled/unjournaled variants.
- Действие: Run admission затем workflow с held B и A commit.
- Точный oracle: List alias не readiness-disjoint; fallback/conflict исключает две stale independent writes. Dict disjoint accepted. Canonical truly-disjoint list elements positive accepted когда parent shape stable; unknown shape fallback.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-EXE-02-02
- Уровень: unit + targeted native integration.
- Setup: Actual A,B,C DAG, events удерживают B; second variant dependency B→C; failed A and hook variants.
- Действие: Execute existing readiness/tier owners.
- Точный oracle: C sees committed A and starts before release B только first variant; join waits second; each call once/seed same/records a,b,c. Failed A blocks C, B retained; semantic hooks tier unchanged.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-EXE-02-03
- Уровень: native integration + test maintenance.
- Setup: Actual local runner/CAS; corrected fixture signatures separately; full existing remediation bodies.
- Действие: Native async tests + selected output readback/cancel; collect first-useful-result/snapshot metrics.
- Точный oracle: No unexpected keyword TypeError; actual selected-profile owner still invoked/validated. Artifacts fresh-readable, pending children awaited; measurements disclose workload no invented speedup.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_exe_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: events, small deterministic producers, fixture persistence только unit ABI проверки. Запрещено: textual marker вместо actual resolution, снятие ownership keyword, fake persistence при native claim.

## 7. Общая интеграция и порядок

Координировать общий async_executor с EXE-01/RES-02; STA-01 owns state mutation semantics, EXE-02 только readiness admission. Existing tier contract удовлетворяет safety boundary и не обязан ускоряться.

Точные общие сценарии: E02-I06-A, E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: RES-02; RES-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Неоднозначный historical path не переименовывать в другой dict key. Fallback меняет только оптимизацию, не порядок scientific repeats/inputs. Расширение list grammar — separate scoped API decision. Rollback может принудить tier path, но не вернуть unsafe alias admission.

## 9. Free-grow и design direction

- design_direction.md §2.2, §4.1, §7: общая доказанная независимость важнее case-specific scheduler.
- policy-design-execution-topology.md §3–6: artifact completion и consumer readiness связаны; unknown dependencies не стираются ради speed.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). История и текущая пригодность раздельны; физическая раскладка не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

Новых блокирующих продуктовых решений не требуется. Реальную доступность supported runtime установить до native проверки; недоступность оформлять NOT_RUN, не PASS.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

