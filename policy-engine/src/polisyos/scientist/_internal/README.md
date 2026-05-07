# Scientist Internal Helpers

`polisyos.scientist._internal` holds private helpers used by compatibility
shims and integration glue. Do not import this package from external plugins or
first-party domain code; stable contracts live in `api.py`, `extensions/`,
`nodes/`, `governance/`, and the other public Scientist hubs.
