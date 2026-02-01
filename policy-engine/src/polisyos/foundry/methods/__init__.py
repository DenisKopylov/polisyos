"""
Foundry Methods Core Types & Protocol.

Phase 3.1 Public API.
"""
from __future__ import annotations

from polisyos.foundry.methods.base import (
    FoundryMethod,
    MethodSignature,
    MethodMetadata,
    SlotSpec,
    SlotType,
    ParameterSpec,
    Unit,
    FidelityLevel,
    ComplexityClass,
    foundry_method,
    check_protocol_compliance,
    parse_fqn,
    is_valid_semver,
)

from polisyos.foundry.methods.exceptions import (
    FoundryMethodError,
    MethodDefinitionError,
    MethodNotFoundError,
    MethodAlreadyRegisteredError,
    SlotConnectionError,
    UnitMismatchError,
    ShapeMismatchError,
    CyclicDependencyError,
    CompilationError,
    ParameterValidationError,
    ArtifactError,
    LawViolationError,
)

__all__ = [
    "FoundryMethod",
    "MethodSignature",
    "MethodMetadata",
    "SlotSpec",
    "SlotType",
    "ParameterSpec",
    "Unit",
    "FidelityLevel",
    "ComplexityClass",
    "foundry_method",
    "check_protocol_compliance",
    "parse_fqn",
    "is_valid_semver",
    "FoundryMethodError",
    "MethodDefinitionError",
    "MethodNotFoundError",
    "MethodAlreadyRegisteredError",
    "SlotConnectionError",
    "UnitMismatchError",
    "ShapeMismatchError",
    "CyclicDependencyError",
    "CompilationError",
    "ParameterValidationError",
    "ArtifactError",
    "LawViolationError",
]

__version__ = "3.1.0"
