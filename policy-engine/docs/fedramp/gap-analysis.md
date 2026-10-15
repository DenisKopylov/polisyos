# FedRAMP Gap Analysis (Phase 4)

Owner: `@platform-owners`
Source of truth: `policy-engine/docs/fedramp/poam.json`, `policy-engine/docs/fedramp/nist-800-53-mapping.json`, and current control-owner evidence.

## Status note (2026-10-14)

The target dates below have passed. This page does not record completion evidence
or establish a current FedRAMP authorization or 3PAO assessment. The linked
`docs/fedramp/poam.json` is prepared 2026-02-08 and still records its milestones
as planned; `docs/fedramp/nist-800-53-mapping.json` is generated 2026-02-08 and
retains open gaps. Reconcile those dated records with the control owner before
using them as current status. In particular, the SC-28 mapping labels the
control `implemented` while its `gaps` field says CMEK support is pending.

Review method: repository-document inspection at source pin
`8dd933600dd7a5a8a5b48432c6089d63b81ca641` on 2026-10-14; no current control-owner
or external assessment evidence was obtained.

## Summary

Phase 4 closes confidential-computing and software-supply-chain controls for PolicyOS.
Remaining gaps are now concentrated in process and operational evidence.

## Open Gaps

| Control | Gap                                                       | Priority | Target     |
| ------- | --------------------------------------------------------- | -------- | ---------- |
| CA-8    | 3PAO penetration test not completed                       | Critical | 2026-04-30 |
| SC-12   | HSM-backed signing root and key ceremony not formalized   | High     | 2026-04-01 |
| CP-9    | Backup/restore runbook and restore drill evidence pending | High     | 2026-05-01 |
| PL-2    | Full System Security Plan narrative package pending       | High     | 2026-04-15 |
| IR-4    | Incident response playbook and tabletop evidence pending  | Medium   | 2026-05-01 |
| SA-9    | Formal ISA agreements for external data providers pending | Medium   | 2026-05-15 |
| SC-28   | CMEK option not yet implemented                           | Medium   | 2026-06-30 |

## Implemented in Phase 4

- Confidential execution gate with TEE attestation models and enforcement hook.
- SBOM generation, vulnerability parsing, and deployment policy gate.
- Audit package extension to include SBOM material and metadata.
- Security telemetry for attestation and SBOM decisions.

## Evidence Artifacts

- `docs/fedramp/nist-800-53-mapping.json`
- `docs/fedramp/poam.json`
- `ops/policy/policies/vulnerability.rego`
- `src/polisyos/core/security/tee.py`
- `src/polisyos/core/security/sbom.py`
