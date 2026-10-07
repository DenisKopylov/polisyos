"Independent packet validator recomputes edge denominators and file identity."

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


observed_o = Path(__file__).parent
R = Path("/workspace/e02-E-continuation-20261006")


def _admit_require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


_NO_PATH = object()


def admit_source(sha: object, path: object = _NO_PATH) -> None:
    """Refuse unbound or option-like Git objects before any child process."""
    _admit_require(
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
        "source requires an exact commit SHA",
    )
    if path is not _NO_PATH:
        _admit_require(isinstance(path, str) and bool(path), "source path requires a string")
        _admit_require(
            not any(character.isspace() or character == "\0" for character in path),
            "source path contains ambiguous characters",
        )
        relative = Path(path)
        _admit_require(
            not relative.is_absolute()
            and bool(relative.parts)
            and relative.as_posix() == path
            and ".." not in relative.parts,
            "source path must be repository relative",
        )
        _admit_require(not path.startswith("-") and ":" not in path, "source path is ambiguous")


def validate(d: object) -> None:
    admit_source(d["source_scope"]["publication_companion_sha"])
    for reference in d["artifact_refs"]:
        admit_source(d["source_scope"]["publication_companion_sha"], reference["path"])
    if not (d["schema"] == "e02.E.public_surface_import_owner_packet.v1"):
        raise AssertionError
    actual = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [
            _resolve_executable("git"),
            "rev-parse",
            d["source_scope"]["publication_companion_sha"] + "^{tree}",
        ],
        cwd=R,
        text=True,
    ).strip()
    if not (actual == d["source_scope"]["publication_companion_tree"]):
        raise AssertionError("candidate tree")
    rows = d["edge_symbol_owner_matrix"]
    original = [r for r in rows if r["scope"] == "original audit12"]
    bkt = [r for r in rows if r["scope"] == "BKT separate family delta"]
    frc = [r for r in rows if r["scope"] == "FRC separate family delta"]
    if not (len(original) == 12 and len(bkt) == 7 and len(frc) == 1):
        raise AssertionError
    pending = [r for r in rows if r["status"] == "pending_owner_admission"]
    if not (d["denominators"]["targeted_current_pending_owner_edges"] == len(pending) == 14):
        raise AssertionError("pending denominator")
    if not (
        sum(r["status"] == "pending_owner_admission" for r in original)
        == d["denominators"]["original12_remaining_owner_edges"]
        == 9
    ):
        raise AssertionError
    if not (
        sum(r["status"] == "resolved_existing_E_facade" for r in original)
        == d["denominators"]["original12_resolved_edges"]
        == 3
    ):
        raise AssertionError
    if not (
        sum(r["status"] == "pending_owner_admission" for r in bkt)
        == d["denominators"]["BKT_separate_pending_owner_edges"]
        == 5
    ):
        raise AssertionError
    if not (d["owner_preview_native"]["owner_admission"] == "not_ratified"):
        raise AssertionError("owner admission cannot be minted by library preview")
    if not (
        d["denominators"]["new_unadmitted_cross_root_module_edges"] == 12
        and d["denominators"]["E_changed_path_report_rows"] == 35
        and d["denominators"]["all_report_rows"] == 163
    ):
        raise AssertionError
    seen = set()
    for ref in d["artifact_refs"]:
        if not (ref["path"] not in seen):
            raise AssertionError
        seen.add(ref["path"])
        p = observed_o / ref["path"]
        b = p.read_bytes()
        if not (len(b) == ref["bytes"]):
            raise AssertionError(("size", ref["path"]))
        if not (hashlib.sha256(b).hexdigest() == ref["sha256"]):
            raise AssertionError(("hash", ref["path"]))
    if not (
        d["publication_companion"]["candidate_sha"]
        == d["source_scope"]["publication_companion_sha"]
        and d["publication_companion"]["verdict"] == "GO"
    ):
        raise AssertionError
    if d["publication_companion"]["unrelated_inventory_delta"] is not False:
        raise AssertionError
    if not (d["publication_companion"]["public_surface"]["polisyos.calibration"]["count"] == 28):
        raise AssertionError
    if not (
        d["publication_companion"]["public_surface"]["polisyos.foundry.uncertainty"]["count"] == 16
    ):
        raise AssertionError


packet = json.loads((observed_o / "packet.json").read_text())
validate(packet)
controls = []
for label, mutation in [
    ("corrupt-hash-marker-retained", lambda d: d["artifact_refs"][0].update(sha256="0" * 64)),
    (
        "corrupt-size-marker-retained",
        lambda d: d["artifact_refs"][0].update(bytes=d["artifact_refs"][0]["bytes"] + 1),
    ),
    (
        "denominator-zero-marker-retained",
        lambda d: d["denominators"].update(targeted_current_pending_owner_edges=0),
    ),
    (
        "minted-owner-admission",
        lambda d: d["owner_preview_native"].update(owner_admission="ratified"),
    ),
]:
    d = copy.deepcopy(packet)
    mutation(d)
    try:
        validate(d)
    except AssertionError as exc:
        controls.append({"name": label, "outcome": "REJECTED", "reason": str(exc)})
    else:
        raise AssertionError("corrupt packet passed " + label)
result = {
    "outcome": "PASS",
    "artifact_refs_validated": len(packet["artifact_refs"]),
    "matrix_rows_validated": len(packet["edge_symbol_owner_matrix"]),
    "negative_controls": controls,
    "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(observed_o / "packet-validation.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
