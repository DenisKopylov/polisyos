"""Enumerate and execute the real RetrievalService construction boundaries."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import subprocess
import sys
import tokenize
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
TARGETS = {
    "polisyos.fabric.retrieval.RetrievalService",
    "polisyos.fabric.retrieval.service.RetrievalService",
}


@dataclass(frozen=True)
class ConstructorSite:
    """A lexical identity; line numbers are coordinates, never the identity."""

    path: str
    owner: str
    ordinal: int
    call: ast.Call

    @property
    def identity(self) -> str:
        return f"{self.path}::{self.owner}::RetrievalService[{self.ordinal}]"


def _current_python_paths() -> tuple[list[str], int]:
    indexed = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "src"],
        cwd=ROOT,
    )
    committed = subprocess.check_output(
        ["git", "ls-tree", "-rz", "--name-only", "HEAD", "--", "src"], cwd=ROOT
    )
    first = {
        p.decode()
        for p in indexed.split(b"\0")
        if p.endswith(b".py") and (ROOT / p.decode()).is_file()
    }
    base = {p.decode() for p in committed.split(b"\0") if p.endswith(b".py")}
    second = set(base)
    prefix = (
        subprocess.check_output(["git", "rev-parse", "--show-prefix"], cwd=ROOT).decode().strip()
    )
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "src"],
        cwd=ROOT,
    ).split(b"\0")
    cursor = 0
    while cursor < len(status):
        entry = status[cursor]
        cursor += 1
        if not entry:
            continue
        code, path = entry[:2].decode(), entry[3:].decode().removeprefix(prefix)
        if "R" in code or "C" in code:
            original = status[cursor].decode().removeprefix(prefix)
            cursor += 1
            if "R" in code:
                second.discard(original)
        if path.endswith(".py"):
            if "D" in code:
                second.discard(path)
            else:
                second.add(path)
    assert first == second, {
        "index_and_untracked_only": sorted(first - second),
        "head_plus_status_only": sorted(second - first),
    }
    return sorted(first), len(base)


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else None
    return None


def _expand(name: str | None, aliases: dict[str, str]) -> str | None:
    if not name:
        return name
    head, dot, tail = name.partition(".")
    return aliases.get(head, head) + (dot + tail if dot else "")


def _ast_sites(path: str, source: str) -> list[ConstructorSite]:
    tree = ast.parse(source, filename=path)
    # A direct/barrel import of this owner necessarily spells its module or class.
    # Every current source file is read, counted and hashed before this exact reject.
    if "retrieval" not in source and "RetrievalService" not in source:
        return []
    found: list[ConstructorSite] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.aliases: dict[str, str] = {}
            self.owners: list[str] = []
            self.ordinals: dict[str, int] = {}

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.level:
                parts = path.removeprefix("src/").removesuffix(".py").split("/")
                package = parts[:-1]
                module = ".".join(package[: len(package) - node.level + 1])
                module += ("." + node.module) if node.module else ""
            else:
                module = node.module or ""
            for alias in node.names:
                self.aliases[alias.asname or alias.name] = f"{module}.{alias.name}"

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                self.aliases[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            value = _expand(_name(node.value), self.aliases)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if value:
                        self.aliases[target.id] = value
                    else:
                        self.aliases.pop(target.id, None)

        def _scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
            saved = self.aliases.copy()
            self.owners.append(node.name)
            for statement in node.body:
                self.visit(statement)
            self.owners.pop()
            self.aliases = saved

        visit_FunctionDef = _scope  # noqa: N815 - stdlib NodeVisitor dispatch names
        visit_AsyncFunctionDef = _scope  # noqa: N815
        visit_ClassDef = _scope  # noqa: N815

        def visit_Call(self, node: ast.Call) -> None:
            if _expand(_name(node.func), self.aliases) in TARGETS:
                owner = ".".join(self.owners) or "<module>"
                ordinal = self.ordinals.get(owner, 0) + 1
                self.ordinals[owner] = ordinal
                found.append(ConstructorSite(path, owner, ordinal, node))
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _token_call_positions(source: str) -> set[tuple[int, int]]:
    """Independently tokenize imports, aliases and qualified invocation starts."""
    if "retrieval" not in source and "RetrievalService" not in source:
        return set()
    tokens = [
        t
        for t in tokenize.generate_tokens(io.StringIO(source).readline)
        if t.type not in {tokenize.COMMENT, tokenize.NL, tokenize.INDENT, tokenize.DEDENT}
    ]
    aliases: dict[str, str] = {}
    for index, token in enumerate(tokens):
        if token.string == "from":
            cursor, module = index + 1, ""
            while cursor < len(tokens) and tokens[cursor].string != "import":
                module += tokens[cursor].string
                cursor += 1
            cursor += 1
            while cursor < len(tokens) and tokens[cursor].type != tokenize.NEWLINE:
                item = tokens[cursor]
                if item.type == tokenize.NAME:
                    alias = item.string
                    if cursor + 2 < len(tokens) and tokens[cursor + 1].string == "as":
                        alias = tokens[cursor + 2].string
                        cursor += 2
                    aliases[alias] = f"{module}.{item.string}"
                cursor += 1
        elif token.string == "import" and (
            index == 0 or tokens[index - 1].type == tokenize.NEWLINE
        ):
            cursor, module = index + 1, ""
            while cursor < len(tokens) and (
                tokens[cursor].type == tokenize.NAME or tokens[cursor].string == "."
            ):
                if tokens[cursor].string == "as":
                    break
                module += tokens[cursor].string
                cursor += 1
            alias = module.split(".")[0]
            if cursor + 1 < len(tokens) and tokens[cursor].string == "as":
                alias = tokens[cursor + 1].string
            aliases[alias] = module if alias != module.split(".")[0] else alias
    # Simple alias assignments are resolved to a fixed point, independently of the AST walk.
    for _ in range(len(tokens)):
        changed = False
        for index in range(len(tokens) - 2):
            if tokens[index].type != tokenize.NAME or tokens[index + 1].string != "=":
                continue
            cursor, name = index + 2, ""
            while cursor < len(tokens) and (
                tokens[cursor].type == tokenize.NAME or tokens[cursor].string == "."
            ):
                name += tokens[cursor].string
                cursor += 1
            expanded = _expand(name, aliases)
            is_alias = cursor < len(tokens) and tokens[cursor].type == tokenize.NEWLINE
            canonical = "polisyos.fabric.retrieval.service.RetrievalService"
            if is_alias and expanded in TARGETS and aliases.get(tokens[index].string) != canonical:
                aliases[tokens[index].string] = canonical
                changed = True
        if not changed:
            break
    calls: set[tuple[int, int]] = set()
    for index, token in enumerate(tokens):
        if token.type != tokenize.NAME or (
            index and tokens[index - 1].string in {".", "class", "def"}
        ):
            continue
        cursor, name = index + 1, token.string
        while cursor + 1 < len(tokens) and tokens[cursor].string == ".":
            name += "." + tokens[cursor + 1].string
            cursor += 2
        if (
            cursor < len(tokens)
            and tokens[cursor].string == "("
            and _expand(name, aliases) in TARGETS
        ):
            calls.add(token.start)
    return calls


@lru_cache(maxsize=1)
def constructor_census() -> tuple[list[ConstructorSite], dict[str, Any]]:
    """Walk every current src Python file, reconciling two independent scans."""
    paths, base_count = _current_python_paths()
    sites: list[ConstructorSite] = []
    unreadable: list[dict[str, str]] = []
    ast_positions, token_positions = set(), set()
    source_hashes = {}
    for path in paths:
        try:
            source = (ROOT / path).read_text("utf-8")
            source_hashes[path] = hashlib.sha256(source.encode()).hexdigest()
            members = _ast_sites(path, source)
            independent = _token_call_positions(source)
        except (OSError, UnicodeError, SyntaxError, tokenize.TokenError) as exc:
            unreadable.append({"path": path, "reason": str(exc), "status": "ambiguous"})
            continue
        sites.extend(members)
        ast_positions.update((path, site.call.lineno, site.call.col_offset) for site in members)
        token_positions.update((path, line, column) for line, column in independent)
    assert not unreadable, unreadable
    assert ast_positions == token_positions, {
        "ast_only": sorted(ast_positions - token_positions),
        "token_only": sorted(token_positions - ast_positions),
    }
    assert source_hashes == {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths
    }, "current source changed during complete census"
    return sites, {
        "path_denominator": "current src/** (tracked plus non-ignored untracked)",
        "file_type_denominator": ".py",
        "head_tracked_python_files": base_count,
        "current_python_files": len(paths),
        "independent_head_plus_status_python_files": len(paths),
        "ast_call_count": len(ast_positions),
        "independent_token_call_count": len(token_positions),
        "unreadable": unreadable,
        "sites": [
            {
                "identity": site.identity,
                "line": site.call.lineno,
                "column": site.call.col_offset,
                "expression_sha256": hashlib.sha256(ast.dump(site.call).encode()).hexdigest(),
                "catalog_argument": next(
                    (ast.dump(k.value) for k in site.call.keywords if k.arg == "dataset_catalog"),
                    "<absent>",
                ),
            }
            for site in sites
        ],
    }


@pytest.fixture(scope="module")
def catalog_context(tmp_path_factory):
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.fabric.retrieval.providers import resolve_retrieval_providers
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.quality.acquisition_planner import RealAcquisitionOwnerGateway

    root = tmp_path_factory.mktemp("gy-d1-catalog")
    source = root / "production_data"
    source.mkdir()
    (source / "data_contracts.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {
                        "metric_id": "metric.gy_d1_catalog_only",
                        "display_name": "D1 recorded measurement",
                        "source_column": "value",
                        "jurisdiction": "UA",
                        "granularity": "annual",
                    }
                ]
            }
        )
    )
    (source / "source_bindings.json").write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "metric_id": "metric.gy_d1_catalog_only",
                        "connector_id": "static_csv",
                        "dataset_id": "d1-recorded.csv",
                        "trust": 0.9,
                    }
                ]
            }
        )
    )
    graph = catalog_api.build_production_data_contract_catalog_graph(
        production_root=source, graph_root=root / "graph"
    )
    providers = resolve_retrieval_providers()
    control = object.__new__(ControlPlaneService)
    control._registry_providers = resolve_control_registry_providers(gy_catalog_graph=graph)
    control._tracer = providers.tracer
    control._metrics = providers.metrics
    control._cas_root = root / "cas"
    control._retrieval_catalog = graph
    acquisition = RealAcquisitionOwnerGateway(repo_root=root)
    yield {
        "root": root,
        "source": source,
        "curated": root / "empty_curated",
        "graph": graph,
        "control": control,
        "acquisition": acquisition,
    }
    graph.close()


def _construct(
    site: ConstructorSite, context: dict[str, Any], monkeypatch, *, remove_catalog=False
):
    from polisyos.fabric.retrieval.service import RetrievalService
    from polisyos.runtime.http.services.control.artifacts import _resolve_curated_dir

    monkeypatch.setenv("POLISYOS_CURATED_DIR", str(context["curated"]))
    if site.owner.startswith("RealAcquisitionOwnerGateway."):
        owner = context["acquisition"]
    elif site.owner.startswith(("NaturalLanguageRunMixin.", "ControlPlaneService.")):
        owner = context["control"]
    else:
        raise AssertionError(f"ambiguous: constructor owner context unavailable: {site.identity}")
    local = {
        "self": owner,
        "curated_dir": context["curated"],
        "cas_root": context["root"] / "cas",
        "graph": context["graph"],
        "dataset_catalog": context["graph"],
        "retrieval_catalog": context["graph"],
    }
    global_values = {
        "RetrievalService": RetrievalService,
        "Path": Path,
        "_resolve_curated_dir": _resolve_curated_dir,
    }
    expression = deepcopy(site.call)
    if remove_catalog:
        matches = [keyword for keyword in expression.keywords if keyword.arg == "dataset_catalog"]
        assert len(matches) == 1, f"catalog keyword absent at {site.identity}"
        matches[0].value = ast.copy_location(ast.Constant(None), matches[0].value)
    # This deliberately executes the tracked owner's constructor, not supplied data.
    return eval(compile(ast.Expression(expression), site.path, "eval"), global_values, local)  # noqa: S307


def test_complete_constructor_census():
    sites, report = constructor_census()
    assert sites, report
    sys.__stdout__.write(json.dumps({"constructor_census": report}, indent=2) + "\n")


def test_actual_constructor_resolves_catalog(catalog_context, monkeypatch):
    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.read_api.catalog import DatasetCatalogGraph

    sites, report = constructor_census()
    outcomes = []
    for site in sites:
        try:
            service = _construct(site, catalog_context, monkeypatch)
            response = service.resolve(
                DataResolveRequest(
                    data_needs=[DataNeed(metric="metric.gy_d1_catalog_only")],
                    mode="fastlane",
                    allow_explore_fallback=False,
                )
            )
            assert isinstance(service._dataset_catalog, DatasetCatalogGraph), "catalog is not real"
            assert service._dataset_catalog is catalog_context["graph"], (
                "catalog is not selected graph"
            )
            assert response.fetch_plans, "catalog did not resolve"
            assert response.fetch_plans[0].metric_id == "metric.gy_d1_catalog_only"
            assert response.fetch_plans[0].dataset_id == "d1-recorded.csv"
            assert response.fetch_plans[0].metadata["resolution_route"] == "catalog"
        except Exception as exc:
            outcomes.append(
                {
                    "identity": site.identity,
                    "passed": False,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            outcomes.append({"identity": site.identity, "passed": True})
    assert len(outcomes) == report["ast_call_count"]
    sys.__stdout__.write(json.dumps({"constructor_resolution": outcomes}, indent=2) + "\n")
    assert all(row["passed"] for row in outcomes), json.dumps(
        {"census": report, "outcomes": outcomes}, indent=2
    )


def _fetch_context(owner, root: Path, monkeypatch):
    """Compose concrete runtime owners with actual file-backed Fabric registries."""
    from polisyos.fabric.retrieval import providers as provider_owner
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.quality.acquisition_planner import RealAcquisitionOwnerGateway

    monkeypatch.setattr(provider_owner, "_default_registry", lambda: owner.providers.registry)
    monkeypatch.setattr(provider_owner, "_default_profiles", lambda: owner.providers.profiles)
    control = object.__new__(ControlPlaneService)
    control._registry_providers = resolve_control_registry_providers(
        connectors=owner.providers.registry,
        source_profiles=owner.providers.profiles,
        gy_catalog_graph=owner.graph,
    )
    control._tracer = owner.providers.tracer
    control._metrics = owner.providers.metrics
    control._cas_root = owner.cas_root
    control._retrieval_catalog = owner.graph
    return {
        "root": root,
        "curated": owner.curated_dir,
        "graph": owner.graph,
        "control": control,
        "acquisition": RealAcquisitionOwnerGateway(repo_root=root),
    }


def _measurement(
    service,
    *,
    plan,
    providers,
    ledger_root: Path,
    promotion_input,
    design_problem,
    execute_outcome=None,
):
    """Exercise actual fetch, persisted root, evidence bridge and N9 obligation."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.fabric.retrieval.custody import FabricFetchCustodyError, resolve_persisted_fetch
    from polisyos.pdc import PromotionObligationClass
    from polisyos.runtime.quality.confidence_ledger import (
        ConfidenceLedgerSession,
        ConfidenceRiskBudgetScope,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootProducer,
        build_fabric_measurement_requirement,
    )
    from polisyos.runtime.quality.promotion_sequence import (
        CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        PROMOTION_SEQUENCE_REF,
        N9PromotionEvidenceBridgeRepository,
        _run_canonical_promotion_sequence_for_verification,
    )

    store = FileSystemCAS(service._executor._cas_root)
    graph = service._dataset_catalog
    repository = N9PromotionEvidenceBridgeRepository(
        store=store,
        measurement_catalog=graph,
        measurement_providers=providers,
    )
    roots = ()
    refusal = None
    binding = None
    data = None
    try:
        outcome = (
            execute_outcome
            if execute_outcome is not None
            else service.execute_fetch_plans([plan], persist_payload=True)
        )
        execution = outcome.previews[0]
        if execution.fetch_receipt_ref is None:
            # There is no producer input to bridge. Preserve this observed null;
            # N9 below must issue its own non-satisfied MEASUREMENT obligation.
            raise FabricFetchCustodyError("fabric_fetch_receipt_absent")
        fetched = resolve_persisted_fetch(
            store=store,
            fetch_receipt_ref=execution.fetch_receipt_ref,
            catalog=graph,
            providers=providers,
        )
        data = fetched.result.data
        selected = fetched.used_plan
        requirement = build_fabric_measurement_requirement(
            catalog=graph,
            catalog_binding=graph.bind_fetch_target(
                metric_id=selected.metric_id,
                connector_id=selected.connector_id,
                request_dataset_id=selected.dataset_id,
                profile_id=selected.profile_id,
                filters=selected.filters,
            ),
            design_problem=design_problem,
        )
        envelope = MeasurementRootProducer(artifact_store=store).produce_from_fabric_fetch(
            fetch_receipt_ref=execution.fetch_receipt_ref,
            catalog=graph,
            providers=providers,
            design_problem=design_problem,
            source_requirement=requirement,
        )
        bridge = repository.persist_measurement_root(
            promotion_input=promotion_input,
            envelope=envelope,
        )
        roots = (bridge,)
        binding = {
            "fetch_receipt_ref": execution.fetch_receipt_ref.model_dump(mode="json"),
            "payload_ref": execution.payload_ref.model_dump(mode="json"),
            "measurement_payload_ref": envelope.payload_ref,
            "n9_bridge_ref": bridge.model_dump(mode="json"),
        }
    except FabricFetchCustodyError as exc:
        refusal = exc.code
    current = promotion_input.model_copy(update={"producer_root_refs": roots})
    owner_binding = current.design_problem_binding
    scope = ConfidenceRiskBudgetScope(
        scope_owner_ref=PROMOTION_SEQUENCE_REF,
        authority_purpose="n9_promotion",
        owner_scope_key=f"design-problem:{owner_binding.design_problem_id}",
        owner_projection_hash=owner_binding.problem_content_hash,
        epoch_ref=None,
        model_ref=owner_binding.model_spec_ref,
        rule_ref=CANONICAL_PROMOTION_SEQUENCE_SCHEMA_VERSION,
        schema_ref=owner_binding.problem_schema_version,
    )
    ledger = ConfidenceLedgerSession._for_verification(
        ROOT,
        risk_scope=scope,
        artifact_store=FileSystemCAS(ledger_root / "cas"),
        state_root=ledger_root / "state",
    )
    receipt = _run_canonical_promotion_sequence_for_verification(
        current,
        confidence_ledger_session=ledger,
        promotion_evidence_resolver=repository,
    )
    measurement = next(
        row
        for row in receipt.obligations
        if row.obligation_role == "class_gate"
        and row.obligation_class == PromotionObligationClass.MEASUREMENT
    )
    return {
        "measurement_status": measurement.status.value,
        "measurement_detail": measurement.detail,
        "consumer_promotable": receipt.consumer_promotable,
        "custody_refusal": refusal,
        "bindings": binding,
        "data": data,
    }


