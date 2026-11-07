"""Source-backed local producers for candidate executable continuity tests."""

from __future__ import annotations

import builtins
import importlib
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict, PrivateAttr

from polisyos.core.artifacts import ArtifactWriteOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


class AdmissionNode:
    """One actual SQLite effect and selected CAS output, with passive config."""

    def __init__(self, database: Path, value: int = 7) -> None:
        self.database = database
        self.value = value

    @property
    def spec(self) -> InputAwareNodeSpec:
        return InputAwareNodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_admission_probe@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                capabilities=Capability.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
            ),
            state_writes=["params.result"],
            input_rules=(),
        )

    def bind(self, params: dict[str, int]) -> AdmissionNode:
        return type(self)(self.database, params.get("value", self.value))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects(value INTEGER)")
            connection.execute("INSERT INTO effects VALUES (?)", (self.value,))
        ref = ctx.store.put_json(
            {"value": self.value},
            ArtifactWriteOptions(kind="fixture.admission.result", media_type="application/json"),
            return_selected_profile=True,
        )
        state.params["result"] = self.value
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


class ChangedAdmissionNode(AdmissionNode):
    """Same component/spec but a different real implementation."""

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        raise AssertionError("changed implementation must be refused before this effect")


class OtherAdmissionNode(AdmissionNode):
    """A distinct actual residual registration in a mixed supported population."""

    @property
    def spec(self) -> InputAwareNodeSpec:
        spec = super().spec
        spec.metadata = spec.metadata.model_copy(
            update={"component_id": ComponentId.parse("scientist.node_other_admission_probe@1.0.0")}
        )
        return spec


class AdmissionSettings(BaseModel):
    """Settings whose private and extra values must remain part of config."""

    model_config = ConfigDict(extra="allow")

    value: int = 7
    _offset: int = PrivateAttr(default=1)


class ConfiguredAdmissionNode(AdmissionNode):
    """Actual producer reads private and extra settings before its effect."""

    def __init__(self, database: Path) -> None:
        super().__init__(database)
        self.settings = AdmissionSettings(extra_offset=2)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.value = (
            self.settings.value
            + self.settings._offset
            + self.settings.extra_offset
            + (10 if "value" in self.settings.model_fields_set else 0)
        )
        return super().execute(ctx, state)


class RuntimeImportAdmissionNode(AdmissionNode):
    """A method-local dependency is outside the finite source profile."""

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        import sqlite3 as dynamic_dependency

        del dynamic_dependency
        return super().execute(ctx, state)


class NestedImportAdmissionNode(AdmissionNode):
    """Nested callable imports must not evade the same profile boundary."""

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        def nested():
            import sqlite3 as dependency

            return dependency

        nested()
        return super().execute(ctx, state)


class DynamicImportAdmissionNode(AdmissionNode):
    """An explicit dynamic loader does not provide a closed source basis."""

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        importlib.import_module("sqlite3")
        return super().execute(ctx, state)


class BuiltinsImportAdmissionNode(AdmissionNode):
    """A loader obtained through the builtins module is equally unsupported."""

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        builtins.__import__("sqlite3")
        return super().execute(ctx, state)
