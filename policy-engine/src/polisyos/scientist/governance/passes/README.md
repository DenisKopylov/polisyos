# Governance Passes (`polisyos.scientist.governance.passes`)

Owner: `team-scientist`
Last updated: 2026-05-05

## Purpose

This package contains builtin Scientist governance passes for safety,
freshness, privacy, equity, citation, transportability, refutation,
incentive-compatibility, human review, and related workflow gates.

## Public API

Public extension ABI is `polisyos.scientist_governance_passes` in
`architecture/extension_points.toml`. Builtin pass implementations remain
package-private unless exported by the pass registry.

## Internal Layout

| Path | Role |
| --- | --- |
| `base.py` | Shared pass protocol and context helpers. |
| `*_pass.py` | Builtin pass implementations. |
| `_artifact_resolution.py` | Private artifact lookup helper. |

## Extension Points

External passes use the `polisyos.scientist_governance_passes` entry-point
group and must return a validator-pass compatible object. Builtin pass
factories are declared in `pass_entrypoints.py` and mirrored in
`pyproject.toml` so installed packages and in-repo fallback discovery resolve
the same pass IDs.

## Tests

Use `tests/unit/scientist/governance/`, `tests/unit/scientist/nodes/`, and
Scientist integration tests when pass behavior affects workflow output.

## Operability Links

- `docs/reference/scientist/continuous-governance.md`
- `docs/reference/scientist/human-oversight.md`
- `architecture/extension_points.toml`

## Known Shims/Deprecations

Pass ID renames require registry compatibility and a release/migration note
when saved workflow specs can reference the old ID.
