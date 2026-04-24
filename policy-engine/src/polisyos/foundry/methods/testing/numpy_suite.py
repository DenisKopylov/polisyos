"""Public testing numpy suite module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from polisyos.foundry.methods.base import MethodSignature


@dataclass(frozen=True, slots=True)
class NumpySuiteResult:
    """Report whether a NumPy-backend output passed lightweight backend checks."""

    passed: bool
    message: str = ""


class NumpyMethodTestSuite:
    """Lightweight checks for NUMPY backend methods."""

    def __init__(self, signature: MethodSignature) -> None:
        self.signature = signature

    def validate_output(self, output: Any) -> NumpySuiteResult:
        if isinstance(output, dict):
            for value in output.values():
                if isinstance(value, np.ndarray):
                    if value.dtype == object:
                        return NumpySuiteResult(False, "object dtype arrays are not allowed")
            return NumpySuiteResult(True)
        if isinstance(output, np.ndarray) and output.dtype == object:
            return NumpySuiteResult(False, "object dtype arrays are not allowed")
        return NumpySuiteResult(True)
