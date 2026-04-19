# Schema Codegen Targets

Generated schema bindings and target-specific codegen outputs are coordinated
here. Generated files may live outside `schemas/`, but their source schema and
regeneration command must be registered in `architecture/generated_artifacts.toml`.

Planned targets:

```text
codegen/
|-- typescript/
|-- python_stubs/
`-- rust/
```
