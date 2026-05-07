# Unit Tests

- Owner: team-quality
- Purpose: fast, isolated tests that mirror the canonical product package layout.
- Allowed contents: unit tests, local fixtures, package mirror directories, and authoring docs for high-volume test areas.
- Local verification: `uv run pytest tests/unit -q`
- Maintenance: keep new tests in package-mirrored locations unless an architecture test topology exception names the owner and sunset.
