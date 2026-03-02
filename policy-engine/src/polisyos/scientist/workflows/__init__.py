from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scientist.workflows.builder import (
        build_default_registry,
        build_execution_context,
        build_registry_with_builtin_nodes,
        run_causal_full_workflow,
        run_default_workflow,
    )
    from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
    from polisyos.scientist.workflows.default import default_workflow_spec
    from polisyos.scientist.workflows.engine_base import WorkflowEngine, WorkflowEngineFactory
    from polisyos.scientist.workflows.engine_langgraph import (
        LangGraphEngine,
        LangGraphEngineFactory,
    )
    from polisyos.scientist.workflows.engine_simple import SimpleLoopEngine

__all__ = [
    "WorkflowEngine",
    "WorkflowEngineFactory",
    "LangGraphEngine",
    "LangGraphEngineFactory",
    "SimpleLoopEngine",
    "build_default_registry",
    "build_execution_context",
    "build_registry_with_builtin_nodes",
    "run_default_workflow",
    "run_causal_full_workflow",
    "default_workflow_spec",
    "causal_full_workflow_spec",
]


def __getattr__(name: str):
    if name in {
        "build_default_registry",
        "build_execution_context",
        "build_registry_with_builtin_nodes",
        "run_causal_full_workflow",
        "run_default_workflow",
    }:
        from polisyos.scientist.workflows.builder import (
            build_default_registry,
            build_execution_context,
            build_registry_with_builtin_nodes,
            run_causal_full_workflow,
            run_default_workflow,
        )

        return {
            "build_default_registry": build_default_registry,
            "build_execution_context": build_execution_context,
            "build_registry_with_builtin_nodes": build_registry_with_builtin_nodes,
            "run_causal_full_workflow": run_causal_full_workflow,
            "run_default_workflow": run_default_workflow,
        }[name]
    if name in {"default_workflow_spec", "causal_full_workflow_spec"}:
        from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
        from polisyos.scientist.workflows.default import default_workflow_spec

        return {
            "default_workflow_spec": default_workflow_spec,
            "causal_full_workflow_spec": causal_full_workflow_spec,
        }[name]
    if name in {"WorkflowEngine", "WorkflowEngineFactory"}:
        from polisyos.scientist.workflows.engine_base import WorkflowEngine, WorkflowEngineFactory

        return {
            "WorkflowEngine": WorkflowEngine,
            "WorkflowEngineFactory": WorkflowEngineFactory,
        }[name]
    if name == "SimpleLoopEngine":
        from polisyos.scientist.workflows.engine_simple import SimpleLoopEngine

        return SimpleLoopEngine
    if name in {"LangGraphEngine", "LangGraphEngineFactory"}:
        from polisyos.scientist.workflows.engine_langgraph import (
            LangGraphEngine,
            LangGraphEngineFactory,
        )

        return {
            "LangGraphEngine": LangGraphEngine,
            "LangGraphEngineFactory": LangGraphEngineFactory,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
