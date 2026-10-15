# Migration records

This is a repository-only index to migration records. It helps readers find
context; it does not promote a record into handbook navigation or certify that
a described migration is current. Use each record's own status, date, and
evidence. Where a record does not declare status or ownership, this index does
not supply it.

## Direct records

- [Data Forge shim sunset rollback](data_forge_shim_sunset_rollback.md) labels
  itself “active rollback notes,” dated 2026-05-02, and names `team-data-forge`.
  It describes rollback triggers and steps; this index does not verify the
  current release state.
- [Dataset manifest migration](dataset-manifest-migration.md) describes the
  format-only `DatasetManifest` 0.9-to-1.0 conversion and its compatibility
  boundary. It explicitly leaves historical-payload validation and provenance
  decisions separate.
- [TrinityBundle-only migration guide](phase4_trinity_only.md) documents the
  Phase 4 migration away from legacy surface IR. The guide itself does not
  establish the current runtime state.
- [Ukraine Part B Ops composition](ukraine-data-ops-entrypoint.md) records the
  candidate `ukraine-data` console composition, caller boundary, and the Linux
  installed-wheel/C7 verification that remains open.

## Dated archive

Browse [archive/2026-q1](archive/2026-q1/). The archive location identifies a
dated collection, not completion, supersession, current ownership, or runtime
verification; consult each record's own evidence for those claims.
