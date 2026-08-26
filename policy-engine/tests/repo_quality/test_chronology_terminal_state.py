from __future__ import annotations

import ast
import copy
import os
import subprocess
import tomllib
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.contracts import chronology as contract
from polisyos.core.contracts.runtime import UniversalPolicyCapabilityRealityLabel

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOCATION_PATH = (
    REPO_ROOT / "architecture" / "production_quality" / "chronology_capability_allocation.toml"
)
ENTRY_HASH_PREFIX = b"polisyos.chronology.capability-allocation-entry.v2\0"

type ChronologyCapabilityRealityLabel = (
    Literal["absent/unallocated"] | UniversalPolicyCapabilityRealityLabel
)
ChronologyPropertyResult = Literal["not_established", "established"]
ChronologyCapabilitySubject = Literal[
    "common_protocol_primitive",
    "generic_qualification_consumer",
    "epoch_family_producer",
    "release_family_producer",
    "run_family_producer",
    "movement_family_producer",
    "confidence_family_producer",
    "accepted_anchor_consumer",
    "writer_independent_holder",
    "family_audit_api_dashboard",
]
ChronologyActivationSignal = Literal[
    "cluster_2_common_protocol",
    "cluster_2_generic_consumer",
    "cluster_4_epoch_composition",
    "cluster_4_epoch_producer",
    "deferred_gy_gap3",
    "deferred_gy_gap5",
    "deferred_gy_gap6",
    "blocked_gy_gap2",
    "epoch_anchor_unappointed",
    "epoch_holder_unappointed",
    "family_surface_deferred",
    "whole_history_holder_not_established",
]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ChronologyCapabilityStateChange(_FrozenModel):
    row_kind: Literal["capability"]
    subject_key: ChronologyCapabilitySubject
    effective_after_cluster: Literal["cluster_2", "cluster_3", "cluster_4"]
    status: ChronologyCapabilityRealityLabel
    canonical_owner_ref: str
    routing_ref: str
    activation_signal: ChronologyActivationSignal


class ChronologyPropertyStateChange(_FrozenModel):
    row_kind: Literal["property"]
    subject_key: Literal["whole_history_authenticity"]
    effective_after_cluster: Literal["cluster_2", "cluster_3", "cluster_4"]
    status: ChronologyPropertyResult
    canonical_owner_ref: str
    routing_ref: str
    activation_signal: ChronologyActivationSignal


ChronologyCapabilityHistoryPayload = Annotated[
    ChronologyCapabilityStateChange | ChronologyPropertyStateChange,
    Field(discriminator="row_kind"),
]


class ChronologyCapabilityHistoryEntry(_FrozenModel):
    ordinal: int = Field(ge=0)
    predecessor_kind: Literal["genesis", "entry"]
    previous_entry_hash: contract.Digest | None
    payload: ChronologyCapabilityHistoryPayload
    entry_hash: contract.Digest


class ChronologyCapabilityHistory(_FrozenModel):
    schema_version: Literal["polisyos.chronology.capability-allocation-history.v2"]
    history_id: Literal["gy-n12-clusters-2-4"]
    entries: tuple[ChronologyCapabilityHistoryEntry, ...]


OWNER_ROUTE = {
    "common_protocol_primitive": ("core.chronology", "GY-N12-C2"),
    "generic_qualification_consumer": (
        "runtime.quality.chronology_qualification",
        "GY-N12-C2",
    ),
    "epoch_family_producer": ("runtime.quality.semantic_epoch", "GY-N12-C4"),
    "release_family_producer": ("release_family", "GY-GAP3"),
    "run_family_producer": ("recursive_run", "GY-GAP5"),
    "movement_family_producer": ("movement", "GY-GAP6"),
    "confidence_family_producer": ("confidence_composition", "GY-GAP2"),
    "accepted_anchor_consumer": ("epoch_anchor_acceptance", "GY-N12-C3"),
    "writer_independent_holder": ("epoch_anchor_holder", "GY-N12-C3"),
    "family_audit_api_dashboard": ("family_projection", "GY-N12-C4"),
    "whole_history_authenticity": ("epoch_history", "GY-N12-C3"),
}

