# Быстрый старт

> За 15-20 минут подготовьте первое рабочее окружение, проверьте import surface
> и выполните минимальный `compile -> execute` smoke path.

!!! info "Verified with"
Проверено 2026-04-17 на локальном macOS workstation (Apple Silicon):
Python 3.14.0, Node 22.22.2, `uv 0.9.21`.
Реально выполнены команды `uv run polisyos --version`,
`uv run python -c "from polisyos.ir import ProblemFrame; from polisyos.foundry import compile_program; print(ProblemFrame.__name__, callable(compile_program))"`,
и `python3 -m tools.cli workspace doctor --list-surfaces`.

## Что понадобится

- чистый checkout `polisyos/policy-engine`;
- Python `3.14.x`;
- Node `22.x`;
- `uv`;
- примерно 2 ГБ свободного места.

Поддерживаемая матрица описана в [Environment Matrix](../reference/environment-matrix.md).

## Что вы получите

- локально работающий CLI и import surface;
- первый CAS-backed Foundry smoke run;
- понятный следующий шаг для вашей роли: backend, frontend, platform, security
  или domain/policy.

## 1. Клонируйте репозиторий и поднимите минимальный contributor path

```bash
git clone https://github.com/DenisKopylov/polisyos.git
cd polisyos/policy-engine
python3 -m tools.cli workspace bootstrap --profile runtime --skip-frontend --skip-playwright
python3 -m tools.cli workspace doctor --skip-playwright
```

Этот tutorial намеренно использует backend-only path. Полный install matrix,
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

Самый короткий проверенный путь в текущем дереве использует
`run_trivial_compile_execute`.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.foundry.quickstart import run_trivial_compile_execute

with TemporaryDirectory(prefix="polisyos-quickstart-") as tmp:
    result = run_trivial_compile_execute(cas_root=Path(tmp))
    print("compile_ok:", result.compile_ok)
    print("execute_ok:", result.execute_ok)
    print("exec_plan_artifact:", result.exec_plan_artifact_id)
    print("simulation_result_artifact:", result.simulation_result_artifact_id)
    print("cas_root:", tmp)
```

Helper принудительно использует CPU-first JAX path:

- `JAX_PLATFORM_NAME=cpu`
- `JAX_PLATFORMS=cpu`

Это стабилизирует первый запуск на Apple Silicon и не мешает later-on перейти
на opt-in Metal extras.

Репрезентативный вывод:

```text
compile_ok: True
execute_ok: True
exec_plan_artifact: sha256:...
simulation_result_artifact: sha256:...
cas_root: /var/folders/.../polisyos-quickstart-...
```

## 4. Посмотрите, какие артефакты были созданы

После успешного запуска quickstart напечатает `cas_root`.

Посмотреть манифесты:

```bash
find "$CAS_ROOT/artifacts" -name '*.manifest.json' | head
```

Прочитать `kind` и `artifact_id`:

```python
import json
from pathlib import Path

cas_root = Path("/path/to/your/cas")

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
python3 -m tools.cli workspace verify --backend-only --skip-doctor
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
