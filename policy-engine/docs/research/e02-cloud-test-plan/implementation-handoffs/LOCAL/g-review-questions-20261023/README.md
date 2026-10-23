# E02: вопросы для G, 23 октября 2026

**Статус: предложение для архитектурного решения.** Авторская ветка `codex/e02-unified-local-20261009`. Приёмка кода, публикация integration и formal finding adjudication остаются у G. `code_acceptance=false`; `closure_ids=[]`. Это не global source/input/backend freeze.

## Что просим решить

| ID | Вопрос | Рекомендуемый маршрут | Статус |
|---|---|---|---|
| IR-Q1 | Как согласовать публичные overrides schema name/version у producer с обязательным owner contract у reader? | Один owner contract для write/read; явная миграция принятых overrides | **Новый вопрос**: [варианты и проверки](Q1-override-owner-contract.md) |
| IR-Q2 | Как версионировать owner contracts и историческую совместимость там, где сегодняшний DTO/writer допускает открытые версии? | Версионированная политика owner; согласованный reader-first rollout, без silent migration | **Новый вопрос**: [Mobility / Causal Discovery](Q2-version-compatibility.md) |
| PAG | Legal relation/permission и переход consumers | Сохранить protected refusal до подлинного основания; отделить выбор миграции от внешнего юридического факта | **Ранее открыт**, [ссылки и точная граница](existing-pending-questions.md) |
| R4 | Conditional candidate transport diagnostic при сохранении protected refusal | Extend существующий persisted result; outer `UNSUPPORTED/NONE/false` не меняется | **Ранее открыт**, [готовое предложение](existing-pending-questions.md) |

Предлагаемый порядок: сначала IR-Q1 (единый owner и поведение override), затем IR-Q2 (версии/совместимость); PAG/R4 можно рассматривать независимо. Просим вернуть выбранный вариант, owner и условия миграции/rollout, границу статуса и приёмочный falsifier. Отсутствующие факты о версиях, law, issuer, custody, currentness и calibration не возникают из архитектурного решения.

[Необходимые owner/external inputs](required-inputs.md) включают шесть Welfare roles и T1/T2/S1/S2. Выбор candidate/authority plane **не переоткрывается**: уже действует S0-K06 — candidate может нести объявленное unknown, authority-band admission требует установленного основания. Исправление ClassVar introspection, imports, JSON fixtures и мостов с уже известным owner law выполняет исполнитель без нового решения G.

## Почему это системный вопрос

Полный исследованный source denominator — **195 Python-файлов `policy-engine/src/polisyos/ir/**/*.py`**, не весь repository. AST нашёл 134 вызова `get_json_artifact` в 67 caller files. Из них вне исходного selected reader cohort остаются **93 callsites в 53 файлах**: 84 typed rows без полной owner declaration (70 с override обоих schema arguments, 14 только с константами), 5 уже centrally enforced typed rows, 2 generic selectors с известным producer law и 2 случая неизвестного owner law. Сумма: `70+14+5+2+2=93`. Все пять уже centrally enforced producer APIs также допускают overrides: defaults сами по себе не задают supported set.

[Полный CSV этих 93 строк](remaining-93-callsite-census.csv) содержит caller, producer, exact source SHA и source view. 93 — число callsites, а не число producer functions. Метрики в `packet.json` отдельно помечают functions with owner source и caller-path/function pairs; generic selector не считается producer function. Ни строки, ни общие task routes не являются новыми closures.

## Source и проверка

Исследовательский entry: commit `5b5871c4e5e1f682a7526e2c5c3b97d0b043ce75`, tree `7511cb8c5c524027ea48dd414ea00a18c2914944`, parent `b376f78ea82dda7ffceed89ad432135a7c17bf6e`. CSV содержит 81 current-canonical и 12 RAW-candidate call rows. Из 53 caller files 43 совпадают с entry HEAD, 5 — известные local dirty versions, 5 — unpublished RAW postimages. Последние не выдаются за опубликованный код. Полный raw census и input manifest указаны с hashes в [packet.json](packet.json); CSV сохраняет source references без копирования source bodies.

Source counterexamples исследованы статически. **Runtime falsifiers именно IR-Q1/Q2: UNRUN.** Ранний selected admission replay дал 88 PASS / 20 FAIL (108 tests): 14 отказов ClassVar field inventory и 6 obsolete Trinity test seams. Их engineering repair продолжается; этот replay не доказывает варианты IR-Q1/Q2. Последующие изменения не становятся принятой частью исходного census автоматически. Один baseline input mismatch `causal_graph.py` остаётся P41 `not_established`, без inherited claim.

G remote checkpoint при подготовке пакета: `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`. Он не меняет два ранее открытых вопроса. Выборы `b7adafe89423bc6906a5fb86c38e579a381ad2ee`, `798bd1ab9646378f49fd127b3f04ebe71aca67d2`, `d40bca270ef5c456e8233196e4d8d65e099777a7` остаются действующими; этот пакет их не переоткрывает.

## Pattern pass и продолжение

P31/P40: единый owner invariant вместо последовательного исправления отдельных readers. P29/P32/P38: contract declaration недостаточна; нужны actual producer → persisted manifest/bytes → shared admission → consumer, zero-payload-read negatives и removal control. P35: приведён полный file-type denominator. P37: байты recomputed; owner law независимо reconciled; issuer/currentness не считаются установленными по наличию полей. P39: mandatory tests, facades, schema/config/generator и handoff companions вне механического path budget. P41: provenance каждого red проверяется от собственного slice base.

Пока G рассматривает пакет, продолжаются известные owner bridges, ClassVar/fixture repairs, native typing/quality cohorts, HTE POST/CAS/GET и независимые проверки. Исторические 282 findings / 291 occurrences и B198 сохраняются; отдельный full-ID proposal closeout ещё готовится.
