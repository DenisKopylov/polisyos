# Platform Acceptance Audit

Related reference: [Operations Reference](index.md), [Handoff and Platform Review](handoff-and-platform-review.md), [Ratchet Policy](../ratchet-policy.md). Related guides: [Installation](../../how-to/install.md), [Onboarding Tracks](../../how-to/onboarding/index.md), [Release Policy](../../how-to/release-policy.md).

> This is the WS-7B closeout document: one end-to-end acceptance pass that turns
> Phases 1-6 into one coherent platform.

## Automated Audit

Run the repo-tracked automated portion from `policy-engine/`:

```bash
./scripts/acceptance-audit \
  --summary docs/archive/reports/platform-acceptance.md \
  --json-output docs/archive/reports/platform-acceptance.json
```

The automated pass checks these surfaces together:

| Acceptance slice | Repo-tracked evidence |
|---|---|
| Toolchain consistency | `.python-version`, `.nvmrc`, workspace helpers, composite GitHub Actions, environment matrix |
| Repo root coherence | root `README.md`, `policy-engine/README.md`, ADR-0096 |
| Ownership / merge governance | `.github/CODEOWNERS`, repo ruleset, labels, PR template, ownership and quality-gate docs |
| Required checks / release path | canonical workflows, release docs, release fragment tooling, canary helper |
| Runbooks / retention / observability | runbook index, recovery docs, observability topology, platform review scorecard |
| Dependency / security / workflow trust | Renovate, action freshness tooling, workflow policy checks, Scorecard / provenance coverage |

If you want the manual rehearsals to become blocking too, pass a filled evidence
file:

```bash
./scripts/acceptance-audit \
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

## Contributor Journey

Phase 7 closes the loop between setup, role onboarding, and platform policy:

1. Confirm the host surface in [Environment Matrix](../environment-matrix.md).
2. Run the canonical install path from [Installation](../../how-to/install.md):
   `./scripts/bootstrap` -> `./scripts/doctor`.
3. Pick the nearest role track from [Onboarding Tracks](../../how-to/onboarding/index.md).
4. Run the scoped contributor gate with `./scripts/verify`.
5. For cross-platform changes, finish with `./scripts/acceptance-audit`.

The platform is not considered integrated if any of those steps require chat
archaeology or contradictory docs.

## Required Manual Rehearsals

These are the manual items that complete WS-7B and can be recorded in the
manual evidence TOML:

| Evidence key | What to exercise | Minimum expectation |
|---|---|---|
| `clean_machine_bootstrap` | Fresh clone on a clean machine | `./scripts/bootstrap`, `./scripts/doctor`, `./scripts/verify` complete without ad hoc fixes |
| `backend_walkthrough` | Backend contributor path | Follow `docs/how-to/onboarding/backend-engineer.md` and verify the backend-only fast gate |
| `frontend_walkthrough` | Frontend contributor path | Follow `docs/how-to/onboarding/frontend-engineer.md` and verify the frontend-only fast gate |
| `platform_walkthrough` | Platform contributor path | Follow `docs/how-to/onboarding/platform-ops-engineer.md` and exercise bootstrap / doctor / verify / observability entry points |
| `release_dry_run` | Release rehearsal | Run the local release note / version / canary path or an equivalent GitHub dry run |
| `incident_tabletop` | Critical runbook quality check | Walk one alert-to-runbook path and confirm timeline, rollback, escalation, and follow-up are explicit |

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
