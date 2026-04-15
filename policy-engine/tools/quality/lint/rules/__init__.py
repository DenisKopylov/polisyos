"""Registry for extensible lint rules."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuleContext:
    path: Path
    repo_root: Path
    source: str
    tree: Any
    policy: str
    data: dict[str, Any]


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    path: Path
    lineno: int
    message: str
    fixable: bool = False
    start_lineno: int | None = None
    end_lineno: int | None = None


@dataclass(frozen=True)
class RuleFix:
    rule_id: str
    path: Path
    description: str
    rendered_source: str


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    description: str
    check: Callable[[RuleContext], Sequence[RuleViolation]]
    fix: Callable[[RuleContext, Sequence[RuleViolation]], RuleFix | None] | None = None


_RULES: dict[str, RuleDefinition] = {}
_LOADED = False


def register_rule(rule: RuleDefinition) -> RuleDefinition:
    """Register a lint rule definition."""

    _RULES[rule.rule_id] = rule
    return rule


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")
    _LOADED = True


def iter_rules(prefix: str | None = None) -> tuple[RuleDefinition, ...]:
    """Return registered rules, optionally filtered by prefix."""

    _ensure_loaded()
    rules = tuple(sorted(_RULES.values(), key=lambda rule: rule.rule_id))
    if prefix is None:
        return rules
    return tuple(rule for rule in rules if rule.rule_id.startswith(prefix))
