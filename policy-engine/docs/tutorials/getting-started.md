# Быстрый старт

Revised: 2026-10-14
Owner: `@docs-owners`
Source of truth: `pyproject.toml`, `.python-version`, `.nvmrc`, `package.json`,
`tools/devx/workspace/{_common,bootstrap,doctor}.py`, `src/polisyos/foundry/_quickstart.py`,
`src/polisyos/ir/__init__.py`, `src/polisyos/foundry/__init__.py`,
`docs/reference/policy-design-case-failure-patterns.md`.
Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
`src/polisyos/` production implementation unchanged.
Review basis: command/source paths inspected; tests, examples, installs and runtime were not run
for this edit.

> Подготовьте рабочее окружение, проверьте import surface и выполните минимальный
> `compile -> execute` smoke path.

!!! info "Historical workstation receipt (2026-04-17)"
    На локальном macOS workstation (Apple Silicon) использовались Python 3.14.0,
    Node 22.22.2 и `uv 0.9.21`. Тогда реально выполнили `uv run polisyos --version`,
    `uv run python -c "from polisyos.ir import ProblemFrame; from polisyos.foundry import compile_program; print(ProblemFrame.__name__, callable(compile_program))"`
    и `python3 -m tools.cli workspace doctor --list-surfaces`. Это датированный receipt
    конкретной машины, не повторный запуск при обновлении страницы.

Текущие command entrypoints читаются из `pyproject.toml` и `tools/registry.py`; их наличие в
source не подтверждает успешный запуск. Только callout выше содержит исторический execution
receipt, а ожидаемые и иллюстративные результаты ниже не являются новыми receipts.

## Что понадобится

- чистый checkout `polisyos/policy-engine`;
- Python `3.14.x`;
- `uv 0.9.21`.

Этот walkthrough использует backend-only bootstrap и не требует Node workspace. Для полного
runtime/frontend profile нужны Node `22.x`, Corepack и pnpm `10.33.2`; поддерживаемая матрица
описана в [Environment Matrix](../reference/environment-matrix.md).

## Что вы получите

- локально работающий CLI и import surface;
- первый CAS-backed Foundry smoke run;
- понятный следующий шаг для вашей роли: backend, frontend, platform, security
  или domain/policy.

## 1. Клонируйте репозиторий и поднимите минимальный contributor path

```bash
git clone https://github.com/DenisKopylov/polisyos.git
cd polisyos/policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
```

Профиль `runtime` синхронизирует extras `lint + test + runtime`; `--skip-frontend` убирает
проверку Node и установку JS workspace. Bootstrap всё равно установит pre-commit hook, если
не добавить `--skip-hooks`. `--skip-doctor` предотвращает автоматический
doctor, который независимо проверил бы Node, Playwright, lockfiles и generated contracts.
В этом walkthrough намеренно используется backend-only path. Полный install matrix,
frontend bootstrap и troubleshooting собраны в [Installation](../how-to/install.md).

## 2. Проверьте CLI и import surface

```bash
uv run polisyos --version
```

Ожидаемый вывод:

```text
polisyos 0.1.0
```

```bash
uv run python -c "from polisyos.ir import ProblemFrame; from polisyos.foundry import compile_program; print(ProblemFrame.__name__, callable(compile_program))"
```

Ожидаемый вывод:

```text
ProblemFrame True
```

Если на этом шаге что-то ломается, переходите к
[Installation](../how-to/install.md#troubleshooting).

## 3. Выполните минимальный compile-and-execute пример

В текущем source tree helper `run_trivial_compile_execute` показывает короткий
compile-and-execute путь с файловым CAS. Более широкий workflow описан в
[Foundry Compile/Execute reference](../reference/foundry/compile-execute.md) и tutorial
[First Policy Analysis](first-policy-analysis.md).

```python
from pathlib import Path

from polisyos.foundry._quickstart import run_trivial_compile_execute

cas_root = Path(".polisyos/quickstart-cas")
result = run_trivial_compile_execute(cas_root=cas_root)
print("compile_ok:", result.compile_ok)
print("execute_ok:", result.execute_ok)
print("exec_plan_artifact:", result.exec_plan_artifact_id)
print("simulation_result_artifact:", result.simulation_result_artifact_id)
print("cas_root:", cas_root)
```

Helper задает CPU-first JAX defaults, если соответствующие environment variables еще не заданы:

- `JAX_PLATFORM_NAME=cpu`
- `JAX_PLATFORMS=cpu`

Это помогает первому запуску на Apple Silicon; явные значения в окружении сохраняются, а
Metal остается opt-in через `apple-metal` extra.

Иллюстративный вывод; это не fresh-run receipt:

```text
compile_ok: True
execute_ok: True
exec_plan_artifact: sha256:...
simulation_result_artifact: sha256:...
cas_root: .polisyos/quickstart-cas
```

!!! note "P02 / E02 F: граница этого smoke path"
    Import check и вызов quickstart helper не доказывают, что нейтральный установленный
    consumer читает curated defaults из упакованного артефакта и не закрывают E02 F.
    Installed-default проверка требует такого consumer и привязки всех конечных catalog
    resources от tracked source bytes через sdist и wheel; подробности задает
    [P02 installed-default consumer discriminator](../reference/policy-design-case-failure-patterns.md).

Этот quickstart — короткий Foundry demo path. Даже успешные `compile_ok` и `execute_ok` не
являются результатом policy analysis, evidence admissibility или разрешением публиковать
рекомендацию.

## 4. Посмотрите, какие артефакты были созданы

После запуска quickstart напечатает `cas_root`; пример выше сохраняет его в локальном,
gitignored каталоге `.polisyos/quickstart-cas`, чтобы следующий шаг мог прочитать манифесты.

Посмотреть манифесты:

```bash
CAS_ROOT=.polisyos/quickstart-cas
find "$CAS_ROOT/artifacts" -name '*.manifest.json' | head
```

Прочитать `kind` и `artifact_id`:

```python
import json
from pathlib import Path

cas_root = Path(".polisyos/quickstart-cas")

for manifest_path in sorted(cas_root.glob("artifacts/**/*.manifest.json")):
    manifest = json.loads(manifest_path.read_text())
    print(manifest["kind"], manifest["artifact_id"])
```

Обычно вы увидите как минимум:

- `foundry.exec_plan`
- `foundry.simulation_result`
- `foundry.metrics`
- `foundry.state_snapshot`

## 5. Прогоните быстрый локальный gate

```bash
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

Это не обязательный шаг для smoke tutorial, но он хороший marker, что рабочая
поверхность уже пригодна для первых правок.

## Что дальше

- Если вы новый contributor, начните с
  [Installation](../how-to/install.md) и
  [Contributor Start Here](../reference/contributor-start-here.md).

- Если вам нужен первый аналитический walkthrough, откройте
  [First Policy Analysis](first-policy-analysis.md).

- Если вы идете по роли, выберите нужный track в
  [Onboarding Tracks](../how-to/onboarding/index.md).
