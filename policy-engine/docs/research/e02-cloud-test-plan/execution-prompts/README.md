# Промпты для исполнения E02: A–G

Это семь компактных промптов для будущих самостоятельных root-задач, не запущенных здесь. Их итоговый tracked-каталог в репозитории: `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/`. Перед стартом проверьте, что в `origin/main` лежит полный пакет результатов 15 машин; каждый root фиксирует актуальный base SHA. Зоны A–F — из [`execution-organization`](../execution-organization/README.md), распределение пакетов и findings — из TSV рядом с ним.

Расположение: **A/C/G локально**, **B/D/E/F в облаке**. Полный production dataset не копировать. Каждый A–G — один root с ёмкостью до 20 прямых исполнителей; никаких субагентов второго уровня. Для A–F начать с двух авторов независимых механизмов, максимум четыре при доказанной непересекаемости; остальные ищут владельцев/потребителей, строят оракулы и отрицательные проверки, независимо рецензируют. У G один издатель integration branch, другие исполнители занимаются review, receipt и affected-consumer mapping.

Скопируйте в каждую задачу только её prompt A–G. В каждом prompt дано прямое указание прочитать полный репозиторный `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md` как обязательную инструкцию; отдельный текст HANDOFF копировать не нужно. G стартует параллельно с A–F, ведёт единственную integration branch `codex/e02-integration` и принимает точные topic-branch SHA через Git. Межчатовая переписка и автоматическая передача не предполагаются. Ни один prompt не разрешает push в `main`.

Промпты: [A — цикл и custody](A.md), [B — runtime](B.md), [C — данные и schema](C.md), [D — search](D.md), [E — calibration/UQ](E.md), [F — causal/SCM](F.md), [G — интеграция](G.md).
