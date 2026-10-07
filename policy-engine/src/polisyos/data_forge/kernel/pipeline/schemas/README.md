# Data Forge Pipeline Schema Facade

This package is a compatibility import point for schema contracts owned by
`polisyos.data_forge.kernel.schemas`. Import new code from the canonical path;
do not add internal callers through this alias. The facade re-exports the same
`CompatibilityMode`, `SchemaRegistry`, and `SchemaVersion` objects.

An unreleased notice fragment announces the alias sunset. Its bounded window
begins with the published notice release N and runs through the later of the
next minor release and 90 days after N. Until that fragment is published, no
calendar sunset date is assigned; release preparation records the actual
publication and sunset dates in `architecture/shims.toml`.
