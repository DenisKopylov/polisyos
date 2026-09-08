"""Compile the public verifier response through the complete client generator chain."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from polisyos.runtime.http.services.public_decision_verification_contracts import (
    PublicDecisionVerificationResponse,
)


def test_public_verification_schema_generates_json_typed_client(tmp_path: Path) -> None:
    """The public document must compile as recursive JSON, including its exclusions."""
    app = FastAPI()

    @app.get("/record", response_model=PublicDecisionVerificationResponse)
    def record() -> PublicDecisionVerificationResponse:
        raise NotImplementedError("schema generation does not call the endpoint")

    product_root = Path(__file__).resolve().parents[4]
    schema_path = tmp_path / "openapi.json"
    schema_path.write_text(json.dumps(app.openapi()), encoding="utf-8")
    generated_path = tmp_path / "client.ts"
    subprocess.run(
        [
            sys.executable,
            str(product_root / "tools/ops_runners/runtime/generate_runtime_client.py"),
            "--openapi",
            str(schema_path),
            "--out-ts",
            str(generated_path),
            "--out-js",
            str(tmp_path / "client.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    subprocess.run(
        [
            str(product_root / "apps/runtime-dashboard/node_modules/.bin/openapi-typescript"),
            str(schema_path),
            "--output",
            str(tmp_path / "types.ts"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    subprocess.run(
        [
            "node",
            str(product_root / "packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs"),
            "--types",
            str(tmp_path / "types.ts"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    canonical_path = tmp_path / "canonical.ts"
    subprocess.run(
        [
            "node",
            str(product_root / "packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs"),
            "--openapi",
            str(schema_path),
            "--client",
            str(generated_path),
            "--out-ts",
            str(canonical_path),
            "--runtime-js",
            str(tmp_path / "client.js"),
            "--out-js",
            str(tmp_path / "canonical.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    imports = {
        "raw": "import type { PublicDecisionVerificationResponse as Response } from './client';",
        "canonical": "import type { PublicDecisionVerificationResponse as Response } from './canonical';",
        "openapi": (
            "import type { components } from './types';\n"
            "type Response = components['schemas']['PublicDecisionVerificationResponse'];"
        ),
    }
    consumers = []
    for surface, import_statement in imports.items():
        consumer = tmp_path / f"{surface}-consumer.ts"
        consumer.write_text(
            import_statement
            + """

type Document = NonNullable<Response['public_document']>;
let valid: Document = {nested: [null, true, false, 0, -1, 1.25, 'text', {}, []]};
for (let depth = 0; depth < 30; depth++) valid = {nested: [valid]};
// @ts-expect-error a function is not JSON even when nested under valid containers
const functionValue: Document = {nested: [{value: () => 'invented'}]};
// @ts-expect-error undefined is not a JSON value
const undefinedValue: Document = {nested: [{value: undefined}]};
void [valid, functionValue, undefinedValue];
""",
            encoding="utf-8",
        )
        consumers.append(consumer)
    result = subprocess.run(
        [
            "node",
            str(product_root / "packages/runtime-api-client/node_modules/typescript/bin/tsc"),
            "--noEmit",
            "--strict",
            "--skipLibCheck",
            "--target",
            "ES2023",
            "--moduleResolution",
            "bundler",
            "--module",
            "ESNext",
            str(generated_path),
            str(canonical_path),
            str(tmp_path / "types.ts"),
            *(str(consumer) for consumer in consumers),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
