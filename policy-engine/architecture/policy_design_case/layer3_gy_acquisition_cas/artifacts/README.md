# Acquisition artifact storage

Maintenance route: team-runtime.

Hash-named artifact directories pair payload bytes with manifests. Write through Core artifact-store and acquisition owners, then verify content and manifest bindings. Do not hand-edit a blob or infer custody from a directory name.

Owning entrypoint: `tools/quality/validation/check_layer3_gy_acquisition_executor.py`.

This local document explains the directory role. Its presence does not certify the contents or close a product capability.
