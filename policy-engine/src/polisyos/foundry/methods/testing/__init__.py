"""
Testing Infrastructure for Foundry Methods.

Provides utilities for validating FoundryMethod implementations, including
protocol compliance checks, JAX transformation verification, and golden record
regression testing (Law M).
"""
from __future__ import annotations

from polisyos.foundry.methods.testing.fixtures import (
    SampleParamsFactory,
    SampleStateFactory,
    create_sample_params,
    create_sample_state,
)
from polisyos.foundry.methods.testing.golden import (
    GoldenContext,
    GoldenRecord,
    GoldenRecordRef,
    GoldenStore,
    GoldenVerificationResult,
    VerificationStatus,
    hash_pytree,
)
from polisyos.foundry.methods.testing.jax_suite import JaxMethodTestSuite
from polisyos.foundry.methods.testing.numpy_suite import (
    NumpyMethodTestSuite,
    NumpySuiteResult,
)
from polisyos.foundry.methods.testing.solver_suite import (
    SolverMethodTestSuite,
    SolverSuiteResult,
)
from polisyos.foundry.methods.testing.suite import (
    CheckCategory,
    MethodTestSuite,
    TestCheck,
    TestResult,
)

__all__ = [
    "MethodTestSuite",
    "TestCheck",
    "TestResult",
    "CheckCategory",
    "GoldenContext",
    "GoldenRecord",
    "GoldenStore",
    "GoldenRecordRef",
    "GoldenVerificationResult",
    "VerificationStatus",
    "hash_pytree",
    "create_sample_state",
    "create_sample_params",
    "SampleStateFactory",
    "SampleParamsFactory",
    "JaxMethodTestSuite",
    "NumpyMethodTestSuite",
    "NumpySuiteResult",
    "SolverMethodTestSuite",
    "SolverSuiteResult",
]