INITIAL_STATE = (
    (
        "common_protocol_primitive",
        "implemented_but_not_orchestrated",
        "cluster_2_common_protocol",
    ),
    (
        "generic_qualification_consumer",
        "implemented_but_not_orchestrated",
        "cluster_2_generic_consumer",
    ),
    ("epoch_family_producer", "producer_missing", "cluster_4_epoch_producer"),
    ("release_family_producer", "absent/unallocated", "deferred_gy_gap3"),
    ("run_family_producer", "absent/unallocated", "deferred_gy_gap5"),
    ("movement_family_producer", "absent/unallocated", "deferred_gy_gap6"),
    (
        "confidence_family_producer",
        "absent/unallocated",
        "blocked_gy_gap2",
    ),
    (
        "accepted_anchor_consumer",
        "absent/unallocated",
        "epoch_anchor_unappointed",
    ),
    (
        "writer_independent_holder",
        "absent/unallocated",
        "epoch_holder_unappointed",
    ),
    (
        "family_audit_api_dashboard",
        "surface_missing",
        "family_surface_deferred",
    ),
    (
        "whole_history_authenticity",
        "not_established",
        "whole_history_holder_not_established",
    ),
)

CLUSTER4_TRANSITIONS = (
    (
        "common_protocol_primitive",
        "implemented",
        "cluster_4_epoch_composition",
    ),
    (
        "generic_qualification_consumer",
        "implemented",
        "cluster_4_epoch_composition",
    ),
    ("epoch_family_producer", "implemented", "cluster_4_epoch_producer"),
)

GOLDEN_ENTRY_HASHES = (
    "sha256:98c3139f01d2c5f01581cda0e518f88a3c2f857e425301dab6ab5c3c72ae7b43",
    "sha256:0a57911f80ef2bc7007c2b94f6544e6102927be85ff3732936e1ba19f19bb6b9",
    "sha256:782cf8d5ea5cf2b4a5dc67405830876b4f8ddbec08704467c351d30fd965676a",
    "sha256:cb6c384e522adb27d972e11b04fec7ba3da87af4f1b8e4a9bf09814e8dd76c3e",
    "sha256:586705f2354cd47291041c15a2b433dc31388cc5c13a9ea1fc11a274a3ce613c",
    "sha256:251ac17dbe4f0bce18b91af193cad96a6bdbcffdc61f305b5123db00369bb5b0",
    "sha256:65f10304a1914adf3d21797b1aaf762bc228294a4f499db0ade71dc16c044acd",
    "sha256:f7793368a7d090886f1548ac95419ee7881155b36448f15da214a276b7ed8387",
    "sha256:74a563ad786a10e526d9e42932c388a2d22cdb74fe904df9da8f1fd9960817f4",
    "sha256:4944f378e657fb167e2cb269a4f60ec7c8f0e3ac35270538b8c90445520d74f7",
    "sha256:058ec4a577e2fa6a15c449347e5dd0fb1d63221ba14277e43a916ce7edd35616",
    "sha256:beef50dcfb95420814f05c52a6aa2a7b3dbdda6662529154923ad4b8e7126857",
    "sha256:84f6e1a9855a14d00b97bb3ebf545cf18c4cb9926ce22dbdbf1ae2207d711870",
    "sha256:ad10ee0430b8e839986c5e2dd734ccfc48564ff915729dcd49856c0fa1e21564",
)

ACTIVATION_BY_SUBJECT = {
    "common_protocol_primitive": {
        "cluster_2_common_protocol",
        "cluster_4_epoch_composition",
    },
    "generic_qualification_consumer": {
        "cluster_2_generic_consumer",
        "cluster_4_epoch_composition",
    },
    "epoch_family_producer": {"cluster_4_epoch_producer"},
    "release_family_producer": {"deferred_gy_gap3"},
    "run_family_producer": {"deferred_gy_gap5"},
    "movement_family_producer": {"deferred_gy_gap6"},
    "confidence_family_producer": {"blocked_gy_gap2"},
    "accepted_anchor_consumer": {"epoch_anchor_unappointed"},
    "writer_independent_holder": {"epoch_holder_unappointed"},
    "family_audit_api_dashboard": {"family_surface_deferred"},
    "whole_history_authenticity": {"whole_history_holder_not_established"},
}

