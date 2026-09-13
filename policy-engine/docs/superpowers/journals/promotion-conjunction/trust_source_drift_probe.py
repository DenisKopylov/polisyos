# ruff: noqa: T201
"""Exercise the existing trust owner against changed source bytes in scratch.

This journal instrument is invoked directly; it adds no production mechanism.
The owner writes and checks its own scratch artifact before a comment-only source
mutation retains all original declarations. Only its original drift exception
is an accepted witness. Owner call returns and exceptions are distinguished from
the outer process status; the imported owner is reused to avoid import repeats.
"""

from __future__ import annotations

import hashlib
import io
import json
import signal
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType, ModuleType

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
SOURCE = Path("src/polisyos/runtime/quality/promotion_safety.py")
OWNER = Path("tools/quality/validation/check_trust_claim_posture.py")
RAW = ROOT / "docs/superpowers/journals/promotion-conjunction/raw"
# In-memory compilation excluded costly imports; the actual CLI exceeded 7 min.
WAVE_TIMEOUT_SECONDS = 1800


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _run_owner(
    owner: ModuleType, mode: str, scratch: Path
) -> tuple[int | None, str | None, dict[str, object]]:
    arguments = [mode, "--repo-root", str(scratch), "--json"]
    started = time.perf_counter()
    stdout, stderr = io.StringIO(), io.StringIO()
    returned: int | None = None
    raised: str | None = None
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            returned = owner.main(arguments)
    except ValueError as error:
        raised = f"{type(error).__name__}: {error}"
    finally:
        print(stdout.getvalue(), end="", flush=True)
        print(stderr.getvalue(), end="", flush=True)
        print(
            json.dumps(
                {
                    "owner_callable": str(ROOT / OWNER) + "::main",
                    "owner_arguments": arguments,
                    "owner_returned": returned,
                    "owner_raised": raised,
                    "owner_elapsed_seconds": time.perf_counter() - started,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return returned, raised, json.loads(stdout.getvalue())


def _wave_timeout(_signum: int, _frame: FrameType | None) -> None:
    raise TimeoutError("explicit 1800-second source drift probe wave timeout")


def main() -> int:
    """Retain the actual owner rejection and explicit measurement boundaries."""
    started = time.perf_counter()
    successful_reads: list[dict[str, object]] = []
    attempted_reads: list[str] = []
    before: dict[Path, bytes] = {}
    verdict = "UNRUN"
    detail: dict[str, object] = {}
    result = 2
    boundaries = [
        "minimal_source_fixture: other production sources are excluded; whole-repository "
        "trust posture is not decided by this witness",
        "source_semantics: a byte-binding witness does not establish source or promotion "
        "semantic acceptance",
        "delegated_reads: imports and subprocess internals are not instrumented by this "
        "wrapper; the owner prints its own actual-read receipt and unread boundaries",
        "selected_authority: copied identity and custody documents are read as bytes; "
        "interpretation remains bounded by the existing owner selectors",
    ]
    prior_alarm = signal.signal(signal.SIGALRM, _wave_timeout)
    signal.alarm(WAVE_TIMEOUT_SECONDS)
    try:
        from tools.quality.validation import check_trust_claim_posture as owner

        paths = (SOURCE, OWNER, owner._IDENTITY_PATH, owner._DEBT_REGISTER_PATH, owner._OUTPUT_PATH)
        for relative in paths:
            attempted_reads.append(relative.as_posix())
            content = (ROOT / relative).read_bytes()
            before[relative] = content
            successful_reads.append({"path": relative.as_posix(), "sha256": _digest(content)})
        print(
            json.dumps(
                {
                    "root_inputs_actually_read": successful_reads,
                    "root_selector": [path.as_posix() for path in paths],
                    "unresolved_by_construction": boundaries,
                    "wave_timeout_seconds": WAVE_TIMEOUT_SECONDS,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        with tempfile.TemporaryDirectory(prefix="trust-source-probe-", dir=RAW) as temporary:
            scratch = Path(temporary)
            source = before[SOURCE]
            owner._minimal_probe_repo(
                scratch,
                source.decode("utf-8"),
                basis_root=ROOT,
                source_name="runtime/quality/promotion_safety.py",
            )
            returned, raised, _ = _run_owner(owner, "--write", scratch)
            if returned != 0 or raised is not None:
                raise RuntimeError("scratch owner writer failed")
            returned, raised, _ = _run_owner(owner, "--check", scratch)
            if returned != 0 or raised is not None:
                raise RuntimeError("unmutated scratch owner check failed")
            target = scratch / SOURCE
            mutated = source + b"\n# PC probe: declarations retained, source bytes changed.\n"
            target.write_bytes(mutated)
            actual = target.read_bytes()
            if actual != mutated or not actual.startswith(source) or actual == source:
                raise RuntimeError("comment-only source mutation was not established")
            print(
                json.dumps(
                    {
                        "source_mutation": {
                            "path": str(target),
                            "before_sha256": _digest(source),
                            "after_sha256": _digest(actual),
                            "original_source_prefix_preserved": True,
                            "added_suffix": actual[len(source) :].decode("utf-8"),
                        }
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            returned, raised, report = _run_owner(owner, "--check", scratch)
            detail = {
                "original_owner_returned": returned,
                "original_owner_raised": raised,
                "original_owner_error": report.get("error"),
                "original_owner_verdict": report.get("verdict"),
            }
            if (
                returned is not None
                or raised != "ValueError: DS11-GENERATED-DRIFT"
                or report.get("error") != "ValueError: DS11-GENERATED-DRIFT"
                or report.get("verdict") != "UNRUN"
            ):
                raise RuntimeError("original owner source-drift rejection was not observed")
        for relative, content in before.items():
            if (ROOT / relative).read_bytes() != content:
                raise RuntimeError(f"root input changed during probe: {relative}")
        verdict = "PASS"
        result = 0
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        detail["probe_error"] = f"{type(error).__name__}: {error}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prior_alarm)
        print(
            json.dumps(
                {
                    "probe": "promotion_safety_source_bytes_rebinding",
                    "verdict": verdict,
                    "process_returncode": result,
                    "elapsed_seconds": time.perf_counter() - started,
                    "root_inputs_actually_read": successful_reads,
                    "root_read_attempts": attempted_reads,
                    "unresolved_by_construction": boundaries,
                    **detail,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
