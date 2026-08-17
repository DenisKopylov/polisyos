"""DS16-C03 — the typed producer contract for readiness and scientific-depth values.

`DS4-C23` removed two surfaces that were **minting** authority: `PublicSectorReadiness`
composed a readiness verdict from local thresholds, regexes, dwell state and disputes,
and `ScientificDepth` invented remedies, acquisition refs, E-values, claim extinction,
cohort timelines and stress rankings. C23 performed containment only and registered the
producer binding as debt owned by DS16.

This module is that binding. Every member of the retired inventory resolves here to
exactly one disposition, and the disposition is **served**, never inferred by the client.

Why the contract is a refusal register
--------------------------------------
Measured, not assumed: of the eleven retired value families, **none** has a runtime
producer. The concepts either do not exist anywhere in `src/` (E-values, remedies,
embargo, stress rankings, revocation ledgers) or live only in the offline `scientist`
and `foundry` packages and have never been runtime-resident (fairness, harm, cohort
timelines). Establishing them is an *analysis* capability, and the DS16 plan's "Not yet"
list explicitly disclaims establishing the underlying analysis — this slice binds a
producer to a surface.

So the contract does not define value fields that the runtime would populate with
`null`. That shape is `contract_only` by construction and is exactly what the capability
reality check names. Instead every member is a **typed refusal**: a first-class served
record carrying the reason the value is absent and, where one exists, the surface that
legitimately owns the real data. The refusal is a value the runtime can and does supply.

This is also what makes C05's behavioural assertion writable. A discriminated `state`
gives the surface a *distinguishable* "no value" that is not an absent key — an optional
field is how "unavailable" silently becomes "zero" one slice later.

What was NOT minted
-------------------
`ScientificDepth` bound generated identifiability correctly (DS4-C23's own wording), and
`identifiability` is served today on `QuantityUncertainty` and `DecisionPacketEffectSize`.
It is therefore not a member of this inventory; it is recorded as the one value the
retired surface consumed honestly.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

INVENTORY_VERSION = "ds16-c03.1"

# The retired surfaces, kept as identity so a disposition can never drift from the
# module it was recovered from. `bc1d01001` is the DS4-C23 containment commit.
RETIRED_READINESS_MODULE = (
    "apps/runtime-dashboard/src/features/runs/domain/publicSectorReadiness.ts"
)
RETIRED_SCIENTIFIC_MODULE = "apps/runtime-dashboard/src/features/runs/domain/scientificDepth.ts"
RETIREMENT_COMMIT = "bc1d01001"


class AuthorityValueId(StrEnum):
    """Every value family the retired surfaces minted, recovered from their source."""

    READINESS_COMPOSITE_VERDICT = "readiness.composite_verdict"
    READINESS_LENS_PROJECTION = "readiness.lens_projection"
    READINESS_FAIRNESS_AUDIT = "readiness.fairness_audit"
    READINESS_HARM_ASSESSMENT = "readiness.harm_assessment"
    READINESS_EMBARGO_OVERLAY = "readiness.embargo_overlay"
    READINESS_SLOW_REVIEW = "readiness.slow_review"
    READINESS_REVOCATION_LEDGER = "readiness.revocation_ledger"
    SCIENTIFIC_IDENTIFIABILITY_REMEDY = "scientific.identifiability_remedy"
    SCIENTIFIC_SENSITIVITY_E_VALUE = "scientific.sensitivity_e_value"
    SCIENTIFIC_COHORT_TIMELINE = "scientific.cohort_timeline"
    SCIENTIFIC_STRESS_RANKING = "scientific.stress_ranking"


class ValueRefusalCode(StrEnum):
    """Why a value is refused. Every code is a property of the VALUE, never of effort."""

    NO_RUNTIME_COMPOSITION_RULE = "no_runtime_composition_rule"
    """No governed rule composes this value; composing one on the surface is the C23 sin."""

    NO_RUNTIME_ESTIMATOR = "no_runtime_estimator"
    """The estimator does not exist anywhere in the source tree."""

    ANALYSIS_NOT_RUNTIME_RESIDENT = "analysis_not_runtime_resident"
    """The analysis exists offline only; serving it would establish a new capability."""

    NO_RUNTIME_PRODUCER = "no_runtime_producer"
    """No producer of this concept exists in the source tree under any name."""

    OWNED_BY_ANOTHER_SURFACE = "owned_by_another_surface"
    """Real data exists and is already served by a different, named owner."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RefusedAuthorityValue(_StrictModel):
    """A served, first-class refusal. The absence itself is the supplied value."""

    value_id: AuthorityValueId
    state: Literal["refused"] = "refused"
    refusal_code: ValueRefusalCode
    reason: str = Field(min_length=1)
    retired_from: str = Field(min_length=1)
    owner_surface: str | None = None

    @model_validator(mode="after")
    def _owner_is_named_only_when_owned(self) -> Self:
        owned = self.refusal_code is ValueRefusalCode.OWNED_BY_ANOTHER_SURFACE
        if owned and not self.owner_surface:
            raise ValueError("owned_by_another_surface must name the owning surface")
        if not owned and self.owner_surface is not None:
            raise ValueError("only owned_by_another_surface may name an owning surface")
        return self


