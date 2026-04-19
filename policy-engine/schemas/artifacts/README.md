# Artifact Schemas

Versioned JSON Schemas for published Data Forge and runtime artifacts.

Planned examples:

```text
artifacts/
|-- academic/skg_v1.json
|-- catalog/dataset_v1.json
|-- legal/provision_v1.json
`-- ukraine/release_bundle_v1.json
```

Every published ArtifactRef should include `schema_id` and `schema_version`
that resolve to this registry.
