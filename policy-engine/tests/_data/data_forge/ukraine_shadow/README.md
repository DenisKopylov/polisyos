# Ukraine shadow bundle fixtures

The baseline and candidate bundles are used by the shadow reader’s metadata-integrity tests. Their tracked `publish/bundle.json` files retain seven declarations each and their original SHA-256 values. The test-owned `_materialize_shadow_checksum_bundle` helper copies the tracked JSON files into `tmp_path` and writes the corresponding small text sentinel at `normalized/demography_inputs.parquet`.

That sentinel exists only to exercise path existence and byte-checksum reporting. It is not Parquet data and must not be used by normalization, calibration, simulation, or other data consumers. The shadow reader hashes bytes; it does not validate file format. The helper also checks that each fixed sentinel digest still matches the unchanged bundle manifest, while drift/removal controls call the real reader with the manifest entry retained.

Tests that need a genuine normalized Parquet must exercise the supported `SourceAdapter.normalize` producer from explicit controlled raw inputs under a distinct synthetic fixture identity and its own manifest. Do not change these existing bundle hashes to bless replacement bytes.
