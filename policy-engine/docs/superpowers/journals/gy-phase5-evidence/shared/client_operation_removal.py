"""Remove the POST producer in memory and run the unchanged client transport test."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from tools.ops_runners.runtime import generate_runtime_client as owner


def main() -> int:
    """Retain schema/test markers while removing the deciding generated operation."""
    scratch = Path(".tmp/gyphase5-client-operation-removal")
    scratch.mkdir(parents=True, exist_ok=True)
    source = Path("packages/runtime-api-client")
    owner._GENERATED_POST_OPERATION_IDS = owner._GENERATED_POST_OPERATION_IDS - {
        "submit_run_normative_evidence"
    }
    sys.argv = [
        "generate_runtime_client",
        "--openapi",
        "schemas/runtime_api_v1.openapi.json",
        "--out-ts",
        str(scratch / "runtimeApiClient.ts"),
        "--out-js",
        str(scratch / "runtimeApiClient.js"),
    ]
    owner.main()
    for name in ("canonicalRuntimeApiClient.js", "runtimeApiClient.test.mjs"):
        shutil.copyfile(source / name, scratch / name)
    (scratch / "package.json").write_text('{"type":"module"}\n')
    markers = "NormativeEvidenceSubmissionRequest" in (scratch / "runtimeApiClient.ts").read_text()
    if not markers:
        raise RuntimeError("removal discarded the required DTO marker")
    command = [
        "node",
        "--test",
        "--test-name-pattern",
        "normative evidence submission",
        str(scratch / "runtimeApiClient.test.mjs"),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    sys.stdout.write(
        json.dumps(
            {
                "command": command,
                "returncode": result.returncode,
                "dto_markers_retained": markers,
                "test_bytes_equal": (
                    (source / "runtimeApiClient.test.mjs").read_bytes()
                    == (scratch / "runtimeApiClient.test.mjs").read_bytes()
                ),
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            indent=2,
        )
        + "\n"
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
