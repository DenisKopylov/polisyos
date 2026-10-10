#!/usr/bin/env python3
"""Run source-bound Morris, final-consumption, and coercion-failure probes in isolated imports.

V5 is a prepared artifact and is not run during preparation. It verifies the
frozen producer, validator, executor, and test inputs; mutates only in-memory
source bytes in child import hooks; and uses real pytest selectors plus retained
module/consumer events to classify property removals. Child runs have a bounded
60-second deadline and preserve partial streams on timeout as ERROR/UNRUN.
"""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import time


SOURCE_REL = Path("src/polisyos/foundry/methods/catalog/sensitivity/screening.py")
TEST_REL = Path("tests/unit/foundry/methods/catalog/sensitivity/test_screening.py")
SOURCE_SHA256 = "b9a2a2dfc1e70473047a48500e9da2eab2c9180e567e36935017657caa7973e2"
TEST_SHA256 = "56f30b88836d86b3e811821f5bfae3d155fa9e185059e8da490d440fff0266f3"
FROZEN_HELPER_INPUTS = {
    "src/polisyos/foundry/methods/components/io.py": "79172d1619e3424d6282f0d5eaa89fdaf08d65d0de620b078562f1e7b16b86c9",
    "src/polisyos/foundry/methods/backends/chain_executor.py": "ecb335acfa0cca4574b101d328317534d22320164f5730239a69d1c78261b7ed",
    "src/polisyos/foundry/methods/backends/async_chain_executor.py": "3b75e619092347c74dd51a92ab4e46e67d966965426a0903ad124c2c34a19c51",
    "tests/unit/foundry/methods/backends/test_backends.py": "0f4c2a3d615f9bf7e45d5dabcf5f6621fc407499901a50af791096d647c31548",
}
FROZEN_INPUTS = {
    str(SOURCE_REL): SOURCE_SHA256,
    str(TEST_REL): TEST_SHA256,
    **FROZEN_HELPER_INPUTS,
}
MODULE = "polisyos.foundry.methods.catalog.sensitivity.screening"
SELECTOR = (
    "tests/unit/foundry/methods/catalog/sensitivity/test_screening.py"
    "::test_morris_dispatches_real_three_dimensional_chain"
)
MUTATIONS = ("slot_tensor_to_matrix", "remove_3d_effect_assignment")
IO_REL = Path("src/polisyos/foundry/methods/components/io.py")
IO_MODULE = "polisyos.foundry.methods.components.io"
GENERIC_SELECTOR = (
    "tests/unit/foundry/methods/backends/test_backends.py"
    "::test_chain_rejects_incompatible_same_name_value_from_partial_fallback"
)
GENERIC_PROBES = ("validator_intact", "remove_materialized_validator")
COERCION_SELECTOR = (
    "tests/unit/foundry/methods/backends/test_backends.py"
    "::test_chain_rejects_recognized_ragged_fallback_before_dispatch"
)
COERCION_PROBES = ("coercion_intact", "coercion_failure_returns_none")
CHILD_TIMEOUT_SECONDS = 60


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_product_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / SOURCE_REL).is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("Could not locate policy-engine product root from harness path")


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    actual: dict[str, str] = {}
    for relative_path, expected_hash in FROZEN_INPUTS.items():
        path = root / relative_path
        actual_hash = sha256(path.read_bytes())
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Frozen input changed at {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        actual[relative_path] = actual_hash
    return actual


def sitecustomize_source() -> str:
    return """from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys

MODULE = "polisyos.foundry.methods.catalog.sensitivity.screening"
SOURCE = Path(os.environ["E02_MORRIS_SOURCE"])
EXPECTED_SOURCE_SHA256 = os.environ["E02_MORRIS_SOURCE_SHA256"]
MUTATION = os.environ["E02_MORRIS_MUTATION"]
EVENT = Path(os.environ["E02_MORRIS_EVENT"])
PRODUCT_ROOT = Path(os.environ["E02_MORRIS_PRODUCT_ROOT"])
FROZEN_INPUTS = json.loads(os.environ["E02_MORRIS_FROZEN_INPUTS"])

def digest(data):
    return hashlib.sha256(data).hexdigest()

def verify_frozen_inputs():
    actual = {}
    for relative_path, expected_hash in FROZEN_INPUTS.items():
        actual_hash = digest((PRODUCT_ROOT / relative_path).read_bytes())
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Frozen input changed at {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        actual[relative_path] = actual_hash
    return actual

verify_frozen_inputs()

def mutate(source):
    common = (
        b'namespace="sensitivity.global"',
        b'version="1.0.0"',
        b'"parameter_levels"',
        b'"mu_star"',
        b'"n_trajectories"',
        b'"n_factors"',
    )
    if MUTATION == "slot_tensor_to_matrix":
        old = (
            b'                    "parameter_levels",\\n'
            b'                    SlotType.TENSOR,'
        )
        new = (
            b'                    "parameter_levels",\\n'
            b'                    SlotType.MATRIX,'
        )
    elif MUTATION == "remove_3d_effect_assignment":
        old = (
            b'                if levels.ndim == 3:\\n'
            b'                    delta_x = levels[t, s + 1] - levels[t, s]\\n'
            b'                    changed = np.where(np.abs(delta_x) > 1e-12)[0]\\n'
            b'                    if len(changed) > 0:\\n'
            b'                        factor_idx = changed[0]\\n'
            b'                        ees[t, factor_idx] = delta_y / delta_x[factor_idx]\\n'
        )
        new = (
            b'                if levels.ndim == 3:\\n'
            b'                    pass\\n'
        )
    else:
        raise RuntimeError(f"Unknown Morris mutation: {MUTATION}")

    if source.count(old) != 1:
        raise RuntimeError(
            f"Expected exactly one source-bound mutation target for {MUTATION}; "
            f"found {source.count(old)}"
        )
    mutated = source.replace(old, new, 1)
    if mutated == source:
        raise RuntimeError(f"Mutation did not change Morris source: {MUTATION}")
    missing = [marker.decode() for marker in common if marker not in mutated]
    if missing:
        raise RuntimeError(f"Mutation removed public markers: {missing}")
    if b'class MorrisSensitivityEstimator:' not in mutated:
        raise RuntimeError("Mutation removed the Morris method class")
    if b'"result":' not in mutated or b'"sigma"' not in mutated:
        raise RuntimeError("Mutation removed the result shape markers")
    if MUTATION == "slot_tensor_to_matrix":
        if b'                    "parameter_levels",\\n                    SlotType.MATRIX,' not in mutated:
            raise RuntimeError("Matrix-slot mutation was not retained in memory")
        if b'                    "parameter_levels",\\n                    SlotType.TENSOR,' in mutated:
            raise RuntimeError("Tensor slot unexpectedly remains after type mutation")
    else:
        if old in mutated or b'"parameter_levels"' not in mutated:
            raise RuntimeError("3D effect computation was not removed cleanly")
        if b'                    SlotType.TENSOR,' not in mutated:
            raise RuntimeError("3D-removal probe changed the typed Tensor contract")
    return mutated

class MutatingLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        verified_inputs = verify_frozen_inputs()
        original = SOURCE.read_bytes()
        original_hash = digest(original)
        if original_hash != EXPECTED_SOURCE_SHA256:
            raise RuntimeError(
                f"Frozen Morris source changed before import: {original_hash}"
            )
        mutated = mutate(original)
        module.__file__ = str(SOURCE)
        module.__package__ = MODULE.rpartition(".")[0]
        print(
            "E02_MORRIS_MUTATION_APPLIED="
            + json.dumps(
                {
                    "mutation": MUTATION,
                    "source_sha256": original_hash,
                    "in_memory_mutated_sha256": digest(mutated),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        exec(compile(mutated, str(SOURCE), "exec"), module.__dict__)
        EVENT.parent.mkdir(parents=True, exist_ok=True)
        with EVENT.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "event": "morris_module_exec_completed",
                    "module": MODULE,
                    "mutation": MUTATION,
                    "source_sha256": original_hash,
                    "in_memory_mutated_sha256": digest(mutated),
                    "module_exec_completed": True,
                    "frozen_inputs": verify_frozen_inputs(),
                },
                stream,
                sort_keys=True,
            )
            stream.write("\\n")

class MutationFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != MODULE:
            return None
        return importlib.util.spec_from_loader(
            fullname,
            MutatingLoader(),
            origin=str(SOURCE),
        )

if MODULE in sys.modules:
    raise RuntimeError("Morris module loaded before the mutation hook")
sys.meta_path.insert(0, MutationFinder())
"""


def generic_sitecustomize_source() -> str:
    """Generate the generic final-validator probe hook."""
    return r"""from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

MODULE = "polisyos.foundry.methods.components.io"
SOURCE = Path(os.environ["E02_GENERIC_SOURCE"])
EXPECTED_SOURCE_SHA256 = os.environ["E02_GENERIC_SOURCE_SHA256"]
MUTATION = os.environ["E02_GENERIC_MUTATION"]
EVENT = Path(os.environ["E02_GENERIC_EVENT"])
DISPATCH_EVENT = Path(os.environ["E02_GENERIC_DISPATCH_EVENT"])
PRODUCT_ROOT = Path(os.environ["E02_MORRIS_PRODUCT_ROOT"])
FROZEN_INPUTS = json.loads(os.environ["E02_MORRIS_FROZEN_INPUTS"])
_EVENT_LOCK = threading.Lock()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_frozen_inputs():
    actual = {}
    for relative_path, expected_hash in FROZEN_INPUTS.items():
        actual_hash = digest((PRODUCT_ROOT / relative_path).read_bytes())
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Frozen input changed at {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        actual[relative_path] = actual_hash
    return actual


def mutate(source):
    if MUTATION in ("validator_intact", "coercion_intact"):
        return source
    if MUTATION == "coercion_failure_returns_none":
        old = (
            b"    except Exception as exc:\n"
            b"        raise _ArrayLikeCoercionError(\n"
            b"            f\"recognized array-like value could not be coerced: {type(value).__name__}\"\n"
            b"        ) from exc"
        )
        new = b"    except Exception as exc:\n        return None"
        if source.count(old) != 1:
            raise RuntimeError("Expected one source-bound recognized-array coercion failure branch")
        mutated = source.replace(old, new, 1)
        markers = (
            b"class _ArrayLikeCoercionError", b"def _as_array_like(",
            b"def validate_value_for_slot(", b"np.asarray(value)", b"could not be coerced",
        )
        missing = [marker.decode() for marker in markers if marker not in mutated]
        if missing:
            raise RuntimeError(f"Coercion-failure removal did not preserve helper markers: {missing}")
        if old in mutated or mutated == source:
            raise RuntimeError("Recognized coercion failure was not removed in memory")
        return mutated
    if MUTATION != "remove_materialized_validator":
        raise RuntimeError(f"Unknown generic probe mutation: {MUTATION}")
    marker = b"def _validate_materialized_input_slots("
    end_marker = b"\ndef dematerialize_method_output("
    if source.count(marker) != 1:
        raise RuntimeError("Expected one final materialized-input validator definition")
    start = source.index(marker)
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError("Could not bound final materialized-input validator body")
    old_function = source[start:end]
    if b"validate_value_for_slot(" not in old_function:
        raise RuntimeError("Final validator body lacks its source-bound slot check")
    replacement = (
        b"def _validate_materialized_input_slots(\n"
        b"    *, signature: MethodSignature, materialized_state: Any\n"
        b") -> None:\n"
        b"    return None"
    )
    mutated = source[:start] + replacement + source[end:]
    if mutated == source or marker not in mutated:
        raise RuntimeError("Final-validator removal did not preserve its function marker")
    return mutated


def _record_dispatch(frame, event, arg):
    del arg
    if event != "call" or not frame.f_code.co_qualname.endswith(
        "_ConsumeMatrixPayload.pure_step"
    ):
        return
    payload = {
        "event": "consumer_pure_step_called",
        "qualname": frame.f_code.co_qualname,
        "thread": threading.current_thread().name,
    }
    encoded = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    with _EVENT_LOCK:
        descriptor = os.open(
            DISPATCH_EVENT,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        try:
            os.write(descriptor, encoded)
        finally:
            os.close(descriptor)


class MutatingLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        verify_frozen_inputs()
        original = SOURCE.read_bytes()
        original_hash = digest(original)
        if original_hash != EXPECTED_SOURCE_SHA256:
            raise RuntimeError(
                f"Frozen final-validator source changed before import: {original_hash}"
            )
        mutated = mutate(original)
        module.__file__ = str(SOURCE)
        module.__package__ = MODULE.rpartition(".")[0]
        exec(compile(mutated, str(SOURCE), "exec"), module.__dict__)
        EVENT.parent.mkdir(parents=True, exist_ok=True)
        with EVENT.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "event": "io_validation_module_exec_completed",
                    "module": MODULE,
                    "mutation": MUTATION,
                    "source_sha256": original_hash,
                    "in_memory_mutated_sha256": digest(mutated),
                    "module_exec_completed": True,
                    "frozen_inputs": verify_frozen_inputs(),
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")


class MutationFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != MODULE:
            return None
        return importlib.util.spec_from_loader(
            fullname,
            MutatingLoader(),
            origin=str(SOURCE),
        )


if MODULE in sys.modules:
    raise RuntimeError("Final-validator module loaded before the probe hook")
sys.meta_path.insert(0, MutationFinder())
sys.setprofile(_record_dispatch)
threading.setprofile(_record_dispatch)
"""



def _decode_child_stream(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_child(argv: list[str], *, cwd: Path, env: dict[str, str]) -> dict[str, object]:
    """Run one bounded child, retaining partial streams after timeout."""
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, check=False,
            timeout=CHILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None, "timed_out": True,
            "timeout_seconds": CHILD_TIMEOUT_SECONDS,
            "duration_seconds": time.monotonic() - started,
            "stdout": _decode_child_stream(exc.stdout),
            "stderr": _decode_child_stream(exc.stderr),
        }
    return {
        "returncode": completed.returncode, "timed_out": False,
        "timeout_seconds": CHILD_TIMEOUT_SECONDS,
        "duration_seconds": time.monotonic() - started,
        "stdout": _decode_child_stream(completed.stdout),
        "stderr": _decode_child_stream(completed.stderr),
    }

def classify_probe(
    mutation: str,
    returncode: int,
    event_path: Path,
    junit_path: Path,
    expected_inputs: dict[str, str],
) -> tuple[bool, bool, str]:
    """Validate the hook event and classify the executed property probe.

    Returns ``(receipt_valid, property_removal_detected, decision)``. A valid
    receipt can honestly show that a mutation escaped the current test.
    """
    if not event_path.is_file():
        return False, False, "the import hook did not retain its completion event"
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, False, f"the import hook event was unreadable: {exc}"
    if (
        event.get("event") != "morris_module_exec_completed"
        or event.get("module") != MODULE
        or event.get("mutation") != mutation
        or event.get("source_sha256") != SOURCE_SHA256
        or event.get("module_exec_completed") is not True
        or not isinstance(event.get("in_memory_mutated_sha256"), str)
    ):
        return False, False, "the retained hook event did not bind the expected in-memory module"
    if event.get("frozen_inputs") != expected_inputs:
        return False, False, "the hook event did not bind all frozen producer and consumer inputs"

    if not junit_path.is_file():
        return False, False, "pytest did not produce the expected JUnit receipt"
    try:
        junit_root = ET.parse(junit_path).getroot()
    except (OSError, ET.ParseError) as exc:
        return False, False, f"JUnit XML was malformed or unreadable: {exc}"

    cases = junit_root.findall(".//testcase")
    target_name = "test_morris_dispatches_real_three_dimensional_chain"
    if len(cases) != 1:
        return False, False, f"expected exactly one executed selector testcase, found {len(cases)}"
    case = cases[0]
    if case.attrib.get("name") != target_name:
        return False, False, f"unexpected JUnit testcase: {case.attrib.get('name')!r}"
    if not case.attrib.get("classname", "").endswith("test_screening"):
        return False, False, f"unexpected JUnit testcase module: {case.attrib.get('classname')!r}"
    if junit_root.findall(".//error") or any(case.find(tag) is not None for tag in ("error", "skipped")):
        return False, False, "JUnit records an error or skip instead of a completed property testcase"

    failure = case.find("failure")
    if failure is None:
        if returncode != 0:
            return False, False, f"pytest exited {returncode} without a testcase failure node"
        return (
            True,
            False,
            "the in-memory mutation was applied and the real selector passed; the property escaped",
        )
    if returncode != 1:
        return False, False, f"expected pytest assertion-failure exit 1, got {returncode}"

    failure_text = failure.attrib.get("message", "") + "\n" + (failure.text or "")
    if mutation == "slot_tensor_to_matrix":
        lowered = failure_text.lower()
        if "parameter_levels" not in failure_text:
            return True, False, "the selector failed outside the mutated parameter_levels contract"
        if not any(token in lowered for token in ("rank", "slot", "incompatible", "matrix")):
            return True, False, "the selector failure did not identify the changed slot contract"
        return True, True, "the real selector rejected the mutated parameter_levels contract"

    if "mu_star" not in failure_text or not any(
        token in failure_text for token in ("Mismatched elements", "Not equal to tolerance")
    ):
        return True, False, "the selector failed outside the removed mu_star effect assertion"
    return True, True, "the real selector detected removal of 3D elementary-effect computation"


def classify_generic_probe(
    mutation: str,
    returncode: int,
    event_path: Path,
    dispatch_path: Path,
    junit_path: Path,
    expected_inputs: dict[str, str],
) -> tuple[bool, bool, int, str]:
    """Classify the real sync/async final-validator removal probe."""
    if not event_path.is_file():
        return False, False, 0, "the final-validator import hook did not retain its completion event"
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, False, 0, f"the final-validator hook event was unreadable: {exc}"
    if (
        event.get("event") != "io_validation_module_exec_completed"
        or event.get("module") != IO_MODULE
        or event.get("mutation") != mutation
        or event.get("source_sha256") != FROZEN_HELPER_INPUTS[str(IO_REL)]
        or event.get("module_exec_completed") is not True
        or not isinstance(event.get("in_memory_mutated_sha256"), str)
        or event.get("frozen_inputs") != expected_inputs
    ):
        return False, False, 0, "the hook event did not bind the requested source mutation and frozen inputs"

    dispatches = []
    if dispatch_path.is_file():
        try:
            dispatches = [
                json.loads(line)
                for line in dispatch_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as exc:
            return False, False, 0, f"the retained consumer-dispatch event was malformed: {exc}"
    if any(
        event.get("event") != "consumer_pure_step_called"
        or not str(event.get("qualname", "")).endswith("_ConsumeMatrixPayload.pure_step")
        for event in dispatches
    ):
        return False, False, len(dispatches), "the dispatch trace did not identify the actual consumer method"

    if not junit_path.is_file():
        return False, False, len(dispatches), "pytest did not produce the generic-probe JUnit receipt"
    try:
        junit_root = ET.parse(junit_path).getroot()
    except (OSError, ET.ParseError) as exc:
        return False, False, len(dispatches), f"generic-probe JUnit was malformed or unreadable: {exc}"

    cases = junit_root.findall(".//testcase")
    expected_name = "test_chain_rejects_incompatible_same_name_value_from_partial_fallback"
    if len(cases) != 6:
        return False, False, len(dispatches), f"expected six sync/async array-like cases, found {len(cases)}"
    if any(not case.attrib.get("name", "").startswith(expected_name) for case in cases):
        return False, False, len(dispatches), "JUnit contains a testcase outside the selected sync/async negatives"
    if junit_root.findall(".//error") or any(
        case.find("error") is not None or case.find("skipped") is not None for case in cases
    ):
        return False, False, len(dispatches), "JUnit records an error or skip instead of six completed cases"
    failures = [case for case in cases if case.find("failure") is not None]

    if mutation == "validator_intact":
        if returncode != 0 or failures or dispatches:
            return False, False, len(dispatches), "intact-validator positive did not pass with zero consumer dispatches"
        return True, False, 0, "six malformed sync/async inputs were rejected before the consumer ran"

    if mutation != "remove_materialized_validator":
        return False, False, len(dispatches), f"unexpected generic mutation {mutation!r}"
    if returncode not in (0, 1):
        return False, False, len(dispatches), f"unexpected pytest exit code {returncode}"
    if len(dispatches) != 6:
        return False, False, len(dispatches), "expected six real consumer calls after removing the final validator"
    if not failures:
        return True, False, len(dispatches), "the helper was removed and all six malformed values reached the consumer, but JUnit stayed green"
    failure_text = "\\n".join(
        case.find("failure").attrib.get("message", "") + "\\n" + (case.find("failure").text or "")
        for case in failures
    )
    if returncode == 1 and len(failures) == 6 and all(
        "did not raise" in (
            case.find("failure").attrib.get("message", "") + "\\n" + (case.find("failure").text or "")
        ).lower()
        for case in failures
    ):
        return True, True, len(dispatches), "all six typed sync/async rejection assertions failed after real consumer dispatch"
    return True, False, len(dispatches), f"the property mutation produced a failure outside the six expected typed-stage assertions: {failure_text[:500]}"



def classify_coercion_probe(
    mutation: str, returncode: int, event_path: Path, dispatch_path: Path,
    junit_path: Path, expected_inputs: dict[str, str],
) -> tuple[bool, bool, int, list[dict[str, str]], str]:
    """Classify the intact and removed recognized-coercion failure branches."""
    if not event_path.is_file():
        return False, False, 0, [], "the IO-validation hook has no completion event"
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, False, 0, [], f"the IO-validation event is unreadable: {exc}"
    if (
        event.get("event") != "io_validation_module_exec_completed"
        or event.get("module") != IO_MODULE
        or event.get("mutation") != mutation
        or event.get("source_sha256") != FROZEN_HELPER_INPUTS[str(IO_REL)]
        or event.get("module_exec_completed") is not True
        or not isinstance(event.get("in_memory_mutated_sha256"), str)
        or event.get("frozen_inputs") != expected_inputs
    ):
        return False, False, 0, [], "hook event did not bind the in-memory coercion mutation and frozen inputs"
    dispatches = []
    if dispatch_path.is_file():
        try:
            dispatches = [
                json.loads(line) for line in dispatch_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, json.JSONDecodeError) as exc:
            return False, False, 0, [], f"dispatch trace is malformed: {exc}"
    if any(
        item.get("event") != "consumer_pure_step_called"
        or not str(item.get("qualname", "")).endswith("_ConsumeMatrixPayload.pure_step")
        for item in dispatches
    ):
        return False, False, len(dispatches), [], "dispatch trace did not identify the real matrix consumer"
    if not junit_path.is_file():
        return False, False, len(dispatches), [], "pytest produced no coercion-probe JUnit receipt"
    try:
        root = ET.parse(junit_path).getroot()
    except (OSError, ET.ParseError) as exc:
        return False, False, len(dispatches), [], f"coercion JUnit is malformed: {exc}"
    cases = root.findall(".//testcase")
    expected = "test_chain_rejects_recognized_ragged_fallback_before_dispatch"
    if len(cases) != 2 or any(not c.attrib.get("name", "").startswith(expected) for c in cases):
        return False, False, len(dispatches), [], f"expected exactly sync/async ragged cases, got {len(cases)}"
    if any(c.find("skipped") is not None for c in cases):
        return False, False, len(dispatches), [], "JUnit skipped a coercion case"
    stages = []
    for case in cases:
        name = case.attrib.get("name", "")
        detail = "\n".join(
            n.attrib.get("message", "") + "\n" + (n.text or "")
            for n in (case.find("failure"), case.find("error")) if n is not None
        )
        mode = "sync" if name.endswith("[sync]") else "async" if name.endswith("[async]") else "unknown"
        outcome = "error" if case.find("error") is not None else "failure" if case.find("failure") is not None else "pass"
        stages.append({"case": name, "mode": mode, "outcome": outcome, "detail": detail[:1200]})
    failures = [x for x in stages if x["outcome"] in ("failure", "error")]
    if mutation == "coercion_intact":
        if returncode != 0 or failures or dispatches:
            return False, False, len(dispatches), stages, "intact typed rejection did not pass before dispatch"
        return True, False, 0, stages, "both ragged sync/async values were rejected before consumer dispatch"
    if mutation != "coercion_failure_returns_none":
        return False, False, len(dispatches), stages, f"unexpected coercion mutation {mutation!r}"
    if returncode != 1 or len(dispatches) != 2 or len(failures) != 2:
        return False, False, len(dispatches), stages, "removal did not produce two real dispatches and two JUnit failure/error nodes"
    if any(x["mode"] == "unknown" or not any(token in x["detail"].lower() for token in ("valueerror", "methodcontracterror")) for x in failures):
        return False, False, len(dispatches), stages, "JUnit did not identify both consumer/typed-stage outcomes"
    return True, True, 2, stages, "coercion exception removed; both ragged values reached the real consumer and failed outside the typed stage"

def main() -> int:
    root = find_product_root()
    verified_inputs = verify_frozen_inputs(root)
    source = root / SOURCE_REL
    test = root / TEST_REL
    hook_sources = {mutation: sitecustomize_source() for mutation in MUTATIONS}
    generic_hook_sources = {
        mutation: generic_sitecustomize_source()
        for mutation in (*GENERIC_PROBES, *COERCION_PROBES)
    }
    for mutation, hook_source in (*hook_sources.items(), *generic_hook_sources.items()):
        compile(hook_source, f"<sitecustomize:{mutation}>", "exec")
    raw_root = Path(__file__).resolve().parent / "morris-marker-removal-harness-v5-20261010"
    run_id = time.strftime("run-%Y%m%dT%H%M%SZ") + f"-{os.getpid()}"
    run_dir = raw_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    outcomes = []
    for mutation in MUTATIONS:
        verify_frozen_inputs(root)
        mutation_dir = run_dir / mutation
        mutation_dir.mkdir(parents=True, exist_ok=False)
        hook_dir = run_dir / "hook" / mutation
        hook_dir.mkdir(parents=True, exist_ok=False)
        hook_path = hook_dir / "sitecustomize.py"
        hook_source = hook_sources[mutation]
        hook_path.write_text(hook_source, encoding="utf-8")
        hook_sha256 = sha256(hook_path.read_bytes())

        junit_path = mutation_dir / "pytest.junit.xml"
        event_path = mutation_dir / "hook-applied.json"
        argv = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit_path}",
            SELECTOR,
        ]
        env = os.environ.copy()
        additions = [str(hook_dir), str(root / "src")]
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            additions.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(additions)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["E02_MORRIS_SOURCE"] = str(source)
        env["E02_MORRIS_SOURCE_SHA256"] = SOURCE_SHA256
        env["E02_MORRIS_MUTATION"] = mutation
        env["E02_MORRIS_EVENT"] = str(event_path)
        env["E02_MORRIS_PRODUCT_ROOT"] = str(root)
        env["E02_MORRIS_FROZEN_INPUTS"] = json.dumps(FROZEN_INPUTS, sort_keys=True)
        child = run_child(argv, cwd=root, env=env)
        duration_seconds = child["duration_seconds"]
        stdout_path = mutation_dir / "stdout.txt"
        stderr_path = mutation_dir / "stderr.txt"
        stdout_path.write_text(child["stdout"], encoding="utf-8")
        stderr_path.write_text(child["stderr"], encoding="utf-8")
        post_run_inputs = verify_frozen_inputs(root)
        if child["timed_out"]:
            receipt_valid, detected = False, False
            reason = (
                f"child exceeded {CHILD_TIMEOUT_SECONDS}s; partial stdout/stderr retained; "
                "JUnit is ERROR/UNRUN and was not used as property evidence"
            )
        else:
            receipt_valid, detected, reason = classify_probe(
                mutation, child["returncode"], event_path, junit_path, verified_inputs
            )
        if post_run_inputs != verified_inputs:
            receipt_valid = False
            detected = False
            reason = "frozen producer/consumer inputs changed during the child run"
        outcomes.append(
            {
                "mutation": mutation,
                "argv": argv,
                "cwd": str(root),
                "returncode": child["returncode"],
                "timed_out": child["timed_out"],
                "timeout_seconds": child["timeout_seconds"],
                "child_status": "ERROR/UNRUN" if child["timed_out"] else "COMPLETED",
                "duration_seconds": duration_seconds,
                "receipt_valid": receipt_valid,
                "property_removal_detected": detected,
                "decision": reason,
                "hook_event": str(event_path),
                "hook_event_sha256": sha256(event_path.read_bytes()) if event_path.is_file() else None,
                "hook_source": str(hook_path),
                "hook_source_sha256": hook_sha256,
                "frozen_inputs": verified_inputs,
                "child_inputs": {
                    "module": MODULE,
                    "frozen_inputs": verified_inputs,
                    "source_path": str(source),
                    "source_sha256": SOURCE_SHA256,
                    "test_path": str(test),
                    "test_sha256": TEST_SHA256,
                    "selector": SELECTOR,
                    "timeout_seconds": CHILD_TIMEOUT_SECONDS,
                    "mutation": mutation,
                    "hook_event": str(event_path),
                    "OPENBLAS_NUM_THREADS": env["OPENBLAS_NUM_THREADS"],
                    "OMP_NUM_THREADS": env["OMP_NUM_THREADS"],
                },
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "junit": str(junit_path),
            }
        )

    generic_results = []
    generic_root = run_dir
    generic_runs = [
        ("generic-final-consumption", mutation, GENERIC_SELECTOR, "generic")
        for mutation in GENERIC_PROBES
    ] + [
        ("recognized-coercion-failure", mutation, COERCION_SELECTOR, "coercion")
        for mutation in COERCION_PROBES
    ]
    for probe_group, mutation, selector, probe_kind in generic_runs:
        verify_frozen_inputs(root)
        mutation_dir = generic_root / probe_group / mutation
        mutation_dir.mkdir(parents=True, exist_ok=False)
        hook_dir = run_dir / "hook" / f"generic-{mutation}"
        hook_dir.mkdir(parents=True, exist_ok=False)
        hook_path = hook_dir / "sitecustomize.py"
        hook_source = generic_hook_sources[mutation]
        hook_path.write_text(hook_source, encoding="utf-8")
        hook_sha256 = sha256(hook_path.read_bytes())

        junit_path = mutation_dir / "pytest.junit.xml"
        event_path = mutation_dir / "hook-applied.json"
        dispatch_path = mutation_dir / "consumer-dispatch.jsonl"
        argv = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            f"--junitxml={junit_path}",
            selector,
        ]
        env = os.environ.copy()
        additions = [str(hook_dir), str(root / "src")]
        existing_pythonpath = env.get("PYTHONPATH")
        if existing_pythonpath:
            additions.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(additions)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["OPENBLAS_NUM_THREADS"] = "1"
        env["OMP_NUM_THREADS"] = "1"
        env["E02_GENERIC_SOURCE"] = str(root / IO_REL)
        env["E02_GENERIC_SOURCE_SHA256"] = FROZEN_HELPER_INPUTS[str(IO_REL)]
        env["E02_GENERIC_MUTATION"] = mutation
        env["E02_GENERIC_EVENT"] = str(event_path)
        env["E02_GENERIC_DISPATCH_EVENT"] = str(dispatch_path)
        env["E02_MORRIS_PRODUCT_ROOT"] = str(root)
        env["E02_MORRIS_FROZEN_INPUTS"] = json.dumps(FROZEN_INPUTS, sort_keys=True)
        child = run_child(argv, cwd=root, env=env)
        duration_seconds = child["duration_seconds"]
        stdout_path = mutation_dir / "stdout.txt"
        stderr_path = mutation_dir / "stderr.txt"
        stdout_path.write_text(child["stdout"], encoding="utf-8")
        stderr_path.write_text(child["stderr"], encoding="utf-8")
        post_run_inputs = verify_frozen_inputs(root)
        typed_stages = []
        if child["timed_out"]:
            receipt_valid, detected, dispatch_count = False, False, None
            reason = (
                f"child exceeded {CHILD_TIMEOUT_SECONDS}s; partial streams retained; "
                "JUnit is ERROR/UNRUN and was not used as property evidence"
            )
        elif probe_kind == "coercion":
            receipt_valid, detected, dispatch_count, typed_stages, reason = classify_coercion_probe(
                mutation, child["returncode"], event_path, dispatch_path,
                junit_path, verified_inputs,
            )
        else:
            receipt_valid, detected, dispatch_count, reason = classify_generic_probe(
                mutation, child["returncode"], event_path, dispatch_path,
                junit_path, verified_inputs,
            )
        if post_run_inputs != verified_inputs:
            receipt_valid = False
            detected = False
            reason = "frozen producer/consumer inputs changed during the child run"
        generic_results.append(
            {
                "probe_group": probe_group,
                "probe_kind": probe_kind,
                "mutation": mutation,
                "selector": selector,
                "typed_stage_outcomes": typed_stages,
                "argv": argv,
                "cwd": str(root),
                "returncode": child["returncode"],
                "timed_out": child["timed_out"],
                "timeout_seconds": child["timeout_seconds"],
                "child_status": "ERROR/UNRUN" if child["timed_out"] else "COMPLETED",
                "duration_seconds": duration_seconds,
                "receipt_valid": receipt_valid,
                "property_removal_detected": detected,
                "consumer_dispatch_count": dispatch_count,
                "decision": reason,
                "hook_event": str(event_path),
                "hook_event_sha256": sha256(event_path.read_bytes()) if event_path.is_file() else None,
                "dispatch_event": str(dispatch_path),
                "dispatch_event_sha256": sha256(dispatch_path.read_bytes()) if dispatch_path.is_file() else None,
                "hook_source": str(hook_path),
                "hook_source_sha256": hook_sha256,
                "frozen_inputs": verified_inputs,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "junit": str(junit_path),
            }
        )

    report = {
        "harness": str(Path(__file__).resolve()),
        "product_root": str(root),
        "pinned_source": {"path": str(source), "sha256": SOURCE_SHA256},
        "pinned_test": {"path": str(test), "sha256": TEST_SHA256},
        "frozen_inputs": verified_inputs,
        "selector": SELECTOR,
        "run_directory": str(run_dir),
        "results": outcomes,
        "all_probe_receipts_valid": all(item["receipt_valid"] for item in outcomes),
        "all_removals_detected": all(item["property_removal_detected"] for item in outcomes),
        "generic_selector": GENERIC_SELECTOR,
        "generic_probe_results": [
            item for item in generic_results if item["mutation"] in GENERIC_PROBES
        ],
        "coercion_selector": COERCION_SELECTOR,
        "coercion_probe_results": [
            item for item in generic_results if item["mutation"] in COERCION_PROBES
        ],
        "all_generic_probe_receipts_valid": all(
            item["receipt_valid"] for item in generic_results if item["mutation"] in GENERIC_PROBES
        ),
        "all_coercion_probe_receipts_valid": all(
            item["receipt_valid"] for item in generic_results if item["mutation"] in COERCION_PROBES
        ),
        "recognized_coercion_failure_removal_detected": any(
            item["mutation"] == "coercion_failure_returns_none"
            and item["property_removal_detected"] for item in generic_results
        ),
        "generic_final_validator_removal_detected": any(
            item["mutation"] == "remove_materialized_validator"
            and item["property_removal_detected"]
            for item in generic_results
        ),
    }
    report_path = run_dir / "result.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    # Exit status reports evidence integrity, not whether the current test
    # caught every mutation. A valid receipt can document a real escape.
    return (
        0
        if report["all_probe_receipts_valid"]
        and report["all_generic_probe_receipts_valid"]
        and report["all_coercion_probe_receipts_valid"]
        else 2
    )

if __name__ == "__main__":
    raise SystemExit(main())
