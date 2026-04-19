# Создание governance pass

Related how-to: [Write Governance Pass](../how-to/write-governance-pass.md). Related reference: [Scientist Governance Passes](../reference/scientist/governance-passes.md).

> Этот tutorial рассчитан на инженера, который добавляет новый governance check в Scientist и хочет дойти до состояния "pass существует, зарегистрирован, запускается и тестируется".

!!! info "Verified with"
    Эта страница была перепроверена 2026-04-17 на текущем дереве, macOS,
    Python 3.14 и `uv`.
    Реально проверены импорт базовых типов
    `PassContext` / `ValidatorPass`
    и dry-run scaffold:
    `uv run polisyos-tools architecture scaffold governance-pass --name my_pass --output ... --test-output ... --dry-run`.

Мы пройдём минимальный, но реальный путь: создадим pass, зарегистрируем factory, подключим его к canonical governance surface и проверим blocker/warning semantics тестом.

Перед ручным редактированием можно взять canonical dry-run scaffold:

```bash
uv run polisyos-tools architecture scaffold governance-pass \
  --name my_pass \
  --output src/polisyos/scientist/governance/passes/my_pass.py \
  --test-output tests/scientist/governance/test_my_pass.py \
  --dry-run
```

## Шаг 1. Создайте класс pass

Добавьте новый файл под `src/polisyos/scientist/governance/passes/`, например `my_pass.py`:

```python
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext, ValidatorPass


class MyPass(ValidatorPass):
    @property
    def pass_id(self) -> str:
        return "my_check"

    @property
    def estimated_cost_ms(self) -> int:
        return 10

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if not ctx.state.get("my_artifact_key"):
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["my_artifact_key"],
                    message="Required artifact is missing.",
                    severity=IssueSeverity.BLOCKER,
                    code="MY_ARTIFACT_MISSING",
                    suggestion="Produce my_artifact_key before governance.",
                )
            ]
        return []
```

На что обратить внимание сразу:

- `pass_id` должен быть стабильным и уникальным;
- `BLOCKER` используйте только когда workflow действительно нельзя продвигать дальше;
- `WARNING` подходит для recoverable quality/risk signals;
- `INFO` лучше оставлять для audit trails и human-review hints.

## Шаг 2. Подключите pass к registry factories

Добавьте import и factory в `src/polisyos/scientist/governance/pass_entrypoints.py`:

```python
from .passes.my_pass import MyPass


def my_pass_factory() -> ValidatorPass:
    return MyPass()
```

И не забудьте включить factory в `builtin_governance_pass_factories()` и `__all__`.

Это и есть fallback path, который runtime использует, когда внешние entry points не подхвачены.

## Шаг 3. Экспортируйте pass из package facade

Добавьте pass в `src/polisyos/scientist/governance/passes/__init__.py`, чтобы его можно было безопасно импортировать через публичную package surface.

## Шаг 4. Если pass canonical, привяжите его к family policy

Если новый pass должен входить в обязательный governance набор для observation family, обновите `src/polisyos/ir/observation/governance.py`:

1. добавьте alias в `GovernancePassAliasRegistry.default()`;
2. включите canonical id в `mandatory_governance_passes` у нужной family policy.

Минимальный alias выглядит так:

```python
GovernancePassAlias(
    canonical_pass_id="my_check",
    runtime_pass_id="my_check",
    status=GovernancePassAliasStatus.RUNTIME,
)
```

Если pass пока экспериментальный и не должен быть обязательным по умолчанию, этот шаг можно отложить.

## Шаг 5. Добавьте unit test

Первый тест обычно создаёт `PassContext` напрямую:

```python
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile

from polisyos.scientist.governance.passes.my_pass import MyPass


def test_my_pass_blocks_missing_artifact() -> None:
    ctx = PassContext(
        ir=None,
        state={"my_artifact_key": None},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="run_test",
    )

    issues = MyPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].severity.value == "blocker"
    assert issues[0].code == "MY_ARTIFACT_MISSING"
```

Полезный второй тест после этого: happy path без issues.

## Шаг 6. Проверьте, что pass виден и запускается

Минимальный локальный набор:

```bash
pytest tests/scientist/governance -x --tb=short
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/validation/check_docstring_quality.py --repo-root . --allowlist tools/validation/docstring_quality_allowlist.txt
```

Если pass стал частью canonical governance surface, дополнительно проверьте reference page и observation-family mapping.

## Шаг 7. Добавьте evidence mapping

Для D1-L6 новый pass считается документированным только после того, как его
claim связан с артефактом или тестом:

1. добавьте pass в [Governance Passes reference](../reference/scientist/governance-passes.md), если он builtin или canonical;
2. укажите, какой artifact/report получает оператор: `ComplianceIssue`,
   `GovernanceReport`, `CalibrationValidationBundle`,
   `scientist.governance_accountability_artifact` или другой persisted output;
3. если pass поддерживает SOTA/default-readiness claim, добавьте benchmark or
   eval reference до такого claim.

Минимальный traceability format:

```text
pass_id -> emitted issue/artifact -> regression test -> phase gate or benchmark
```

## Как читать blocker и warning semantics

- `BLOCKER`: workflow нельзя продвигать без исправления или явного human override.
- `WARNING`: результат usable, но риск должен быть показан оператору или downstream review surface.
- `INFO`: неблокирующий след для аудита, telemetry или follow-up review.

Хороший practical template в текущем дереве: `StrategicResponsePass`. Он показывает state-first lookup, escalation в strict profile и понятные issue codes.

## Что дальше

- Для полного checklist смотрите [Write Governance Pass](../how-to/write-governance-pass.md)
- Для API/contract surface смотрите [Governance Passes reference](../reference/scientist/governance-passes.md)
- Для architectural rationale откройте [Governance Model](../explanation/governance-model.md)
