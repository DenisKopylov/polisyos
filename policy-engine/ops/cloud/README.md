# Cloud Operations

- Owner: `team-ops`
- Artifact type: `cloud-infrastructure-contracts`

`ops/cloud/` owns cloud deployment assets, GCP launch helpers, and operational
cloud templates.

- `deploy/assets/`: ignored local shard and environment assets.
- `gcp/`: GCP bootstrap, worker launch, upload, and watcher helpers.

`gcp/package_repo.sh` builds the repository bundle from the exact committed Git
source tree named in the archive filename. It reads Hatch force-include sources
from that same tree, so worktree aliases and uncommitted bytes are not archive
inputs. Git replacement refs are ignored, and nested checkout callers are
resolved from the repository root for the source-freeze check. Commit the
intended source before packaging. The output path is created exclusively; an
existing file or symlink is preserved and causes a refusal.

With `UPLOAD=1`, the script streams the already-open archive descriptor through
`gcloud storage cp -`. This keeps the upload bound to that file identity without
handing a descriptor path to a parallel worker. Extracted source trees are
worker build inputs, not archive-producer workspaces.

Runtime command implementations remain in `tools/ops_runners/cloud/`; legacy product
root directories forward to those canonical locations.
