"""Import-light names shared by option/program consumers and its verifier."""

from __future__ import annotations

from typing import Literal

OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED = "option_program_correspondence_not_established"

DeclaredProgramCorrespondenceStatus = Literal[
    "declared_program_match", "mismatch", "not_established"
]

__all__ = [
    "OPTION_PROGRAM_CORRESPONDENCE_NOT_ESTABLISHED",
    "DeclaredProgramCorrespondenceStatus",
]
