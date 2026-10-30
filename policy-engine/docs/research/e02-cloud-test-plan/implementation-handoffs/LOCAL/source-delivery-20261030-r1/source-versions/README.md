# E02 uncomposed source versions

`postimage-patches.tar.gz` holds ordinary UTF-8 Git-format source patches, one per distinct target path and source version, against the commit recorded in `catalog.json`. Different patches may be mutually incompatible alternatives, may include predecessors and can represent obsolete work. They are preserved for review or composition; they are not applied, verified, accepted or independent capabilities. The catalog pins each patch hash, source postimage hash, baseline preimage hash and all known original paths.

The scope is the recognized code-only postimage locations under the listed E02 proposal roots; it is not an inventory of arbitrary local files. No production payload, local database, CAS, dependency, environment or complete checkout is packaged. Research output/data and JSON/YAML test data are excluded. One named sanitization unit test contains explicitly synthetic credential-shaped test fixtures (alongside example.org and example.test); these are preserved byte-for-byte and classified in the catalog. No actual credentials were identified by the bounded scan.

Unpack a selected patch and run `git apply --check` against the exact base before composition. Multiple patch files for the same target are alternative versions, not a combined change.
