"""Behavioral LA-017 controls with exact, independently recorded outcomes.

Each selected parameter must be run in its own pytest process. Its three phases
share that process but get separate inputs, CAS roots, caches, and patch scopes.
This is an internal comparison control, not legal authority or LA-017 closure.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import marshal
import os
import platform
import sys
import textwrap
import traceback
from dataclasses import asdict, dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.legal_evaluation import impact_diff
from polisyos.lex.legal_evaluation.impact_diff import NormImpactAnalyzer, NormImpactReport
from polisyos.lex.normpack.diff import NormDiff
from polisyos.lex.simulator import cli

MODES = (
    "producer_topics",
    "report_bridge",
    "markdown_disclaimer",
    "manifest_edge",
    "report_reconciliation",
    "diff_reconstruction",
    "delta_replay",
    "issue_total_bound",
    "scope_guard",
)
PHASES = ("positive_before", "removal_negative", "positive_restored")


@dataclass
class Result:
    kind: str
    value: Any = None
    exception_type: str | None = None
    exception_text: str | None = None
    traceback_sha256: str | None = None
    traceback_text: str | None = None


@dataclass
class Phase:
    phase: str
    pid: int
    root: str
    result: Result
    owner: str
    callable_sha256: str
    readset: dict[str, str]
    plugin_names: list[str]
    flags: dict[str, Any]
    writes: list[dict[str, Any]]
    input_sha256: str
    observed_calls: list[dict[str, Any]]
    code_sha256: str
    harness_errors: list[str] = field(default_factory=list)


def _rule(nid: str, kind: RuleType, expression: str) -> NormRule:
    key = "must_not" if kind is RuleType.PROHIBITION else "must"
    return NormRule(
        norm_id=nid,
        rule_type=kind,
        description=f"Rule {nid}",
        backend_refs=["expr_ast"],
        backend_metadata={key: expression},
    )


def _packs() -> tuple[NormPack, NormPack]:
    same = _rule("n.same", RuleType.PERMISSION, "2 >= 1")
    return (
        NormPack(
            pack_id="pack.old",
            jurisdiction="ua",
            norms=[
                same,
                _rule("n.modified", RuleType.OBLIGATION, "2 >= 1"),
                _rule("n.removed", RuleType.PROHIBITION, "2 > 1"),
            ],
        ),
        NormPack(
            pack_id="pack.new",
            jurisdiction="ua",
            norms=[
                same,
                _rule("n.modified", RuleType.OBLIGATION, "2 >= 3"),
                _rule("n.added", RuleType.PERMISSION, "2 >= 1"),
            ],
        ),
    )


def _persist(cas: FileSystemCAS, payload: dict[str, Any], diff_ref: Any) -> Any:
    return cas.put_json(
        payload,
        PutOptions(
            kind=NormImpactReport.ARTIFACT_KIND,
            media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
            inputs=[input_ref_from_artifact_ref(diff_ref, role="norm_diff")],
        ),
        return_selected_profile=True,
    )


def _source_readset() -> dict[str, str]:
    root = Path.cwd().resolve()
    found: dict[str, str] = {}
    for _name, module in sorted(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if not path or not str(path).endswith(".py"):
            continue
        try:
            real = Path(path).resolve()
            rel = real.relative_to(root).as_posix()
            if not rel.startswith(("src/polisyos/", "tests/", "tools/")):
                continue
            data = real.read_bytes()
        except (OSError, ValueError):
            continue
        found[rel] = hashlib.sha256(data).hexdigest()
    return found


def _callable_hash(obj: Any) -> str:
    try:
        body = inspect.getsource(obj).encode()
    except (OSError, TypeError):
        body = repr(obj).encode()
    return hashlib.sha256(body).hexdigest()


def _observe(mode: str, phase: str, root: Path, request: pytest.FixtureRequest) -> Phase:
    root.mkdir(parents=True, exist_ok=False)
    if any(root.iterdir()):
        raise RuntimeError("phase CAS root was not empty at phase start")
    cache_prefix = root / "bytecode-cache"
    cache_prefix.mkdir()
    prior_cache_prefix = sys.pycache_prefix
    cache_initial_bytes = sum(x.stat().st_size for x in cache_prefix.rglob("*") if x.is_file())
    sys.pycache_prefix = str(cache_prefix)
    writes: list[dict[str, Any]] = []
    outcome: Result
    owner, attr = _owner(mode)
    fn = getattr(owner, attr)
    fn_hash = _callable_hash(fn)
    code = getattr(fn, "__code__", None)
    code_hash = (
        hashlib.sha256(marshal.dumps(code)).hexdigest()
        if code is not None
        else hashlib.sha256(repr(fn).encode()).hexdigest()
    )
    calls: list[dict[str, Any]] = []
    old_profiler = sys.getprofile()

    def observer(frame: Any, event: str, arg: Any) -> Any:
        if event == "call" and code is not None and frame.f_code is code:
            event = {
                "pid": os.getpid(),
                "module": frame.f_globals.get("__name__"),
                "function": frame.f_code.co_name,
                "source": str(Path(frame.f_code.co_filename).resolve()),
                "first_line": frame.f_code.co_firstlineno,
                "code_sha256": hashlib.sha256(marshal.dumps(frame.f_code)).hexdigest(),
            }
            if mode == "scope_guard":
                old, new = frame.f_locals.get("old_pack"), frame.f_locals.get("new_pack")
                instance = frame.f_locals.get("self")
                event.update(
                    {
                        "old_jurisdiction": getattr(old, "jurisdiction", None),
                        "new_jurisdiction": getattr(new, "jurisdiction", None),
                        "report_schema_version": getattr(instance, "_report_schema_version", None),
                    }
                )
            calls.append(event)
        return observer

    sys.setprofile(observer)
    try:
        value = _exercise(mode, phase, root, request, writes)
        outcome = Result("value", value=value)
    except Exception as exc:  # recorded as ERROR evidence; never qualifies a removal red
        tb = traceback.format_exc()
        outcome = Result(
            "exception",
            exception_type=type(exc).__qualname__,
            exception_text=str(exc),
            traceback_sha256=hashlib.sha256(tb.encode()).hexdigest(),
            traceback_text=tb,
        )
    finally:
        sys.setprofile(old_profiler)
    plugins = sorted(
        type(p).__module__ + "." + type(p).__qualname__
        for p in request.config.pluginmanager.get_plugins()
    )
    flags = {
        "argv": list(sys.argv),
        "python_flags": {
            "optimize": sys.flags.optimize,
            "no_site": sys.flags.no_site,
            "no_user_site": sys.flags.no_user_site,
            "dont_write_bytecode": sys.dont_write_bytecode,
        },
        "env": {
            k: os.environ.get(k)
            for k in (
                "PYTEST_ADDOPTS",
                "PYTEST_PLUGINS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTHONPATH",
                "PYTHONOPTIMIZE",
                "PYTHONPYCACHEPREFIX",
            )
        },
    }
    phase_flags = dict(flags)
    phase_flags["bytecode_cache"] = str(cache_prefix)
    phase_flags["bytecode_cache_initial_bytes"] = cache_initial_bytes
    phase_flags["bytecode_cache_after_bytes"] = sum(
        x.stat().st_size for x in cache_prefix.rglob("*") if x.is_file()
    )
    phase_flags["sys_dont_write_bytecode"] = sys.dont_write_bytecode
    phase_flags["prior_bytecode_cache"] = prior_cache_prefix
    sys.pycache_prefix = prior_cache_prefix
    old_pack, new_pack = _packs()
    input_descriptor: dict[str, Any] = {
        "mode": mode,
        "old_pack": old_pack.model_dump(mode="json"),
        "new_pack": new_pack.model_dump(mode="json"),
        "passes": [] if mode == "scope_guard" else ["legal"],
        "legal_backend": None if mode == "scope_guard" else "expr_ast",
        "selected_schema_version": "1.1",
    }
    if mode == "scope_guard":
        input_descriptor["cross_jurisdiction_new_pack"] = new_pack.model_copy(
            update={"jurisdiction": "us"}
        ).model_dump(mode="json")
        input_descriptor["legacy_setup_schema_version"] = "1.0"
    input_bytes = json.dumps(input_descriptor, sort_keys=True, separators=(",", ":")).encode()
    owner_module = getattr(
        owner, "__module__", getattr(owner, "__name__", owner.__class__.__qualname__)
    )
    return Phase(
        phase,
        os.getpid(),
        str(root),
        outcome,
        f"{owner_module}.{getattr(owner, '__qualname__', owner.__class__.__qualname__)}.{attr}",
        fn_hash,
        _source_readset(),
        plugins,
        phase_flags,
        writes,
        hashlib.sha256(input_bytes).hexdigest(),
        calls,
        code_hash,
    )


def _owner(mode: str) -> tuple[Any, str]:
    if mode == "producer_topics":
        return impact_diff, "_infer_candidate_topics_v1_1"
    if mode == "report_bridge":
        return NormImpactAnalyzer, "_persist_report"
    if mode == "markdown_disclaimer":
        return cli, "render_impact_markdown"
    if mode == "manifest_edge":
        return impact_diff, "load_norm_impact_report"
    if mode in {
        "report_reconciliation",
        "diff_reconstruction",
        "delta_replay",
        "issue_total_bound",
    }:
        return impact_diff, "_reconcile_selected_report"
    return NormImpactAnalyzer, "analyze"


def _exercise(
    mode: str, phase: str, root: Path, request: pytest.FixtureRequest, writes: list[dict[str, Any]]
) -> Any:
    if mode == "producer_topics":
        cas = FileSystemCAS(root)
        report = NormImpactAnalyzer(
            cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
        ).analyze(*_packs())
        if report.cas_artifact_ref is None:
            return {"setup": "report_not_persisted"}
        reopened = impact_diff.load_norm_impact_report(FileSystemCAS(root), report.cas_artifact_ref)
        return sorted((t.kpi_id, t.description) for t in reopened.report.affected_kpis)
    if mode == "report_bridge":
        cas = FileSystemCAS(root)
        report = NormImpactAnalyzer(
            cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
        ).analyze(*_packs())
        if report.cas_artifact_ref is None:
            return {"persisted": False, "ref": None}
        try:
            reopened = impact_diff.load_norm_impact_report(
                FileSystemCAS(root), report.cas_artifact_ref
            )
            return {
                "persisted": True,
                "binding": reopened.diff_binding,
                "has_diff": reopened.diff is not None,
                "ref": str(report.cas_artifact_ref),
            }
        except ValueError as exc:
            return {
                "persisted": True,
                "reader_error": str(exc),
                "ref": str(report.cas_artifact_ref),
            }
    if mode == "markdown_disclaimer":
        cas = FileSystemCAS(root)
        report = NormImpactAnalyzer(
            cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
        ).analyze(*_packs())
        rendered = cli.render_impact_markdown(report)
        return {
            "disclaimer_present": "not measured effects or legal conclusions" in rendered,
            "render_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        }
    if mode == "manifest_edge":
        cas = FileSystemCAS(root)
        report = NormImpactAnalyzer(
            cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
        ).analyze(*_packs())
        issued = report.norm_diff_artifact_ref
        if issued is None:
            return {"setup": "no_diff_ref"}
        alt = cas.put_json(
            load_core_json_artifact(cas, issued),
            PutOptions(
                kind=NormDiff.ARTIFACT_KIND,
                media_type=NormDiff.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=NormDiff.ARTIFACT_SCHEMA_NAME, version="1.0"),
                producer=ProducerInfo(component="control.counterfeit", version="1"),
            ),
            return_selected_profile=True,
        )
        fresh = impact_diff.load_norm_impact_report(FileSystemCAS(root), report.cas_artifact_ref)
        payload = fresh.report.model_dump(mode="json")
        forged = cas.put_json(
            payload,
            PutOptions(
                kind=NormImpactReport.ARTIFACT_KIND,
                media_type=NormImpactReport.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=NormImpactReport.ARTIFACT_SCHEMA_NAME, version="1.1"),
                inputs=[input_ref_from_artifact_ref(alt, role="norm_diff")],
            ),
            return_selected_profile=True,
        )
        try:
            loaded = impact_diff.load_norm_impact_report(FileSystemCAS(root), forged)
            return {"accepted": True, "binding": loaded.diff_binding}
        except ValueError as exc:
            return {"accepted": False, "error": str(exc)}
    if mode in {
        "report_reconciliation",
        "diff_reconstruction",
        "delta_replay",
        "issue_total_bound",
    }:
        cas = FileSystemCAS(root)
        report = NormImpactAnalyzer(
            cas, passes=("legal",), legal_backend="expr_ast", report_schema_version="1.1"
        ).analyze(*_packs())
        if report.norm_diff_artifact_ref is None:
            return {"setup": "no_diff_ref"}
        fresh = impact_diff.load_norm_impact_report(FileSystemCAS(root), report.cas_artifact_ref)
        payload = fresh.report.model_dump(mode="json")
        diff_ref = report.norm_diff_artifact_ref
        if mode == "report_reconciliation":
            payload["norms_added"] = 99
        elif mode == "delta_replay":
            payload["compliance_deltas"][0]["pass_id"] = "safety"  # noqa: S105 - governance pass identifier
        elif mode == "issue_total_bound":
            payload["metadata"]["old_issues_total"] = 0
        else:
            diff = NormDiff.model_validate(load_core_json_artifact(cas, diff_ref))
            dp = diff.model_dump(mode="json")
            next(c for c in dp["changes"] if c["norm_id"] == "n.added")["new_rule"] = None
            diff_ref = cas.put_json(
                dp,
                PutOptions(
                    kind=NormDiff.ARTIFACT_KIND,
                    media_type=NormDiff.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(name=NormDiff.ARTIFACT_SCHEMA_NAME, version="1.0"),
                ),
                return_selected_profile=True,
            )
            payload["norm_diff_ref"] = str(diff_ref.artifact_id)
            payload["norm_diff_artifact_ref"] = diff_ref.model_dump(mode="json")
        forged = _persist(cas, payload, diff_ref)
        try:
            loaded = impact_diff.load_norm_impact_report(FileSystemCAS(root), forged)
            return {
                "accepted": True,
                "norms_added": loaded.report.norms_added,
                "delta_count": len(loaded.report.compliance_deltas),
            }
        except ValueError as exc:
            return {"accepted": False, "error": str(exc)}
    # Scope guard: establish the valid legacy 1.0 same-jurisdiction setup first,
    # with a fresh CAS and independent observer for each phase.
    cas = FileSystemCAS(root)
    old, new = _packs()
    legacy = NormImpactAnalyzer(cas, passes=(), report_schema_version="1.0").analyze(old, new)
    if legacy.cas_artifact_id is None:
        return {"setup": "legacy_not_persisted", "writes": []}
    # Schema 1.0 persists its artifact ID without claiming a selected-view ref.
    # Prove the real legacy ID is readable before measuring the mismatch call.
    reopened = impact_diff.load_norm_impact_report(FileSystemCAS(root), legacy.cas_artifact_id)
    legacy_ready = reopened.diff_binding == "legacy_unbound" and reopened.diff is not None
    foreign = new.model_copy(update={"jurisdiction": "us"})
    original = FileSystemCAS.put_json

    def observed_put(
        store: FileSystemCAS, obj: object, opts: PutOptions, *args: Any, **kwargs: Any
    ) -> Any:
        if store is cas:
            record = {
                "pid": os.getpid(),
                "callable": _callable_hash(original),
                "kind": opts.kind,
                "schema": {"name": opts.schema.name, "version": opts.schema.version}
                if opts.schema is not None
                else None,
                "payload_sha256": hashlib.sha256(
                    json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()
                ).hexdigest(),
            }
            writes.append(record)
        return original(store, obj, opts, *args, **kwargs)

    outcome: dict[str, Any]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FileSystemCAS, "put_json", observed_put)
        try:
            result = NormImpactAnalyzer(cas, passes=(), report_schema_version="1.1").analyze(
                old, foreign
            )
            outcome = {
                "outcome": "returned",
                "selected_ref": str(result.cas_artifact_ref) if result.cas_artifact_ref else None,
            }
        except ValueError as exc:
            outcome = {"outcome": "value_error", "error": str(exc)}
    outcome.update(
        {
            "legacy_ready": legacy_ready,
            "writes": writes,
            "observer_restored": FileSystemCAS.put_json is original,
            "observer_patch_count_after": len(patch._setattr),
        }
    )
    return outcome


def _mutant(mode: str, original: Any) -> Any:
    if mode == "producer_topics":
        return lambda diff: [
            t.model_copy(update={"description": "Operational KPI"}) for t in original(diff)
        ]
    if mode == "report_bridge":

        def no_bridge(self: Any, report: Any) -> Any:
            return self._cas.put_json(
                report.model_dump(mode="json"),
                PutOptions(
                    kind=report.ARTIFACT_KIND,
                    media_type=report.ARTIFACT_MEDIA_TYPE,
                    schema=SchemaInfo(name=report.ARTIFACT_SCHEMA_NAME, version="1.1"),
                    inputs=[],
                ),
                return_selected_profile=True,
            )

        return no_bridge
    if mode == "markdown_disclaimer":
        return lambda report: original(report).replace(
            "These are heuristic topics inferred from changed rule types, not measured effects or legal conclusions.",
            "",
        )
    if mode == "manifest_edge":

        class Edge(ast.NodeTransformer):
            count = 0

            def visit_Assign(self, node: ast.Assign) -> Any:
                if any(isinstance(t, ast.Name) and t.id == "expected_edge" for t in node.targets):
                    self.count += 1
                    node.value = ast.Subscript(
                        value=ast.Attribute(ast.Name("manifest", ast.Load()), "inputs", ast.Load()),
                        slice=ast.Constant(0),
                        ctx=ast.Load(),
                    )
                return self.generic_visit(node)

        transformer = Edge()
        tree = ast.fix_missing_locations(
            transformer.visit(ast.parse(textwrap.dedent(inspect.getsource(original))))
        )
        if transformer.count != 1:
            raise RuntimeError("manifest-edge mutation did not identify exactly one assignment")
        namespace = dict(vars(impact_diff))
        exec(compile(tree, inspect.getsourcefile(original) or "<C95-control>", "exec"), namespace)  # noqa: S102 - source-only removal probe
        return namespace[original.__name__]
    if mode in {
        "report_reconciliation",
        "diff_reconstruction",
        "delta_replay",
        "issue_total_bound",
    }:
        return lambda report, diff: None

    class Guard(ast.NodeTransformer):
        count = 0

        def visit_If(self, node: ast.If) -> Any:
            if "old_pack.jurisdiction != new_pack.jurisdiction" in ast.unparse(node.test):
                self.count += 1
                node.test = ast.Constant(False)
            return self.generic_visit(node)

    transformer = Guard()
    tree = ast.fix_missing_locations(
        transformer.visit(ast.parse(textwrap.dedent(inspect.getsource(original))))
    )
    if transformer.count != 1:
        raise RuntimeError("scope-guard mutation did not identify exactly one predicate")
    namespace = dict(vars(impact_diff))
    exec(compile(tree, inspect.getsourcefile(original) or "<C95-control>", "exec"), namespace)  # noqa: S102 - source-only removal probe
    return namespace[original.__name__]


def _property_holds(mode: str, observed: Phase) -> bool:
    """One property predicate for all three phases; exception data never qualifies."""
    result = observed.result
    if result.kind != "value":
        return False
    value = result.value
    if mode == "producer_topics":
        return dict(value) == {
            "compliance_cost": "Candidate topic inferred from an obligation rule type; no cost or effect has been measured.",
            "operational_restrictions": "Candidate topic inferred from a prohibition rule type; no restriction or effect has been measured.",
            "regulatory_flexibility": "Candidate topic inferred from a permission rule type; no flexibility or effect has been measured.",
        }
    if mode == "report_bridge":
        return value.get("binding") == "exact_selected" and value.get("has_diff") is True
    if mode == "markdown_disclaimer":
        return value.get("disclaimer_present") is True
    if mode == "manifest_edge":
        return (
            value.get("accepted") is False
            and value.get("error") == "report_norm_diff_input_mismatch"
        )
    if mode in {
        "report_reconciliation",
        "diff_reconstruction",
        "delta_replay",
        "issue_total_bound",
    }:
        return value.get("accepted") is False and value.get("error") == _reason(mode)
    return (
        value.get("legacy_ready") is True
        and value.get("observer_restored") is True
        and value.get("observer_patch_count_after") == 0
        and value.get("outcome") == "value_error"
        and value.get("error") == "selected_report_jurisdiction_mismatch"
        and not value.get("writes")
    )


def _qualified_removal(mode: str, observed: Phase) -> bool:
    """Reject a false property caused by setup failure or the wrong exception."""
    if observed.result.kind != "value":
        return False
    value = observed.result.value
    if mode == "producer_topics":
        return bool(value) and all(description == "Operational KPI" for _, description in value)
    if mode == "report_bridge":
        return (
            value.get("persisted") is True
            and value.get("reader_error") == "report_norm_diff_input_mismatch"
        )
    if mode == "markdown_disclaimer":
        return value.get("disclaimer_present") is False
    if mode == "manifest_edge" or mode in {
        "report_reconciliation",
        "diff_reconstruction",
        "delta_replay",
        "issue_total_bound",
    }:
        return value.get("accepted") is True
    writes = value.get("writes", [])
    return (
        value.get("legacy_ready") is True
        and value.get("observer_restored") is True
        and value.get("observer_patch_count_after") == 0
        and value.get("outcome") == "returned"
        and value.get("selected_ref") is not None
        and bool(writes)
        and {w["kind"] for w in writes} == {NormDiff.ARTIFACT_KIND, NormImpactReport.ARTIFACT_KIND}
        and all(w["pid"] == observed.pid and w["schema"] is not None for w in writes)
    )


def _reason(mode: str) -> str:
    return {
        "report_reconciliation": "report_norm_diff_counts_mismatch",
        "diff_reconstruction": "selected_norm_diff_inconsistent",
        "delta_replay": "report_compliance_delta_inconsistent",
        "issue_total_bound": "report_issue_total_below_carried_issues",
    }[mode]


@pytest.mark.parametrize("mode", MODES)
def test_exact_same_process_removal_triplet(
    mode: str, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    owner, attr = _owner(mode)
    original = getattr(owner, attr)
    phases: list[Phase] = []

    # Each phase gets a fresh logical fixture, separate CAS, and phase-local cache;
    # the outer owner replacement is always restored in a finally block.
    def phase_in_closed_context(name: str, activate: bool) -> Phase:
        replacement = _mutant(mode, original) if activate else original
        errors: list[str] = []
        with pytest.MonkeyPatch.context() as patch:
            if activate:
                patch.setattr(owner, attr, replacement)
            if getattr(owner, attr) is not replacement:
                errors.append("requested phase callable was not active")
            phase = _observe(mode, name, tmp_path / name, request)
            if len(patch._setattr) != (1 if activate else 0):
                errors.append("unexpected phase-local monkeypatch footprint")
        if len(patch._setattr) != 0:
            errors.append("phase-local monkeypatch context did not fully close")
        if getattr(owner, attr) is not original:
            errors.append("owner callable did not restore at phase boundary")
        phase.harness_errors.extend(errors)
        return phase

    phases.append(phase_in_closed_context("positive_before", False))
    phases.append(phase_in_closed_context("removal_negative", True))
    phases.append(phase_in_closed_context("positive_restored", False))
    # Capture every observation before assertions so a failure still leaves the
    # complete deciding trace in the command output.
    record = {
        "mode": mode,
        "pid_set": sorted({p.pid for p in phases}),
        "phases": [asdict(p) for p in phases],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "cwd": str(Path.cwd()),
            "source_commit": os.environ.get("C95_SOURCE_COMMIT"),
            "source_tree": os.environ.get("C95_SOURCE_TREE"),
        },
    }
    print("C95_ACTUAL_PHASES=" + json.dumps(record, sort_keys=True, separators=(",", ":")))
    assert len(phases) == 3 and len(record["pid_set"]) == 1, (
        "one scenario must complete all phases in one actual PID"
    )
    assert all(not p.harness_errors for p in phases), (
        "phase-local mutation/restore lifecycle failed"
    )
    assert all(
        p.observed_calls and all(call["pid"] == p.pid for call in p.observed_calls) for p in phases
    ), "profile observer did not see the real phase callable execute"
    property_results = [_property_holds(mode, p) for p in phases]
    assert property_results == [True, False, True], (
        "same property did not pass, fail under removal, and pass on restore"
    )
    assert _qualified_removal(mode, phases[1]), (
        "red did not result from the intended removal boundary"
    )
    if mode == "scope_guard":
        for phase in phases:
            assert [
                (
                    c.get("old_jurisdiction"),
                    c.get("new_jurisdiction"),
                    c.get("report_schema_version"),
                )
                for c in phase.observed_calls
            ] == [("ua", "ua", "1.0"), ("ua", "us", "1.1")], (
                "legacy setup and target mismatch call were not both observed"
            )
    assert phases[0].owner == phases[1].owner == phases[2].owner
    assert (
        phases[0].callable_sha256 != phases[1].callable_sha256
        and phases[1].code_sha256 != phases[0].code_sha256
    ), "the selected executable callable/code did not change for the removal phase"
    assert (
        phases[0].callable_sha256 == phases[2].callable_sha256
        and phases[0].code_sha256 == phases[2].code_sha256
    )
    assert phases[0].input_sha256 == phases[1].input_sha256 == phases[2].input_sha256, (
        "phase inputs are not logically identical"
    )
    assert len({p.root for p in phases}) == 3, "CAS roots were reused across phases"
    for left, right in pairwise(phases):
        shared = left.readset.keys() & right.readset.keys()
        assert all(left.readset[path] == right.readset[path] for path in shared), (
            "shared loaded source bytes changed inside the triplet"
        )
