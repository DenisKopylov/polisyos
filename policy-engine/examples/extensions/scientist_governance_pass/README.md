# Scientist Governance Pass Extension Example

This package shows the supported external author interface for
`polisyos.scientist_governance_passes`.

External packages expose exactly one entry point in `pyproject.toml`. The entry
point returns a zero-argument factory for a `ValidatorPass` implementation.

```toml
[project.entry-points."polisyos.scientist_governance_passes"]
"example.audit_marker" = "polisyos_scientist_governance_pass_example:audit_marker_pass_factory"
```

Smoke test:

```bash
python -m pip install -e examples/extensions/scientist_governance_pass
python -m pytest examples/extensions/scientist_governance_pass/tests -q
```
