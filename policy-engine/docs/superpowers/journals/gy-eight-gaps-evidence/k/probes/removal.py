"""Run one actual K consumer test with only its decisive property removed in memory."""

from __future__ import annotations

import argparse
import ast
import inspect
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["source-verifier", "stored-content", "default-extractor"])
    mode = parser.parse_args().mode

    import pytest

    from polisyos.data_forge.domains.academic.knowledge import skg_store
    from polisyos.ir.analytics import literature

    if mode == "source-verifier":
        name = "validate_openalex_source_bound_candidate"
        owner = skg_store
        original = getattr(owner, name)

        def removed(work, claim, **kwargs):
            del kwargs
            return literature.OpenAlexSourceBindingResult(
                claim_id=claim.claim_id, openalex_id=work.openalex_id,
                status="source_bound_candidate",
                span_start=claim.supporting_spans[0].start_char,
                span_end=claim.supporting_spans[0].end_char,
                grounding_ref=f"openalex-source-bound://{work.content_sha256}/{claim.claim_id}",
            )

        setattr(owner, name, removed)
        selected = "tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_source_candidate_ingress_consults_real_source_verifier_before_writes"
    else:
        owner = skg_store if mode == "stored-content" else literature
        name = "_ingest_openalex_claims" if mode == "stored-content" else "evaluate_openalex_claim_extractor_accuracy"
        original = getattr(owner, name)
        tree = ast.parse(inspect.getsource(original))

        class RemoveProperty(ast.NodeTransformer):
            def __init__(self) -> None:
                self.changed = 0

            def visit_Attribute(self, node):
                if mode == "stored-content" and isinstance(node.value, ast.Name) and node.value.id == "claim" and node.attr == "claim_text":
                    self.changed += 1
                    return ast.copy_location(ast.Constant("Stored content fabricated while all IDs and markers remain."), node)
                return self.generic_visit(node)

            def visit_Call(self, node):
                if mode == "default-extractor" and isinstance(node.func, ast.Name) and node.func.id == "extract_span_grounded_claims_from_openalex_work":
                    self.changed += 1
                    node.func = ast.copy_location(ast.Name(id="_extract_openalex_source_candidates", ctx=ast.Load()), node.func)
                return self.generic_visit(node)

        removal = RemoveProperty()
        changed = removal.visit(tree)
        assert removal.changed == 1, {"unexpected_changed_expression_count": removal.changed}
        exec(compile(ast.fix_missing_locations(changed), f"<K {mode} removal>", "exec"), owner.__dict__)
        selected = (
            "tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py::test_source_candidate_ingress_preserves_publication_boundary_and_candidate_authority"
            if mode == "stored-content" else
            "tests/unit/ir/test_literature_openalex_grounding.py::test_extractor_instrument_observes_actual_default_extractor"
        )
    print(json.dumps({"mode": mode, "selected": selected, "mutation_scope": "in-memory actual owner only; production source unchanged"}), flush=True)
    try:
        return pytest.main(["-q", "-s", "-rA", selected])
    finally:
        setattr(owner, name, original)


if __name__ == "__main__":
    raise SystemExit(main())
