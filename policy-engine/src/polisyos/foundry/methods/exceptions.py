"""
Foundry Methods Exception Hierarchy

All exceptions for method-related errors inherit from FoundryMethodError.
Each exception includes context attributes for structured logging and diagnostics.
"""
from __future__ import annotations


class FoundryMethodError(Exception):
    """
    Base exception for all Foundry method errors.

    All method-related exceptions inherit from this class,
    enabling catch-all handling when appropriate.
    """


class MethodDefinitionError(FoundryMethodError):
    """
    Method class is incorrectly defined.

    Raised by @foundry_method decorator when protocol requirements
    are not met (missing signature, pure_step not static, etc.).
    """


class MethodNotFoundError(FoundryMethodError):
    """
    Method not found in registry.

    Raised when attempting to retrieve a method that doesn't exist
    or doesn't match resolution criteria.

    Attributes:
        name: Requested method name or FQN
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Method not found: {name}")


class MethodAlreadyRegisteredError(FoundryMethodError):
    """
    Method already exists in registry.

    Raised when attempting to register a method with the same
    fully qualified name (FQN) as an existing registration.

    Attributes:
        fqn: Fully qualified name of the duplicate method
    """

    def __init__(self, fqn: str) -> None:
        self.fqn = fqn
        super().__init__(f"Method already registered: {fqn}")


class SlotConnectionError(FoundryMethodError):
    """
    Base exception for slot connection failures.

    Raised when slots cannot be connected in method composition.
    Subclasses provide specific failure reasons.
    """


class UnitMismatchError(SlotConnectionError):
    """
    Units are incompatible for slot connection.

    Raised when attempting to connect slots with different dimensions.
    Scale differences within the same dimension are handled by
    the Slot Linker, not raised as errors.

    Attributes:
        source_slot: Name of the source (output) slot
        target_slot: Name of the target (input) slot
        source_unit: Source unit symbol
        target_unit: Target unit symbol
    """

    def __init__(
        self,
        source_slot: str,
        target_slot: str,
        source_unit: str,
        target_unit: str,
    ) -> None:
        self.source_slot = source_slot
        self.target_slot = target_slot
        self.source_unit = source_unit
        self.target_unit = target_unit
        super().__init__(
            f"Unit mismatch: {source_slot}({source_unit}) -> "
            f"{target_slot}({target_unit})"
        )


class ShapeMismatchError(SlotConnectionError):
    """
    Shapes are incompatible for slot connection.

    Raised when attempting to connect slots with incompatible array shapes.

    Attributes:
        source_slot: Name of the source (output) slot
        target_slot: Name of the target (input) slot
        source_shape: Source slot shape tuple
        target_shape: Target slot shape tuple
    """

    def __init__(
        self,
        source_slot: str,
        target_slot: str,
        source_shape: tuple,
        target_shape: tuple,
    ) -> None:
        self.source_slot = source_slot
        self.target_slot = target_slot
        self.source_shape = source_shape
        self.target_shape = target_shape
        super().__init__(
            f"Shape mismatch: {source_slot}{source_shape} -> "
            f"{target_slot}{target_shape}"
        )


class CyclicDependencyError(FoundryMethodError):
    """
    Method chain contains a cycle.

    Raised during DAG composition when methods form
    a cyclic dependency that cannot be topologically sorted.

    Attributes:
        cycle: List of method names forming the cycle
    """

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        cycle_str = " -> ".join(cycle + [cycle[0]])
        super().__init__(f"Cyclic dependency detected: {cycle_str}")


class CompilationError(FoundryMethodError):
    """
    Failed to compile method or chain.

    Raised during compilation when JAX compilation fails
    or other compilation-time errors occur.

    Attributes:
        method_fqn: Fully qualified name of the method that failed
        reason: Detailed failure reason
    """

    def __init__(self, method_fqn: str, reason: str) -> None:
        self.method_fqn = method_fqn
        self.reason = reason
        super().__init__(f"Compilation failed for {method_fqn}: {reason}")


class ParameterValidationError(FoundryMethodError):
    """
    Parameter value is invalid.

    Raised when a parameter value violates bounds or type constraints.

    Attributes:
        param_name: Name of the invalid parameter
        value: The invalid value
        reason: Why the value is invalid
    """

    def __init__(self, param_name: str, value: object, reason: str) -> None:
        self.param_name = param_name
        self.value = value
        self.reason = reason
        super().__init__(
            f"Invalid parameter '{param_name}' = {value!r}: {reason}"
        )


class ArtifactError(FoundryMethodError):
    """
    Error related to method artifacts (provenance, CAS storage).

    Attributes:
        artifact_type: Type of artifact (e.g., "MethodArtifact")
        reason: Failure reason
    """

    def __init__(self, artifact_type: str, reason: str) -> None:
        self.artifact_type = artifact_type
        self.reason = reason
        super().__init__(f"{artifact_type} error: {reason}")


class LawViolationError(FoundryMethodError):
    """
    Raised when runtime checks detect a violation of architecture laws.

    Used in strict mode to validate Law F (pure_step inputs).

    Attributes:
        law: Law identifier (e.g., "F")
        reason: Failure reason
    """

    def __init__(self, law: str, reason: str) -> None:
        self.law = law
        self.reason = reason
        super().__init__(f"Law {law} violation: {reason}")
