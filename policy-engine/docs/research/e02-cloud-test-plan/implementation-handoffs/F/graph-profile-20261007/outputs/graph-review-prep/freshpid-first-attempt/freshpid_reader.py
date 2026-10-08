"""Read actual persisted graph artifacts from a distinct, isolated interpreter."""

import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    specification = json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0, str(Path(specification["product_root"]) / "src"))
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.analytics.causal_graph import load_causal_graph_model
    from polisyos.ir.analytics.mgraph import extract_mgraph_metadata

    assert os.getpid() != specification["producer_pid"]
    store = FileSystemCAS(specification["cas_root"])
    original = load_causal_graph_model(
        store, ArtifactRef.model_validate(specification["original_mgraph_ref"])
    )
    reconciled = load_causal_graph_model(
        store, ArtifactRef.model_validate(specification["reconciled_admg_ref"])
    )
    assert original.model_dump(mode="json") == specification["original_mgraph"]
    assert original.graph_type.value == "mgraph"
    assert extract_mgraph_metadata(original).model_dump(mode="json") == specification[
        "original_missingness_metadata"
    ]
    assert reconciled.model_dump(mode="json") == specification["reconciled_admg"]
    assert reconciled.graph_type.value == "admg"
    original_relations = {
        (edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value, edge.lag)
        for edge in original.edges
    }
    reconciled_relations = {
        (edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value, edge.lag)
        for edge in reconciled.edges
    }
    assert original_relations == reconciled_relations == {
        ("X", "Y", "tail", "arrow", None),
        ("X", "Y", "arrow", "arrow", None),
        ("R_X", "X_star", "tail", "arrow", None),
    }
    assert reconciled.metadata["mgraph"] == original.metadata["mgraph"]
    reverse = load_causal_graph_model(store, ArtifactRef.model_validate(specification["reverse_admg_ref"]))
    assert reverse.model_dump(mode="json") == specification["reverse_admg"]
    assert reverse.graph_type.value == "admg"
    assert {(edge.src, edge.dst, edge.mark_src.value, edge.mark_dst.value, edge.lag) for edge in reverse.edges} == {("X", "Y", "tail", "arrow", None)}
    origins = []
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("polisyos"):
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            continue
        path = Path(origin).resolve()
        body = path.read_bytes()
        origins.append(
            {"module": name, "path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        )
    print(
        json.dumps(
            {
                "check": "PASS",
                "pid": os.getpid(),
                "producer_pid": specification["producer_pid"],
                "isolated": sys.flags.isolated,
                "source_sha": specification["source_sha"],
                "metrics_port_env": os.environ.get("POLISYOS_METRICS_PORT"),
                "original_mgraph_ref": specification["original_mgraph_ref"],
                "reconciled_admg_ref": specification["reconciled_admg_ref"],
                "reverse_admg_ref": specification["reverse_admg_ref"],
                "original_mgraph_metadata": extract_mgraph_metadata(original).model_dump(mode="json"),
                "relation_count": len(original_relations),
                "loaded_origins": origins,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