class SuppliedAuthorityValue(_StrictModel):
    """A value the runtime genuinely computes.

    The inventory holds none today. The variant exists so that a future supplied value
    slots in without a contract change, and so the discriminated union the surface reads
    is the same shape before and after.
    """

    value_id: AuthorityValueId
    state: Literal["supplied"] = "supplied"
    metric_id: str = Field(min_length=1)
    point: float | None = None


AuthorityValue = Annotated[
    RefusedAuthorityValue | SuppliedAuthorityValue,
    Field(discriminator="state"),
]


class RunAuthorityProjection(_StrictModel):
    """The complete disposition of the DS4-C23 inventory for one run.

    Completeness is enforced, not documented: a value silently dropped is the exact
    failure this slice exists to close, so the projection refuses to exist unless every
    `AuthorityValueId` is dispositioned exactly once.
    """

    run_id: str = Field(min_length=1)
    inventory_version: str = Field(min_length=1)
    retirement_commit: str = Field(min_length=1)
    values: tuple[AuthorityValue, ...]

    @model_validator(mode="after")
    def _inventory_is_complete_and_unique(self) -> Self:
        seen = [value.value_id for value in self.values]
        if len(seen) != len(set(seen)):
            raise ValueError("authority value inventory contains a duplicate member")
        if set(seen) != set(AuthorityValueId):
            missing = sorted(member.value for member in set(AuthorityValueId) - set(seen))
            raise ValueError(f"authority value inventory is incomplete: {missing}")
        return self


_READINESS_REFUSALS: tuple[tuple[AuthorityValueId, ValueRefusalCode, str, str | None], ...] = (
    (
        AuthorityValueId.READINESS_COMPOSITE_VERDICT,
        ValueRefusalCode.NO_RUNTIME_COMPOSITION_RULE,
        "No governed artifact defines how a readiness verdict is composed. The retired "
        "surface derived one from local thresholds, regexes, dwell state and disputes; "
        "the inputs are served by their own owners, the composition rule does not exist.",
        None,
    ),
    (
        AuthorityValueId.READINESS_LENS_PROJECTION,
        ValueRefusalCode.OWNED_BY_ANOTHER_SURFACE,
        "Stakeholder-lens projection is audience mapping, owned by the DS0/DS3 audience "
        "grammar. DS16 references that grammar and may not re-derive it.",
        "atlas audience mapping (DS0/DS3)",
    ),
    (
        AuthorityValueId.READINESS_FAIRNESS_AUDIT,
        ValueRefusalCode.ANALYSIS_NOT_RUNTIME_RESIDENT,
        "Fairness analysis is resident in the offline scientist and foundry packages and "
        "has no presence in the HTTP runtime. Serving it would establish an analysis "
        "capability, which this slice explicitly does not claim.",
        None,
    ),
    (
        AuthorityValueId.READINESS_HARM_ASSESSMENT,
        ValueRefusalCode.ANALYSIS_NOT_RUNTIME_RESIDENT,
        "Harm assessment is resident in the offline scientist and foundry packages and "
        "has no presence in the HTTP runtime. Serving it would establish an analysis "
        "capability, which this slice explicitly does not claim.",
        None,
    ),
    (
        AuthorityValueId.READINESS_EMBARGO_OVERLAY,
        ValueRefusalCode.NO_RUNTIME_PRODUCER,
        "No embargo concept exists anywhere in the source tree under any name; the "
        "retired overlay was constructed entirely on the surface.",
        None,
    ),
    (
        AuthorityValueId.READINESS_SLOW_REVIEW,
        ValueRefusalCode.NO_RUNTIME_PRODUCER,
        "Slow-review requirements were derived from browser dwell state held in local "
        "storage. Dwell time is interaction state and never became a runtime value.",
        None,
    ),
    (
        AuthorityValueId.READINESS_REVOCATION_LEDGER,
        ValueRefusalCode.NO_RUNTIME_PRODUCER,
        "No revocation ledger exists. The one 'revocation' token in the served schema is "
        "a step-up authentication class on a reissue endpoint, an unrelated concept.",
        None,
    ),
)

