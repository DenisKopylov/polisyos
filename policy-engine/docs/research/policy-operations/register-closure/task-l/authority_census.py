#!/usr/bin/env python3
"""Complete Task L authority denominator and acquisition-artifact census.

This research-owned tool does not create a runtime capability.  It enumerates
the tracked production/authority surface twice, reports exact named-model
observations, and exposes behavioral falsifiers for a future INT-R5 chain.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


SCHEMA_VERSION = "policyos.research.task_l.authority_census.v1"
PRODUCTION_ROOTS = (
    "src",
    "apps",
    "packages",
    "frontend",
    "ops",
    "schemas",
    "architecture",
)
SOURCE_SUFFIXES = frozenset(
    {
        ".bash",
        ".cjs",
        ".graphql",
        ".html",
        ".js",
        ".json",
        ".jsonl",
        ".jsx",
        ".mjs",
        ".proto",
        ".py",
        ".pyi",
        ".rego",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".yaml",
        ".yml",
        ".zsh",
    }
)
SOURCE_FILENAMES = frozenset({"Dockerfile"})
IGNORED_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".turbo",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
    }
)

# These are the exact names proposed by the admitted INT-R5/PAO-R4 research
# contracts.  Natural-language synonyms are deliberately not promoted into
# implementation evidence.
TARGET_PATTERNS = {
    "int_r5": re.compile(
        r"\b(?:DecisionAuthorityGraph|DelegationValidityCertificate|"
        r"ProtectedEffectAdmissible)\b"
    ),
    "pao_r4": re.compile(
        r"\b(?:PAOR4CrossingReceipt|PolicyToIndividualDecisionReceipt|"
        r"IndividualUseCrossingReceipt|FIREWALL_CLAIM_NOT_ESTABLISHED)\b"
    ),
    "ds20": re.compile(
        r"\b(?:BoundActionPermissionVerification|ActionPermissionVerification|"
        r"RuntimePermission|require_action_permission)\b"
    ),
    "int_r6": re.compile(
        r"\b(?:AuthorityTextSet|AuthorityTextMember|ContentRendition|SemanticConcept|"
        r"MappingAssertion|PresentationVariant|MultilingualAuthorityEquivalenceProtocol|"
        r"MultilingualAuthorityEquivalenceCertificate)\b"
    ),
    "ops_r15_oracle": re.compile(
        r"\b(?:SealedExpectationBundle|EvaluatorObservation|S0_GAP_02_PDL_1|"
        r"CustodyBenchmarkOracle)\b"
    ),
}
TARGET_TERMS = {
    "int_r5": (
        "DecisionAuthorityGraph",
        "DelegationValidityCertificate",
        "ProtectedEffectAdmissible",
    ),
    "pao_r4": (
        "PAOR4CrossingReceipt",
        "PolicyToIndividualDecisionReceipt",
        "IndividualUseCrossingReceipt",
        "FIREWALL_CLAIM_NOT_ESTABLISHED",
    ),
    "ds20": (
        "BoundActionPermissionVerification",
        "ActionPermissionVerification",
        "RuntimePermission",
        "require_action_permission",
    ),
    "int_r6": (
        "AuthorityTextSet",
        "AuthorityTextMember",
        "ContentRendition",
        "SemanticConcept",
        "MappingAssertion",
        "PresentationVariant",
        "MultilingualAuthorityEquivalenceProtocol",
        "MultilingualAuthorityEquivalenceCertificate",
    ),
    "ops_r15_oracle": (
        "SealedExpectationBundle",
        "EvaluatorObservation",
        "S0_GAP_02_PDL_1",
        "CustodyBenchmarkOracle",
    ),
}
TARGET_CALL_PATTERN = re.compile(
    r"\b(?:DecisionAuthorityGraph|DelegationValidityCertificate|"
    r"ProtectedEffectAdmissible|PAOR4CrossingReceipt|"
    r"PolicyToIndividualDecisionReceipt|IndividualUseCrossingReceipt)\s*\("
)
TARGET_EVENT_PATTERN = re.compile(
    r"(?i)(?:event_type|artifact_kind|schema(?:_version)?|receipt_kind|kind)"
    r".{0,160}(?:DecisionAuthorityGraph|DelegationValidityCertificate|"
    r"ProtectedEffectAdmissible|PAOR4CrossingReceipt|"
    r"PolicyToIndividualDecisionReceipt|IndividualUseCrossingReceipt)"
)
TARGET_CALL_GIT_EXPRESSION = (
    r"(DecisionAuthorityGraph|DelegationValidityCertificate|"
    r"ProtectedEffectAdmissible|PAOR4CrossingReceipt|"
    r"PolicyToIndividualDecisionReceipt|IndividualUseCrossingReceipt)"
    r"[[:space:]]*\("
)
TARGET_EVENT_GIT_EXPRESSION = (
    r"(event_type|artifact_kind|schema(_version)?|receipt_kind|kind)"
    r".{0,160}(DecisionAuthorityGraph|DelegationValidityCertificate|"
    r"ProtectedEffectAdmissible|PAOR4CrossingReceipt|"
    r"PolicyToIndividualDecisionReceipt|IndividualUseCrossingReceipt)"
)

INT_R5_CERTIFICATE = "int_r5.delegation_validity_certificate"
DS20_PERMISSION = "ds20.exact_permission_receipt"
PAO_R4_RECEIPT = "pao_r4.crossing_receipt"
CONJUNCTION_RECEIPT = "protected_effect.admissibility_receipt"
PROTECTED_EFFECT = "protected_effect"


class AuthorityChainIncompleteError(ValueError):
    """Raised when a declared authority-chain graph lacks a required edge."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class AuthorityArtifactDeltaError(AssertionError):
    """Raised when one action emits anything beyond its canonical decision."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def complete_chain_fixture() -> dict[str, dict[str, object]]:
    """Return a minimal complete graph used only to prove the validator can fail."""

    return {
        "int-r5-producer": {"consumes": [], "produces": [INT_R5_CERTIFICATE], "effects": []},
        "ds20-producer": {"consumes": [], "produces": [DS20_PERMISSION], "effects": []},
        "pao-r4-producer": {"consumes": [], "produces": [PAO_R4_RECEIPT], "effects": []},
        "conjunction-evaluator": {
            "consumes": [INT_R5_CERTIFICATE, DS20_PERMISSION, PAO_R4_RECEIPT],
            "produces": [CONJUNCTION_RECEIPT],
            "effects": [],
        },
        "protected-consumer": {
            "consumes": [CONJUNCTION_RECEIPT],
            "produces": [],
            "effects": [PROTECTED_EFFECT],
        },
    }


def validate_authority_chain(
    records: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Validate source-to-conjunction-to-effect reachability for INT-R5.

    Args:
        records: Component records with ``consumes``, ``produces``, and ``effects`` lists.

    Returns:
        A small established report when the complete property holds.

    Raises:
        AuthorityChainIncompleteError: If any required producer, edge, or consumer is absent.
    """

    normalized: dict[str, dict[str, frozenset[str]]] = {}
    for component_id, record in records.items():
        if not isinstance(component_id, str) or not component_id:
            raise AuthorityChainIncompleteError("component_id_invalid", repr(component_id))
        normalized[component_id] = {}
        for field in ("consumes", "produces", "effects"):
            raw = record.get(field)
            if not isinstance(raw, (list, tuple, set, frozenset)) or any(
                not isinstance(item, str) or not item for item in raw
            ):
                raise AuthorityChainIncompleteError(
                    "component_field_invalid", f"{component_id}.{field}"
                )
            normalized[component_id][field] = frozenset(raw)

    producers: dict[str, list[str]] = {}
    for component_id, record in normalized.items():
        for artifact in record["produces"]:
            producers.setdefault(artifact, []).append(component_id)
    for required in (INT_R5_CERTIFICATE, DS20_PERMISSION, PAO_R4_RECEIPT):
        owners = producers.get(required, [])
        if len(owners) != 1:
            raise AuthorityChainIncompleteError(
                "required_producer_cardinality", f"{required}:{sorted(owners)}"
            )

    evaluators = [
        component_id
        for component_id, record in normalized.items()
        if CONJUNCTION_RECEIPT in record["produces"]
    ]
    if len(evaluators) != 1:
        raise AuthorityChainIncompleteError(
            "conjunction_evaluator_cardinality", repr(sorted(evaluators))
        )
    evaluator = normalized[evaluators[0]]
    required_inputs = frozenset({INT_R5_CERTIFICATE, DS20_PERMISSION, PAO_R4_RECEIPT})
    missing_inputs = sorted(required_inputs - evaluator["consumes"])
    if missing_inputs:
        raise AuthorityChainIncompleteError(
            "conjunction_evaluator_input_missing", repr(missing_inputs)
        )

    consumers = [
        component_id
        for component_id, record in normalized.items()
        if CONJUNCTION_RECEIPT in record["consumes"] and PROTECTED_EFFECT in record["effects"]
    ]
    if len(consumers) != 1:
        raise AuthorityChainIncompleteError(
            "protected_consumer_cardinality", repr(sorted(consumers))
        )
    return {
        "status": "established",
        "component_count": len(normalized),
        "conjunction_evaluator": evaluators[0],
        "protected_consumer": consumers[0],
    }


