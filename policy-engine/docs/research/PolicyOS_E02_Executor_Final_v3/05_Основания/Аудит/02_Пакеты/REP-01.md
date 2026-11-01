# REP-01 — прямой Scientist replay owner и сохранённая совместимость

## 1. Решение

**Ограниченно оценён, не закрыт. Новый подтверждённый product defect не установлен.** Главный ремонт LA-033 сделан: десять root lazy bindings, Core delayed import, dynamic inventory и benchmark указывают прямо на `scientist.replay.deterministic`. Старый `runtime.replay` сохраняет20 точных exports для compatibility окна, не содержит отдельного алгоритма и не расширяет root API.

Native root import действительно прошёл без stubs и без загрузки Scientist/compatibility. Canonical identity/CLI checks ниже исполнялись через explicit dependency seams; native full replay/resume и wheel не заявлены. Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Полная исходная карточка](../05_Источники/REP-01_исходные_строки.txt), [pinned sources](../05_Источники/C77_источники.json).

## 2. Матрица исходных требований

| ID | Фактический owner/результат | Остаток |
|---|---|---|
| LA-033 | Root10 прямо разрешаются в Scientist; Core import остаётся delayed; benchmark alias связан с direct owner; inventory whitelist изменён; shim20 identity/signatures/enums сохранены | Native full import graph, persisted replay/resume, wheel/CP6 и downstream retirement qualification G01/G02 |
| LK15 | `runtime.manifest` теперь package с тем же import address; on-disk RunManifest1.0 и runtime API writer/reader существуют. `runtime.quality.replay` — отдельный canary schema/algorithm | Новый local roundtrip не historical external corpus; Core DTO не объявлен эквивалентным старому формату G03 |

Не объявлять сохранённый shim дефектом только потому, что исходный план описывает eventual retirement. Окно поддержки и удаление публичного root — разные решения. Исправления checkpoint/CAS/долговечности не доказаны сменой import path.

## 3. Producer → owner → consumer

Root facade (`S01`) хранит ровно10 lazy адресов и кэширует полученный объект. Compatibility facade (`S02`) присваивает20 actual canonical objects. Core `_cmd_replay` делает отложенный import Scientist, нормализует packet ref и передаёт CAS в `completeness_check`; `--check-only` возвращает status без вызова backend. Только обычный replay branch импортирует `scientist.replay.backend`; resume отдельно адресует checkpoint owner (`S04`). Native store factory остаётся отдельным declarative backend bridge (`S05`), в diagnostics заменён fixture.

Canonical deterministic (`S03`) различает strategy, seed source, dependency completeness, snapshot-only measurement и actual semantic replay. Graph owner (`S10`) читает manifest inputs и проверяет bytes; backend `replay_packet` строит plan, отказывает incomplete, затем выбирает Foundry/Scientist execution и verification (`S14:122–204`). **Execution branch не запущен C77.** Preserved enums и import identity не доказывают запуск оставшегося workflow узла.

Dynamic TOML содержит ровно один relevant direct deterministic target/allowed_targets для Core CLI, рядом отдельные backend/checkpoint entries (`S06`). Benchmark direct import и локальный legacy-named alias `runtime_replay` указывают на canonical Scientist (`S07:24–26`). Имя alias не означает сохранённый compatibility hop.

## 4. Свежие проверки