EXPECTED_EPOCH_RUNTIME_PATH = (
    "src/polisyos/runtime/quality/generation_cycle.py::"
    "GenerationCycleController._promote_completed_generation",
    "src/polisyos/runtime/quality/open_world_risk.py::"
    "PromotionRuntime.__init__[semantic_epoch_service=unallocated_policy_query]",
    "src/polisyos/runtime/quality/open_world_risk.py::"
    "PromotionRuntime.__init__[epoch_queries=persisted_negative_owner]",
    "src/polisyos/runtime/quality/open_world_risk.py::"
    "PromotionRuntime._prepare_completed_generation",
    "src/polisyos/runtime/quality/epoch_validity_cascade.py::"
    "PromotionOwnerQueryContextAuthority.persist_for_promotion",
    "src/polisyos/runtime/quality/open_world_risk.py::"
    "_PersistedNegativeEpochQueryOwner.resolve_for_promotion",
    "src/polisyos/runtime/quality/semantic_epoch.py::SemanticEpochService.qualify_chronology_query",
    "src/polisyos/runtime/quality/semantic_epoch.py::"
    "SemanticEpochService._qualification_consumer.qualify",
)


def _payload_mapping(
    payload: ChronologyCapabilityHistoryPayload,
) -> dict[str, object]:
    return {
        "row_kind": payload.row_kind,
        "subject_key": payload.subject_key,
        "effective_after_cluster": payload.effective_after_cluster,
        "status": payload.status,
        "canonical_owner_ref": payload.canonical_owner_ref,
        "routing_ref": payload.routing_ref,
        "activation_signal": payload.activation_signal,
    }


def _entry_mapping(entry: ChronologyCapabilityHistoryEntry) -> dict[str, object]:
    return {
        "ordinal": entry.ordinal,
        "predecessor_kind": entry.predecessor_kind,
        "previous_entry_hash": entry.previous_entry_hash,
        "payload": _payload_mapping(entry.payload),
    }


def _entry_hash(entry: ChronologyCapabilityHistoryEntry) -> contract.Digest:
    canonical = contract._canonical_raw_bytes(_entry_mapping(entry))
    return contract._sha256_digest(
        ENTRY_HASH_PREFIX,
        len(canonical).to_bytes(8, "big"),
        canonical,
    )


def _load_history_mapping(raw: dict[str, Any]) -> ChronologyCapabilityHistory:
    if set(raw) != {"schema_version", "history_id", "entries"}:
        raise ValueError("allocation history has unknown or missing top-level keys")
    raw_entries = raw.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("allocation entries must be physical TOML array tables")
    normalized: list[dict[str, Any]] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("allocation entry is not a TOML table")
        entry = dict(raw_entry)
        if "previous_entry_hash" not in entry:
            if entry.get("ordinal") != 0 or entry.get("predecessor_kind") != "genesis":
                raise ValueError("only the TOML genesis may omit previous_entry_hash")
            entry["previous_entry_hash"] = None
        normalized.append(entry)

    history = ChronologyCapabilityHistory.model_validate(
        {
            "schema_version": raw["schema_version"],
            "history_id": raw["history_id"],
            "entries": tuple(normalized),
        },
        strict=True,
    )
    seen: set[tuple[str, str]] = set()
    owners: dict[str, tuple[str, str]] = {}
    previous: contract.Digest | None = None
    previous_cluster = -1
    cluster_rank = {"cluster_2": 2, "cluster_3": 3, "cluster_4": 4}
    for ordinal, entry in enumerate(history.entries):
        if entry.ordinal != ordinal:
            raise ValueError("allocation ordinals are not contiguous")
        expected_kind = "genesis" if ordinal == 0 else "entry"
        if entry.predecessor_kind != expected_kind:
            raise ValueError("allocation predecessor kind differs from ordinal")
        if entry.previous_entry_hash != previous:
            raise ValueError("allocation predecessor hash is not the prior entry")
        if entry.entry_hash != _entry_hash(entry):
            raise ValueError("allocation entry hash is invalid")

        payload = entry.payload
        key = (payload.subject_key, payload.effective_after_cluster)
        if key in seen:
            raise ValueError("duplicate subject/cluster allocation transition")
        seen.add(key)
        rank = cluster_rank[payload.effective_after_cluster]
        if rank < previous_cluster:
            raise ValueError("allocation clusters are not monotone")
        previous_cluster = rank

        owner_route = (payload.canonical_owner_ref, payload.routing_ref)
        if OWNER_ROUTE[payload.subject_key] != owner_route:
            raise ValueError("allocation owner or routing identity is unknown")
        if payload.activation_signal not in ACTIVATION_BY_SUBJECT[payload.subject_key]:
            raise ValueError("allocation activation signal is unknown for its subject")
        prior_owner_route = owners.setdefault(payload.subject_key, owner_route)
        if prior_owner_route != owner_route:
            raise ValueError("allocation owner or routing identity mutated")
        previous = entry.entry_hash
    return history


