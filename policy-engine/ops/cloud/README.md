# Cloud Operations

`ops/cloud/` owns cloud deployment assets, GCP launch helpers, and operational
cloud templates.

- `deploy/assets/`: ignored local shard and environment assets.
- `gcp/`: GCP bootstrap, worker launch, upload, and watcher helpers.

Runtime command implementations remain in `tools/ops/cloud/`; legacy product
root directories forward to those canonical locations.
