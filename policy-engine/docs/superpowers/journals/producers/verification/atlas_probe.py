"""Remove one real verifier rejection in memory; an unchanged HTTP negative must fail."""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from polisyos.runtime.http.services import public_decision_verification as owner


def main() -> int:
    """Run the unchanged persisted-signature corruption witness after one mutation."""
    method = owner.PublicDecisionVerificationService._verify_entry
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    predicate = ast.dump(
        ast.parse(
            "verification.status is not artifacts.SignatureVerificationStatus.VALID",
            mode="eval",
        ).body
    )
    removed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.dump(node.test) == predicate:
            node.test = ast.copy_location(ast.Constant(value=False), node.test)
            removed += 1
    if removed != 1:
        raise RuntimeError(f"expected one cryptographic rejection, found {removed}")
    namespace = dict(vars(owner))
    # Compile only the checked local method AST into this disposable interpreter.
    exec(compile(ast.fix_missing_locations(tree), inspect.getfile(method), "exec"), namespace)  # noqa: S102
    owner.PublicDecisionVerificationService._verify_entry = namespace["_verify_entry"]
    return int(
        pytest.main(
            [
                "tests/unit/runtime/http/test_public_decision_verification_routes.py::"
                "test_owned_run_packet_is_redacted_issued_and_publicly_verified",
                "-q",
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
