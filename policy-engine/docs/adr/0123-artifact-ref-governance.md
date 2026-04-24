# ADR-0123: ArtifactRef Governance Metadata

## Status

Proposed

## Date

2026-04-18

## Context

Every Data Forge output — raw capture, normalized record, SKG batch, DAG,
snapshot — is referenced by an `ArtifactRef`. Today the ref carries `uri` and
`sha256` only. SOTA platforms (Databricks UC, Atlan, DataHub) require every
artifact reference to carry enough metadata for:

- ownership and compliance (owner, license, PII class);
- lineage (producer version, input ArtifactRefs, trace ID);
- schema and contract binding (schema_id, schema_version);
- operational policy (retention class, freshness SLA, access class);
- reproducibility (producer pipeline run, git SHA, model hashes).

Without this on the ref, governance, audit, and debugging require out-of-band
lookups that do not survive archival.

## Decision

Extend `ArtifactRef` (IR contract) with a mandatory governance block. The
schema is declared in `polisyos.ir.artifact.ArtifactRef` and versioned under
ADR-0114 / ADR-0005:

| Field              | Type          | Required | Notes                                                 |            |                |              |              |
| ------------------ | ------------- | -------- | ----------------------------------------------------- | ---------- | -------------- | ------------ | ------------ |
| `uri`              | string        | yes      | CAS URI or lakehouse path.                            |            |                |              |              |
| `sha256`           | hex string    | yes      | Content hash.                                         |            |                |              |              |
| `schema_id`        | string        | yes      | Logical name of the payload schema.                   |            |                |              |              |
| `schema_version`   | semver string | yes      | Matches the schema registry.                          |            |                |              |              |
| `producer`         | string        | yes      | Fully qualified asset/stage identifier.               |            |                |              |              |
| `producer_version` | string        | yes      | Release version of the producer code.                 |            |                |              |              |
| `git_sha`          | string        | yes      | Commit SHA that produced the artifact.                |            |                |              |              |
| `trace_id`         | string        | yes      | W3C OTel trace id of the run (ADR-0116).              |            |                |              |              |
| `snapshot_id`      | string        | yes      | Parent lakehouse snapshot (ADR-0122).                 |            |                |              |              |
| `inputs`           | list[ref]     | yes      | Upstream ArtifactRefs consumed.                       |            |                |              |              |
| `owner`            | string        | yes      | Team identifier.                                      |            |                |              |              |
| `license`          | SPDX string   | yes      | Distribution license of the payload.                  |            |                |              |              |
| `pii_level`        | enum          | yes      | `none \                                               | low \      | medium \       | high \       | restricted`. |
| `retention_class`  | enum          | yes      | `ephemeral \                                          | standard \ | long_lived \   | regulated`.  |              |
| `access_class`     | enum          | yes      | `public \                                             | internal \ | confidential \ | restricted`. |              |
| `freshness_sla`    | duration      | yes      | Max age after which the artifact is considered stale. |            |                |              |              |
| `signature`        | detached sig  | opt      | Ed25519 signature per ADR-0010.                       |            |                |              |              |
| `tags`             | map[str,str]  | opt      | Free-form governance tags.                            |            |                |              |              |

Validation is enforced at three boundaries: writers (reject missing fields),
read_api (reject unsafe combinations — e.g. `pii_level=restricted` to a
`public` consumer), and CI schema-drift gate (ADR-0114).

## Consequences

- Governance, audit, and lineage queries become pure local reads on the ref.
- Consumers can enforce policy without callbacks.
- Retro-filling existing artifacts requires a migration pass before Phase 3.
- Runtime ref payload grows; a canonical JSON form and a CBOR form are both
  maintained to keep transport costs bounded.

## Related Decisions

- Extends: ADR-0010 (CAS signing), ADR-0021 (connector schema contracts),
  ADR-0104 (IR canonical CAS policy), ADR-0108 (IR schema catalog).

- Depends on: ADR-0114 (schema registry), ADR-0116 (OTel observability),
  ADR-0122 (lakehouse snapshots).

- Related: ADR-0105 (Trinity linking), ADR-0062 (knowledge snapshot id input ref).
