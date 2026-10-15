# Write a Governance Pass

> Implement, register, test, and connect a new Scientist governance pass using
> the current pass API.

Freshness: 2026-10-14.

Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; read-only inspection of
`src/polisyos/core/governance/passes/base.py`,
`src/polisyos/scientist/governance/pass_entrypoints.py`,
`src/polisyos/scientist/governance/pass_registry.py`,
`src/polisyos/scientist/governance/passes/strategic_response_pass.py`,
`tools/devx/architecture/templates/governance_pass.py.tmpl`, and the referenced
tests. Tests and scaffold were not run. This supersedes the previous 2026-04-17
freshness marker and is not a runtime receipt.

This page covers pass registration and integration. The tutorial [Creating a
Governance Pass](../tutorials/creating-governance-pass.md) is a separate
blocker-only worked example: it describes warning/info guidance, but the shown
test does not cover those cases.

## Inputs

- an invariant that the pass must check;
- a decision about whether the pass is built-in only or canonical for an
  observation family;
- the minimum artifact/state key from which the pass can produce a deterministic
  verdict.

## Outputs

- a pass class and factory registration;
- unit tests for blocker/warning semantics;
- alias/policy wiring if the pass is part of the canonical governance surface;
- an updated reference page if the pass creates a new auditable claim.

## Commands

```bash
uv run polisyos-tools architecture scaffold governance-pass \
  --name my_pass \
  --output src/polisyos/scientist/governance/passes/my_pass.py \
  --test-output tests/unit/scientist/governance/test_my_pass.py \
  --dry-run
uv run pytest tests/unit/scientist/governance -x --tb=short
uv run --extra docs python -m mkdocs build --strict
```

Quick start for the skeleton:

```bash
uv run polisyos-tools architecture scaffold governance-pass \
  --name my_pass \
  --output src/polisyos/scientist/governance/passes/my_pass.py \
  --test-output tests/unit/scientist/governance/test_my_pass.py \
  --dry-run
```

## 1. Implement the pass interface

The current base types are:

- `PassContext`
- `ValidatorPass`
- `ComplianceIssue`
- `IssueSeverity`

Use the actual interface from `polisyos.core.governance.passes.base`:

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

Scaffold is a placeholder, not a severity contract: the pinned template returns
`IssueSeverity.WARNING` for its TODO artifact lookup. The hand-written blocker
example above intentionally demonstrates a stronger gate. Replace the TODO,
choose severity from the actual workflow consequence, and test both the refused
and accepted paths before treating a new pass as a governance gate.

For a small real example to study, start with:

- `src/polisyos/scientist/governance/passes/strategic_response_pass.py`

This pass shows:

- how to read state;
- how to distinguish a blocker from a warning;
- how to request human review in strict mode.

## 2. Understand `ComplianceIssue`

The current issue model supports:

- `IssueSeverity.INFO`
- `IssueSeverity.WARNING`
- `IssueSeverity.BLOCKER`

Useful fields:

- `pass_id`
- `path`
- `message`
- `severity`
- `code`
- `suggestion`
- `input_value`

Practical interpretation of severity:

- `BLOCKER`: the run cannot proceed.
- `WARNING`: the run can proceed, but the risk must be shown to the operator.
- `INFO`: a non-blocking audit signal or human-review request.

## 3. Read state and artifacts

`PassContext` currently provides access to:

- `ir`: an optional `TrinityBundle`;
- `state`: mutable workflow state dictionary
- `registry_bundle`: an optional registry object;
- `profile`: `ValidationProfile`
- `run_id`: the current run ID.

Typical read pattern:

```python
def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
    state = ctx.state

    summary = state.get("my_summary")
    artifacts_index = state.get("artifacts_index", {})
    params = state.get("params", {})

    if summary is None and "my_bundle_ref" in artifacts_index:
        ...
```

The two most common patterns in existing passes are:

- read an already materialized summary directly from `ctx.state`;
- retrieve a CAS artifact reference from `ctx.state["artifacts_index"]` and use
  it to load the full bundle.

## 4. Register the pass

There are currently two registration surfaces.

### Built-in pass in this repository

If the pass lives directly in this repository:

1. Add the class under `src/polisyos/scientist/governance/passes/`.
2. Add a factory in `src/polisyos/scientist/governance/pass_entrypoints.py`.
3. Export the class from `src/polisyos/scientist/governance/passes/__init__.py`.

The runtime uses these built-in fallback factories when external entry points
are not found.

### External or plugin pass

Entry-point group:

