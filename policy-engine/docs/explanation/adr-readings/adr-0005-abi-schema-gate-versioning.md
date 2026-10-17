# English reader translation of ADR-0005: ABI versioning gate via JSON Schema snapshots

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0005-abi-schema-gate-versioning.md`

This page translates the decision text in the [source ADR](../../adr/0005-abi-schema-gate-versioning.md), whose SHA-256 is
`29f805a0fa15037dd3aca9b35403e54468e6fc5b97871e15a2712a8a56b04730`.
The generated ADR index reports the source status as `accepted` at the source
pin. This derivative does not ratify or revise the decision and does not
establish that the decision was implemented.

- **Date:** 2026-02-06
- **Status in source:** Accepted
- **Decision:** Introduce a mandatory ABI CI gate based on committed JSON
  Schema snapshots, semantic diffs, and a `schema_version` major-version bump
  check for breaking changes.

## Context

Contract models in `polisyos.ir.*` and the world ABI dictionaries / enums
(`EdgeKind`, `NodeKind`) are used as a cross-layer ABI by Foundry, Scientist,
Lex, Scholar, and Fabric.

Before this ADR:

- `tools/quality/diagnostics/gen_schema.py` was a single-purpose tool focused
  on the outdated `PolicySurfaceIR`.
- There was no semantic diff distinguishing breaking from non-breaking
  changes.
- There was no automated check that a breaking change received the correct
  version bump.

## Decision

1. Store ABI model definitions in `src/polisyos/schemas/abi_models/__init__.py` for definitions, public API, and selectors, and keep registered entries in `catalog.py`.
2. Store snapshot artifacts under `schemas/snapshots/{ir,fabric}` with
   `_manifest.json`.
3. `tools/quality/diagnostics/gen_schema.py`:
   - generates snapshots from the ABI registry;
   - supports `--check`;
   - writes a manifest with `priority`, `compat_mode`,
     `schema_version`, `sha256_full`, and `sha256_semantic` fields.
4. `tools/quality/diagnostics/abi_diff.py`:
   - builds semantic diffs;
   - classifies changes;
   - checks for a major-version bump on breaking changes (`p0`);
   - produces JSON / Markdown / GitHub reports.
5. The CI workflow `.github/workflows/abi.yml`:
   - generates current snapshots;
   - compares them with baseline snapshots from the PR base SHA;
   - publishes a sticky report;
   - blocks merge when the verdict is `FAIL`.

## Compatibility Profiles

Each ABI entry in `src/polisyos/schemas/abi_models/catalog.py` has a
`compat_mode`:

- `strict`: adding fields counts as breaking (relevant to contracts whose
  consumers may validate with `additionalProperties=false`).
- `tolerant`: optional additive changes are allowed as compatible.

## Versioning Rules

- A breaking change (`p0`) requires a major-version bump:
  `X.Y -> (X+1).0` or `major` greater than the baseline major.
- Breaking changes (`p1/p2`) raise a warning.
- Metadata-only changes (`title/description/...`) do not require a bump.

## Rename Handling

`abi_diff` first matches models by `abi_key`, then by `aliases`, and then
uses `sha256_semantic` / similarity as a fallback.

## Consequences

### Advantages

- ABI regressions are detected early, before merge.
- Contract changes have a verifiable history.
- Strict / tolerant compatibility policy is explicit.

### Disadvantages

- Developers have an additional step: maintain snapshots in the commit.
- The repository grows (schema snapshots + manifests).

### Risks

- Pydantic / Python upgrades may change schema generation.
- Classification edge cases may produce false warnings.

### Mitigations

- Pin the CI environment (Python 3.11) and update snapshots atomically.
- Maintain unit tests for `abi_diff` classification.
- Use per-entry `compat_mode` for precise semantics.

## Related Decisions

- Extended by: ADR-0114 (schema registry and evolution rules), ADR-0123
  (ArtifactRef governance metadata).
