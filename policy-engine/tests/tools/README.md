# Tools Tests

`tests/tools` covers the executable tooling surface around `polisyos-tools`,
workspace automation, acceptance audits, architecture ratchets, and release
tooling. The slice currently contains `23` `test_*.py` files.

## Purpose

- Keep the canonical tool surface discoverable and testable from pytest.
- Catch regressions in workspace, release, architecture, and diagnostics gates.
- Provide a landing page for tool-focused tests without opening the tools docs.

## Where To Start

- [`../../tools/README.md`](../../tools/README.md)
- `test_unified_cli.py` for the canonical CLI surface.
- `test_acceptance_audit.py`, `test_workspace_phase3.py`, and
  `test_release_notes_tooling.py` for common contributor-facing failures.

## Public Entrypoints

- CLI and workspace gates:
  `test_unified_cli.py`, `test_workspace_phase3.py`,
  `test_core_runtime_closeout.py`, `test_core_runtime_long_soak.py`

- Architecture and quality ratchets:
  `test_architecture_phase3.py`, `test_lint_imports_phase3.py`,
  `test_phase4_consolidation.py`, `test_phase7_ratchet.py`

- Release/acceptance gates:
  `test_acceptance_audit.py`, `test_release_artifact_policy.py`,
  `test_release_notes_tooling.py`, `test_remote_acceptance.py`

## Depends On / Depended On By

### Depends On

- [`../../tools/README.md`](../../tools/README.md)
- [`../../docs/reference/tools.md`](../../docs/reference/tools.md)
- `tools/cli.py` and the zoned `tools/**` implementation tree

### Depended On By

- Contributor workflows such as `workspace verify`, `workspace ci-parity`, and
  acceptance audit flows

- Release and CI ratchets that rely on stable tool behavior

## Common Commands

Run commands from `policy-engine/`.

```bash
# conceptual: tooling slice
uv run pytest tests/tools -q

# conceptual: targeted CLI sanity
uv run pytest tests/tools/test_unified_cli.py -q
```

## Test And Verification Commands

The collect-only command below was smoke-checked on `2026-04-17`.

```bash
cd policy-engine
uv run pytest --collect-only tests/tools -q
```

## Reference Docs

- [`../../tools/README.md`](../../tools/README.md)
- [`../../docs/reference/tools.md`](../../docs/reference/tools.md)
- [`../TESTING_POLICY.md`](../TESTING_POLICY.md)

## Last Updated

2026-04-17
