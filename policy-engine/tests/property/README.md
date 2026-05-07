# Property Tests

- Owner: team-quality
- Purpose: property-based and generative tests that validate invariants across product domains.
- Allowed contents: Hypothesis tests, generative strategies, invariant fixtures, and domain subtrees that mirror production package ownership.
- Local verification: `uv run pytest tests/property -q`
- Maintenance: generated examples and caches stay outside this directory; new high-volume domains need a local ownership document.
