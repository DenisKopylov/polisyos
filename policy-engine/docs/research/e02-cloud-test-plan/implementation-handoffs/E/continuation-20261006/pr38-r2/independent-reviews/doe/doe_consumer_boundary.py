(
    "Fresh default-codec and evaluator-pair p"  # Exact bound literal continuation.
    "rovenance boundaries, no source writes."  # Exact bound literal continuation.
)

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.methods.autotune.models import MutationArtifact
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SequenceCandidateGenerator,
)
from polisyos.scientist.methods.doe._receipt import _load_analysis, _persist_analysis
from polisyos.scientist.methods.doe.analysis import analyze_sensitivity
from polisyos.scientist.methods.doe.designs import SensitivityPlan
from polisyos.scientist.methods.search.sensitivity_adapter import SensitivityAwareCandidateGenerator


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-doe-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer")


def snapshot() -> str:
    names = (
        subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "ls-files", "-z", "policy-engine/src"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in names if p}
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


before = snapshot()
store = FileSystemCAS(OUT / "doe-native-cas")
refs = json.loads((OUT / "doe_refs.json").read_text())
ref = ArtifactRef.model_validate(refs["canonical"])
base = MutationArtifact(loop_id="independent_sensitivity_review")
codec = PydanticMutationCodec(MutationArtifact)
if not (codec.decode(base.model_dump(mode="json")) == base):
    raise AssertionError
wrapped = SensitivityAwareCandidateGenerator.from_artifact(
    SequenceCandidateGenerator([base]), store, ref
)
candidate = wrapped.generate([], None, {})
if not (candidate["_sensitivity"]["analysis_ref"] == ref.model_dump(mode="json")):
    raise AssertionError
try:
    codec.decode(candidate)
except ValueError as exc:
    codec_error = {"type": type(exc).__name__, "message": str(exc)}
else:
    raise AssertionError(
        "Expected default PydanticMutationCodec t"  # Exact bound literal continuation.
        "o refuse unadmitted metadata field"  # Exact bound literal continuation.
    )
_write_stdout(
    json.dumps(
        {
            "case": "default_codec_admits_base_refuses_decorator_metadata",
            "outcome": "OBSERVED_OWNER_RESIDUAL",
            "detail": codec_error,
        }
    ),
    flush=True,
)

# A numerical reader can bind supplied X/Y but cannot authenticate the evaluator
# that paired them. Recompute a mismatched finite outcome series and read it back;
# the declared evaluator-provenance limitation must remain explicit.
payload = from_canonical_bytes(store.get_bytes(ref))
plan = SensitivityPlan.model_validate(payload["plan"])
samples = np.asarray(payload["samples"], dtype=float)
outputs = np.roll(np.asarray(payload["outputs"], dtype=float), 1)
fixture_truth = samples[:, 0] + samples[:, 1] + 2 * samples[:, 0] * samples[:, 1]
if np.array_equal(outputs, fixture_truth):
    raise AssertionError
result = analyze_sensitivity(plan, samples, outputs)
newref = _persist_analysis(store, plan, samples, outputs, result)
reopened = FileSystemCAS(store.root)
if not (_load_analysis(reopened, newref) == result):
    raise AssertionError
newpayload = json.loads(reopened.get_bytes(newref))
if not (newpayload["evaluator_provenance"] == "not_established"):
    raise AssertionError
if not (newpayload["population_law_status"] == "not_established"):
    raise AssertionError
if not (newpayload["authority_purpose"] == "exploratory_parameter_experiment"):
    raise AssertionError
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(ROOT / "policy-engine/src") for p in origins.values())):
    raise AssertionError
if not (snapshot() == before):
    raise AssertionError
receipt = {
    "source_sha": "f07b7d485531b96a206ae9b2aad7acf5f2755324",
    "source_before_after_identical": True,
    "source_snapshot_sha256": before,
    "all_polisyos_origins_pinned": True,
    "polisyos_module_count": len(origins),
    "default_codec_boundary": codec_error,
    "coherently_recomputed_misaligned_pairs": {
        "numerical_readback": "accepted supplied X/Y",
        "evaluator_provenance": newpayload["evaluator_provenance"],
        "population_law_status": newpayload["population_law_status"],
        "authority_purpose": newpayload["authority_purpose"],
        "analysis_ref": newref.model_dump(mode="json"),
    },
    "owner": "D Scientist default Search/autotune and source-evaluator owner",
    "required_next_result": (
        "admit existing generator/codec metadata carrier and actual p"
        "roposal consumer; persist/reopen exact ref and test ranking-"
        "dependent behavior. Numeric CAS reproduction alone cannot au"
        "thenticate source evaluator pairing."
    ),
}
(OUT / "doe-consumer-boundary-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "case": "coherent_XY_evaluator_provenance_boundary",
            "outcome": "DECLARED_BOUNDARY_CONFIRMED",
            "detail": receipt["coherently_recomputed_misaligned_pairs"],
        }
    ),
    flush=True,
)