def _is_source(path: Path) -> bool:
    return path.suffix.casefold() in SOURCE_SUFFIXES or path.name in SOURCE_FILENAMES


def _filesystem_paths(repo_root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for root_name in PRODUCTION_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for directory, directory_names, file_names in os.walk(root):
            directory_names[:] = sorted(
                name for name in directory_names if name not in IGNORED_PARTS
            )
            base = Path(directory)
            for file_name in sorted(file_names):
                path = base / file_name
                relative = path.relative_to(repo_root)
                if _is_source(relative):
                    paths.append(relative.as_posix())
    return tuple(sorted(paths))


def _git_paths(repo_root: Path) -> tuple[str, ...]:
    completed = subprocess.run(  # noqa: S603 - fixed Git executable and literal arguments
        ("git", "ls-files", "-z", "--", *PRODUCTION_ROOTS),
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    paths = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        path = Path(raw.decode("utf-8"))
        if not any(part in IGNORED_PARTS for part in path.parts) and _is_source(path):
            paths.append(path.as_posix())
    return tuple(sorted(paths))


def _path_digest(paths: tuple[str, ...]) -> str:
    return "sha256:" + hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()


def _git_grep_files(
    repo_root: Path,
    denominator: frozenset[str],
    terms: tuple[str, ...],
) -> tuple[str, ...]:
    expression_args = tuple(argument for term in terms for argument in ("-e", term))
    completed = subprocess.run(  # noqa: S603 - fixed Git executable and literal arguments
        ("git", "grep", "-l", "-I", *expression_args, "--", *PRODUCTION_ROOTS),
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(completed.stderr.strip() or "git grep failed")
    return tuple(sorted(path for path in completed.stdout.splitlines() if path in denominator))


def _git_grep_line_sites(
    repo_root: Path,
    denominator: frozenset[str],
    expression: str,
    *,
    ignore_case: bool = False,
) -> tuple[str, ...]:
    arguments = ["git", "grep", "-n", "-I", "-E"]
    if ignore_case:
        arguments.append("-i")
    arguments.extend(("-e", expression, "--", *PRODUCTION_ROOTS))
    completed = subprocess.run(  # noqa: S603 - fixed Git executable and literal roots
        tuple(arguments),
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in {0, 1}:
        raise RuntimeError(completed.stderr.strip() or "git grep failed")
    sites: list[str] = []
    for row in completed.stdout.splitlines():
        path, line_number, _ = row.split(":", 2)
        if path in denominator:
            sites.append(f"{path}:{line_number}")
    return tuple(sorted(sites))


def _class_base_names(node: ast.ClassDef) -> tuple[str, ...]:
    return tuple(sorted(ast.unparse(base) for base in node.bases))


def _ast_authority_providers(
    texts: Mapping[str, str],
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, str], ...]]:
    providers: list[dict[str, object]] = []
    ambiguous: list[dict[str, str]] = []
    for relative, text in sorted(texts.items()):
        if not relative.endswith(".py"):
            continue
        try:
            tree = ast.parse(text, filename=relative)
        except (SyntaxError, ValueError) as exc:
            ambiguous.append({"path": relative, "error": type(exc).__name__})
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {
                member.name
                for member in node.body
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if {"for_request", "for_job"} <= methods:
                bases = _class_base_names(node)
                providers.append(
                    {
                        "path": relative,
                        "class_name": node.name,
                        "line": node.lineno,
                        "bases": list(bases),
                        "protocol_or_abstract": any(
                            base.rsplit(".", 1)[-1] in {"Protocol", "ABC"} for base in bases
                        ),
                    }
                )
    return tuple(providers), tuple(ambiguous)


def _indentation_authority_providers(
    texts: Mapping[str, str],
) -> tuple[dict[str, object], ...]:
    """Derive provider classes without using Python's AST decoder."""

    class_header = re.compile(
        r"^(?P<indent>[ \t]*)class\s+(?P<name>[A-Za-z_]\w*)"
        r"(?:\((?P<bases>[^\n]*)\))?\s*:\s*(?:#.*)?$"
    )
    method_header = re.compile(r"^(?P<indent>[ \t]*)(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*\(")
    providers: list[dict[str, object]] = []
    for relative, text in sorted(texts.items()):
        if not relative.endswith(".py"):
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines):
            matched_class = class_header.match(line)
            if matched_class is None:
                continue
            class_indent = len(matched_class.group("indent").expandtabs(8))
            methods: set[str] = set()
            for candidate in lines[index + 1 :]:
                if not candidate.strip() or candidate.lstrip().startswith("#"):
                    continue
                candidate_indent = len(candidate) - len(candidate.lstrip(" \t"))
                if candidate_indent <= class_indent:
                    break
                matched_method = method_header.match(candidate)
                if matched_method is not None:
                    methods.add(matched_method.group("name"))
            if {"for_request", "for_job"} <= methods:
                bases = tuple(
                    sorted(
                        base.strip()
                        for base in (matched_class.group("bases") or "").split(",")
                        if base.strip()
                    )
                )
                providers.append(
                    {
                        "path": relative,
                        "class_name": matched_class.group("name"),
                        "line": index + 1,
                        "bases": list(bases),
                        "protocol_or_abstract": any(
                            base.rsplit(".", 1)[-1] in {"Protocol", "ABC"} for base in bases
                        ),
                    }
                )
    return tuple(providers)


def census_repository(repo_root: Path) -> dict[str, object]:
    """Walk the complete declared production denominator and report target evidence.

    The filesystem walk and Git-index listing are independent set derivations.
    Target-name file counts are independently repeated through ``git grep``.
    Unreadable members remain explicit ambiguities.
    """

    repo_root = repo_root.resolve()
    filesystem_paths = _filesystem_paths(repo_root)
    git_paths = _git_paths(repo_root)
    filesystem_set = frozenset(filesystem_paths)
    git_set = frozenset(git_paths)

    unreadable: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    for relative in filesystem_paths:
        try:
            texts[relative] = (repo_root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            unreadable.append({"path": relative, "error": type(exc).__name__})

    filesystem_hits: dict[str, tuple[str, ...]] = {}
    git_hits: dict[str, tuple[str, ...]] = {}
    for family, pattern in TARGET_PATTERNS.items():
        filesystem_hits[family] = tuple(
            sorted(path for path, text in texts.items() if pattern.search(text))
        )
        git_hits[family] = _git_grep_files(repo_root, git_set, TARGET_TERMS[family])

    conjunction_files = tuple(
        sorted(
            set(filesystem_hits["int_r5"])
            & set(filesystem_hits["pao_r4"])
            & set(filesystem_hits["ds20"])
        )
    )
    filesystem_call_sites = tuple(
        sorted(
            f"{path}:{line_number}"
            for path, text in texts.items()
            for line_number, line in enumerate(text.splitlines(), start=1)
            if TARGET_CALL_PATTERN.search(line)
        )
    )
    git_call_sites = _git_grep_line_sites(
        repo_root,
        git_set,
        TARGET_CALL_GIT_EXPRESSION,
    )
    filesystem_event_sites = tuple(
        sorted(
            f"{path}:{line_number}"
            for path, text in texts.items()
            for line_number, line in enumerate(text.splitlines(), start=1)
            if TARGET_EVENT_PATTERN.search(line)
        )
    )
    git_event_sites = _git_grep_line_sites(
        repo_root,
        git_set,
        TARGET_EVENT_GIT_EXPRESSION,
        ignore_case=True,
    )
    target_counts_agree = all(
        filesystem_hits[family] == git_hits[family] for family in TARGET_PATTERNS
    )
    ast_providers, python_parse_ambiguous = _ast_authority_providers(texts)
    indentation_providers = _indentation_authority_providers(texts)
    concrete_providers = tuple(row for row in ast_providers if not row["protocol_or_abstract"])

    return {
        "schema_version": SCHEMA_VERSION,
        "repository_root": repo_root.as_posix(),
        "denominator": {
            "roots": list(PRODUCTION_ROOTS),
            "suffixes": sorted(SOURCE_SUFFIXES),
            "special_filenames": sorted(SOURCE_FILENAMES),
            "filesystem_count": len(filesystem_paths),
            "git_count": len(git_paths),
            "filesystem_path_digest": _path_digest(filesystem_paths),
            "git_path_digest": _path_digest(git_paths),
            "derivations_agree": filesystem_paths == git_paths,
            "filesystem_only": sorted(filesystem_set - git_set),
            "git_only": sorted(git_set - filesystem_set),
            "file_type_counts": dict(
                sorted(
                    Counter(
                        Path(path).suffix.casefold() or Path(path).name for path in filesystem_paths
                    ).items()
                )
            ),
            "unreadable_count": len(unreadable),
            "unreadable": unreadable,
        },
        "target_census": {
            "filesystem_files_by_family": {
                family: list(paths) for family, paths in filesystem_hits.items()
            },
            "git_grep_files_by_family": {family: list(paths) for family, paths in git_hits.items()},
            "target_count_derivations_agree": target_counts_agree,
            "int_r5_files": len(filesystem_hits["int_r5"]),
            "pao_r4_files": len(filesystem_hits["pao_r4"]),
            "ds20_files": len(filesystem_hits["ds20"]),
            "int_r6_files": len(filesystem_hits["int_r6"]),
            "ops_r15_oracle_files": len(filesystem_hits["ops_r15_oracle"]),
            "conjunction_evaluator_files": len(conjunction_files),
            "conjunction_evaluator_paths": list(conjunction_files),
            "target_call_sites": len(filesystem_call_sites),
            "filesystem_target_call_line_sites": list(filesystem_call_sites),
            "git_target_call_line_sites": list(git_call_sites),
            "target_call_derivations_agree": filesystem_call_sites == git_call_sites,
            "target_event_or_artifact_sites": len(filesystem_event_sites),
            "filesystem_target_event_or_artifact_line_sites": list(filesystem_event_sites),
            "git_target_event_or_artifact_line_sites": list(git_event_sites),
            "target_event_derivations_agree": filesystem_event_sites == git_event_sites,
        },
        "acquisition_authority_provider_census": {
            "required_methods": ["for_job", "for_request"],
            "python_file_denominator": sum(path.endswith(".py") for path in filesystem_paths),
            "ast_provider_classes": list(ast_providers),
            "indentation_provider_classes": list(indentation_providers),
            "derivations_agree": ast_providers == indentation_providers,
            "python_parse_ambiguous_count": len(python_parse_ambiguous),
            "python_parse_ambiguous": list(python_parse_ambiguous),
            "concrete_provider_count": len(concrete_providers),
            "status": "not_established" if not concrete_providers else "observed",
        },
        "authority_chain": {
            "status": "not_established",
            "capability_label": "absent/unallocated",
            "reason": (
                "No exact INT-R5 certificate/graph or PAO-R4 crossing-receipt "
                "implementation was observed in the complete declared denominator."
            ),
            "structured_runtime_records": 0,
            "missing_required_artifacts": [
                INT_R5_CERTIFICATE,
                PAO_R4_RECEIPT,
                CONJUNCTION_RECEIPT,
            ],
            "bounded_limitation": (
                "The named-model census does not promote semantically similar code under unrelated "
                "names into the INT-R5 contract; such a candidate requires owner adjudication."
            ),
        },
    }


def authority_artifacts(root: Path) -> dict[str, dict[str, object]]:
    """Read every CAS manifest below ``root`` and bind it to its payload when JSON."""

    artifacts: dict[str, dict[str, object]] = {}
    for manifest_path in sorted(root.rglob("*.manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AuthorityArtifactDeltaError(
                "authority_manifest_ambiguous",
                f"{manifest_path.as_posix()}:{type(exc).__name__}",
            ) from exc
        if not isinstance(manifest, dict):
            raise AuthorityArtifactDeltaError(
                "authority_manifest_ambiguous", manifest_path.as_posix()
            )
        artifact_id = manifest.get("artifact_id")
        kind = manifest.get("kind")
        if not isinstance(artifact_id, str) or not isinstance(kind, str):
            raise AuthorityArtifactDeltaError(
                "authority_manifest_ambiguous", manifest_path.as_posix()
            )
        blob_name = manifest_path.name.removesuffix(".manifest.json") + ".blob"
        blob_path = manifest_path.with_name(blob_name)
        payload: object | None = None
        try:
            payload = json.loads(blob_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AuthorityArtifactDeltaError(
                "authority_payload_ambiguous",
                f"{blob_path.as_posix()}:{type(exc).__name__}",
            ) from exc
        artifacts[artifact_id] = {
            "kind": kind,
            "schema": manifest.get("schema"),
            "payload": payload,
            "manifest_path": manifest_path.as_posix(),
        }
    return artifacts


def assert_single_authority_delta(
    before: Mapping[str, Mapping[str, object]],
    after: Mapping[str, Mapping[str, object]],
    *,
    expected_ref: str,
    expected_kind: str,
) -> dict[str, object]:
    """Require one decision plus its three content-bound custody companions.

    The check is semantic rather than name-only: every allowed companion must
    point back to the exact decision ref.  A neutral-kind extra artifact is
    therefore rejected even when it avoids certificate-like vocabulary.
    """

    new_refs = sorted(set(after) - set(before))
    if expected_ref not in new_refs:
        raise AuthorityArtifactDeltaError(
            "unexpected_authority_artifact_delta",
            f"expected decision {expected_ref!r}; observed={new_refs!r}",
        )
    observed_kind = after[expected_ref].get("kind")
    if observed_kind != expected_kind:
        raise AuthorityArtifactDeltaError(
            "canonical_authority_decision_kind_mismatch",
            f"expected={expected_kind!r}; observed={observed_kind!r}",
        )
    companions = [after[ref] for ref in new_refs if ref != expected_ref]
    companion_kinds = Counter(str(companion.get("kind")) for companion in companions)
    expected_companion_kinds = Counter(
        {
            "runtime_quality.evidence_authority_envelope": 1,
            "runtime_quality.diagnostic_event": 1,
            "runtime_quality.trust_boundary_attestation": 1,
        }
    )
    if companion_kinds != expected_companion_kinds or any(
        not _companion_binds_decision(
            companion,
            expected_ref=expected_ref,
            expected_kind=expected_kind,
        )
        for companion in companions
    ):
        raise AuthorityArtifactDeltaError(
            "unexpected_authority_artifact_delta",
            f"companion_kinds={dict(companion_kinds)!r}; refs={new_refs!r}",
        )
    return {
        "new_artifact_count": 1,
        "new_artifact_refs": new_refs,
        "canonical_decision_kind": observed_kind,
        "custody_companion_count": len(companions),
        "duplicate_competence_certificate_count": 0,
    }


def _companion_binds_decision(
    artifact: Mapping[str, object],
    *,
    expected_ref: str,
    expected_kind: str,
) -> bool:
    payload = artifact.get("payload")
    if not isinstance(payload, dict):
        return False
    kind = artifact.get("kind")
    if kind == "runtime_quality.evidence_authority_envelope":
        return (
            payload.get("artifact_ref") == expected_ref
            and payload.get("cas_ref") == expected_ref
            and payload.get("artifact_kind") == expected_kind
        )
    if kind == "runtime_quality.diagnostic_event":
        return payload.get("payload_ref") == expected_ref and payload.get("artifact_refs") == [
            expected_ref
        ]
    if kind == "runtime_quality.trust_boundary_attestation":
        materials = payload.get("expected_materials")
        products = payload.get("expected_products")
        if not isinstance(materials, list) or not isinstance(products, list):
            return False
        material_refs = {row.get("ref") for row in materials if isinstance(row, dict)}
        product_refs = {row.get("ref") for row in products if isinstance(row, dict)}
        return expected_ref in material_refs and expected_ref in product_refs
    return False


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_root", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run the current-tree census and print canonical JSON."""

    args = _parse_args()
    report = census_repository(args.repo_root)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))  # noqa: T201
    denominator = report["denominator"]
    target = report["target_census"]
    provider = report["acquisition_authority_provider_census"]
    return (
        0
        if (
            denominator["derivations_agree"]
            and denominator["unreadable_count"] == 0
            and target["target_count_derivations_agree"]
            and target["target_call_derivations_agree"]
            and target["target_event_derivations_agree"]
            and provider["derivations_agree"]
            and provider["python_parse_ambiguous_count"] == 0
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
