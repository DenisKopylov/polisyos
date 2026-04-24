# tools/foundry

Canonical tooling surface for Foundry ABI maintenance tasks.

## Commands

| Command                        | Purpose                                                                            |
| ------------------------------ | ---------------------------------------------------------------------------------- |
| `generate_stubs.py`            | Regenerate `.pyi` stubs for the public Foundry methods API                         |
| `update_signature_baseline.py` | Refresh the committed Foundry signature baseline after an approved breaking change |

## Canonical usage

```bash
uv run polisyos-tools foundry generate-stubs
uv run polisyos-tools foundry update-signature-baseline
```

Legacy `scripts/generate_stubs.py` and `scripts/update_signature_baseline.py`
remain as thin compatibility wrappers only.
