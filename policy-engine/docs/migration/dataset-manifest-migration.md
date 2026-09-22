# Dataset manifest migration

The `DatasetManifest` schema is owned by Fabric identity.  Its historical
`0.9` to `1.0` converter therefore lives at
`polisyos.fabric.identity.migrations.migrate_manifest_0_9_to_1_0`.

The converter is a format-only operation:

- `datasetName` and `rawHash` are renamed only when their snake-case aliases
  are absent;
- unknown fields and absent fields remain observable;
- equal or conflicting duplicate aliases are not silently resolved;
- no missing `raw_hash`, `created_at`, provenance, or admission fact is
  fabricated.

The generic Common migration engine remains Fabric-neutral.  The canonical
CLI explicitly registers the Fabric migration, while
`polisyos.common.migrations.manifest` remains a narrow compatibility adapter
for legacy callers during the transition.  That adapter deliberately retains
the old local callback and registration side effect without importing Fabric;
its duplicate rename profile is bounded compatibility debt, not a second
schema owner.

This package characterizes the supported legacy profile and registration
paths.  It does not establish that every historical `0.9` payload satisfies
the current `DatasetManifest` DTO or that its raw content has been verified;
those are separate validation and provenance decisions.
