"""Model profile registry for scientist LLM runs."""

from .models import ModelProfile
from .registry import ModelProfileRegistry

__all__ = [
    "ModelProfile",
    "ModelProfileRegistry",
]