def test_every_constructor_binds_full_fetch_into_n9_and_catalog_removal_refuses(
    tmp_path, monkeypatch
):
    """The denominator is discovered constructors; each actual boundary must pass."""
    import pandas as pd

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.pdc import PromotionObligationStatus
    from polisyos.runtime.quality.promotion_sequence import N9DesignProblemBinding
    from tests.unit.fabric.test_retrieval_fetch_custody import build_worldbank_fetch_owner
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _d1_worldbank_problem,
        _promotion_input,
    )

    sites, report = constructor_census()
    outcomes = []
    for index, site in enumerate(sites):
        root = tmp_path / str(index)
        root.mkdir()
        with build_worldbank_fetch_owner(root) as owner, monkeypatch.context() as patch:
            context = _fetch_context(owner, root, patch)
            problem = _d1_worldbank_problem(owner)
            initial = _promotion_input(
                design_problem_binding=N9DesignProblemBinding.from_problem(problem)
            )
            row = {"identity": site.identity}
            try:
                request = DataResolveRequest(
                    data_needs=[DataNeed(metric=owner.plan.metric_id)],
                    mode="fastlane",
                    allow_explore_fallback=False,
                )
                reference = owner.service.resolve(request)
                assert reference.fetch_plans, "real owner positive control cannot resolve"
                service = _construct(site, context, patch)
                resolved = service.resolve(request)
                row["caller_resolved_catalog"] = bool(resolved.fetch_plans)
                # A removed catalog must reach N9 too. Retain a real reference plan
                # as a negative input; a positive still owes this caller's resolve.
                plan = (resolved.fetch_plans or reference.fetch_plans)[0]
                assert plan.metadata["resolution_route"] == "catalog"
                baseline = _measurement(
                    service,
                    plan=plan,
                    providers=owner.providers,
                    ledger_root=root / "baseline-ledger",
                    promotion_input=initial,
                    design_problem=problem,
                )
                actual = baseline.pop("data")
                row["baseline"] = baseline
                assert baseline["measurement_status"] == PromotionObligationStatus.SATISFIED.value
                assert row["caller_resolved_catalog"], "actual caller catalog did not resolve"
                assert baseline["custody_refusal"] is None
                pd.testing.assert_frame_equal(actual, owner.frame)
                # Keep the exact real plan, including every catalog marker, across removal.
                frozen_plan = plan.model_dump(mode="json")
                removed = _construct(site, context, patch, remove_catalog=True)
                negative = _measurement(
                    removed,
                    plan=plan,
                    providers=owner.providers,
                    ledger_root=root / "removed-ledger",
                    promotion_input=initial,
                    design_problem=problem,
                )
                assert negative.pop("data") is None
                row["catalog_removed"] = negative
                assert plan.model_dump(mode="json") == frozen_plan
                assert negative["custody_refusal"] == "catalog_fetch_owner_missing"
                assert negative["measurement_status"] != PromotionObligationStatus.SATISFIED.value
                assert negative["consumer_promotable"] is False
            except Exception as exc:
                row.update(passed=False, reason=f"{type(exc).__name__}: {exc}")
            else:
                row["passed"] = True
            outcomes.append(row)
    assert len(outcomes) == report["ast_call_count"]
    finding_ids = sorted(row["identity"] for row in outcomes if not row["passed"])
    packet = {
        "constructor_denominator": report["ast_call_count"],
        "outcomes": outcomes,
        "finding_ids": finding_ids,
    }
    sys.__stdout__.write(json.dumps(packet, indent=2) + "\n")
    assert not finding_ids, json.dumps(packet, indent=2)