_SCIENTIFIC_REFUSALS: tuple[tuple[AuthorityValueId, ValueRefusalCode, str, str | None], ...] = (
    (
        AuthorityValueId.SCIENTIFIC_IDENTIFIABILITY_REMEDY,
        ValueRefusalCode.NO_RUNTIME_ESTIMATOR,
        "Identifiability state is served on QuantityUncertainty and was bound correctly "
        "by the retired surface. The REMEDY — which dataset, RCT or instrument would "
        "repair it, and its acquisition ref — requires an acquisition planner that does "
        "not exist in the source tree.",
        None,
    ),
    (
        AuthorityValueId.SCIENTIFIC_SENSITIVITY_E_VALUE,
        ValueRefusalCode.NO_RUNTIME_ESTIMATOR,
        "No E-value estimator exists anywhere in the source tree, so neither the E-value "
        "nor the claim-extinction verdict derived from it has a producer.",
        None,
    ),
    (
        AuthorityValueId.SCIENTIFIC_COHORT_TIMELINE,
        ValueRefusalCode.ANALYSIS_NOT_RUNTIME_RESIDENT,
        "Cohort transition analysis is resident offline and is not served per run; the "
        "retired timeline interpolated shares that no runtime computation produced.",
        None,
    ),
    (
        AuthorityValueId.SCIENTIFIC_STRESS_RANKING,
        ValueRefusalCode.NO_RUNTIME_PRODUCER,
        "No stress-scene or stress-ranking producer exists in the source tree; the "
        "retired ranking ordered scenes the surface itself invented.",
        None,
    ),
)


def _refusal(
    value_id: AuthorityValueId,
    code: ValueRefusalCode,
    reason: str,
    owner_surface: str | None,
) -> RefusedAuthorityValue:
    retired = (
        RETIRED_READINESS_MODULE
        if value_id.value.startswith("readiness.")
        else RETIRED_SCIENTIFIC_MODULE
    )
    return RefusedAuthorityValue(
        owner_surface=owner_surface,
        reason=" ".join(reason.split()),
        refusal_code=code,
        retired_from=retired,
        value_id=value_id,
    )


def authority_value_dispositions() -> tuple[AuthorityValue, ...]:
    """The inventory's dispositions, independent of any run."""

    return tuple(
        _refusal(value_id, code, reason, owner)
        for value_id, code, reason, owner in (*_READINESS_REFUSALS, *_SCIENTIFIC_REFUSALS)
    )


def build_run_authority_projection(run_id: str) -> RunAuthorityProjection:
    """Produce the complete disposition of the retired inventory for one run.

    Every member is dispositioned for every run. The projection's own validator refuses
    an incomplete inventory, so a value cannot be dropped by omission.
    """

    return RunAuthorityProjection(
        inventory_version=INVENTORY_VERSION,
        retirement_commit=RETIREMENT_COMMIT,
        run_id=run_id,
        values=authority_value_dispositions(),
    )


def authority_value_inventory_artifact() -> dict[str, object]:
    """The persisted, content-addressed form of the contract.

    Run-independent by construction: the dispositions are properties of the values, not
    of any run, so the artifact would be a lie if a run id could change it.
    """

    dispositions = [value.model_dump(mode="json") for value in authority_value_dispositions()]
    payload: dict[str, object] = {
        "inventory_version": INVENTORY_VERSION,
        "member_count": len(dispositions),
        "retired_modules": [RETIRED_READINESS_MODULE, RETIRED_SCIENTIFIC_MODULE],
        "retirement_commit": RETIREMENT_COMMIT,
        "values": dispositions,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {**payload, "content_sha256": f"sha256:{digest}"}
