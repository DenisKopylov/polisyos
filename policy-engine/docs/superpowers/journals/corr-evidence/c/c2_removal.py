"""Remove C2 runtime properties in memory while retaining their emitted markers."""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest


def main() -> int:
    """Exercise the unchanged actual-source controls under one decisive removal."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "property",
        choices=(
            "preservation", "source_intake", "source_profile", "writer_projection", "effect_epoch"
        ),
    )
    args = parser.parse_args()
    prefix = "tests/unit/runtime/quality/test_generation_source.py::"
    if args.property == "effect_epoch":
        import ast
        import inspect
        import textwrap

        from polisyos.runtime.quality.promotion_sequence import N9PromotionEvidenceBridgeRepository

        original = N9PromotionEvidenceBridgeRepository._resolve_effect_record
        tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
        targets = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "source.schema_version != record.source_schema_ref"
        ]
        if len(targets) != 1:
            raise ValueError("effect_source_epoch_guard_identity_unresolved")
        targets[0].test = ast.Constant(value=False)
        namespace = dict(original.__globals__)
        exec(compile(ast.fix_missing_locations(tree), "<effect-epoch-removal>", "exec"), namespace)  # noqa: S102
        with patch.object(
            N9PromotionEvidenceBridgeRepository,
            "_resolve_effect_record",
            namespace[original.__name__],
        ):
            return int(
                pytest.main(
                    [
                        prefix + "test_current_effect_bridge_binds_actual_historical_emitter_epoch",
                        "-q",
                    ]
                )
            )
    if args.property == "preservation":
        from polisyos.runtime.quality.generation_cycle import N4GenerationPort

        original = N4GenerationPort.__call__

        async def summary_only(
            self: N4GenerationPort, *args: object, **kwargs: object
        ) -> object:
            result = await original(self, *args, **kwargs)
            return result.result if hasattr(result, "result") else result

        with patch.object(N4GenerationPort, "__call__", summary_only):
            return int(
                pytest.main(
                    [
                        prefix + "test_default_controller_custody_and_missing_protected_admission",
                        "-q",
                    ]
                )
            )
    from polisyos.runtime.quality import generation_source

    if args.property == "source_profile":
        with patch.object(generation_source, "_has_source_owner_profile", lambda _manifest: True):
            return int(
                pytest.main(
                    [prefix + "test_source_replay_requires_actual_persistence_owner_profile", "-q"]
                )
            )
    if args.property == "writer_projection":
        with patch.object(
            generation_source, "_writer_projection_preserves_grounding", lambda **_inputs: True
        ):
            return int(
                pytest.main(
                    [
                        prefix + "test_effect_writer_json_projection_preserves_complete_cg1",
                        prefix + "test_semantically_changed_writer_projection_refuses",
                        "-q",
                    ]
                )
            )
    # Pydantic's compiled validator retains this original function object.
    # Replace only its runtime code, not the schema, markers, artifact or test.
    validator = generation_source.GenerationSourceHandoff._validate_source_bindings
    code = validator.__code__
    validator.__code__ = (lambda self: self).__code__
    try:
        return int(
            pytest.main(
                [
                    prefix + "test_actual_source_roundtrip_and_repeat_identity",
                    prefix + "test_source_intake_recomputes_original_candidate_provenance",
                    "-q",
                ]
            )
        )
    finally:
        validator.__code__ = code


if __name__ == "__main__":
    raise SystemExit(main())