def _load_history() -> ChronologyCapabilityHistory:
    return _load_history_mapping(tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8")))


def _git_candidate_paths() -> set[str]:
    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
            "*.pyi",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return {item.decode() for item in completed.stdout.split(b"\0") if item}


def _rehash_raw_history(raw: dict[str, Any]) -> None:
    previous: contract.Digest | None = None
    for ordinal, entry in enumerate(raw["entries"]):
        entry["ordinal"] = ordinal
        entry["predecessor_kind"] = "genesis" if ordinal == 0 else "entry"
        if ordinal == 0:
            entry.pop("previous_entry_hash", None)
        else:
            entry["previous_entry_hash"] = previous
        mapping = {
            "ordinal": ordinal,
            "predecessor_kind": entry["predecessor_kind"],
            "previous_entry_hash": previous,
            "payload": dict(entry["payload"]),
        }
        canonical = contract._canonical_raw_bytes(mapping)
        entry["entry_hash"] = contract._sha256_digest(
            ENTRY_HASH_PREFIX,
            len(canonical).to_bytes(8, "big"),
            canonical,
        )
        previous = entry["entry_hash"]


def _filesystem_candidate_paths() -> set[str]:
    discovered: list[str] = []
    for directory, child_dirs, files in os.walk(REPO_ROOT, followlinks=False):
        child_dirs[:] = [name for name in child_dirs if name != ".git"]
        root = Path(directory)
        for name in files:
            if name.endswith((".py", ".pyi")):
                discovered.append((root / name).relative_to(REPO_ROOT).as_posix())
    payload = b"\0".join(item.encode() for item in discovered)
    if payload:
        payload += b"\0"
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        cwd=REPO_ROOT,
        input=payload,
        check=False,
        capture_output=True,
    )
    if ignored.returncode not in {0, 1}:
        raise AssertionError(ignored.stderr.decode(errors="replace"))
    ignored_paths = {item.decode() for item in ignored.stdout.split(b"\0") if item}
    return set(discovered) - ignored_paths


def _classify(candidate: str) -> str:
    first = candidate.split("/", 1)[0]
    if first == "tests":
        return "test_only"
    if first == "benchmarks":
        return "benchmark_only"
    if first == "examples":
        return "example_only"
    if first in {"src", "tools", "apps", "ops", "architecture"}:
        return "production_capable"
    if candidate in {"jax_bootstrap.py", "migrate.py"}:
        return "production_capable"
    raise AssertionError(f"unclassified Python/stub path: {candidate}")


def _parse_candidate_tree(paths: set[str]) -> tuple[dict[str, str], dict[str, ast.Module]]:
    roles: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    parse_errors: dict[str, str] = {}
    for candidate in sorted(paths):
        roles[candidate] = _classify(candidate)
        try:
            trees[candidate] = ast.parse(
                (REPO_ROOT / candidate).read_text(encoding="utf-8"),
                filename=candidate,
            )
        except (SyntaxError, UnicodeDecodeError) as exc:
            parse_errors[candidate] = str(exc)
    assert not parse_errors
    return roles, trees


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix is not None else node.attr
    return None


