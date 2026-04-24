# FedRAMP Gap Analysis (Phase 4)

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
- `ops/opa/policies/vulnerability.rego`
- `src/polisyos/core/security/tee.py`
- `src/polisyos/core/security/sbom.py`
