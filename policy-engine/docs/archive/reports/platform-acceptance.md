# Platform Acceptance Audit

- Automated blockers: 0
- Manual blockers: 0
- Manual checks still pending: 0

| Check | Kind | Status | Detail |
|---|---|---|---|
| Toolchain consistency | automated | pass | Python 3.14.x, Node 22.x, and uv 0.9.21 stay aligned across local docs and composite actions. |
| Repo root coherence | automated | pass | Root and product READMEs still agree on the workspace gateway vs canonical product-root split. |
| Ownership coverage | automated | pass | Ownership is covered in both repo control plane and product docs. |
| Repository ruleset and merge governance | automated | pass | Ruleset, merge-governance doc, PR template, labels taxonomy, and ratchet enforcement are all repo-tracked. |
| Required checks | automated | pass | Required PR gates stay consistent between ruleset, docs, and workflow files. |
| Release path | automated | pass | Release workflow, release policy, immutable fragment snapshots, and release helpers are wired together. |
| Runbook presence | automated | pass | Core incident, restore, docs, release, and benchmark runbooks are present. |
| Bootstrap and doctor quality | automated | pass | Bootstrap, doctor, verify, ci-parity, acceptance-audit, and the contributor journey docs are in place. |
| Dependency freshness process | automated | pass | Dependency freshness is covered by Renovate, nightly workflow audits, and repo-tracked docs. |
| Workflow identity hardening and runner trust model | automated | pass | Workflow policy checks pass and the trust model is documented. |
| Config and secrets governance | automated | pass | Config and secrets governance is documented with safe example env files. |
| Generated artifact lifecycle | automated | pass | Generated artifact lifecycle is tracked in repo policy and automation. |
| External security signals | automated | pass | External supply-chain posture is covered by Scorecard, release provenance/signing, and SECURITY.md. |
| Delivery-performance signals | automated | pass | Platform scorecard keeps throughput and instability metrics visible. |
| Retention and restore posture | automated | pass | Retention policy and recovery runbooks cover restore posture. |
| Observability ownership | automated | pass | Observability signals stay routed through named owners and runbooks. |
| Clean-machine bootstrap rehearsal | manual | pass | Re-clone the repo on a clean machine and run polisyos-tools workspace bootstrap -> polisyos-tools workspace doctor -> polisyos-tools workspace verify. Notes: Clean checkout rehearsal passed on Hetzner from detached HEAD ccde518 in /root/polisyos-clean-next: polisyos-tools workspace bootstrap --profile runtime --skip-hooks completed, Playwright Chromium launched, lockfile/schema/runtime-contract checks passed, and doctor reported a ready contributor machine. |
| Backend contributor walkthrough | manual | pass | Follow docs/how-to/onboarding/backend-engineer.md on a representative contributor path. Notes: Backend walkthrough passed from clean checkout ccde518 on Hetzner: polisyos-tools workspace verify --skip-doctor --pytest-workers 16 completed the non-benchmark pytest slice with 7586 passed / 142 skipped and the benchmark slice with 6 passed / 7 skipped. The compositional-causality harness, twin-network counterfactual pipeline, and merge-determinism property tests now pass under 16-way xdist. |
| Frontend contributor walkthrough | manual | pass | Follow docs/how-to/onboarding/frontend-engineer.md on a representative contributor path. Notes: Frontend walkthrough passed from clean checkout ccde518 as part of polisyos-tools workspace verify --skip-doctor --pytest-workers 16: npm typecheck, npm lint, npm format check, npm architecture check, npm contract fixtures, and vitest component tests all passed (99 files, 258 tests). |
| Platform contributor walkthrough | manual | pass | Follow docs/how-to/onboarding/platform-ops-engineer.md and exercise bootstrap/doctor/verify surfaces. Notes: Platform walkthrough passed from clean checkout ccde518: full polisyos-tools workspace verify --skip-doctor --pytest-workers 16 was green, and ops/docker/observability.compose.yml was exercised with docker compose up/down under COMPOSE_PROJECT_NAME=polisyos-clean-obs. Prometheus /-/ready returned "Prometheus Server is Ready." and Grafana /api/health returned database=ok, version=10.4.3 before the stack was torn down. |
| Release rehearsal or dry run | manual | pass | Exercise the local release-note/version/canary path or the GitHub release workflow dry run. Notes: Release version validation, curated release-note build with metadata JSON, and live runtime canary all passed from clean checkout ccde518. The canary and release-notes artifacts were written to /tmp/polisyos-release-*.{md,json} on the Hetzner runner. |
| Incident / runbook tabletop | manual | pass | Walk one critical operational path from alert to runbook to postmortem follow-up. Notes: Reviewed the runtime alert-to-runbook path through observability-topology.md and runtime-api-outage.md, including timeline capture, rollback, escalation, and postmortem sections. |

## Gap List

- No blockers remain in the current acceptance audit.