def _execute_actual_nl_fetch(service, resolved, *, remove_persistence=False):
    """Evaluate the actual NL owner's blocking fetch expression with real inputs."""
    import asyncio

    from polisyos.common.async_tools import run_blocking_async

    path = ROOT / "src/polisyos/runtime/http/services/control/nl_pipeline.py"
    text = path.read_text()
    tree = ast.parse(text)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _name(node.func) == "run_blocking_async"
        and node.args
        and _name(node.args[0]) == "retrieval.execute_fetch_plans"
    ]
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    independent = sum(
        1
        for index in range(len(tokens) - 2)
        if [token.string for token in tokens[index : index + 3]]
        == ["retrieval", ".", "execute_fetch_plans"]
    )
    assert len(calls) == independent == 1
    call = deepcopy(calls[0])
    if remove_persistence:
        keyword = next(item for item in call.keywords if item.arg == "persist_payload")
        keyword.value = ast.copy_location(ast.Constant(False), keyword.value)
    code = compile(ast.fix_missing_locations(ast.Expression(call)), str(path), "eval")
    result = asyncio.run(
        eval(  # noqa: S307 - execute the tracked owner expression, never supplied data
            code,
            {"run_blocking_async": run_blocking_async},
            {"retrieval": service, "resolve_outcome": resolved},
        )
    )
    return result, {
        "path": str(path.relative_to(ROOT)),
        "line": call.lineno,
        "expression_sha256": hashlib.sha256(ast.dump(call).encode()).hexdigest(),
        "ast_call_denominator": len(calls),
        "token_call_denominator": independent,
    }


