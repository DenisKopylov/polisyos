# Scientist Node Example

Install this package in editable mode to exercise the public
`polisyos.scientist_nodes` entry-point contract:

```bash
python -m pip install -e examples/extensions/scientist_node
polisyos components list --kind scientist_node --tag external-example
```

The node updates `ExperimentState.params` and returns a deterministic
`NodeOutcome` without external services.
