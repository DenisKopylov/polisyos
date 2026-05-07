# Scientist Methods Unit Tests

- Owner: team-scientist
- Purpose: unit coverage for canonical Scientist method packages, including research DAG, discovery, search, and method shims.
- Allowed contents: package-mirrored method tests, local fixtures, compatibility tests, and method contract assertions.
- Local verification: `uv run pytest tests/unit/scientist/methods -q`
- Maintenance: canonical paths live under `src/polisyos/scientist/methods`; legacy method shims need dated sunset evidence.
