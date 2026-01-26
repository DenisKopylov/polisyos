"""
ModelSpec: The "How" artifact - data, agents, assumptions, environment.

This artifact captures the world model configuration against which policies
are simulated. Multiple ModelSpecs can be used for sensitivity analysis.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal, Sequence

from pydantic import BeforeValidator, Field, model_validator

from polisyos.ir.kernel.base import KernelModel, reject_float
from polisyos.ir.kernel.numbers import DecimalValue
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.types import EntityType, TranslatableString

# Constants
ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ARTIFACT_ID_PATTERN = r"^sha256:[a-f0-9]{64}$"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
MAX_ASSUMPTIONS = 100
MAX_AGENT_TYPES = 50
MAX_ENVIRONMENT_PARAMS = 100

UnitIntervalValue = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1)]


class FidelityLevel(str, Enum):
    """Simulation fidelity levels."""

    SURROGATE_FLUID = "surrogate_fluid"  # Fastest, least accurate
    SURROGATE_DISCRETE = "surrogate_discrete"
    HYBRID = "hybrid"
    FULL_DISCRETE = "full_discrete"  # Slowest, most accurate


class AssumptionType(str, Enum):
    """Types of modeling assumptions."""

    BEHAVIORAL = "behavioral"  # Agent behavior assumptions
    STRUCTURAL = "structural"  # Economic structure assumptions
    PARAMETRIC = "parametric"  # Parameter value assumptions
    DISTRIBUTIONAL = "distributional"  # Distribution shape assumptions
    TEMPORAL = "temporal"  # Time-related assumptions
    BOUNDARY = "boundary"  # Boundary condition assumptions


class AssumptionSpec(KernelModel):
    """
    Explicit modeling assumption.

    Documents assumptions made in the world model for transparency
    and sensitivity analysis.
    """

    assumption_id: str = Field(..., pattern=ID_PATTERN)
    assumption_type: AssumptionType
    description: str = Field(..., max_length=500)
    value: DecimalValue | str | bool | None = Field(
        None, description="Quantified assumption value if applicable"
    )
    confidence: UnitIntervalValue | None = Field(
        None, description="Confidence in this assumption (0-1)"
    )
    source: str | None = Field(None, max_length=200, description="Source/citation")
    sensitivity_flag: bool = Field(
        False, description="Flag for sensitivity analysis priority"
    )
    notes: list[str] = Field(default_factory=list, max_length=5)


class AgentTypeConfig(KernelModel):
    """
    Configuration for a type of agent in the simulation.

    Defines agent heterogeneity and behavioral parameters.
    """

    agent_type_id: str = Field(..., pattern=ID_PATTERN)
    entity_type: EntityType
    name: TranslatableString | None = None

    # Population
    population_count: int | None = Field(None, ge=0)
    population_share: UnitIntervalValue | None = None
    max_population: int | None = Field(None, ge=0)

    # Behavioral parameters
    utility_function: str | None = Field(
        None, pattern=ID_PATTERN, description="Reference to utility function"
    )
    risk_aversion: DecimalValue | None = None
    discount_rate: DecimalValue | None = None

    # Heterogeneity
    attribute_distributions: dict[str, Any] = Field(
        default_factory=dict, description="Distribution specs for heterogeneous attributes"
    )

    # Adaptation
    adaptive: bool = Field(False, description="Whether agents use learned policies")
    policy_model: str | None = Field(None, description="RL policy model type if adaptive")

    notes: list[str] = Field(default_factory=list, max_length=5)


class AgentConfig(KernelModel):
    """Complete agent configuration for the model."""

    agent_types: list[AgentTypeConfig] = Field(
        default_factory=list,
        max_length=MAX_AGENT_TYPES,
        description="Agent type configurations",
    )
    total_agents: int | None = Field(None, ge=0, description="Total agent population")
    max_agents: int | None = Field(None, ge=0, description="Maximum agent capacity")
    interaction_topology: Literal["random", "lattice", "network", "spatial"] | None = Field(
        None, description="Agent interaction topology"
    )
    network_graph_ref: str | None = Field(
        None, pattern=ARTIFACT_ID_PATTERN, description="Reference to network graph artifact"
    )


class EnvironmentParam(KernelModel):
    """Environment/exogenous parameter specification."""

    param_id: str = Field(..., pattern=ID_PATTERN)
    value: DecimalValue | str | bool
    unit_id: str | None = Field(None, pattern=ID_PATTERN)
    description: str | None = Field(None, max_length=200)
    time_varying: bool = Field(False, description="Whether value changes over time")
    time_series_ref: str | None = Field(
        None, pattern=ARTIFACT_ID_PATTERN, description="Reference to time series data"
    )


class EnvironmentConfig(KernelModel):
    """Environment configuration for the simulation."""

    params: list[EnvironmentParam] = Field(
        default_factory=list,
        max_length=MAX_ENVIRONMENT_PARAMS,
        description="Environment parameters",
    )
    random_seed: int | None = Field(None, description="RNG seed for reproducibility")
    stochastic: bool = Field(True, description="Whether simulation is stochastic")
    parallel_worlds: int = Field(1, ge=1, description="Number of parallel simulations")


class ModelSpec(KernelModel):
    """
    ModelSpec: The "How" artifact (WorldModel).

    Specifies the world model configuration including data snapshots,
    agent configuration, assumptions, and environment parameters.
    Multiple ModelSpecs can test the same PolicySpec for sensitivity analysis.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)

    # Identity
    model_id: str = Field(..., pattern=ID_PATTERN, description="Unique model identifier")

    # Data References
    data_snapshot_ref: str = Field(
        ...,
        pattern=ARTIFACT_ID_PATTERN,
        description="Reference to DataSnapshot artifact (initial world state)",
    )
    registry_bundle_ref: str | None = Field(
        None,
        pattern=ARTIFACT_ID_PATTERN,
        description="Reference to RegistryBundle for mechanisms/units",
    )

    # Time Configuration
    time_semantics: TimeSemantics | None = Field(
        None, description="Temporal configuration (step duration, discounting)"
    )

    # Agent Configuration
    agent_config: AgentConfig = Field(
        default_factory=AgentConfig,
        description="Agent population and behavior configuration",
    )

    # Assumptions
    assumptions: list[AssumptionSpec] = Field(
        default_factory=list,
        max_length=MAX_ASSUMPTIONS,
        description="Explicit modeling assumptions",
    )

    # Environment
    environment_config: EnvironmentConfig = Field(
        default_factory=EnvironmentConfig,
        description="Environment parameters and configuration",
    )

    # Fidelity Control
    fidelity_level: FidelityLevel = Field(
        default=FidelityLevel.HYBRID,
        description="Simulation fidelity level",
    )

    # Calibration State
    calibrated: bool = Field(False, description="Whether model has been calibrated")
    calibration_ref: str | None = Field(
        None, pattern=ARTIFACT_ID_PATTERN, description="Reference to calibration results"
    )

    # Metadata
    name: TranslatableString | None = Field(None, description="Human-readable model name")
    description: str | None = Field(None, max_length=2000)
    labels: list[str] = Field(default_factory=list, max_length=20)
    version_tag: str | None = Field(None, max_length=50, description="Semantic version tag")
    notes: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_model_spec(self) -> "ModelSpec":
        """Validate internal consistency of the model spec."""

        _validate_unique_ids(self.assumptions, "assumption_id")
        _validate_unique_ids(self.agent_config.agent_types, "agent_type_id")
        _validate_unique_ids(self.environment_config.params, "param_id")

        if self.agent_config.agent_types:
            total_share = sum(
                (agent.population_share or Decimal("0"))
                for agent in self.agent_config.agent_types
            )
            if total_share > Decimal("1"):
                raise ValueError(
                    f"Agent type population shares sum to {total_share}, exceeds 1.0"
                )

        return self


def _validate_unique_ids(items: Sequence[KernelModel], attr: str) -> None:
    """Validate that all items have unique values for the given attribute."""

    seen: set[str] = set()
    for item in items:
        value = getattr(item, attr)
        if value in seen:
            raise ValueError(f"duplicate {attr}: {value}")
        seen.add(value)
