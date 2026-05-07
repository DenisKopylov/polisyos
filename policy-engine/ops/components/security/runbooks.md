# Security Runbooks

Escalation: `team-security` primary; `team-platform` joins for identity,
policy, or infrastructure remediation.

| Alert or symptom | Runbook |
| --- | --- |
| `TenantBoundaryViolation`, `CrossTenantAccessAttempt`, `RuntimeAuthFailuresSpike` | [CAS or OPA Outage](../../../docs/runbooks/cas-opa-outage.md) |
| `TEEAttestationFailureRate`, `TEEUnavailableOnConfidentialNode`, `SBOMCriticalCVEDetected`, `SBOMDeploymentGateDenySpike` | [Artifact Signing or SBOM Failure](../../../docs/runbooks/artifact-signing-sbom-failure.md) |
| `PlaintextConnectionDetected`, `MTLSCertificateExpiringSoon` | [Key Rotation](../../../docs/runbooks/key-rotation.md) |

