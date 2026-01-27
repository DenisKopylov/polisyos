"""Workflow engine abstractions and implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.workflow.engine_base import WorkflowEngine, WorkflowEngineFactory
from polisyos.scientist.workflow.engine_simple import SimpleLoopEngine

if TYPE_CHECKING:
    from polisyos.scientist.workflow.engine_langgraph import LangGraphEngine, LangGraphEngineFactory

__all__ = [
    "WorkflowEngine",
    "WorkflowEngineFactory",
    "LangGraphEngine",
    "LangGraphEngineFactory",
    "SimpleLoopEngine",
]


def __getattr__(name: str):
    if name in {"LangGraphEngine", "LangGraphEngineFactory"}:
        from polisyos.scientist.workflow.engine_langgraph import (
            LangGraphEngine,
            LangGraphEngineFactory,
        )

        return {"LangGraphEngine": LangGraphEngine, "LangGraphEngineFactory": LangGraphEngineFactory}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