```text
polisyos.scientist_governance_passes
```

The target entry point must resolve to one of:

- a `ValidatorPass` subclass with a zero-argument constructor; or
- a zero-argument factory that returns a `ValidatorPass`.

Duplicate `pass_id` values are rejected during loading.

## 5. Test the pass

In the example below, the test creates `PassContext` directly; use the project's
current helper functions if they fit the new pass.

Pattern from `tests/unit/scientist/governance/test_strategic_response_pass.py`:

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

Useful examples to study:

- `tests/unit/scientist/governance/test_strategic_response_pass.py`
- `tests/unit/scientist/governance/test_pass_registry.py`

## 5a. Record the evidence contract

Any new governance pass that supports a causal, fairness, calibration,
accountability, or SOTA-facing claim must have an explicit connection to an
artifact or test:

- blocker/warning semantics are covered by a unit test;
- the new `pass_id` is documented in [Scientist Governance
  Passes](../reference/scientist/governance-passes.md) if the pass becomes
  built-in or canonical;
- claim-level output writes a `ComplianceIssue`, `GovernanceReport`,
  `CalibrationValidationBundle`, `scientist.governance_accountability_artifact`
  or another persisted artifact;

- benchmark or evaluation evidence exists before the pass is used to support a
  SOTA/default-readiness claim.

Minimum checks:

```bash
uv run pytest tests/unit/scientist/governance/test_my_pass.py -q
uv run pytest tests/unit/scientist/governance/test_pass_registry.py -q
```

## 6. Integrate the pass into the workflow

`polisyos.ir.observation.governance` currently has two related registries:

- `GovernancePassAliasRegistry`
- `ObservationFamilyPolicyRegistry`

How they work:

- `GovernancePassAliasRegistry` maps stable canonical pass names to runtime
  pass IDs.
- `ObservationFamilyPolicyRegistry` determines which canonical pass IDs are
  required for a specific observation family.

This means that pass inclusion in the workflow is currently family-driven, not
controlled through a direct field in `PolicySpec`.

If the new pass should become part of the canonical governance surface:

1. Add an alias to `GovernancePassAliasRegistry.default()`.
2. Add the canonical alias name to the appropriate `mandatory_governance_passes`
   in `ObservationFamilyPolicyRegistry.default()`.

Example:

```python
GovernancePassAlias(
    canonical_pass_id="my_check",
    runtime_pass_id="my_check",
    status=GovernancePassAliasStatus.RUNTIME,
)
```

## 7. Real example: `StrategicResponsePass`

`StrategicResponsePass` is a useful pattern because it is:

- small enough to read quickly;
- current enough to reflect the runner/artifact patterns in use;
- explicit about blocker, warning, and human-review escalation.

It demonstrates:

- state-first lookup with an artifact fallback;
- escalation in strict profile through `ctx.state["human_review_request"]`;
- clear `ComplianceIssue.code` values.

## Rollback

If the pass should not enter the tree or its canonical policy is not ready:

1. Remove the factory registration and package-facade export.
2. Revert the alias/policy wiring in `polisyos.ir.observation.governance`.
3. Remove the reference updates if the pass does not create an auditable surface
   in this PR.

## Troubleshooting

- If the pass does not run, first check `pass_entrypoints.py` and `__all__`, not
  the workflow code.
- If the pass appears in the runtime registry but is not part of the canonical
  family policy, check `GovernancePassAliasRegistry` and
  `ObservationFamilyPolicyRegistry`.
- If severity behaves unexpectedly, check `ValidationProfile` and the exact
  state key read by the pass.

## Checklist

- the pass class is created;
- `pass_id` is unique;
- the factory or entry point is registered;
- tests are added;
- the alias registry is updated if the pass is part of canonical observation
  policy;
- the observation-family policy is updated if the pass should run by default
  for that family;
- reference documentation is updated if the pass adds a new auditable
  governance claim;
- benchmark/evaluation requirements are recorded before making a
  SOTA/default-readiness claim.

## Related files

- `src/polisyos/core/governance/passes/base.py`
- `src/polisyos/scientist/governance/pass_registry.py`
- `src/polisyos/scientist/governance/pass_entrypoints.py`
- `src/polisyos/scientist/governance/passes/__init__.py`
- `src/polisyos/scientist/governance/passes/strategic_response_pass.py`
- `src/polisyos/ir/observation/governance.py`
- `docs/reference/scientist/governance-passes.md`
- `docs/reference/scientist/calibration-governance.md`
- `docs/reference/scientist/reliability-scorecard.md`
