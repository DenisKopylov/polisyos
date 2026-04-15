# tools/calibration

Calibration analysis helpers for comparing shard hypotheses and run telemetry.

Use the unified entry point:

```bash
polisyos-tools calibration --help
polisyos-tools calibration compare-shards /tmp/calibration
```

Operational rules:

- Treat missing shard telemetry as `no_data`, not as a successful zero result.
- JSON/JSONL parsing errors must include file and line context.
- Summary outputs are written atomically through shared filesystem helpers.
