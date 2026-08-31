# Scientist Replay

Replay owns deterministic re-execution, dead-letter replay, semantic diffs, and
replay verification reports for Scientist runs.

Use this hub for:

- deterministic replay planning, completeness, and verification contracts in
  `deterministic.py`;
- replay backend execution and dead-letter inspection;
- semantic diff models and comparators;
- replay verification reports and registries.

`polisyos.runtime.replay` is a compatibility facade over `deterministic.py`.
New first-party replay consumers use the Scientist-owned module directly.

Do not add new modules under `polisyos.scientist.replay.backend`. The retired legacy module
is a Phase 4.4 compatibility shim for `polisyos.scientist.replay.backend` and
sunsets on 2026-11-30.

Tests live under `tests/unit/scientist/replay`.
