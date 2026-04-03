# Написание governance pass

> Реализуйте, зарегистрируйте, протестируйте и подключите новый Scientist governance pass, используя текущий pass API.

## 1. Реализуйте интерфейс pass

Базовые типы сейчас такие:

- `PassContext`
- `ValidatorPass`
- `ComplianceIssue`
- `IssueSeverity`

Используйте реальный интерфейс из `polisyos.core.governance.passes.base`:

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

Если нужен простой реальный пример для копирования, начните с:

- `src/polisyos/scientist/governance/passes/strategic_response_pass.py`

Этот pass хорошо показывает:

- как читать state
- как различать blocker и warning
- как запрашивать human review в strict mode

## 2. Разберитесь с `ComplianceIssue`

Текущая модель issue поддерживает:

- `IssueSeverity.INFO`
- `IssueSeverity.WARNING`
- `IssueSeverity.BLOCKER`

Полезные поля:

- `pass_id`
- `path`
- `message`
- `severity`
- `code`
- `suggestion`
- `input_value`

Практическая интерпретация severity:

- `BLOCKER`: запуск нельзя продвигать дальше
- `WARNING`: можно продолжать, но риск нужно показать оператору
- `INFO`: неблокирующий audit signal или human-review request

## 3. Чтение state и artifacts

`PassContext` сейчас даёт доступ к:

- `ir`: опциональный `TrinityBundle`
- `state`: mutable workflow state dictionary
- `registry_bundle`: опциональный registry object
- `profile`: `ValidationProfile`
- `run_id`: текущий run id

Типичный паттерн чтения:

```python
def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
    state = ctx.state

    summary = state.get("my_summary")
    artifacts_index = state.get("artifacts_index", {})
    params = state.get("params", {})

    if summary is None and "my_bundle_ref" in artifacts_index:
        ...
```

Два самых частых паттерна в существующих passes:

- читать уже materialized summary напрямую из `ctx.state`
- вытаскивать CAS artifact ref из `ctx.state["artifacts_index"]` и уже по нему загружать bundle целиком

## 4. Зарегистрируйте pass

Сейчас есть две поверхности регистрации.

### Built-in pass внутри репозитория

Если pass живёт прямо в этом репозитории:

1. добавьте класс в `src/polisyos/scientist/governance/passes/`
2. добавьте factory в `src/polisyos/scientist/governance/pass_entrypoints.py`
3. экспортируйте класс из `src/polisyos/scientist/governance/passes/__init__.py`

Именно эти built-in fallback factories использует runtime, когда внешние entry points не найдены.

### Внешний или plugin pass

Группа entry points:

```text
polisyos.scientist_governance_passes
```

Target entry point должен разрешаться в:

- `ValidatorPass` subclass с zero-arg constructor
- либо zero-arg factory, который возвращает `ValidatorPass`

Дублирующиеся `pass_id` отклоняются при загрузке.

## 5. Протестируйте pass

В текущем дереве тесты чаще всего создают `PassContext` напрямую, а не через специальную fixture helper-функцию.

Паттерн из `tests/scientist/governance/test_strategic_response_pass.py`:

```python
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile


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
    assert issues[0].code == "MY_ARTIFACT_MISSING"
```

Хорошие места для изучения:

- `tests/scientist/governance/test_strategic_response_pass.py`
- `tests/scientist/governance/test_pass_registry.py`

## 6. Интеграция в workflow

В `polisyos.ir.observation.governance` сейчас есть два связанных registry:

- `GovernancePassAliasRegistry`
- `ObservationFamilyPolicyRegistry`

Как это работает:

- `GovernancePassAliasRegistry` связывает стабильные canonical pass names с runtime pass ids
- `ObservationFamilyPolicyRegistry` определяет, какие canonical pass ids обязательны для конкретной observation family

То есть включение pass в workflow сейчас family-driven, а не через прямое поле в `PolicySpec`.

Если новый pass должен стать частью canonical governance surface:

1. добавьте alias в `GovernancePassAliasRegistry.default()`
2. добавьте canonical alias name в нужный `mandatory_governance_passes` внутри `ObservationFamilyPolicyRegistry.default()`

Пример:

```python
GovernancePassAlias(
    canonical_pass_id="my_check",
    runtime_pass_id="my_check",
    status=GovernancePassAliasStatus.RUNTIME,
)
```

## 7. Реальный пример: `StrategicResponsePass`

`StrategicResponsePass` — хороший шаблон, потому что он:

- достаточно маленький, чтобы быстро прочитать
- достаточно новый, чтобы отражать текущие runner/artifact patterns
- явно показывает blocker, warning и human-review escalation

Что именно он демонстрирует:

- state-first lookup с fallback на artifact
- escalation в strict profile через `ctx.state["human_review_request"]`
- понятные `ComplianceIssue.code`

## Чеклист

- класс pass создан
- `pass_id` уникален
- factory или entry point зарегистрирован
- тесты добавлены
- alias registry обновлён, если pass должен быть частью canonical observation policy
- observation-family policy обновлена, если pass должен запускаться по умолчанию для family

## Связанные файлы

- `src/polisyos/core/governance/passes/base.py`
- `src/polisyos/scientist/governance/pass_registry.py`
- `src/polisyos/scientist/governance/pass_entrypoints.py`
- `src/polisyos/scientist/governance/passes/__init__.py`
- `src/polisyos/scientist/governance/passes/strategic_response_pass.py`
- `src/polisyos/ir/observation/governance.py`
