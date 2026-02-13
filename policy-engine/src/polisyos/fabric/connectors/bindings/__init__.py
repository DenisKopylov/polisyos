"""Binding profiles — reusable data-schema-to-Foundry-slot mapping configurations.

This package is pure-data: NO jax, numpy, or heavy execution imports.
"""

from .models import BindingProfile, BindingRuleSpec, BindingStrategy, BindingTransformSpec
from .registry import BindingProfileRegistry

__all__ = [
    "BindingProfile",
    "BindingProfileRegistry",
    "BindingRuleSpec",
    "BindingStrategy",
    "BindingTransformSpec",
]
