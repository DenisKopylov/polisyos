# Create a Governance Pass

English edition: 2026-10-14 (translation only; not a source-freshness or execution claim).

Related how-to: [Write Governance Pass](../how-to/write-governance-pass.md). Related reference: [Scientist Governance Passes](../reference/scientist/governance-passes.md).

> This tutorial is for an engineer adding a governance check to Scientist and
> aiming to reach the point where the pass exists, is registered, runs, and is
> tested.

!!! info "Historical review (2026-04-17)"
    The previous revision recorded imports of `PassContext` / `ValidatorPass`
    and a dry-run scaffold in the environment used at that time. This is not a
    receipt that the full tutorial or its tests were run. Source paths were read
    at pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; the production
    implementation under `src/polisyos/` has not changed since that pin. The
    examples and tests were not run for this documentation refresh.

This tutorial walks through adding a pass and registering its factory, then
shows a unit test for a blocker case. Warning and info are described separately
as guidance for choosing severity; the shown test does not cover them.

Before editing by hand, you can start with the canonical dry-run scaffold:

```bash
uv run polisyos-tools architecture scaffold governance-pass \
  --name my_pass \
  --output src/polisyos/scientist/governance/passes/my_pass.py \
  --test-output tests/unit/scientist/governance/test_my_pass.py \
  --dry-run
```

## Step 1. Create the pass class

Add a new file under `src/polisyos/scientist/governance/passes/`, for example
`my_pass.py`:

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

Keep the following points in mind:

- `pass_id` must be stable and unique.
- Use `BLOCKER` only when the workflow truly cannot proceed.
- `WARNING` is suitable for recoverable quality/risk signals.
- Reserve `INFO` for audit trails and human-review hints.

## Step 2. Connect the pass to registry factories

Add an import and factory in
`src/polisyos/scientist/governance/pass_entrypoints.py`:

```python
from .passes.my_pass import MyPass


def my_pass_factory() -> ValidatorPass:
    return MyPass()
```

Also include the factory in `builtin_governance_pass_factories()` and `__all__`.

This is the fallback path the runtime uses when external entry points are not
discovered.

## Step 3. Export the pass from the package facade

Add the pass to `src/polisyos/scientist/governance/passes/__init__.py` so it can
be safely imported through the public package surface.

## Step 4. If the pass is canonical, bind it to the family policy

If the new pass must be part of the required governance set for an observation
family, update `src/polisyos/ir/observation/governance.py`:

1. Add an alias to `GovernancePassAliasRegistry.default()`.
2. Add the canonical ID to `mandatory_governance_passes` for the relevant family
   policy.

The minimum alias looks like this:

```python
GovernancePassAlias(
    canonical_pass_id="my_check",
    runtime_pass_id="my_check",
    status=GovernancePassAliasStatus.RUNTIME,
)
```

If the pass is still experimental and should not be required by default, you can
defer this step.

## Step 5. Add a unit test

The first test usually creates `PassContext` directly:

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

A useful second test is a happy path with no issues.

## Step 6. Check that the pass is discoverable and runs

Minimum local checks:

```bash
pytest tests/unit/scientist/governance -x --tb=short
uv run --extra docs python -m mkdocs build --strict
uv run --extra docs python tools/quality/validation/check_docstring_quality.py --repo-root . --allowlist tools/quality/validation/docstring_quality_allowlist.txt
```

If the pass becomes part of the canonical governance surface, also check the
reference page and observation-family mapping.

## Step 7. Add evidence mapping

For D1-L6, the new pass is documented only after its claim is connected to an
artifact or test:

1. Add the pass to the [Governance Passes reference](../reference/scientist/governance-passes.md)
   if it is built-in or canonical.
2. State which artifact/report the operator receives: `ComplianceIssue`,
   `GovernanceReport`, `CalibrationValidationBundle`,
   `scientist.governance_accountability_artifact` or another persisted output;
3. If the pass supports a SOTA/default-readiness claim, add a benchmark or
   evaluation reference before making that claim.

Minimum traceability format:

```text
pass_id -> emitted issue/artifact -> regression test -> phase gate or benchmark
```

## Choosing severity

The following definitions are design guidance, not test results from this
tutorial. The shown test checks only the blocker case; add separate cases for
warning and info if the new pass should emit them.

- `BLOCKER`: the workflow cannot proceed without a fix or explicit human
  override.
- `WARNING`: the result is usable, but the risk must be shown to the operator or
  a downstream review surface.
- `INFO`: a non-blocking trace for audit, telemetry, or follow-up review.

`StrategicResponsePass` is a useful current example in the tree. It shows
state-first lookup, escalation in strict profile, and clear issue codes.

## Next steps

- For the full checklist, see [Write Governance Pass](../how-to/write-governance-pass.md).
- For the API/contract surface, see the [Governance Passes reference](../reference/scientist/governance-passes.md).
- For the architectural rationale, see the [Governance Model](../explanation/governance-model.md).