def _epoch_runtime_paths(production: dict[str, ast.Module]) -> tuple[tuple[str, ...], ...]:
    """Derive the production N9-to-generic-consumer negative qualification route."""

    def method(
        candidate: str,
        class_name: str,
        function_name: str,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        tree = production.get(candidate)
        if tree is None:
            return None
        matches = [
            child
            for statement in tree.body
            if isinstance(statement, ast.ClassDef) and statement.name == class_name
            for child in statement.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            and child.name == function_name
        ]
        return matches[0] if len(matches) == 1 else None

    def has_call(
        function: ast.FunctionDef | ast.AsyncFunctionDef | None,
        called_name: str,
    ) -> bool:
        return function is not None and any(
            isinstance(node, ast.Call) and _dotted_name(node.func) == called_name
            for node in ast.walk(function)
        )

    open_world_path = "src/polisyos/runtime/quality/open_world_risk.py"
    generation_path = "src/polisyos/runtime/quality/generation_cycle.py"
    cascade_path = "src/polisyos/runtime/quality/epoch_validity_cascade.py"
    semantic_path = "src/polisyos/runtime/quality/semantic_epoch.py"
    promotion_init = method(open_world_path, "PromotionRuntime", "__init__")
    if promotion_init is None:
        return ()

    service_assignment = any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and isinstance(node.value, ast.Call)
        and _dotted_name(node.value.func) == "SemanticEpochService.for_unallocated_policy_query"
        and any(
            _dotted_name(target) == "self.semantic_epoch_service"
            for target in (node.targets if isinstance(node, ast.Assign) else (node.target,))
        )
        for node in ast.walk(promotion_init)
    )
    negative_owner_injection = any(
        isinstance(node, ast.Call)
        and _dotted_name(node.func) == "PromotionOwnerQueryContextAuthority"
        and any(
            keyword.arg == "epoch_queries"
            and isinstance(keyword.value, ast.Call)
            and _dotted_name(keyword.value.func) == "_PersistedNegativeEpochQueryOwner"
            and any(
                nested.arg == "semantic_epoch_service"
                and _dotted_name(nested.value) == "self.semantic_epoch_service"
                for nested in keyword.value.keywords
            )
            for keyword in node.keywords
        )
        for node in ast.walk(promotion_init)
    )
    required_calls = (
        (
            method(
                generation_path,
                "GenerationCycleController",
                "_promote_completed_generation",
            ),
            "runtime._prepare_completed_generation",
        ),
        (
            method(open_world_path, "PromotionRuntime", "_prepare_completed_generation"),
            "self.context_authority.persist_for_promotion",
        ),
        (
            method(
                cascade_path,
                "PromotionOwnerQueryContextAuthority",
                "persist_for_promotion",
            ),
            "self._epoch_queries.resolve_for_promotion",
        ),
        (
            method(
                open_world_path,
                "_PersistedNegativeEpochQueryOwner",
                "resolve_for_promotion",
            ),
            "self._semantic_epoch_service.qualify_chronology_query",
        ),
        (
            method(semantic_path, "SemanticEpochService", "qualify_chronology_query"),
            "self._qualification_consumer.qualify",
        ),
    )
    if (
        not service_assignment
        or not negative_owner_injection
        or not all(has_call(function, called_name) for function, called_name in required_calls)
    ):
        return ()
    return (EXPECTED_EPOCH_RUNTIME_PATH,)


def _assert_epoch_runtime_topology(topology: dict[str, object]) -> None:
    assert topology["epoch_runtime_paths"] == (EXPECTED_EPOCH_RUNTIME_PATH,)


def _remove_scoped_call(
    trees: dict[str, ast.Module],
    *,
    candidate: str,
    class_name: str | None,
    function_name: str,
    called_name: str,
) -> tuple[dict[str, ast.Module], int]:
    mutated = dict(trees)
    mutated[candidate] = copy.deepcopy(trees[candidate])

    class Remover(ast.NodeTransformer):
        def __init__(self) -> None:
            self.current_class: str | None = None
            self.current_function: str | None = None
            self.removed = 0

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
            previous = self.current_class
            self.current_class = node.name
            rewritten = self.generic_visit(node)
            self.current_class = previous
            return rewritten

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            previous = self.current_function
            self.current_function = node.name
            rewritten = self.generic_visit(node)
            self.current_function = previous
            return rewritten

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802
            previous = self.current_function
            self.current_function = node.name
            rewritten = self.generic_visit(node)
            self.current_function = previous
            return rewritten

        def visit_Call(self, node: ast.Call) -> ast.AST:
            if (
                self.current_class == class_name
                and self.current_function == function_name
                and _dotted_name(node.func) == called_name
            ):
                self.removed += 1
                return ast.copy_location(ast.Constant(value=None), node)
            return self.generic_visit(node)

    remover = Remover()
    mutated[candidate] = remover.visit(mutated[candidate])  # type: ignore[assignment]
    return mutated, remover.removed