def test_actual_nl_fetch_default_binds_measurement_and_persistence_removal_refuses(
    tmp_path, monkeypatch
):
    import pandas as pd

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.pdc import PromotionObligationStatus
    from polisyos.runtime.quality.promotion_sequence import N9DesignProblemBinding
    from tests.unit.fabric.test_retrieval_fetch_custody import build_worldbank_fetch_owner
    from tests.unit.runtime.quality.test_promotion_sequence import (
        _d1_worldbank_problem,
        _promotion_input,
    )

    sites, _ = constructor_census()
    nl = [site for site in sites if site.path.endswith("/nl_pipeline.py")]
    assert len(nl) == 1
    with build_worldbank_fetch_owner(tmp_path) as owner:
        context = _fetch_context(owner, tmp_path, monkeypatch)
        service = _construct(nl[0], context, monkeypatch)
        resolved = service.resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric=owner.plan.metric_id)],
                mode="fastlane",
                allow_explore_fallback=False,
            )
        )
        assert resolved.fetch_plans
        problem = _d1_worldbank_problem(owner)
        initial = _promotion_input(
            design_problem_binding=N9DesignProblemBinding.from_problem(problem)
        )
        outcomes = []
        try:
            for removed in (False, True):
                execution, expression = _execute_actual_nl_fetch(
                    service, resolved, remove_persistence=removed
                )
                measured = _measurement(
                    service,
                    plan=resolved.fetch_plans[0],
                    providers=owner.providers,
                    ledger_root=tmp_path / f"nl-ledger-{removed}",
                    promotion_input=initial,
                    design_problem=problem,
                    execute_outcome=execution,
                )
                data = measured.pop("data")
                outcomes.append(
                    {
                        "persistence_removed": removed,
                        "expression": expression,
                        "measurement": measured,
                    }
                )
                if removed:
                    assert data is None
                    assert execution.previews[0].fetch_receipt_ref is None
                    assert measured["custody_refusal"] == "fabric_fetch_receipt_absent"
                    assert (
                        measured["measurement_status"] != PromotionObligationStatus.SATISFIED.value
                    )
                else:
                    pd.testing.assert_frame_equal(data, owner.frame)
                    assert (
                        measured["measurement_status"] == PromotionObligationStatus.SATISFIED.value
                    )
                assert measured["consumer_promotable"] is False
        finally:
            sys.__stdout__.write(
                json.dumps({"actual_nl_fetch_persistence": outcomes}, indent=2) + "\n"
            )
