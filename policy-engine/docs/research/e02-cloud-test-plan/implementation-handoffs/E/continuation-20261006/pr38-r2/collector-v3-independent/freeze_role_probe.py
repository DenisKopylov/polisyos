"""Synthetic external-freeze role probe, zero native/gate commands."""

import hashlib
import json
import runpy
import shutil
import sys
from argparse import Namespace
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact value.
        "y flush without logging side effects."  # Exact value.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).parent
SOURCE = Path(
    "/workspace/e02-E-pr38-r2-receipts/common"  # Exact value.
    "-wave-publication-prep/collect_wave_v3_f"  # Exact value.
    "inal.py"  # Exact value.
)
OLD = Path(
    "/workspace/e02-E-pr38-r2-receipts/common-wave-publication-pr"
    "ep/synthetic-controls-v2/positive/wave"
)
module = runpy.run_path(str(SOURCE), run_name="independent_synthetic_freeze_role_probe")
if not (
    hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    == "a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec"
):
    raise AssertionError


def rewrite(value: object, wave: object) -> object:
    if isinstance(value, str):
        return value.replace(str(OLD), str(wave))
    if isinstance(value, list):
        return [rewrite(v, wave) for v in value]
    if isinstance(value, dict):
        return {k: rewrite(v, wave) for k, v in value.items()}
    return value


rows = []
for role in ["raw", "private"]:
    wave = OUT / "synthetic-freeze-role" / role / "wave"
    shutil.copytree(OLD, wave)
    for path in wave.rglob("*.json"):
        path.write_text(json.dumps(rewrite(json.loads(path.read_text()), wave), indent=2) + "\n")
    plan = json.loads((wave / "plan.json").read_text())
    freeze = wave / role / "source-freeze.json"
    freeze.parent.mkdir(exist_ok=True)
    data = {
        "frozen_sha": plan["candidate_sha"],
        "tree": plan["candidate_tree_sha"],
        "one_wave_output_root": str(wave),
        "remote_ls_readback_sha": plan["candidate_sha"],
        "source_tree_dirty": False,
        "reviews": [],
        (
            "synthetic_only_marker"  # Exact value.
        ): (
            "private/raw role marker is synthetic and"  # Exact value.
            " carries no actual config"  # Exact value.
        ),
    }
    freeze.write_text(json.dumps(data, indent=2) + "\n")
    publication = wave.parent / "publication"
    observed = module["collect"](
        Namespace(
            repo=ROOT,
            candidate=plan["candidate_sha"],
            wave_root=wave,
            publication_root=publication,
            freeze_receipt=freeze,
            max_moderate_bytes=8 * 1024 * 1024,
            capture_incomplete=False,
        )
    )
    copied = publication / "source-freeze-receipt.json"
    rows.append(
        {
            "role": role,
            "source_path": str(freeze),
            "state": observed["collection_state"],
            "synthetic_payload_copied": copied.read_bytes() == freeze.read_bytes(),
            "product_native_or_gate_commands_executed": 0,
        }
    )
result = {
    "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "scope": "Synthetic role-only probe; no actual private input touched",
    "controls": rows,
    "property": (
        "The explicit freeze_receipt copy uses freeze.parent as admis"
        "sion root and discards raw/private parent role."
    ),
}
(OUT / "freeze-role-probe.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
