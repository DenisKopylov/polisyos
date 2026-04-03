# Ratchet Policy

Related reference: [Quality Gates](quality-gates.md), [Merge Governance](merge-governance.md), [Contributor Start Here](contributor-start-here.md), [Generated Artifacts](generated-artifacts.md), [Configuration Profiles](configuration-profiles.md), [Platform Acceptance Audit](operations/platform-acceptance-audit.md).

> After Phase 7 closeout, no new subsystem or major surface should merge as an
> improvisation.

## When This Applies

Use this policy whenever a PR introduces or substantially expands any of these:

- a new `src/polisyos/<package>` or other durable subsystem boundary;
- a new documented public facade or major supported surface;
- a new runtime API family, operator-facing workflow, or release surface;
- a new generated-artifact family that must stay committed or reviewed;
- a new config/secret family or new trust boundary;
- a new observability surface, rollout path, or incident/runbook responsibility.

This policy is usually not needed for docs-only changes, localized refactors, or
small internal edits that do not create a new durable surface.

## Required Evidence

Every new subsystem or major surface must ship with these questions answered in
the same change set:

| Requirement | Where to record it |
|---|---|
| Owner and fallback owner | `docs/reference/ownership.md`, `.github/CODEOWNERS`, nearest package `README.md` |
| Docs entry point | nearest package `README.md`, reference/how-to/tutorial page, or runbook |
| Test strategy | tests path plus the validation command in PR summary and package README |
| Compatibility classification | PR labels, release fragment, and `docs/how-to/release-policy.md` language |
| Review / merge-governance impact | PR template, `docs/reference/quality-gates.md`, `docs/reference/merge-governance.md` |
| Bootstrap / doctor impact | `tools/workspace/**`, `scripts/*`, install/onboarding docs, or explicit “none” note |
| Config / secrets impact | `docs/reference/configuration-profiles.md`, `.env.example`, deployment notes, or explicit “none” note |
| Generated-artifact impact | `architecture/generated_artifacts.toml`, `docs/reference/generated-artifacts.md`, or explicit “none” note |
| Observability / rollout impact | `docs/reference/operations/observability-topology.md`, `docs/how-to/review-rollouts.md`, or explicit “none” note |
| Release / runbook impact | release fragment, `docs/how-to/release-policy.md`, runbooks, or explicit “none” note |

If one of these truly does not apply, record that explicitly instead of leaving
it implicit.

## Golden Path

For a new package or durable surface, the default authoring path is:

1. Scaffold or update the nearest package README with
   `python3 tools/architecture/scaffold.py package-readme --module ...`.
2. Fill the ownership and change-ratchet sections in that README.
3. Update the relevant entry point in docs, not only a leaf page.
4. Add or update the release fragment when the change is operator-visible,
   compatibility-sensitive, or part of the shipped platform story.
5. Run `./scripts/acceptance-audit` when the change spans repo policy, release,
   onboarding, governance, or other cross-phase surfaces.

## Merge-Time Expectations

The PR template carries a dedicated Phase 7 ratchet section for new subsystems
and major surfaces. Treat it as a minimum bar, not as optional prose.

The fast PR workflow also validates that section in CI. At minimum, the author
must explicitly declare the ratchet applies, complete the required checkboxes,
and ship a package README when introducing a new `src/polisyos/<package>`
surface.

The expected answer quality is:

- concrete owner, not “team later”;
- explicit docs entry point, not “document later”;
- real test path, not “covered by CI somehow”;
- explicit compatibility stance, not silence;
- explicit operational implications, even when the answer is “none”.

## Ongoing Maintenance Policy

After closeout, these rules are continuous policy:

- Baselines change deliberately, never implicitly.
- Dependency exceptions carry an owner and expiry date.
- Architecture exceptions carry an owner and expiry date.
- Flaky-test quarantines carry an owner and expiry date.
- Config and secret exceptions carry an owner and expiry date.
- Workflow and security exceptions carry an owner and expiry date.
- Postmortem action items carry an owner, due date, and closeout check.
- Every new package ships with a README, ownership mapping, public-surface
  stance, test placement, and docs impact review.
- Each quarter, run the platform review from
  [Handoff and Platform Review](operations/handoff-and-platform-review.md).