1. **Native standalone root:** unmodified `polisyos.runtime` импортируется, `__all__` содержит10, Scientist и runtime.replay отсутствуют в `sys.modules`; unknown attribute даёт AttributeError. Exit0. Это настоящий native узкий результат, не blanket UNRUN.
2. **P01:** actual root bindings не загружают shim; затем actual shim сохраняет20 identities/signatures и точные enum values.4 existing light test bodies PASS —3 из REP-01 и1 exact compatibility. Canonical definitions настоящие, но import graph заменён явными seams; native full package PASS не заявлен.
3. **P02:** actual CLI check-only читает persisted synthetic decision packet: present1, incomplete/strategy_unresolved, exit1; missing packet даёт packet_unreadable, exit1. Несовместимые `--check-only --export` дают exit2 без создания output. Import trace начинается с direct Scientist, backend не вызывается.
4. **P03:** actual strategy/seed/bit-exact/skip сохраняют разные смыслы. Seed берётся из declared replay effective seed; missing simulation ref не становится bit-exact pass. SKIP помечен `verification_skipped`, не назван проведённой проверкой.
5. **P04:** actual graph/completeness over four persisted synthetic artifacts: complete Scientist-role graph; tampered binding blob переводит результат в incomplete/corrupted. Это проверка contract/bytes, **не реальный содержательно исполнимый policy workflow**.
6. **P05:** actual RunManifest writer → log artifact → finalize → persisted readback сохраняет schema1.0/status/artifact refs. Actual EnvironmentManifestRef передан через dependency bridge. Quality replay module доступен отдельно; его алгоритм не исполнялся.
7. **P06:** actual benchmark top-level import/alias statements разрешают тот же canonical object. Whole benchmark suite не запускался.

Literal census: все **3009 tracked `.py/.toml`** в `policy-engine/src`, `policy-engine/benchmarks` и указанном dynamic inventory просмотрены на точную строку `polisyos.runtime.replay`; occurrences0. Полный denominator/file list сохранён. Это **не** доказательство отсутствия динамически составленных FQN, downstream callers или production-трафика.

## 5. Что сохранить и что осталось

**Сохранить:** direct canonical owner, отложенные Core imports, root10, shim20 и точную identity; complete/recoverable/incomplete и bit-exact/CI-bounded/skip; существующие historical bytes/readers; independent `runtime.quality.replay`; current manifest/profile/integrity admission вместо доверия названию API. Wire-existing уже выполнен — новый replay subsystem не требуется.

**C77-G01 — native activation/package.** Запустить на supported runtime existing compatibility/import tests, persisted check-only и настоящий небольшой replay/resume с fresh checkpoint head; bundle transfer и installed wheel совместить с CP6. В C77 actual CLI/graph/file mechanisms исполнены, но store factory, native loader admission и custody — fixtures. Full replay/resume tests прочитаны, не PASS. Прежние RES-отчёты не переаттестуются и не подменяют это исполнение.

**C77-G02 — compatibility retirement.** Оставить20 поддержанных exports до согласованного окна; отдельно проверить downstream FQN/monkeypatch/documentation/package consumers. Не расширять root до20, не удалять stable root вместе с промежуточным модулем. Exact literal census ограничен указанным source denominator.

**C77-G03 — смысл результата и LK15.** `RunManifest1.0` не заменять похожим Core DTO без format mapping/corpus. Synthetic roundtrip подтверждает нынешний writer/reader, не все старые run directories. Snapshot-only availability не actual re-execution, bit-exact refs не empirical validity, SKIP не validation. CI-bounded branch прочитана, но здесь не исполнена и не квалифицирована как статистический confidence interval. Отсутствие universal deterministic model inventor не имеет отношения к этой migration и новым дефектом не считается.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C77_REP01/commands.json) · [Observations/cases](../04_Проверки/C77_REP01/bounded_diagnostics.json) · [Seams/native](../04_Проверки/C77_REP01/native_verification.json) · [Остатки](../01_Реестры/C77_остатки.json).

Final bounded run02 exit0:6 MATCH,4 unchanged bodies/cases PASS. Initial run01 тоже успешен, final добавляет benchmark binding и import identities. Full native pytest отсутствует; обычные canonical/manifest imports блокированы текущим Python3.12/Python3.14 contract graph. Import feasibility отдельно сохранил TypeVar(default=...) failure. Environment failures не product defects. Pydantic также вне project baseline. Native standalone root PASS отделён от blocked full suite.

Canonical actual definitions исполнялись без original imports, с actual IDs/graph/canon и отказными placeholders для неиспользованных paths; это не fake canonical objects и не native package. CLI whole module использует fixture factory; core JSON bridge — actual verified bytes+canon decoder, но native codec-profile admission UNRUN. Historical API whole module использует actual DTO через dependency bridge. Checkout чист, dependencies/source не менялись; внешние сервисы не вызывались.

**77/127 рассмотрены ограниченно. Следующий — CAN-01. Полного закрытия нет; фаза2 не начата.**
