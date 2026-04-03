# Быстрый старт

> Установите PolicyOS из исходников и запустите первый end-to-end пример Foundry примерно за 15 минут.

!!! info "Проверено на текущем дереве"
    Эта страница была проверена 2026-04-03 на macOS с Python 3.14.
    Команды `pip install -e ".[all]"`, `polisyos --version`,
    `from polisyos.ir import ProblemFrame` и
    `from polisyos.foundry import compile_program`
    были реально запущены в свежем окружении.

## Предварительные требования

- Python 3.14+
  - macOS: `brew install python@3.14`
  - Ubuntu/Debian: установите Python 3.14 из совместимого источника, например deadsnakes
- Git
- Около 2 ГБ свободного места под JAX и связанные зависимости

## Установка

Клонируйте репозиторий и установите рекомендуемое полное окружение для документации:

```bash
git clone <repo-url> policy-engine
cd policy-engine
pip install -e ".[all]"
```

Если нужен только базовый пакет и основные контракты, используйте минимальную установку:

```bash
pip install -e ".[core]"
```

`.[core]` намеренно минимален. `.[all]` — рекомендуемая стартовая точка для tutorial-страниц, потому что именно этот набор extras был проверен вместе со smoke-прогонами из документации.

Если хотите, можно использовать виртуальное окружение:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Примечания для Apple Silicon:

- В текущем дереве на macOS уже подключён `jax-metal`.
- В документации JAX этот путь также может называться `jax[metal]`.
- Quickstart helper ниже по умолчанию принудительно включает CPU-режим JAX, чтобы первый запуск был стабильным.
- Если вы хотите именно Metal backend, ожидайте дополнительную platform-specific настройку.

## Проверка установки

Запускайте команды из корня репозитория.

```bash
polisyos --version
```

Ожидаемый вывод:

```text
polisyos 0.1.0
```

```bash
python -c "from polisyos.ir import ProblemFrame; print('OK')"
```

Ожидаемый вывод:

```text
OK
```

```bash
python -c "from polisyos.foundry import compile_program; print('OK')"
```

Ожидаемый вывод:

```text
OK
```

## Минимальный пример

Самый простой полностью рабочий пример в текущем дереве использует встроенный quickstart helper. Он создаёт минимальный registry-backed Trinity bundle, компилирует его, выполняет и оставляет CAS-артефакты для дальнейшего просмотра.

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

Этот helper выставляет:

- `JAX_PLATFORMS=cpu`
- `JAX_PLATFORM_NAME=cpu`

Это делает первый запуск на Apple Silicon стабильным и при этом всё равно прогоняет полный compile-and-execute путь.

Пример вывода из реального запуска:

```text
compile_ok: True
execute_ok: True
exec_plan_artifact: sha256:9710c288fb1d972f1fd53a2f24b10dda05e2a37d222e8b8c6974fb70af46d19e
simulation_result_artifact: sha256:631a92d475c617773b6cc3c9ad56cd835fc651485fbe30b83d52f9b101b4f143
cas_root: /var/folders/.../polisyos-quickstart-...
```

Хэши артефактов и временный путь у вас будут другими.

## Как посмотреть результаты

Quickstart пишет content-addressed артефакты в каталог `cas_root`, который печатается в конце запуска.

Посмотреть манифесты:

```bash
find "$CAS_ROOT/artifacts" -name '*.manifest.json' | head
```

Прочитать виды артефактов из манифестов:

```python
import json
from pathlib import Path

cas_root = Path("/path/to/your/cas")

for manifest_path in sorted(cas_root.glob("artifacts/**/*.manifest.json")):
    manifest = json.loads(manifest_path.read_text())
    print(manifest["kind"], manifest["artifact_id"])
```

В успешном запуске вы увидите, как минимум, такие kinds:

- `foundry.exec_plan`
- `foundry.simulation_result`
- `foundry.metrics`
- `foundry.state_snapshot`

Чтобы отдельно прочитать payload с метриками шага:

```python
import json
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes

cas_root = Path("/path/to/your/cas")
store = FileSystemCAS(cas_root)

metrics_manifest = None
for manifest_path in cas_root.glob("artifacts/**/*.manifest.json"):
    manifest = json.loads(manifest_path.read_text())
    if manifest["kind"] == "foundry.metrics":
        metrics_manifest = manifest
        break

if metrics_manifest is None:
    raise RuntimeError("No foundry.metrics artifact found in this CAS root.")

metrics = from_canonical_bytes(
    store.get_bytes(ArtifactID(metrics_manifest["artifact_id"]))
)
print(metrics)
```

Репрезентативный payload метрик:

```text
{
  'applied_nodes': 1,
  'checked_constraints': 0,
  'constraint_hard_fail': 0,
  'op_nodes': 4,
  'patch_ops': 2,
  'skipped_nodes': 0,
  'step': 0,
  'step_latency_ms': 183
}
```

Это даёт простой ASCII-снимок таймлайна запуска: один выполненный шаг, его latency и счётчики узлов.

## Что дальше

- Перейдите к [First Policy Analysis](first-policy-analysis.md) за аналитическим walkthrough с данными World Bank
- Используйте [Installation](../how-to/install.md) для extras, troubleshooting и development setup
- Смотрите [Run Causal Analysis](../how-to/run-causal-analysis.md) для discovery, identification, bounds и strategic response
- Смотрите [Reference index](../reference/index.md) за API-деталями
