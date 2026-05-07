# Architecture Directory

- Owner: team-architecture
- Purpose: repository-level contracts, baselines, gates, inventories, and exception ledgers that define the accepted layout and quality policy.
- Allowed contents: TOML/JSON/Markdown contracts, generated baseline snapshots, architecture evidence packs, and named subdirectories for gate-specific inventories.
- Local verification: `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json`
- Maintenance: keep contracts current with accepted topology changes; obsolete exceptions must include owner, rationale, and sunset before they remain here.
