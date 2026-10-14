# How-to Guides

Практические рецепты для конкретных задач. Если вы только подключаетесь к
репозиторию, начните с [Contributor Start Here](../reference/contributor-start-here.md).
Для общего понимания продукта и его границ используйте архитектурные документы,
связанные на странице для contributors; здесь собраны шаги для уже выбранной задачи.

Для первого прохода используйте маршрут [Contributor Start Here](../reference/contributor-start-here.md)
→ [Getting Started](../tutorials/getting-started.md) → [Onboarding Tracks](onboarding/index.md)
→ нужный recipe ниже → ближайший reference/package README. Tutorials демонстрируют отдельные
surfaces; они не являются доказательством функционального E2E policy flow или готовой к
публикации рекомендации.

## Подготовить окружение и выбрать путь

| Задача | Guide | Что покрывает |
| --- | --- | --- |
| Установка Python, docs или frontend toolchain | [Installation](install.md) | Профили bootstrap, prerequisites и troubleshooting |
| Выбрать путь для своей роли | [Onboarding Tracks](onboarding/index.md) | Backend, frontend, platform, security и domain/policy tracks |
| Перенести старую ветку на текущие контракты | [Post-Refactor Migration](post-refactor-migration.md) | Trinity, public surface, runtime contracts и path-aware docs checks |

## Добавить или изменить поверхность продукта

| Задача | Guide | Что покрывает |
| --- | --- | --- |
| Добавить runtime endpoint | [Add Runtime Route](add-runtime-route.md) | Scaffold, app wiring, OpenAPI и client checks |
| Добавить поддерживаемый Python import path | [Add Public Facade](add-public-facade.md) | `__all__`, facade ownership и public-surface guardrails |
| Добавить IR type с schema lifecycle | [Add Schema-Backed IR Type](add-schema-backed-ir-type.md) | Model/enum, schema catalog и ABI snapshot |
| Подключить data source или Fabric connector | [Add Data Source](add-data-source.md) | Connector registration и profile |
| Обновить dashboard API client | [Update Runtime Dashboard API Client](update-runtime-dashboard-api-client.md) | OpenAPI → generated client → dashboard types |
| Добавить Scientist governance pass | [Write Governance Pass](write-governance-pass.md) | Pass registration и blocker/warning semantics |
| Обновить схемы и API snapshots | [Manage Schemas](manage-schemas.md) | ABI snapshots, OpenAPI export и drift checks |

## Запустить и сопровождать систему

| Задача | Guide | Что покрывает |
| --- | --- | --- |
| Развернуть Runtime API | [Deploy Runtime](deploy-runtime.md) | App factory, config, dashboard и production notes |
| Выполнить run или ingestion через control plane | [Use Control Plane](use-control-plane.md) | Run/ingest/Lex операции, jobs, workers и outbox |
| Диагностировать неудачный run | [Debug Failed Run](debug-failed-run.md) | Timeline, lineage и control-plane state |
| Выполнить causal analysis | [Run Causal Analysis](run-causal-analysis.md) | Discovery, identification, bounds, sensitivity и strategic response |
| Настроить Lex pipeline | [Configure Lex Pipeline](configure-lex-pipeline.md) | Stage-level и control-plane сценарии |
| Запустить benchmarks | [Run Benchmarks](run-benchmarks.md) | Benchmark registry и report artifacts |

## Проверить и выпустить изменение

| Задача | Guide | Что покрывает |
| --- | --- | --- |
| Изменить CI/CD или release workflow | [Operate the CI/CD Platform](operate-ci-cd-platform.md) | Canonical workflows, required checks и supply-chain policy |
| Проверить migration или rollout | [Review Migrations and Rollouts](review-rollouts.md) | Migration class, rollout checklist, rollback и owner |
| Изменить committed generated output | [Manage Generated Artifacts](manage-generated-artifacts.md) | Lifecycle map, regeneration и approval owners |
| Изменить version/deprecation policy | [Release, Versioning, and Deprecation Policy](release-policy.md) | Version namespaces, deprecation windows и migration guides |
| Применить GitHub labels и branch rules | [Apply GitHub Governance](apply-github-governance.md) | Ручной UI checklist для tracked governance |

Для документации используйте [Documentation Style Guide](../style-guide.md) и
docs-only workflow на странице [Contributor Start Here](../reference/contributor-start-here.md).
Там же указаны профиль `docs`, targeted Markdown lint, strict MkDocs build и
docs-accuracy check; path-aware `check-docs-gate` выбирает дополнительные проверки
по изменённым путям.
