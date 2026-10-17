# Getting Started

English edition: 2026-10-14 (translation only; not a source-freshness or execution claim).
Owner: `@docs-owners`
Source of truth: `pyproject.toml`, `.python-version`, `.nvmrc`, `package.json`,
`tools/devx/workspace/{_common,bootstrap,doctor}.py`, `src/polisyos/foundry/_internal/quickstart.py`,
`src/polisyos/ir/__init__.py`, `src/polisyos/foundry/__init__.py`,
`docs/reference/policy-design-case-failure-patterns.md`.
Source snapshot: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`;
`src/polisyos/` production implementation unchanged.
Review basis: command/source paths inspected; tests, examples, installs and runtime were not run
for this edit.

> Set up the development environment, check the import surface, and run a minimal
> `compile -> execute` smoke path.

!!! info "Historical workstation receipt (2026-04-17)"
    A local macOS workstation (Apple Silicon) used Python 3.14.0, Node 22.22.2,
    and `uv 0.9.21`. At that time, `uv run polisyos --version`,
    `uv run python -c "from polisyos.ir import ProblemFrame; from polisyos.foundry import compile_program; print(ProblemFrame.__name__, callable(compile_program))"`
    and `python3 -m tools.cli workspace doctor --list-surfaces` were run. This is
    a dated receipt from one machine, not a rerun performed while updating this
    page.

Current command entry points are read from `pyproject.toml` and
`tools/registry.py`; their presence in source does not prove successful
execution. Only the callout above contains a historical execution receipt; the
expected and illustrative results below are not new receipts.

## What you need

- a clean `polisyos/policy-engine` checkout;
- Python `3.14.x`;
- `uv 0.9.21`.

This walkthrough uses backend-only bootstrap and does not require the Node
workspace. A full runtime/frontend profile requires Node `22.x`, Corepack, and
pnpm `10.33.2`; see the [Environment Matrix](../reference/environment-matrix.md)
for the supported versions.

## What you will get

- a locally working CLI and import surface;
- a first CAS-backed Foundry smoke run;
- a clear next step for your role: backend, frontend, platform, security, or
  domain/policy.

## 1. Clone the repository and set up the minimal contributor path

```bash
git clone https://github.com/DenisKopylov/polisyos.git
cd polisyos/policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
```

The `runtime` profile synchronizes the `lint + test + runtime` extras;
`--skip-frontend` skips the Node check and JS workspace installation. Bootstrap
still installs the pre-commit hook unless you add `--skip-hooks`. `--skip-doctor`
prevents the automatic `doctor` run, which would independently check Node,
Playwright, lockfiles, and generated contracts. This walkthrough deliberately
uses the backend-only path. The full installation matrix, frontend bootstrap,
and troubleshooting steps are in [Installation](../how-to/install.md).

## 2. Check the CLI and import surface

```bash
uv run polisyos --version
```

Expected output:

```text
polisyos 0.1.0
```

```bash
uv run python -c "from polisyos.ir import ProblemFrame; from polisyos.foundry import compile_program; print(ProblemFrame.__name__, callable(compile_program))"
```

Expected output:

```text
ProblemFrame True
```

If something fails at this step, see
[Installation](../how-to/install.md#troubleshooting).

## 3. Run the minimal compile-and-execute example

In the current source tree, the `run_trivial_compile_execute` helper shows a
short compile-and-execute path with a filesystem CAS. A broader workflow is
described in the
[Foundry Compile/Execute reference](../reference/foundry/compile-execute.md) and the
[First Policy Analysis](first-policy-analysis.md) tutorial.

```python
from pathlib import Path

from polisyos.foundry._internal.quickstart import run_trivial_compile_execute

cas_root = Path(".polisyos/quickstart-cas")
result = run_trivial_compile_execute(cas_root=cas_root)
print("compile_ok:", result.compile_ok)
print("execute_ok:", result.execute_ok)
print("exec_plan_artifact:", result.exec_plan_artifact_id)
print("simulation_result_artifact:", result.simulation_result_artifact_id)
print("cas_root:", cas_root)
```

The helper sets CPU-first JAX defaults if the corresponding environment
variables are not already set:

- `JAX_PLATFORM_NAME=cpu`
- `JAX_PLATFORMS=cpu`

This helps with a first run on Apple Silicon; explicit environment values are
preserved, and Metal remains opt-in through the `apple-metal` extra.

Illustrative output; this is not a fresh-run receipt:

```text
compile_ok: True
execute_ok: True
exec_plan_artifact: sha256:...
simulation_result_artifact: sha256:...
cas_root: .polisyos/quickstart-cas
```

!!! note "P02 / E02 F: boundary of this smoke path"
    The import check and quickstart-helper call do not prove that a neutral
    installed consumer reads curated defaults from a packaged artifact, and they
    do not close E02 F. An installed-default check requires such a consumer and
    bindings for all terminal catalog resources from tracked source bytes through
    the sdist and wheel; details are defined by the
    [P02 installed-default consumer discriminator](../reference/policy-design-case-failure-patterns.md).

This quickstart is a short Foundry demo path. Even successful `compile_ok` and
`execute_ok` results are not the outcome of a policy analysis, evidence
admissibility, or authorization to publish a recommendation.

## 4. Inspect the artifacts that were created

After running, quickstart prints `cas_root`; the example above stores it in the
local, gitignored `.polisyos/quickstart-cas` directory so the next step can read
the manifests.

List the manifests:

```bash
CAS_ROOT=.polisyos/quickstart-cas
find "$CAS_ROOT/artifacts" -name '*.manifest.json' | head
```

Read `kind` and `artifact_id`:

```python
import json
from pathlib import Path

cas_root = Path(".polisyos/quickstart-cas")

for manifest_path in sorted(cas_root.glob("artifacts/**/*.manifest.json")):
    manifest = json.loads(manifest_path.read_text())
    print(manifest["kind"], manifest["artifact_id"])
```

You will usually see at least:

- `foundry.exec_plan`
- `foundry.simulation_result`
- `foundry.metrics`
- `foundry.state_snapshot`

## 5. Run a fast local gate

```bash
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

This step is not required for the smoke tutorial, but it is a useful signal that
the development surface is ready for initial changes.

## Next steps

- If you are a new contributor, start with
  [Installation](../how-to/install.md) and
  [Contributor Start Here](../reference/contributor-start-here.md).

- For a first analytical walkthrough, open
  [First Policy Analysis](first-policy-analysis.md).

- For role-based onboarding, choose the appropriate track in
  [Onboarding Tracks](../how-to/onboarding/index.md).
