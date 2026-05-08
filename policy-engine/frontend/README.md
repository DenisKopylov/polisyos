---
redirect_stub: true
owner: team-frontend
target_path: apps; packages/runtime-api-client; docs/reference/frontend/workspace-contract.md
reason: legacy frontend handoff path retained while Wave 6 frontend references are swept
created_date: 2026-05-07
sunset_date: 2026-08-05
removal_gate: uv run python tools/quality/validation/check_docs_lifecycle.py --repo-root .
---

# Frontend Handoff

`frontend/` is a legacy handoff path. Active JavaScript workspaces moved in
Phase 2.7:

- apps live under [`../apps/`](../apps/);
- publishable or shared JavaScript packages live under
  [`../packages/`](../packages/);
- the generated runtime API client is
  [`../packages/runtime-api-client/`](../packages/runtime-api-client/).

Use [`../docs/reference/frontend/workspace-contract.md`](../docs/reference/frontend/workspace-contract.md)
for the current workspace contract.
