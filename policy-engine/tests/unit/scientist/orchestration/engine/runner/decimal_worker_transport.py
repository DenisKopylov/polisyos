"""Importable child-process fixture for exact Decimal worker transport."""

from __future__ import annotations

import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState


class DecimalTransportNode:
    """Echo a state only after checking exact Decimal values in the worker."""

    spec = NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_decimal_transport@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="DecimalTransport",
            description="Physical Decimal transport probe",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=["budgets"],
        state_writes=[],
    )

    def __init__(self, expected_budgets: dict[str, Decimal], attempts_path: str) -> None:
        self._expected_budgets = expected_budgets
        self._attempts_path = Path(attempts_path)

    def execute(self, _ctx: Any, state: ExperimentState) -> NodeOutcome:
        for key, value in self._expected_budgets.items():
            assert type(state.budgets[key]) is Decimal
            assert state.budgets[key].as_tuple() == value.as_tuple()

        # Observe the live OS ownership chain before retry owners reap an
        # attempt. A supervisor may own the attempt on the worker's behalf.
        ancestry = []
        cursor = os.getpid()
        observed = set()
        while cursor > 0:
            assert cursor not in observed, "cyclic physical process ancestry"
            observed.add(cursor)
            status = Path(f"/proc/{cursor}/status")
            if status.is_file():
                ppid = next(
                    int(line.split()[1])
                    for line in status.read_text().splitlines()
                    if line.startswith("PPid:")
                )
            else:
                # macOS has no procfs; ps reports the same live OS relation.
                ppid = int(
                    subprocess.check_output(
                        ["ps", "-o", "ppid=", "-p", str(cursor)], text=True
                    ).strip()
                )
            ancestry.append({"pid": cursor, "ppid": ppid})
            cursor = ppid

        with self._attempts_path.open("a") as output:
            output.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "ppid": os.getppid(),
                        "run_id": state.run_id,
                        "ancestry": ancestry,
                    }
                )
                + "\n"
            )
        return NodeOutcome(status="ok", state=state, events=[], artifacts=[])


def execute_decimal_worker(
    payload: dict[str, Any],
    backend: str,
    expected_budgets: dict[str, Decimal],
    attempts_path: str,
    result_sender: Any,
) -> None:
    """Run the production worker bridge from an importable fresh process."""
    registry_module = None
    original_discover_nodes = None
    try:
        from polisyos.scientist.orchestration.engine import registry as registry_module
        from polisyos.scientist.orchestration.engine.runner import serialization as wire

        original_discover_nodes = registry_module.discover_nodes
        if backend == "stdlib":
            wire._dumps = lambda obj: json.dumps(obj, separators=(",", ":")).encode()
            wire._loads = json.loads
        elif backend == "orjson":
            if wire.orjson is None:
                raise RuntimeError("orjson backend requested but unavailable in child")
            wire._dumps = wire.orjson.dumps
            wire._loads = wire.orjson.loads
        else:
            raise ValueError(f"unsupported worker wire backend: {backend}")
        wire._WIRE_MODEL_TYPES = None

        def discover_probe_node(registry: Any, *_args: Any, **_kwargs: Any) -> Any:
            return registry.register(DecimalTransportNode(expected_budgets, attempts_path))

        registry_module.discover_nodes = discover_probe_node
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_in_worker_sync,
        )

        result_sender.send(("result", run_node_in_worker_sync(payload)))
    except BaseException as error:
        result_sender.send(("error", f"{type(error).__name__}: {error!r}"))
    finally:
        if registry_module is not None and original_discover_nodes is not None:
            registry_module.discover_nodes = original_discover_nodes
        result_sender.close()
