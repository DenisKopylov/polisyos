# E02: единый локальный оркестратор

Срез подготовки — 2026-10-09. Задание: исполнить оставшуюся связанную работу, а не повторять отчётные циклы прежних A–F. Автор ведёт собственную candidate-ветку; G независимо принимает код, публикует integration и adjudicates findings. `main` остаётся вне этой задачи.

Рабочая source-композиция — `78be3aff64185e2de24abe710523e14491e36ba6`, tree `7dc9df15aebbdac1e2ba6ba894fff4c31b84b59c`. Пакет документов добавляется поверх неё отдельным коммитом. При старте следует fetch опубликованную G-ветку и записать фактический checkpoint, а не переводить существующую рабочую ветку на старый HEAD.

В базу включены bounded CAN reader, C10 recursion/context/CAS, C11 history/refit/intake и DFK census с исправленным JSON escaping. Их свежая общая focused-проверка: **101 PASS / 7 SKIP / 0 FAIL / 0 ERROR**, 108 случаев, 59,53 секунды; семь пропусков относятся к BoTorch. Это не полный runtime, packaging или authentic closeout. Точная область приёмки и deciding outputs находятся в [G admission](../../implementation-handoffs/G/local-transition-20261009/ADMISSION.json).

Новые L01/L02, ORCH02, C13 и C05 proposal receipts сохранены с исходными source qualifications. **C05 и C12 ещё нужно составить с текущей базой**: доступные source/proposals есть, но переносить целиком их старые recovery-ветки нельзя. Prepared B теперь доступен точным Git fetch; его новая дельта ещё требует исполнения и проверки. У ORCH03 отсутствуют локальные bytes неопубликованного архива; восстановление необходимого механизма из доступного source получает новую identity. Неответившая ORCH01 VM не является зависимостью выполнения канонической очереди.

Полный исходный набор: **127 bundles / 282 findings / 291 criterion occurrences**. Предложения авторов — 198 closed, 54 limited, 23 held, 7 open. Это не число принятых capabilities. Сохраняются исторические решения, включая B198; новых formal closures этим intake не выдано. Полный обход знаменателя и графа записан в [PACK-VALIDATION.json](PACK-VALIDATION.json).

Читать в порядке:

1. [CURRENT-STATE.md](CURRENT-STATE.md) — что действительно доставлено и какие остановки остались.
2. [INPUTS.json](INPUTS.json) — точные source/carrier refs, trees и каналы custody.
3. [EXECUTION-PLAN.md](EXECUTION-PLAN.md) и [TASKS.json](TASKS.json) — связанные задачи, очередность, параллельность и критерии завершения.
4. [MASTER-PROMPT.md](MASTER-PROMPT.md) — готовое задание новому локальному агенту.
5. [DECISIONS.md](DECISIONS.md) — решения, которые следует исследовать, и формат конкретного предложения G.

Новый root вправе исправлять Core, IR, Fabric, Foundry, Scientist, Data Forge, runtime, DTO/API, UI, tooling и их companions в границах E02. Прежние буквы и Cxx — происхождение свидетельств, а не запрет пересечь модуль. Новая продуктовая authority, право, release/currentness или scientific law из этого разрешения не возникают.

Pattern pass: P01/P02/P12 — завершать producer→artifact→bridge→consumer; P04/P05/P07/P08/P09 — сохранять status, authority, time и replay; P27/P31 — один существующий canonical mechanism; P29/P32/P33/P37/P38 — behavioral/content-bound доказательство и его отрицательный discriminator; P35/P39 — полный знаменатель и обязательные companions; P40 — не чинить класс лестницей; P41 — не приписывать красный чужому владельцу без правильного base replay. Acceptance signal — проверенная цепочка на exact source и исходном критерии; запись новой архитектурной идеи сама по себе capability не завершает.
