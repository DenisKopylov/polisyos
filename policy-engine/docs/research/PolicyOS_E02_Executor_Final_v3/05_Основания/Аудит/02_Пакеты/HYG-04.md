# HYG-04 — конечная миграция bootstrap, benchmark aliases и frontend redirect

**C126 · LANE-12 · LA-011, LA-012, LA-013 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

`install.sh`, `jax_bootstrap.py` и redirect-only `frontend/README.md` уже отсутствуют. Рабочие владельцы bootstrap/JAX defaults и apps/packages сохранены. Три benchmark wrappers всё ещё существуют и действительно переэкспортируют root implementations, включая CLI аргументы и коды выхода. Это не три лишних научных алгоритма; их конечное retirement решение ещё не доказано.

**5 MATCH; 9 unchanged test bodies,30cases:24PASS6environmentFAIL. Новых подтверждённых R нет.** Сохраняются G01–G03: миграция точных aliases, supported-native/external compatibility и общая build/link/distribution квалификация. Полного закрытия нет.

## 2. Матрица исходных оснований

| ID | Original repair | Фактическая способность | Остаток |
|---|---|---|---|
| LA-011 | Мигрировать setup users; сохранить ранние defaults и overrides; решить lifecycle notices. | Старые файлы удалены, Common policy — отдельный owner. Actual bootstrap main формирует4профиля.16 bounded subprocess cases останавливаются до numerical imports и подтверждают timing/overrides. | G02: native public CLI, конкретные external obligations и последующие workloads. Удаление файла не доказательство миграции всех пользователей. |
| LA-012 | Снять второй адрес после census, не удалять benchmarks. |3aliases narrow forwarding; actual object identity и canonical/legacy CLI output/error/exit равны в bounded среде. Canonical suite IDs/selection сохраняются. | G01: конечное решение по caller/config/job/package surfaces. Existing advanced census не запускался. |
| LA-013 | Удалить пустой redirect, сохранить навигацию и реальные apps/packages. | README отсутствует; config boundary test PASS, apps/packages существуют. Selected lifecycle120-day fixture отклонён безADR. | G03: full links/build/package artifacts и при необходимости external URL redirect. Не новый frontend. |

## 3. Producer → consumer

[Common owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/common/jax_env/__init__.py#L16-L36) применяет defaults через `setdefault`, сохраняя explicit environment. [Research entrypoint](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/research/benchmarks/jax/bench_domain.py#L137-L146) вызывает preparation перед Foundry imports; прочие3entrypoints делают это перед JAX/Equinox. Guard доказывает только раннюю границу, не корректность последующего benchmark. В `run_mechanism_design.py` поздний импорт retired `foundry.domain.state` остаётся видимым источником qualification риска; guard до него не доходит, полного demo PASS нет.

[Bootstrap main](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/devx/workspace/bootstrap.py#L129-L180) → profile extras → CommandSpec → run_command. В диагностике последний заменён recorder, а baseline checks не исполняются: реальные установки категорически не производились. Native public tools route здесь блокируется Python3.14 syntax в fs.py на available3.12.

[Wrapper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/research/benchmarks/suite_registry.py#L1-L14) → [compat identity/entrypoint adapter](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/lib/compat.py#L14-L64) → root registry. Suite metadata output не научная валидация заявленных suite capabilities. Helper DEFAULT_SHIM_SUNSET не объявляет дату для wrappers, не вызывающих warning helper.

[Redirect validator](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/quality/validation/check_docs_lifecycle.py#L487-L542) проверяет metadata, валидность дат и lifetime>90days/ADR. Имя existing test со словом expired не означает проверку `today > sunset`: такая проверка из данного helper не следует. Для удалённого frontend новый дефект из этого не выводится.

## 4. Свежие проверки

| Проверка | Результат и уровень |
|---|---|
| P01 | Native tier9cases: policy/config3PASS;4JAX entrypoints+identity+wrapper CLI6FAIL из-за fs.py857/runtime mismatch. |
| P02 | Bounded tools.lib parent shell:16JAX order/override cases, identity и2CLI bodies PASS. Actual imports/compat/entry files без изменения. Linux sysconfig предварительно initialized перед simulated Darwin. |
| P03 | Actual bootstrap main:4profile command recordings и invalid profile exit2. Нет installer execution. |
| P04 |2 unchanged lifecycle bodies PASS при selected actual helpers+README traversal adapter; frontend absent/protected roots и120-day unqualified fixture. Не native full docs CLI. |
| P05 |28,235tracked product paths,292lexical matches;3retired paths absent, protected inventory сохранён. Не universal dynamic caller census. |

[Probe](../04_Проверки/C126_HYG04/probe_hyg04.py) · [итоговые cases](../04_Проверки/C126_HYG04/run02/existing_cases.json) · [child commands/output](../04_Проверки/C126_HYG04/run02/children.json) · [bootstrap recordings](../04_Проверки/C126_HYG04/run02/bootstrap_recordings.json) · [census](../04_Проверки/C126_HYG04/run02/census.json) · [команды](../04_Проверки/C126_HYG04/commands.json).

Run01 (20PASS10FAIL, exit1) сохранён.4bounded failures вызваны Linux sysconfig после simulated Darwin; run02 исправляет только окружение probe.6native failures не исчезли и не заменены bounded PASS.

## 5. Остаток и сохранение

**C126-G01:** закончить retirement ровно3aliases с реальным caller/config/job/package решением; не удалять весь `tools/research/benchmarks`. Сохранить root canonical metrics/harness, suite IDs, CLI output/exit и самостоятельные JAX/Lex/data tools. Wheel включает tools, sdist включает benchmarks; установленную совместимость нельзя вывести только из config.

**C126-G02:** supported-native public bootstrap recording и early-order tests, точные внешние obligations и lifecycle justification. Тяжёлые workloads — отдельная квалификация, не реконструкция старого wrapper. Не переносить defaults после JAX и не выполнять реальные installs ради этого аудита.

**C126-G03:** full docs links/lifecycle и общий CP6 workspace build/distribution window. [Runtime Reference Shell helper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/apps/runtime-reference-shell/governedProjectionProof.js#L1-L27) вызывает generated client и возвращает available/unavailable; это самостоятельная диагностическая роль, не обещание production dashboard. `packages/cli` экспортирует styleguide, не executable bin. Обе роли сохраняются; UI/API полнота здесь не доказана.

[Карточка](../05_Источники/HYG-04_исходные_строки.txt) · [sources](../05_Источники/C126_источники.json) · [остатки](../01_Реестры/C126_остатки.json) · [границы](../04_Проверки/C126_HYG04/Чтение_и_границы.md).

**126/127. Следующий CLI-01 — последний пакет фазы1. Фаза заданий исполнителю ещё не начата.**
