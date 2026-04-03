# Contributing to PolicyOS Policy Engine

## Development Environment

The supported contributor baseline is Python 3.14.x, Node 22.x, with `uv 0.9.21` as the canonical
Python environment manager. `.python-version`, `pyproject.toml`, CI, and contributor docs are
expected to stay aligned to that single baseline.

```bash
./scripts/bootstrap
./scripts/doctor
./scripts/verify
./scripts/ci-parity --skip-browser
```

If you need the manual path instead of the repo-local scripts:

```bash
uv sync --frozen --extra lint --extra test --extra runtime
uv run pre-commit install
cd frontend/runtime-dashboard && npm ci --ignore-scripts && npm run playwright:install
```

Optional dependency groups in `pyproject.toml`:

- `lint`: mypy, pre-commit, ruff, and typeshed glue for contributor checks.
- `docs`: MkDocs Material and `mkdocstrings[python]`.
- `test`: pytest, pytest-asyncio, pytest-benchmark, hypothesis, and runtime HTTP test deps.
- `runtime`: the backend contributor umbrella (`runtime-http`, observability, structured logging).
- `research`: the full causal/research umbrella used for heavyweight Foundry/Scientist work.
- `all`: curated capability umbrella for broad product features; it is not the contributor meta-install.

Tiered bootstrap profiles map to the same surfaces:

- `minimal`: `lint + test`
- `docs`: `lint + docs`
- `runtime`: `lint + test + runtime`
- `research`: `lint + test + runtime + research`

System notes:

- JAX CPU works out of the box in the default dev setup.
- Apple Silicon environments may opt into `policy-engine[apple-metal]`; if the Metal backend
  becomes unstable, set `JAX_PLATFORMS=cpu`.
- GPU and accelerator dependencies stay opt-in; if you change them, document the expected local and
  CI environment in the PR.
- `./scripts/doctor --list-surfaces` prints optional env surfaces that the workstation doctor knows
  how to validate.

## Code Style

- Ruff is configured in `pyproject.toml` with `line-length = 100`, `target-version = "py314"`, and
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
- Public surface source of truth: `architecture/public_surface.toml`
- Public surface inventory: `architecture/public_surface_inventory.json` and `docs/reference/public-surface.md`
- Generated artifact lifecycle source of truth: `architecture/generated_artifacts.toml`
- Generated artifact reference map: `docs/reference/generated-artifacts.md`
- Workflow/toolchain baseline guardrail: `.github/workflows/abi.yml`
- CI/CD operating model: `docs/how-to/operate-ci-cd-platform.md`
- Fast PR enforcement: `.github/workflows/abi.yml`
- Standard PR enforcement: `.github/workflows/ci.yml`
- Nightly platform assurance: `.github/workflows/frontend-nightly.yml`
- Release policy workflow: `.github/workflows/release.yml`
- Temporary exceptions registry: `import_exceptions.toml` with human-readable sync in
  `import_exceptions_registry.md`
- Deep-import creep baseline: `architecture/deep_import_baseline.json`
- Architecture guardrail temporary exceptions: `architecture/guardrail_exceptions.toml` with human-readable sync in
  `architecture/guardrail_exceptions_registry.md`
- Golden-path scaffolds: `tools/architecture/scaffold.py`

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

- `abi.yml` is the Fast PR lane: workflow governance, dependency review, import/docs/schema drift,
  fast unit checks, and ABI drift.
- `ci.yml` is the Standard PR lane: runtime HTTP, frontend quality/a11y, contract drift,
  smoke tests, and integration.
- `frontend-nightly.yml` is the Nightly lane: benchmark contours, bundle/lighthouse visibility,
  scheduled dependency audits, and OpenSSF Scorecard.
- `release.yml` is the Release lane: reproducible artifacts, release notes, SBOM/vulnerability
  policy, canary, attestations, and publish.

## PR Process

- Use branch names that match the change type: `feature/...`, `fix/...`, `docs/...`.
- Commit messages may be Russian or English, but they should describe the change clearly.
- Use the repository PR template in `.github/PULL_REQUEST_TEMPLATE.md`.
- Apply the label taxonomy from `.github/labels.yml`: at least one `kind:*`, exactly one
  `compat:*`, and exactly one `release:*`.
- If a documented package entrypoint changes, record whether the touched surface is
  `public_stable`, `public_experimental`, or `internal`.
- Required checks and merge expectations live in `docs/reference/quality-gates.md` and
  `docs/reference/merge-governance.md`.
- New subsystems and major surfaces must satisfy `docs/reference/ratchet-policy.md` and the
  Phase 7 ratchet section in the PR template.
- The default branch-protection bar is green `Fast PR / Gate` and `Standard PR / Gate`.
- Ask subsystem owners for review when a PR crosses package boundaries or changes contracts.
- Merge only after CI is green and all blocking review comments are resolved.
- Cross-boundary rollout PRs must include a `Migration owner`, rollout checklist, and release
  fragment.

## Release and Compatibility

- Version namespaces and deprecation rules live in `docs/how-to/release-policy.md`.
- If a release fragment is required for a public-surface change, include
  `surface_classification` alongside compatibility/migration notes.
- Treat architecture milestones (`Phase`, `WS`, ADR sequence) as planning vocabulary, not as
  package, schema, or runtime API versions.
- Supported release branches and security-reporting expectations live at repository root in
  `SECURITY.md` and `SUPPORT.md`.

## Documentation Requirements

- Every public class, function, and module needs a Google-style docstring.
- A new module under `src/polisyos/**` should update the nearest parent `README.md`.
- Major subsystem READMEs must keep `Where to Start` current when the recommended entrypoints move.
- Public facade changes should regenerate `docs/reference/public-surface.md`.
- Generated artifact lifecycle changes should update `architecture/generated_artifacts.toml` and regenerate
  `docs/reference/generated-artifacts.md`.
- A new IR type should be exported via `src/polisyos/ir/__init__.py` and verified against the ABI
  snapshot flow.
- A new connector should follow `docs/connectors/CONTRIBUTING.md`.
- Operator-visible, compatibility-sensitive, or rollout-sensitive changes should add or update a
  fragment under `release-fragments/unreleased/`.
- Release prep must freeze those entries into `release-fragments/releases/<version>/` before the
  tag is cut.

## Links

- `docs/connectors/CONTRIBUTING.md`
- `docs/style-guide.md`
- `docs/explanation/freeze-policy.md`
- `docs/reference/quality-gates.md`
- `docs/reference/merge-governance.md`
- `docs/reference/ratchet-policy.md`
- `docs/how-to/operate-ci-cd-platform.md`
- `docs/reference/operations/platform-acceptance-audit.md`
- `docs/how-to/review-rollouts.md`
- `docs/how-to/release-policy.md`
