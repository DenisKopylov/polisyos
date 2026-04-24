"""Shared runtime/CI governance evaluation for Fabric connector contract evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .evolution import EvolutionReport, MigrationPlan, SchemaEvolution
from .schema import SchemaVersion

if TYPE_CHECKING:
    from .contract import ConnectorSchemaContract

__all__ = [
    "ContractGovernanceEvaluation",
    "actual_version_bump",
    "evaluate_contract_governance",
    "format_impacted_surfaces",
    "impacted_downstream_surfaces",
]


def actual_version_bump(previous: SchemaVersion, current: SchemaVersion) -> str:
    """Classify the semantic-version delta between two schema versions."""
    if current.major > previous.major:
        return "major"
    if current.minor > previous.minor:
        return "minor"
    if current.patch > previous.patch:
        return "patch"
    return "none"


def impacted_downstream_surfaces(contract: ConnectorSchemaContract) -> tuple[str, ...]:
    """Return the default downstream surfaces used in CI/runtime diagnostics."""
    return (
        f"connector:{contract.connector_id}",
        f"dataset:{contract.dataset_id}",
        f"schema:{contract.schema.schema_id}",
    )


def format_impacted_surfaces(surfaces: tuple[str, ...]) -> str:
    """Render impacted downstream surfaces into a stable diagnostic string."""
    return ", ".join(surfaces)


@dataclass(frozen=True)
class ContractGovernanceEvaluation:
    """Deterministic governance decision shared by runtime and CI gates."""

    contract_id: str
    previous_version: SchemaVersion
    current_version: SchemaVersion
    report: EvolutionReport
    actual_bump: str
    impacted_surfaces: tuple[str, ...]
    missing_governance_requirements: tuple[str, ...]
    migration_plan: MigrationPlan | None = None

    @property
    def errors(self) -> tuple[str, ...]:
        """Return human-readable governance failures for this contract change."""
        if not self.report.changes:
            return ()

        errors: list[str] = []
        impacted = format_impacted_surfaces(self.impacted_surfaces)

        if self.report.breaking_changes:
            if self.actual_bump != "major":
                errors.append(
                    f"{self.contract_id}: breaking changes require major bump "
                    f"({self.previous_version} -> {self.current_version}); "
                    f"impacted={impacted}"
                )
            if self.missing_governance_requirements:
                errors.append(
                    f"{self.contract_id}: breaking changes missing governance metadata: "
                    f"{'; '.join(self.missing_governance_requirements)}; impacted={impacted}"
                )
            return tuple(errors)

        required = self.report.recommended_version_bump
        if required == "minor" and self.actual_bump not in {"minor", "major"}:
            errors.append(
                f"{self.contract_id}: non-breaking schema changes require at least minor bump "
                f"({self.previous_version} -> {self.current_version}); impacted={impacted}"
            )
        elif required == "patch" and self.actual_bump == "none":
            errors.append(
                f"{self.contract_id}: patch-level schema changes require version bump "
                f"({self.previous_version} -> {self.current_version}); impacted={impacted}"
            )
        return tuple(errors)


def evaluate_contract_governance(
    previous_contract: ConnectorSchemaContract,
    current_contract: ConnectorSchemaContract,
    *,
    evolution: SchemaEvolution | None = None,
) -> ContractGovernanceEvaluation:
    """Evaluate one contract change against the Fabric schema-governance policy."""
    evolution_engine = evolution or SchemaEvolution()
    report = evolution_engine.compare(previous_contract.schema, current_contract.schema)
    migration_plan: MigrationPlan | None = None
    if report.changes and report.is_compatible:
        migration_plan = evolution_engine.build_migration_plan(
            previous_contract.schema,
            current_contract.schema,
            table_name=current_contract.dataset_id.replace("*", "_"),
        )

    missing_requirements: tuple[str, ...] = ()
    if report.breaking_changes:
        missing_requirements = tuple(
            current_contract.approval.validate_breaking_change_requirements()
        )

    return ContractGovernanceEvaluation(
        contract_id=current_contract.contract_id,
        previous_version=previous_contract.schema_version,
        current_version=current_contract.schema_version,
        report=report,
        actual_bump=actual_version_bump(
            previous_contract.schema_version,
            current_contract.schema_version,
        ),
        impacted_surfaces=impacted_downstream_surfaces(current_contract),
        missing_governance_requirements=missing_requirements,
        migration_plan=migration_plan,
    )
