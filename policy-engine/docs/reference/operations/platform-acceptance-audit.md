# Platform Acceptance Audit

Related reference: [Operations Reference](index.md), [Handoff and Platform Review](handoff-and-platform-review.md), [Ratchet Policy](../ratchet-policy.md). Related guides: [Installation](../../how-to/install.md), [Onboarding Tracks](../../how-to/onboarding/index.md), [Release Policy](../../how-to/release-policy.md).

Owner: `@platform-owners`
Source of truth: `tools/devx/workspace/acceptance_audit.py`, `docs/archive/reports/platform-acceptance.{md,json}`, `docs/reference/{quality-gates.md,ownership.md}`, and the repo-tracked workflows exercised by the audit

> This is the WS-7B closeout document: one end-to-end acceptance pass that turns
> Phases 1-6 into one coherent platform.

## Automated Audit

Run the repo-tracked automated portion from `policy-engine/`:

```bash
uv run polisyos-tools workspace acceptance-audit \
  --summary docs/archive/reports/platform-acceptance.md \
  --json-output docs/archive/reports/platform-acceptance.json
```

The automated pass checks these surfaces together:

| Acceptance slice                       | Repo-tracked evidence                                                                                                       |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Toolchain consistency                  | `.python-version`, `.nvmrc`, workspace helpers, composite GitHub Actions, environment matrix                                |
| Repo root coherence                    | root `README.md`, `policy-engine/README.md`, ADR-0096                                                                       |
| Ownership / merge governance           | labels, PR template, published workflow inventory, ownership docs, and quality-gate docs                                    |
| Required checks / release path         | current workflow inventory, release docs, release fragment tooling, `build-and-push.yml`, and `signatures.yml`              |
| Runtime contract gates                 | runtime OpenAPI drift check, auth/tenant middleware tests, write-path hardening tests, and the core-runtime closeout ledger |
| Runbooks / retention / observability   | runbook index, recovery docs, observability topology, platform review scorecard                                             |
| Dependency / security / workflow trust | Renovate, action freshness tooling, workflow policy checks, Scorecard / provenance coverage                                 |

Runtime-specific acceptance evidence should include:

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`
- `uv run pytest -q tests/core/security/test_auth_middlewares.py tests/core/security/test_router.py tests/core/security/test_tenant_context.py tests/runtime/http/test_runtime_api_authz.py`
- `uv run pytest -q tests/runtime/http/test_runtime_api_write_path_hardening.py tests/runtime/http/test_control_hardening.py`
- `uv run polisyos-tools workspace core-runtime-closeout --summary docs/archive/reports/core-runtime-closeout.md --json-output docs/archive/reports/core-runtime-closeout.json`

If you want the manual rehearsals to become blocking too, pass a filled evidence
file:

```bash
uv run polisyos-tools workspace acceptance-audit \
  --manual-evidence /tmp/polisyos-platform-acceptance.toml \
  --require-manual-evidence \
  --summary docs/archive/reports/platform-acceptance.md
```

Template:

```bash
cp release/platform-acceptance.evidence.template.toml /tmp/polisyos-platform-acceptance.toml
```

The evidence file also accepts structured entries when you need to preserve
notes or supporting artifact paths:

```toml
[manual.backend_walkthrough]
status = false
notes = "Blocked by one benchmark regression in the backend fast gate."
evidence = ["docs/archive/reports/platform-acceptance-manual.md"]
```

If the local machine is not a good fit for heavyweight suites, you may rehearse
the same path on a remote Linux runner. The repo-tracked helper lives at
`polisyos-tools workspace remote-acceptance` and keeps the acceptance semantics explicit:
iterate in an rsynced worktree, then record the final evidence from a committed
clean checkout. The provisioned remote toolchain exports
`POLISYOS_PYTEST_WORKERS=auto`, so the backend fast gate saturates the remote
CPU for non-benchmark tests while benchmark-marked slices still run serially.

## Contributor Journey

Phase 7 closes the loop between setup, role onboarding, and platform policy:

1. Confirm the host surface in [Environment Matrix](../environment-matrix.md).
2. Run the canonical install path from [Installation](../../how-to/install.md):
   `polisyos-tools workspace bootstrap` -> `polisyos-tools workspace doctor`.
3. Pick the nearest role track from [Onboarding Tracks](../../how-to/onboarding/index.md).
4. Run the scoped contributor gate with `polisyos-tools workspace verify`.
5. For cross-platform changes, finish with `polisyos-tools workspace acceptance-audit`.

The platform is not considered integrated if any of those steps require chat
archaeology or contradictory docs.

## Required Manual Rehearsals

These are the manual items that complete WS-7B and can be recorded in the
manual evidence TOML:

| Evidence key              | What to exercise               | Minimum expectation                                                                                                                      |
| ------------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `clean_machine_bootstrap` | Fresh clone on a clean machine | `polisyos-tools workspace bootstrap`, `polisyos-tools workspace doctor`, `polisyos-tools workspace verify` complete without ad hoc fixes |
| `backend_walkthrough`     | Backend contributor path       | Follow `docs/how-to/onboarding/backend-engineer.md` and verify the backend-only fast gate                                                |
| `frontend_walkthrough`    | Frontend contributor path      | Follow `docs/how-to/onboarding/frontend-engineer.md` and verify the frontend-only fast gate                                              |
| `platform_walkthrough`    | Platform contributor path      | Follow `docs/how-to/onboarding/platform-ops-engineer.md` and exercise bootstrap / doctor / verify / observability entry points           |
| `release_dry_run`         | Release rehearsal              | Run the local release note / version / canary path or an equivalent GitHub dry run                                                       |
| `incident_tabletop`       | Critical runbook quality check | Walk one alert-to-runbook path and confirm timeline, rollback, escalation, and follow-up are explicit                                    |

Recommended local release rehearsal:

```bash
python3 tools/release/check_release_version.py --tag v0.1.0
python3 tools/release/build_release_notes.py \
  --version 0.1.0 \
  --fragments-dir release-fragments/releases/0.1.0 \
  --output /tmp/polisyos-release-notes.md \
  --require-curated-sections compatibility migration api limitations
uv run --extra runtime --extra ml python tools/release/run_release_canary.py \
  --summary /tmp/polisyos-release-canary.md
```

Recommended incident tabletop:

1. Choose one critical path such as runtime outage, canary failure, docs publish
   failure, or retained-artifact recovery.
2. Start from the alert or failing signal in
   [Observability Topology](observability-topology.md).
3. Follow the linked runbook end to end.
4. Record whether escalation, rollback, restore, and postmortem action items
   were obvious without extra tribal knowledge.

## Gap List Rules

The acceptance pass should leave a gap list containing only:

- true misses;
- threshold values that need deliberate ratcheting;
- cleanup items that simplify the platform.

Do not use the gap list as a parking lot for already-accepted ambiguity.

## Closeout Output

The final closeout packet should leave:

- one automated audit summary;
- one machine-readable JSON audit snapshot;
- one filled manual evidence file or equivalent tracked evidence artifact;
- explicit follow-ups only for the remaining real misses.
