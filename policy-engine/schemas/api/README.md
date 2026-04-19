# API Schemas

Canonical OpenAPI documents live here. Existing API snapshots may migrate into
this directory after their generation commands and downstream paths are updated.

Planned layout:

```text
api/
|-- runtime_v1.openapi.json
`-- data_forge_v1.openapi.json
```

Generated clients and frontend types must reference these files through
`architecture/generated_artifacts.toml`.
