# Architecture Directory

- Owner: team-architecture
- Purpose: repository-level contracts, baselines, gates, inventories, and exception ledgers that define the accepted layout and quality policy.
- Allowed contents: repository-wide root contracts plus named taxonomy subdirectories for gates, packages, imports, public surfaces, tests, baselines, tooling, exceptions, and policies.
- Local verification: `uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json`
- Maintenance: keep contracts current with accepted topology changes; obsolete exceptions must include owner, rationale, and sunset before they remain here.

The taxonomy source is `architecture/index.toml`. A root-level TOML file must not
use a domain prefix already assigned to a subdirectory unless it is a canonical
root contract listed in that index. Gate source contracts live under
`architecture/gates/**` and are indexed by gate ID in
`architecture/gates/index.toml`.
