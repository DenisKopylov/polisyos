"""Read-only Phase-5 PR1 source/composition audit; emits no promotion receipt."""

import ast
import asyncio
import inspect
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

ROOT = Path.cwd()


def emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    sys.stdout.flush()


def inventory() -> None:
    from polisyos.runtime.quality import design_generation as dg
    from polisyos.runtime.quality import generation_cycle as gc
    from polisyos.runtime.quality import promotion_sequence as ps
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4

    names = {
        "CanonicalN9PromotionPort",
        "MeasurementRootProducer",
        "build_effective_independence_graph",
        "produce_from_catalog",
    }
    keys = {
        "effective_independence_writer_input",
        "measurement_root_writer_input",
        "effect_obligation_writer_input",
    }
    a = {str(p) for p in Path("src").rglob("*.py") if p.is_file()}
    git_binary = shutil.which("git")
    if git_binary is None:
        raise RuntimeError("git unavailable")
    b = {
        p
        # Fixed read-only argv; the executable is resolved from the station PATH above.
        for p in subprocess.check_output(  # noqa: S603
            [git_binary, "ls-files", "--cached", "--others", "--exclude-standard", "-z", "src"],
            text=True,
        ).split("\0")
        if p.endswith(".py")
    }
    if a != b:
        raise RuntimeError({"walk_only": sorted(a - b), "git_only": sorted(b - a)})
    calls, literals, ambiguous = [], [], []
    for path in sorted(a):
        try:
            tree = ast.parse(Path(path).read_text())
        except (OSError, UnicodeError, SyntaxError) as exc:
            ambiguous.append({"path": path, "error": repr(exc)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                token = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                if token in names:
                    calls.append({"path": path, "line": node.lineno, "call": ast.unparse(node)})
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in keys
            ):
                literals.append({"path": path, "line": node.lineno, "value": node.value})
    controller = gc.GenerationCycleController(repo_root=ROOT)
    problem = n4._design_problem(n4._load_recordings(ROOT)[0])
    try:
        value = asyncio.run(controller._generation_port(problem, cycle_index=0))
        default_generation = asdict(value) if is_dataclass(value) else vars(value)
    except gc.GenerationCycleError as exc:
        default_generation = {"exception": type(exc).__name__, "code": exc.code, "detail": str(exc)}
    explicit_model_without_context = asyncio.run(
        gc.N4GenerationPort(model_id="MiniMaxAI/MiniMax-M2.7", repo_root=ROOT)(
            problem, cycle_index=0
        )
    )
    contracts = {}
    for cls in (
        ps._EffectiveIndependenceWriterInput,
        ps._MeasurementRootWriterInput,
        ps._EffectObligationWriterInput,
        gc.CandidateSummary,
        gc.GenerationCycleRecord,
        dg.GenerationUnderAResult,
        dg.ShadowGeneratedCandidate,
        dg.GroundingDispositionRecord,
        CycleSubstrateContext,
    ):
        fields = sorted(cls.model_fields)
        module = ast.parse(Path(inspect.getfile(cls)).read_text())
        node = next(
            n for n in module.body if isinstance(n, ast.ClassDef) and n.name == cls.__name__
        )
        independent = sorted(
            n.target.id
            for n in node.body
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        )
        # Model fields inherited from the strict base are empty in these owners.
        if fields != independent:
            raise RuntimeError((cls.__name__, fields, independent))
        contracts[cls.__name__] = {
            "owner": inspect.getfile(cls),
            "fields": fields,
            "independent_ast_fields": independent,
            "required": sorted(
                name for name, field in cls.model_fields.items() if field.is_required()
            ),
        }
    emit(
        {
            "source_denominator": {
                "file_types": (
                    "all src/**/*.py regular files, including current untracked lane additions"
                ),
                "count": len(a),
                "identities": sorted(a),
                "identity_sets_equal": True,
                "ambiguous": ambiguous,
            },
            "calls": calls,
            "writer_key_literal_occurrences": literals,
            "typed_boundary_fields": contracts,
            "default_generation": default_generation,
            "model_configured_without_context": asdict(explicit_model_without_context),
            "default_n9_context_provider": repr(controller._promotion_port._context_provider),
            "context_provider_protocol": repr(ps.PromotionContextProvider),
            "binding_owner": inspect.getsource(ps._bind_production_promotion_evidence),
            "default_n4_source_boundary": inspect.getsource(gc.N4GenerationPort),
            "scope": "Mechanism/source boundary only; no candidate or receipt is constructed.",
        }
    )


def catalog() -> None:
    from polisyos.data_forge.read_api import catalog as owner
    from polisyos.runtime.quality.data_forge_binding import measurement_rows_for_catalog_payload

    root = owner._default_production_data_root().resolve()
    curated = root / "curated"
    cp = json.loads((curated / "data_contracts.json").read_text())
    bp = json.loads((curated / "source_bindings.json").read_text())
    contracts = {row["metric_id"]: row for row in cp["contracts"]}
    # Independent denominator from the full cross-product relation, with occurrence ordinals.
    forward = [
        (i, row["metric_id"])
        for i, row in enumerate(bp["bindings"])
        if row["metric_id"] in contracts
    ]
    independent = [
        (i, binding["metric_id"])
        for i, binding in enumerate(bp["bindings"])
        if any(contract["metric_id"] == binding["metric_id"] for contract in cp["contracts"])
    ]
    if forward != independent:
        raise RuntimeError((forward, independent))
    results = []
    for i, metric in forward:
        binding = bp["bindings"][i]
        row = owner._production_contract_dataset_record(
            contract=contracts[metric],
            binding=binding,
            generated_at=str(cp["generated_at"] or bp["generated_at"]),
        )
        payload = row.model_dump(mode="json")
        extracted = measurement_rows_for_catalog_payload(payload)
        results.append(
            {
                "binding_ordinal": i,
                "metric_id": metric,
                "dataset_id": row.id,
                "source_dataset_id": payload["source_dataset_id"],
                "connector": binding["connector_id"],
                "owner_extracted_rows": extracted,
            }
        )
    emit(
        {
            "source_contract_file": str(curated / "data_contracts.json"),
            "source_binding_file": str(curated / "source_bindings.json"),
            "denominator": (
                "Every source_bindings.bindings occurrence whose metric_id resolves in all "
                "data_contracts.contracts (same relation production owner builds)"
            ),
            "binding_identities": forward,
            "independent_binding_identities": independent,
            "identity_sets_equal": True,
            "ambiguous": [],
            "extractions": results,
            "unmatched_bindings": [
                {"ordinal": i, "payload": row}
                for i, row in enumerate(bp["bindings"])
                if row["metric_id"] not in contracts
            ],
            "owner_extractor": inspect.getsource(measurement_rows_for_catalog_payload),
            "scope": (
                "All real production catalog inputs through real record producer and measurement "
                "source extractor; not a fixture catalog and no candidate mapping is invented."
            ),
        }
    )


async def recorded() -> None:
    from polisyos.runtime.quality import generation_cycle as gc
    from tools.quality.validation import check_layer3_gy_design_generation_contract as owner

    rows = owner._load_recordings(ROOT)
    payload = json.loads((ROOT / owner.RECORDING_FIXTURE_PATH).read_text())
    a = [row["recording_id"] for row in rows]
    b = [row["recording_id"] for row in payload["recordings"]]
    if a != b:
        raise RuntimeError((a, b))
    emit(
        {
            "denominator": str(owner.RECORDING_FIXTURE_PATH)
            + (
                " / recordings array (all retained canonical N4 recording members; "
                "diagnostic_archive excluded by its own noncoverage designation)"
            ),
            "owner_identities": a,
            "raw_identities": b,
            "identity_sets_equal": True,
            "scope": (
                "Authentic retained LLM outputs replayed as candidate evidence only. This is not "
                "a current governed design or promotion denominator; no receipt is created."
            ),
        }
    )
    for recording in rows:
        result = await owner._run_live_generation(ROOT, recording=recording)
        dispositions = gc._disposition_candidates(result, existing_candidates=result.candidates)
        candidates = (*result.candidates, *dispositions)
        source_ids = sorted(row.proposal_id for row in result.grounding_dispositions)
        projected_ids = sorted(gc._candidate_id(row) for row in candidates)
        emit(
            {
                "recording_id": recording["recording_id"],
                "result": result.model_dump(mode="json"),
                "n6_disposition_candidates": [asdict(row) for row in dispositions],
                "raw_disposition_identity_set": source_ids,
                "n6_candidate_identity_set": projected_ids,
                "candidate_inputs": [
                    {
                        "candidate_id": gc._candidate_id(row),
                        "content_hash": gc._candidate_content_hash(row),
                        "has_atom": getattr(row, "atom", None) is not None,
                        "has_provenance": getattr(row, "provenance", None) is not None,
                        "has_legacy_writer_keys": [
                            key
                            for key in (
                                "effective_independence_writer_input",
                                "measurement_root_writer_input",
                                "effect_obligation_writer_input",
                            )
                            if hasattr(row, key)
                        ],
                    }
                    for row in candidates
                ],
            }
        )


def independence_sources() -> None:
    from polisyos.runtime.quality.scorecard import (
        _policy_design_evidence_line_rows,
        _policy_design_portfolio_design_rows,
    )

    root = Path("production_data").resolve()
    a = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p.suffix in {".json", ".jsonl"}
    }
    b = {
        str((Path(d) / n).relative_to(root))
        for d, _, names in os.walk(root)
        for n in names
        if Path(n).suffix in {".json", ".jsonl"} and (Path(d) / n).is_file()
    }
    if a != b:
        raise RuntimeError((a, b))
    hits, ambiguous = [], []

    def walk(value: object, pointer: str) -> Iterator[tuple[str, dict[str, object]]]:
        if isinstance(value, dict):
            yield pointer, value
            for key, child in value.items():
                yield from walk(
                    child, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
                )
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, pointer + "/" + str(index))

    crosscheck_failures = []

    def read_documents(name: str) -> Iterator[tuple[str, object]]:
        with (root / name).open() as stream:
            if Path(name).suffix == ".json":
                yield "", json.load(stream)
            else:
                for index, line in enumerate(stream, 1):
                    if line.strip():
                        yield f"line:{index}", json.loads(line)

    for name in sorted(a):
        try:
            # Validate the complete document stream before interpreting its rows.
            for _pointer, _document in read_documents(name):
                pass
        except (OSError, UnicodeError, ValueError) as exc:
            ambiguous.append({"path": name, "error": repr(exc)})
            continue
        for doc_id, document in read_documents(name):
            for pointer, mapping in walk(document, doc_id):
                lines = _policy_design_evidence_line_rows(mapping)
                portfolios = _policy_design_portfolio_design_rows(mapping)
                independent_lines = [
                    item
                    for key, value in mapping.items()
                    if key
                    in {"evidence_lines", "evidence_line_records", "portfolio_evidence_lines"}
                    and isinstance(value, list)
                    for item in value
                    if isinstance(item, dict)
                ]
                independent_portfolios = [
                    item
                    for key, value in mapping.items()
                    if key
                    in {"evidence_portfolio_designs", "portfolio_designs", "evidence_portfolios"}
                    and isinstance(value, list)
                    for item in value
                    if isinstance(item, dict)
                ]
                for node in mapping["nodes"] if isinstance(mapping.get("nodes"), list) else []:
                    if isinstance(node, dict):
                        if (
                            str(node.get("node_type") or "").strip() == "evidence_line"
                            or str(node.get("node_family") or "").strip() == "evidence_line"
                        ):
                            independent_lines.append(node)
                        if (
                            str(node.get("node_type") or "").strip() == "portfolio"
                            or str(node.get("node_family") or "").strip() == "evidence_portfolio"
                        ):
                            independent_portfolios.append(node)

                def normalized(rows: Iterable[Mapping[str, object]]) -> list[str]:
                    return sorted(json.dumps(row, sort_keys=True) for row in rows)

                if normalized(lines) != normalized(independent_lines) or normalized(
                    portfolios
                ) != normalized(independent_portfolios):
                    crosscheck_failures.append({"path": name, "pointer": pointer})
                if lines or portfolios:
                    hits.append(
                        {
                            "path": name,
                            "pointer": pointer,
                            "evidence_lines": lines,
                            "portfolio_designs": portfolios,
                            "source_class": (
                                "retained input, not yet candidate-bound or authority-validated"
                            ),
                        }
                    )
    emit(
        {
            "denominator": {
                "root": str(root),
                "file_types": (
                    "every regular .json and .jsonl file recursively; every nested object in "
                    "every successfully parsed document"
                ),
                "identities": sorted(a),
                "identity_sets_equal": True,
            },
            "executed_owner_extractors": [
                inspect.getsource(_policy_design_evidence_line_rows),
                inspect.getsource(_policy_design_portfolio_design_rows),
            ],
            "hits": hits,
            "ambiguous": ambiguous,
            "owner_vs_independent_full_row_multiset_differences": crosscheck_failures,
            "limitations": [
                "Database table rows and non-JSON formats are outside this typed-PDC JSON "
                "extraction denominator; no global claim that evidence does not exist is made.",
                "An unreadable file is ambiguous, never an empty source.",
                "A structural hit is not a candidate source until its exact claim/portfolio "
                "relation is independently bound.",
            ],
        }
    )
    if crosscheck_failures:
        raise RuntimeError(crosscheck_failures)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "inventory":
        inventory()
    elif mode == "catalog":
        catalog()
    elif mode == "recorded":
        asyncio.run(recorded())
    elif mode == "independence_sources":
        independence_sources()
    else:
        raise ValueError(mode)
