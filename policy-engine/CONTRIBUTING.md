# Contributing to PolicyOS Policy Engine

## Development Environment

The current local baseline is Python 3.14+; on macOS that usually means Homebrew Python. The
package metadata still declares `>=3.11`, but the active development workflow in this repository is
already exercised on Python 3.14.

```bash
pip install -e ".[dev,test,all]"
pytest tests/ -x --tb=short
```

Using a virtual environment is optional, but strongly recommended on Homebrew-managed Python
installations:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Optional dependency groups in `pyproject.toml`:

- `dev`: pytest, pytest-asyncio, pytest-benchmark, hypothesis, mypy, pre-commit, ruff,
  `types-requests`, MkDocs tooling (`mkdocs`, `mkdocs-material`, `mkdocstrings[python]`),
  JupyterLab, matplotlib, seaborn, structlog, mutmut.
- `test`: the shared pytest stack plus `policy-engine[runtime-http]`.
- `all`: umbrella extra that pulls in every current feature extra, including `dev` and `test`
  together with runtime, causal, security, search, analytics, ML, optimization, observability,
  RAG, table-extraction, and related optional stacks.

System notes:

- JAX CPU works out of the box in the default dev setup.
- Apple Silicon environments may prefer `jax-metal`; if the Metal backend becomes unstable, set
  `JAX_PLATFORMS=cpu`.
- GPU and accelerator dependencies stay opt-in; if you change them, document the expected local and
  CI environment in the PR.

## Code Style

- Ruff is configured in `pyproject.toml` with `line-length = 100`, `target-version = "py311"`, and
  the active rule sets `E`, `F`, `I`, `B`, `T20`, `N`.
- Public APIs must be fully type-annotated.
- Public Pydantic DTOs and contracts should use `ConfigDict(extra="forbid")`; in IR this is often
  inherited through shared base models such as `KernelModel`.
- Heavy or boundary-sensitive modules should be imported lazily via `if TYPE_CHECKING`,
  function-local imports, or package-level `__getattr__` facades. See `src/polisyos/fabric/__init__.py`,
  `src/polisyos/runtime/__init__.py`, and `src/polisyos/scientist/api.py` for the prevailing pattern.
- Use Google-style docstrings. The documentation conventions live in `docs/style-guide.md`.

## Testing

- Keep `tests/` structurally aligned with `src/`: `tests/<layer>/...` should mirror
  `src/polisyos/<layer>/...`.
- Test files follow `test_<module>.py`.
- Test functions follow `test_<scenario>()`.

Common fixtures and helpers:

- `runtime_api_env` and `build_runtime_api_env()` for FastAPI/runtime integration coverage.
- `store`, `cas_root`, and artifact helpers from `tests/fixtures/artifacts.py` for CAS-oriented
  tests.
- `in_memory_exporter`, `test_tracer`, and `test_tracer_provider` for observability assertions.
- `build_c7_synthetic_fixture()` and `persist_c7_synthetic_snapshot()` for synthetic observation /
  calibration flows used in integration and advanced Scientist tests.

Markers and decorators in active use:

- Registered markers in `pyproject.toml`: `integration`, `benchmark`, `property`.
- Common decorators in the suite: `pytest.mark.asyncio`, `pytest.mark.hypothesis`.
- `slow` is not currently registered as a standard repo-wide marker, so prefer the declared markers
  above unless you are introducing and wiring a new convention deliberately.

## Architecture Governance

- Freeze policy: `docs/explanation/freeze-policy.md`
- Import gate source of truth: `import_policy.toml`
- CI enforcement: `.github/workflows/arch-freeze.yml`
- Temporary exceptions registry: `import_exceptions.toml` with human-readable sync in
  `import_exceptions_registry.md`

Core import expectations:

| Module | May import | Must not import |
|---|---|---|
| `common` | `common` | other `polisyos.*` packages |
| `ir` | `ir`, `datasets`, allowlisted externals | `foundry`, `scientist`, `fabric`, `lex`, `runtime` |
| `core` | `core`, `ir`, `common` | upper product layers on runtime paths |
| `fabric` | `fabric`, `core`, `ir`, `common` | `scientist`, `foundry` |
| `foundry` | `foundry`, `academic`, `core`, `ir`, `common` | `scientist`, `runtime`, `lex`, `fabric` |
| `scientist` | `scientist`, `lex`, `foundry`, `fabric`, `runtime`, `core`, `ir`, `common`, `academic`, `datasets` | private or deep imports without an approved exception |
| `runtime` | `runtime`, `scientist`, `lex`, `foundry`, `fabric`, `core`, `ir`, `common` | unrelated research or batch layers |
| `lex` | `lex`, `batch_common`, `fabric`, `ir`, `core`, `common` | `scientist` / `foundry` without a registered exception |

CI responsibilities:

- `arch-freeze.yml` tracks boundary drift, exception expiry, deep-import drift, and freeze metrics.
- `arch.yml` runs import-gate linting, Foundry purity checks, Scientist state-read validation, ABI
  checks, runtime/frontend drift checks, and connector architecture lint.

## PR Process

- Use branch names that match the change type: `feature/...`, `fix/...`, `docs/...`.
- Commit messages may be Russian or English, but they should describe the change clearly.
- Required checks depend on scope, but the default bar is green `arch-freeze.yml`, `arch.yml`,
  `abi.yml`, `perf.yml`, and the relevant test workflows such as `causal-phases.yml` or
  `replay.yml`.
- Ask subsystem owners for review when a PR crosses package boundaries or changes contracts.
- Merge only after CI is green and all blocking review comments are resolved.

## Documentation Requirements

- Every public class, function, and module needs a Google-style docstring.
- A new module under `src/polisyos/**` should update the nearest parent `README.md`.
- A new IR type should be exported via `src/polisyos/ir/__init__.py` and verified against the ABI
  snapshot flow.
- A new connector should follow `docs/connectors/CONTRIBUTING.md`.

## Links

- `docs/connectors/CONTRIBUTING.md`
- `docs/style-guide.md`
- `docs/explanation/freeze-policy.md`