def _source_topology(roles: dict[str, str], trees: dict[str, ast.Module]) -> dict[str, object]:
    production = {
        candidate: trees[candidate]
        for candidate, role in roles.items()
        if role == "production_capable"
    }
    consumer_definitions: list[str] = []
    consumer_imports: list[str] = []
    consumer_exports: list[str] = []
    consumer_factory_calls: list[str] = []
    concrete_adapters: list[tuple[str, str]] = []
    public_definitions: list[str] = []
    public_imports: list[str] = []
    public_exports: list[str] = []
    public_calls: list[str] = []
    common_definitions: Counter[str] = Counter()
    common_calls: dict[str, list[str]] = {
        "FullPrefixVerifier": [],
        "build_full_prefix_bundle": [],
    }
    common_names = {
        "ChronologyBundleRequest",
        "FullPrefixVerifier",
        "build_full_prefix_bundle",
    }
    for candidate, tree in production.items():
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "QualificationConsumer":
                    consumer_definitions.append(candidate)
                if node.name == "project_pre_n9_open_world_limitations":
                    public_definitions.append(candidate)
                if node.name in common_names:
                    common_definitions[node.name] += 1
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = {alias.name for alias in node.names}
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if "QualificationConsumer" in names or (
                    module is not None and module.endswith("chronology_qualification")
                ):
                    consumer_imports.append(candidate)
                if "project_pre_n9_open_world_limitations" in names:
                    public_imports.append(candidate)
            if isinstance(node, ast.Call):
                called = _dotted_name(node.func)
                if called is not None and "QualificationConsumer" in called.split("."):
                    consumer_factory_calls.append(candidate)
                if called is not None:
                    if called.split(".")[-1] == "project_pre_n9_open_world_limitations":
                        public_calls.append(candidate)
                    for common_name in common_calls:
                        if called.split(".")[-1] == common_name:
                            common_calls[common_name].append(candidate)
            if isinstance(node, ast.ClassDef):
                methods = {
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if (
                    "reconcile_candidate" in methods
                    and node.name != "NativeChronologyAuthorityAdapter"
                ):
                    concrete_adapters.append((candidate, node.name))
        for statement in tree.body:
            if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                continue
            target = statement.targets[0] if isinstance(statement, ast.Assign) else statement.target
            value = statement.value
            if isinstance(target, ast.Name) and target.id == "__all__" and value is not None:
                for element in getattr(value, "elts", ()):
                    if (
                        isinstance(element, ast.Constant)
                        and element.value == "QualificationConsumer"
                    ):
                        consumer_exports.append(candidate)
                    if (
                        isinstance(element, ast.Constant)
                        and element.value == "project_pre_n9_open_world_limitations"
                    ):
                        public_exports.append(candidate)
    return {
        "production_file_count": len(production),
        "consumer_definitions": tuple(sorted(consumer_definitions)),
        "consumer_imports": tuple(sorted(consumer_imports)),
        "consumer_exports": tuple(sorted(consumer_exports)),
        "consumer_factory_calls": tuple(sorted(consumer_factory_calls)),
        "epoch_runtime_paths": _epoch_runtime_paths(production),
        "concrete_adapters": tuple(sorted(concrete_adapters)),
        "public_definitions": tuple(sorted(public_definitions)),
        "public_imports": tuple(sorted(public_imports)),
        "public_exports": tuple(sorted(public_exports)),
        "public_calls": tuple(sorted(public_calls)),
        "common_definitions": dict(common_definitions),
        "common_calls": {name: tuple(sorted(paths)) for name, paths in common_calls.items()},
    }


def test_allocation_genesis_normalizes_to_explicit_canonical_null() -> None:
    raw = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    assert "previous_entry_hash" not in raw["entries"][0]
    history = _load_history_mapping(raw)
    genesis = history.entries[0]
    assert genesis.previous_entry_hash is None
    assert b'"previous_entry_hash":null' in contract._canonical_raw_bytes(_entry_mapping(genesis))

    missing_non_genesis = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    missing_non_genesis["entries"][1].pop("previous_entry_hash")
    with pytest.raises(ValueError, match="only the TOML genesis"):
        _load_history_mapping(missing_non_genesis)


def test_allocation_history_hashes_and_cluster4_transitions_are_frozen() -> None:
    history = _load_history()
    assert len(history.entries) == len(INITIAL_STATE) + len(CLUSTER4_TRANSITIONS) == 14
    observed = tuple(
        (
            entry.payload.subject_key,
            entry.payload.status,
            entry.payload.activation_signal,
        )
        for entry in history.entries
    )
    assert observed == (*INITIAL_STATE, *CLUSTER4_TRANSITIONS)
    assert tuple(entry.entry_hash for entry in history.entries) == GOLDEN_ENTRY_HASHES
    assert all(
        entry.payload.effective_after_cluster == "cluster_2" for entry in history.entries[:11]
    )
    assert all(
        entry.payload.effective_after_cluster == "cluster_4" for entry in history.entries[11:]
    )


def test_allocation_decoder_rejects_chain_owner_and_type_corruption() -> None:
    raw = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    mutations = []
    wrong_predecessor = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    wrong_predecessor["entries"][1]["previous_entry_hash"] = "sha256:" + "0" * 64
    mutations.append(wrong_predecessor)
    wrong_owner = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    wrong_owner["entries"][0]["payload"]["canonical_owner_ref"] = "candidate.owner"
    _rehash_raw_history(wrong_owner)
    mutations.append(wrong_owner)
    duplicate = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    duplicate["entries"][1]["payload"]["subject_key"] = "common_protocol_primitive"
    duplicate["entries"][1]["payload"]["canonical_owner_ref"] = "core.chronology"
    duplicate["entries"][1]["payload"]["activation_signal"] = "cluster_2_common_protocol"
    _rehash_raw_history(duplicate)
    mutations.append(duplicate)
    wrong_signal = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    wrong_signal["entries"][0]["payload"]["activation_signal"] = "blocked_gy_gap2"
    _rehash_raw_history(wrong_signal)
    mutations.append(wrong_signal)
    wrong_kind = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    wrong_kind["entries"][0]["payload"]["row_kind"] = "property"
    mutations.append(wrong_kind)
    wrong_hash = tomllib.loads(ALLOCATION_PATH.read_text(encoding="utf-8"))
    wrong_hash["entries"][0]["entry_hash"] = "sha256:" + "f" * 64
    mutations.append(wrong_hash)

    for mutation in mutations:
        with pytest.raises((KeyError, TypeError, ValidationError, ValueError)):
            _load_history_mapping(mutation)
    assert raw["entries"][0]["ordinal"] == 0


def test_cluster4_terminal_labels_match_source_derived_chain() -> None:
    git_paths = _git_candidate_paths()
    filesystem_paths = _filesystem_candidate_paths()
    assert git_paths == filesystem_paths
    roles, trees = _parse_candidate_tree(git_paths)
    assert sum(Counter(roles.values()).values()) == len(git_paths)
    topology = _source_topology(roles, trees)

    assert topology["common_definitions"] == {
        "ChronologyBundleRequest": 1,
        "FullPrefixVerifier": 1,
        "build_full_prefix_bundle": 1,
    }
    assert topology["consumer_definitions"] == (
        "src/polisyos/runtime/quality/chronology_qualification.py",
    )
    assert topology["consumer_exports"] == (
        "src/polisyos/runtime/quality/chronology_qualification.py",
    )
    assert topology["consumer_imports"] == ("src/polisyos/runtime/quality/semantic_epoch.py",)
    assert topology["consumer_factory_calls"] == (
        "src/polisyos/runtime/quality/acquisition_executor.py",
        "src/polisyos/runtime/quality/semantic_epoch.py",
    ), topology
    unallocated_mutation, removed = _remove_scoped_call(
        trees,
        candidate="src/polisyos/runtime/quality/semantic_epoch.py",
        class_name="SemanticEpochService",
        function_name="for_unallocated_policy_query",
        called_name="QualificationConsumer.from_unallocated_policy_authority",
    )
    assert removed == 1
    mutated_factory_calls = _source_topology(roles, unallocated_mutation)["consumer_factory_calls"]
    assert mutated_factory_calls != topology["consumer_factory_calls"]
    _assert_epoch_runtime_topology(topology)
    marker_fields = (
        "consumer_definitions",
        "consumer_imports",
        "consumer_exports",
        "consumer_factory_calls",
    )
    topology_mutations = (
        (
            "src/polisyos/runtime/quality/generation_cycle.py",
            "GenerationCycleController",
            "_promote_completed_generation",
            "runtime._prepare_completed_generation",
        ),
        (
            "src/polisyos/runtime/quality/open_world_risk.py",
            "PromotionRuntime",
            "__init__",
            "SemanticEpochService.for_unallocated_policy_query",
        ),
        (
            "src/polisyos/runtime/quality/open_world_risk.py",
            "PromotionRuntime",
            "__init__",
            "_PersistedNegativeEpochQueryOwner",
        ),
        (
            "src/polisyos/runtime/quality/open_world_risk.py",
            "PromotionRuntime",
            "_prepare_completed_generation",
            "self.context_authority.persist_for_promotion",
        ),
        (
            "src/polisyos/runtime/quality/epoch_validity_cascade.py",
            "PromotionOwnerQueryContextAuthority",
            "persist_for_promotion",
            "self._epoch_queries.resolve_for_promotion",
        ),
        (
            "src/polisyos/runtime/quality/open_world_risk.py",
            "_PersistedNegativeEpochQueryOwner",
            "resolve_for_promotion",
            "self._semantic_epoch_service.qualify_chronology_query",
        ),
        (
            "src/polisyos/runtime/quality/semantic_epoch.py",
            "SemanticEpochService",
            "qualify_chronology_query",
            "self._qualification_consumer.qualify",
        ),
    )
    for candidate, class_name, function_name, called_name in topology_mutations:
        mutated_trees, removed = _remove_scoped_call(
            trees,
            candidate=candidate,
            class_name=class_name,
            function_name=function_name,
            called_name=called_name,
        )
        assert removed == 1
        mutated_topology = _source_topology(roles, mutated_trees)
        assert {field: mutated_topology[field] for field in marker_fields} == {
            field: topology[field] for field in marker_fields
        }
        with pytest.raises(AssertionError):
            _assert_epoch_runtime_topology(mutated_topology)
    assert topology["concrete_adapters"] == (
        (
            "src/polisyos/runtime/quality/semantic_epoch.py",
            "SemanticEpochQualificationAdapter",
        ),
    ), topology
    assert topology["common_calls"] == {
        "FullPrefixVerifier": (
            "src/polisyos/core/security/chronology_anchor.py",
            "src/polisyos/core/security/chronology_anchor.py",
            "src/polisyos/runtime/quality/chronology_proof.py",
            "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
        ),
        "build_full_prefix_bundle": (
            "src/polisyos/runtime/quality/chronology_qualification.py",
            "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
        ),
    }
    assert topology["public_definitions"] == ("src/polisyos/runtime/quality/public_export.py",)
    assert topology["public_exports"] == ("src/polisyos/runtime/quality/public_export.py",)
    assert topology["public_imports"] == (
        "src/polisyos/runtime/http/services/control/generation_cycle.py",
        "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
    )
    assert topology["public_calls"] == (
        "src/polisyos/runtime/http/services/control/generation_cycle.py",
        "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
        "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
    )
    public_mutation, removed = _remove_scoped_call(
        trees,
        candidate="src/polisyos/runtime/http/services/control/generation_cycle.py",
        class_name=None,
        function_name="compile_and_run_recursive_generation_cycle",
        called_name="project_pre_n9_open_world_limitations",
    )
    assert removed == 1
    assert _source_topology(roles, public_mutation)["public_calls"] != topology["public_calls"]

    history = _load_history()
    state = {entry.payload.subject_key: entry.payload.status for entry in history.entries}
    expected = {subject: status for subject, status, _ in INITIAL_STATE}
    expected.update({subject: status for subject, status, _ in CLUSTER4_TRANSITIONS})
    assert state == expected
    assert state["common_protocol_primitive"] == "implemented"
    assert state["generic_qualification_consumer"] == "implemented"
    assert state["epoch_family_producer"] == "implemented"
    assert {
        state[subject]
        for subject in (
            "release_family_producer",
            "run_family_producer",
            "movement_family_producer",
            "confidence_family_producer",
            "accepted_anchor_consumer",
            "writer_independent_holder",
        )
    } == {"absent/unallocated"}
    assert state["family_audit_api_dashboard"] == "surface_missing"
    assert state["whole_history_authenticity"] == "not_established"
