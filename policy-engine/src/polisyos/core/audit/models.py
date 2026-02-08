from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class ExportProfile(str, Enum):
    FULL = "full"
    MANIFESTS_ONLY = "manifests_only"


class SigningPolicy(str, Enum):
    STRICT = "strict"
    WARN = "warn"
    SKIP = "skip"


class StepStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass(frozen=True)
class ExportOptions:
    exclude_kinds: frozenset[str] = frozenset()
    profile: ExportProfile = ExportProfile.FULL
    include_visualization: bool = True
    signing_policy: SigningPolicy = SigningPolicy.WARN
    slsa_mode: str | None = None
    slsa_policy: str | None = None
    max_depth: int = 200
    max_nodes: int = 10_000


@dataclass(frozen=True)
class AuditExportResult:
    archive_path: Path
    run_id: str
    artifacts_exported: int
    total_bytes: int
    signatures_included: int
    unsigned_artifacts: list[str]
    prov_entities: int
    prov_activities: int
    prov_agents: int
    warnings: list[str]
    duration_seconds: float


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    message: str
    path: str | None = None
    expected: str | None = None
    actual: str | None = None


@dataclass
class StepResult:
    step_name: str
    status: StepStatus = StepStatus.SKIP
    checks_passed: int = 0
    checks_failed: int = 0
    checks_skipped: int = 0
    duration_ms: float = 0.0
    details: list[str] = field(default_factory=list)


@dataclass
class VerificationReport:
    package_path: str
    run_id: str | None = None
    verified_at: datetime = field(default_factory=utc_now)
    verifier_version: str = "polisyos-audit-verify/1.0.0"
    overall_status: Literal["PASS", "FAIL"] = "FAIL"

    package_integrity: StepResult = field(
        default_factory=lambda: StepResult(step_name="Package Integrity")
    )
    cas_integrity: StepResult = field(default_factory=lambda: StepResult(step_name="CAS Integrity"))
    signature_verification: StepResult = field(
        default_factory=lambda: StepResult(step_name="Signature Verification")
    )
    provenance_validation: StepResult = field(
        default_factory=lambda: StepResult(step_name="Provenance Validation")
    )
    dependency_completeness: StepResult = field(
        default_factory=lambda: StepResult(step_name="Dependency Completeness")
    )
    slsa_verification: StepResult = field(
        default_factory=lambda: StepResult(step_name="SLSA Verification")
    )

    artifacts_checked: int = 0
    artifacts_total: int = 0
    signatures_valid: int = 0
    signatures_total: int = 0
    prov_entities: int = 0
    prov_activities: int = 0
    prov_agents: int = 0

    failures: list[VerificationIssue] = field(default_factory=list)
    warnings: list[VerificationIssue] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_failure(
        self,
        code: str,
        message: str,
        *,
        path: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self.failures.append(
            VerificationIssue(
                code=code,
                message=message,
                path=path,
                expected=expected,
                actual=actual,
            )
        )

    def add_warning(
        self,
        code: str,
        message: str,
        *,
        path: str | None = None,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self.warnings.append(
            VerificationIssue(
                code=code,
                message=message,
                path=path,
                expected=expected,
                actual=actual,
            )
        )

    def finalize(self) -> "VerificationReport":
        self.overall_status = "FAIL" if self.failures else "PASS"
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_path": self.package_path,
            "run_id": self.run_id,
            "verified_at": self.verified_at.isoformat(),
            "verifier_version": self.verifier_version,
            "overall_status": self.overall_status,
            "package_integrity": asdict(self.package_integrity),
            "cas_integrity": asdict(self.cas_integrity),
            "signature_verification": asdict(self.signature_verification),
            "provenance_validation": asdict(self.provenance_validation),
            "dependency_completeness": asdict(self.dependency_completeness),
            "slsa_verification": asdict(self.slsa_verification),
            "artifacts_checked": self.artifacts_checked,
            "artifacts_total": self.artifacts_total,
            "signatures_valid": self.signatures_valid,
            "signatures_total": self.signatures_total,
            "prov_entities": self.prov_entities,
            "prov_activities": self.prov_activities,
            "prov_agents": self.prov_agents,
            "failures": [asdict(item) for item in self.failures],
            "warnings": [asdict(item) for item in self.warnings],
            "environment": self.environment,
            "metadata": self.metadata,
        }
