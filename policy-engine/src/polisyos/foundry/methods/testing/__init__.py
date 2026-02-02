"""
Testing Infrastructure for Foundry Methods.

Provides utilities for validating FoundryMethod implementations, including
protocol compliance checks, JAX transformation verification, and golden record
regression testing (Law M).
"""
from __future__ import annotations

from polisyos.foundry.methods.testing.suite import (
    MethodTestSuite,
    TestCheck,
    TestResult,
    CheckCategory,
)
from polisyos.foundry.methods.testing.golden import (
    GoldenContext,
    GoldenRecord,
    GoldenStore,
    GoldenRecordRef,
    GoldenVerificationResult,
    VerificationStatus,
    hash_pytree,
)
from polisyos.foundry.methods.testing.fixtures import (
    create_sample_state,
    create_sample_params,
    SampleStateFactory,
    SampleParamsFactory,
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
]
