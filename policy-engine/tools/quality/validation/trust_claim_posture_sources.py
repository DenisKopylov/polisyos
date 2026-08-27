"""Canonical filesystem and AST producer for DS11 trust-claim posture sources."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

from polisyos.scientist.evidence.claims.posture import (
    AdmittedSourceMember,
    ClaimSourceBinding,
    EstablishmentClass,
    LiteralSite,
    OwnerBinding,
    ProducerPostureMetadata,
    ReconciledSourceDerivation,
    SourceClaimState,
    SourceCoordinate,
    SourceDerivation,
    SourceDerivationReceipt,
    SourceInventoryRole,
    SourceInventoryRow,
    SourceResolution,
    SupportPredicate,
)

_AUTHORITY_FIELD = "authoritative_for"
_DENIED_FIELD = "may_not_use_for"
_PRODUCER_METADATA_FIELD = "trust_claim_posture"
_FIELD_NAMES = frozenset({_AUTHORITY_FIELD, _DENIED_FIELD})
_SEMANTIC_METHODS = frozenset(
    {
        "intersection",
        "intersection_update",
        "isdisjoint",
        "issubset",
        "issuperset",
        "difference",
        "difference_update",
    }
)


def walk_source_files(repo_root: Path) -> tuple[AdmittedSourceMember, ...]:
    """Walk every Python file below ``repo_root/src`` without Git or clock input."""
    root = repo_root.resolve()
    source_root = (root / "src").resolve()
    if not source_root.is_dir() or not source_root.is_relative_to(root):
        raise ValueError("repo_root/src must be a contained directory")
    members: list[AdmittedSourceMember] = []
    for path in sorted(source_root.rglob("*.py"), key=lambda item: item.as_posix()):
        resolved = path.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(source_root):
            continue
        if "__pycache__" in resolved.parts:
            continue
        raw = resolved.read_bytes()
        raw.decode("utf-8")
        members.append(
            AdmittedSourceMember(
                path=resolved.relative_to(root).as_posix(),
                content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
            )
        )
    return tuple(members)


def derive_ast_sources(repo_root: Path) -> SourceDerivation:
    """Derive the complete raw/exact/role/literal inventory with Python AST."""
    root = repo_root.resolve()
    members = walk_source_files(root)
    rows: list[SourceInventoryRow] = []
    denied_raw_members: list[AdmittedSourceMember] = []
    denied_only_sites: list[LiteralSite] = []
    for member in members:
        path = root / member.path
        raw = path.read_bytes()
        if _DENIED_FIELD.encode() in raw:
            denied_raw_members.append(member)
        if _AUTHORITY_FIELD.encode() not in raw:
            if _DENIED_FIELD.encode() in raw:
                denied_only_sites.extend(_derive_ast_denied_sites(member, raw))
            continue
        rows.append(_derive_ast_row(member, raw))
    ordered = tuple(sorted(rows, key=lambda row: row.path))
    receipt = _build_receipt(
        method="ast",
        scanned_python_count=len(members),
        rows=ordered,
        denied_raw_members=denied_raw_members,
        denied_only_sites=denied_only_sites,
    )
    return SourceDerivation(admitted_sources=members, rows=ordered, receipt=receipt)


def compile_source_claim_bindings(
    derivation: ReconciledSourceDerivation,
    *,
    package_owners: Mapping[str, OwnerBinding],
) -> tuple[ClaimSourceBinding, ...]:
    """Compile reconciled source facts into blocked-until-proven claim bindings."""
    bindings: list[ClaimSourceBinding] = []
    identity_ref = "docs/system-design-decisions/policyos-identity-and-custody-boundary.md"
    for row in derivation.rows:
        owner = _owner_for_path(row.path, package_owners)
        if row.resolution == SourceResolution.AMBIGUOUS:
            coordinates = (
                row.declaration_coordinates or row.carrier_coordinates or row.consumer_coordinates
            )
            if coordinates:
                bindings.append(_unresolved_binding(row, coordinates[0], owner))
            continue
        denied = tuple(sorted({value for site in row.forbidden_sites for value in site.values}))
        metadata_by_key = {
            (item.source_symbol, item.subject): item for item in row.producer_metadata
        }
        emitted = False
        for site in row.authoritative_sites:
            if site.resolution == SourceResolution.RESOLVED:
                for subject in site.values:
                    emitted = True
                    metadata = metadata_by_key.get((site.coordinate.symbol, subject))
                    if metadata is None:
                        predicates = _unestablished_predicates(owner)
                        source_state = SourceClaimState.NOT_ESTABLISHED
                        binding_owner = owner
                        limitations = ("Missing independent claim metadata",)
                        prerequisites: tuple[str, ...] = ()
                        closure_signal = None
                    else:
                        binding_owner = OwnerBinding(
                            owner=metadata.owner,
                            basis="closure_commitment",
                            source_ref=row.path,
                            establishment_class=EstablishmentClass.RECOMPUTED,
                        )
                        predicates = _planned_predicates(binding_owner)
                        source_state = SourceClaimState(metadata.source_state)
                        limitations = tuple(
                            dict.fromkeys(
                                (
                                    "Producer metadata authorizes planning only; "
                                    "support evidence is absent.",
                                    *metadata.limitation_refs,
                                )
                            )
                        )
                        prerequisites = metadata.prerequisite_refs
                        closure_signal = metadata.closure_signal
                    bindings.append(
                        ClaimSourceBinding(
                            coordinate=site.coordinate,
                            content_digest=row.content_digest,
                            resolution=SourceResolution.RESOLVED,
                            source_state=source_state,
                            subject=subject,
                            family="methodology",
                            authoritative_for=(subject,),
                            may_not_use_for=denied,
                            authority_purpose=subject,
                            owner=binding_owner,
                            jurisdiction=None,
                            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
                            review_on=None,
                            review_due=None,
                            source_as_of=None,
                            evidence_refs=(),
                            evidence_bindings=(),
                            limitation_refs=limitations,
                            prerequisite_refs=prerequisites,
                            identity_boundary_ref=identity_ref,
                            declared_scope_assumption=None,
                            supersedes_ref=None,
                            superseded_by_ref=None,
                            predicates=predicates,
                            closure_signal=closure_signal,
                        )
                    )
            else:
                bindings.append(_unresolved_binding(row, site.coordinate, owner))
                emitted = True
        if not emitted and row.resolution in {
            SourceResolution.RUNTIME_BOUND,
            SourceResolution.AMBIGUOUS,
        }:
            coordinates = (
                row.declaration_coordinates or row.carrier_coordinates or row.consumer_coordinates
            )
            if coordinates:
                bindings.append(_unresolved_binding(row, coordinates[0], owner))
    return tuple(
        sorted(
            bindings,
            key=lambda item: (
                item.coordinate.path,
                item.coordinate.line,
                item.coordinate.column,
                item.subject or "",
            ),
        )
    )


def compile_source_adapter(payload: Mapping[str, object]) -> tuple[ClaimSourceBinding, ...]:
    """Reject unregistered adapter schemas, especially the per-run runtime registry."""
    schema = str(payload.get("schema_version") or "")
    if schema == "policyos.runtime.claim_registry.v1":
        raise ValueError("RuntimeClaimRegistry is per-run and unsupported as a posture adapter")
    raise ValueError(f"unsupported posture source adapter schema: {schema or '<missing>'}")


def _derive_ast_row(member: AdmittedSourceMember, raw: bytes) -> SourceInventoryRow:
    text = raw.decode("utf-8")
    try:
        tree = ast.parse(text, filename=member.path)
    except SyntaxError as exc:
        coordinate = SourceCoordinate(
            path=member.path,
            symbol=None,
            line=max(exc.lineno or 1, 1),
            column=max(exc.offset or 1, 1) - 1,
            field_name=_AUTHORITY_FIELD,
            use_kind="carrier",
        )
        return SourceInventoryRow(
            path=member.path,
            content_digest=member.content_digest,
            role=SourceInventoryRole.AMBIGUOUS,
            resolution=SourceResolution.AMBIGUOUS,
            declaration_coordinates=(),
            carrier_coordinates=(coordinate,),
            consumer_coordinates=(),
            authoritative_sites=(),
            forbidden_sites=(),
            runtime_bound=True,
            issue_codes=("DS11-SOURCE-DERIVATION-DISAGREEMENT",),
        )
    parent: dict[ast.AST, ast.AST] = {}
    symbol: dict[ast.AST, str | None] = {}

    def bind(node: ast.AST, current: str | None) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            current = node.name
        symbol[node] = current
        for child in ast.iter_child_nodes(node):
            parent[child] = node
            bind(child, current)

    bind(tree, None)
    producer_metadata = _derive_ast_producer_metadata(tree, symbol)
    semantic_field_nodes = _semantic_authority_field_nodes(tree, parent)
    declarations: list[SourceCoordinate] = []
    carriers: list[SourceCoordinate] = []
    consumers: list[SourceCoordinate] = []
    authority_sites: list[LiteralSite] = []
    forbidden_sites: list[LiteralSite] = []
    exact_seen = False

    def coordinate(
        node: ast.AST,
        field_name: Literal["authoritative_for", "may_not_use_for"],
        use_kind: Literal["declaration", "carrier", "consumer", "collision"],
    ) -> SourceCoordinate:
        return SourceCoordinate(
            path=member.path,
            symbol=symbol.get(node),
            line=max(getattr(node, "lineno", 1), 1),
            column=max(getattr(node, "col_offset", 0), 0),
            field_name=field_name,
            use_kind=use_kind,
        )

    for node in ast.walk(tree):
        field_name = _exact_field_name(node)
        if field_name is None:
            continue
        exact_seen = exact_seen or field_name == _AUTHORITY_FIELD
        declaration_value = _declaration_value(node, parent, field_name=field_name)
        if declaration_value is not _NO_DECLARATION:
            coord = coordinate(node, field_name, "declaration")
            declarations.append(coord)
            site = _literal_site(
                coord,
                declaration_value,
                declaration_form=_ast_declaration_form(node, parent),
            )
            (authority_sites if field_name == _AUTHORITY_FIELD else forbidden_sites).append(site)
            continue
        if field_name != _AUTHORITY_FIELD:
            continue
        if node in semantic_field_nodes:
            consumers.append(coordinate(node, field_name, "consumer"))
        else:
            carriers.append(coordinate(node, field_name, "carrier"))
    declarations = _dedupe_coordinates(declarations)
    carriers = _dedupe_coordinates(carriers)
    consumers = _dedupe_coordinates(consumers)
    authority_sites = _dedupe_sites(authority_sites)
    forbidden_sites = _dedupe_sites(forbidden_sites)
    _validate_producer_metadata_bindings(producer_metadata, authority_sites)
    if not exact_seen:
        line = next(
            (
                index
                for index, value in enumerate(text.splitlines(), 1)
                if _AUTHORITY_FIELD in value
            ),
            1,
        )
        collision = SourceCoordinate(
            path=member.path,
            symbol=None,
            line=line,
            column=max(text.splitlines()[line - 1].find(_AUTHORITY_FIELD), 0),
            field_name=_AUTHORITY_FIELD,
            use_kind="collision",
        )
        return SourceInventoryRow(
            path=member.path,
            content_digest=member.content_digest,
            role=SourceInventoryRole.SUBSTRING_COLLISION,
            resolution=SourceResolution.COLLISION,
            declaration_coordinates=(),
            carrier_coordinates=(collision,),
            consumer_coordinates=(),
            authoritative_sites=(),
            forbidden_sites=tuple(forbidden_sites),
            runtime_bound=False,
            issue_codes=("DS11-SOURCE-COLLISION",),
        )
    has_consumer = bool(consumers)
    if has_consumer and not any(item.field_name == _AUTHORITY_FIELD for item in declarations):
        validated_required_fields = [
            item
            for item in carriers
            if item.field_name == _AUTHORITY_FIELD
            and _is_required_annotated_field(tree, item.line, item.column)
        ]
        if validated_required_fields:
            promoted = validated_required_fields[0]
            carriers.remove(promoted)
            declarations.append(promoted.model_copy(update={"use_kind": "declaration"}))
            declarations = _dedupe_coordinates(declarations)
    has_declaration = any(item.field_name == _AUTHORITY_FIELD for item in declarations)
    role = (
        SourceInventoryRole.DECLARES_AND_CONSUMES
        if has_declaration and has_consumer
        else SourceInventoryRole.DECLARES_ONLY
        if has_declaration
        else SourceInventoryRole.CONSUMES_ONLY
        if has_consumer
        else SourceInventoryRole.CARRIES_ONLY
    )
    runtime_bound = any(
        site.resolution == SourceResolution.RUNTIME_BOUND for site in authority_sites
    )
    return SourceInventoryRow(
        path=member.path,
        content_digest=member.content_digest,
        role=role,
        resolution=SourceResolution.RUNTIME_BOUND if runtime_bound else SourceResolution.RESOLVED,
        declaration_coordinates=tuple(declarations),
        carrier_coordinates=tuple(carriers),
        consumer_coordinates=tuple(consumers),
        authoritative_sites=tuple(authority_sites),
        forbidden_sites=tuple(forbidden_sites),
        producer_metadata=producer_metadata,
        runtime_bound=runtime_bound,
        issue_codes=("DS11-SOURCE-RUNTIME-BOUND",) if runtime_bound else (),
    )


_NO_DECLARATION = object()


def _derive_ast_producer_metadata(
    tree: ast.AST,
    symbols: Mapping[ast.AST, str | None],
) -> tuple[ProducerPostureMetadata, ...]:
    """Derive strict literal producer metadata without accepting runtime objects."""
    declarations: list[ProducerPostureMetadata] = []
    seen_names = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == _PRODUCER_METADATA_FIELD
    ]
    admitted_targets: set[ast.Name] = set()
    for node in ast.walk(tree):
        target: ast.Name | None = None
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            candidate = node.targets[0]
            if isinstance(candidate, ast.Name) and candidate.id == _PRODUCER_METADATA_FIELD:
                target, value = candidate, node.value
        elif isinstance(node, ast.AnnAssign):
            candidate = node.target
            if (
                isinstance(candidate, ast.Name)
                and candidate.id == _PRODUCER_METADATA_FIELD
                and node.value is not None
            ):
                target, value = candidate, node.value
        if target is None or value is None:
            continue
        admitted_targets.add(target)
        try:
            decoded = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
            raise ValueError("DS11-PRODUCER-METADATA: metadata must be a literal mapping") from exc
        if not isinstance(decoded, dict):
            raise ValueError("DS11-PRODUCER-METADATA: metadata must be a literal mapping")
        try:
            declarations.append(
                ProducerPostureMetadata.model_validate(
                    {
                        **decoded,
                        "source_symbol": symbols.get(target),
                        "line": target.lineno,
                        "column": target.col_offset,
                    }
                )
            )
        except ValueError as exc:
            raise ValueError(f"DS11-PRODUCER-METADATA: {exc}") from exc
    if any(node not in admitted_targets for node in seen_names):
        raise ValueError("DS11-PRODUCER-METADATA: metadata must be one direct literal assignment")
    keys = [(item.source_symbol, item.subject) for item in declarations]
    if len(keys) != len(set(keys)):
        raise ValueError("DS11-PRODUCER-METADATA: duplicate producer subject metadata")
    return tuple(
        sorted(
            declarations,
            key=lambda item: (item.source_symbol or "", item.subject, item.line, item.column),
        )
    )


def _validate_producer_metadata_bindings(
    metadata: Sequence[ProducerPostureMetadata],
    authority_sites: Sequence[LiteralSite],
) -> None:
    declared = {
        (site.coordinate.symbol, subject)
        for site in authority_sites
        if site.resolution == SourceResolution.RESOLVED
        for subject in site.values
    }
    unmatched = [item for item in metadata if (item.source_symbol, item.subject) not in declared]
    if unmatched:
        rendered = ", ".join(
            f"{item.source_symbol or '<module>'}:{item.subject}" for item in unmatched
        )
        raise ValueError(
            "DS11-PRODUCER-METADATA: subject must match authoritative_for in the same symbol: "
            + rendered
        )


def _exact_field_name(node: ast.AST) -> Literal["authoritative_for", "may_not_use_for"] | None:
    if isinstance(node, ast.Name) and node.id in _FIELD_NAMES:
        return node.id  # type: ignore[return-value]
    if isinstance(node, ast.Attribute) and node.attr in _FIELD_NAMES:
        return node.attr  # type: ignore[return-value]
    if isinstance(node, ast.keyword) and node.arg in _FIELD_NAMES:
        return node.arg  # type: ignore[return-value]
    if isinstance(node, ast.Constant) and node.value in _FIELD_NAMES:
        return node.value  # type: ignore[return-value]
    if isinstance(node, ast.arg) and node.arg in _FIELD_NAMES:
        return node.arg  # type: ignore[return-value]
    return None


def _declaration_value(
    node: ast.AST,
    parent: Mapping[ast.AST, ast.AST],
    *,
    field_name: Literal["authoritative_for", "may_not_use_for"],
) -> object:
    direct_parent = parent.get(node)
    if isinstance(node, ast.keyword):
        return _NO_DECLARATION if _value_copies_field(node.value, field_name) else node.value
    if isinstance(node, ast.Constant) and isinstance(direct_parent, ast.Dict):
        index = direct_parent.keys.index(node)
        value = direct_parent.values[index]
        return _NO_DECLARATION if _value_copies_field(value, field_name) else value
    if isinstance(node, (ast.Name, ast.Attribute)):
        if isinstance(direct_parent, (ast.Assign, ast.AnnAssign)):
            target = (
                direct_parent.target
                if isinstance(direct_parent, ast.AnnAssign)
                else direct_parent.targets
            )
            targets = target if isinstance(target, list) else [target]
            if any(_contains_node(item, node) for item in targets):
                value = direct_parent.value
                if value is None or _value_copies_field(value, field_name):
                    return _NO_DECLARATION
                return value
    return _NO_DECLARATION


def _ast_declaration_form(
    node: ast.AST, parent: Mapping[ast.AST, ast.AST]
) -> Literal["assignment", "keyword", "dict_key"]:
    if isinstance(node, ast.keyword):
        return "keyword"
    if isinstance(node, ast.Constant) and isinstance(parent.get(node), ast.Dict):
        return "dict_key"
    return "assignment"


def _value_copies_field(value: ast.AST, field_name: str) -> bool:
    return any(_exact_field_name(item) == field_name for item in ast.walk(value))


def _contains_node(root: ast.AST, needle: ast.AST) -> bool:
    return any(item is needle for item in ast.walk(root))


def _is_assignment_target(node: ast.AST, parent: Mapping[ast.AST, ast.AST]) -> bool:
    direct_parent = parent.get(node)
    if not isinstance(direct_parent, (ast.Assign, ast.AnnAssign)):
        return False
    target = (
        direct_parent.target if isinstance(direct_parent, ast.AnnAssign) else direct_parent.targets
    )
    targets = target if isinstance(target, list) else [target]
    return any(_contains_node(item, node) for item in targets)


def _is_direct_semantic_consumer(node: ast.AST, parent: Mapping[ast.AST, ast.AST]) -> bool:
    current = parent.get(node)
    while current is not None:
        if isinstance(current, (ast.Compare, ast.IfExp, ast.BoolOp)):
            return True
        if isinstance(current, ast.BinOp) and isinstance(
            current.op, (ast.BitAnd, ast.BitOr, ast.Sub)
        ):
            return True
        if isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.Not):
            return True
        if isinstance(current, ast.comprehension) and any(
            _contains_node(condition, node) for condition in current.ifs
        ):
            return True
        if isinstance(current, (ast.Assert, ast.If, ast.While)):
            test = current.test
            return _contains_node(test, node)
        if isinstance(current, ast.Call):
            function = current.func
            if isinstance(function, ast.Attribute) and function.attr in _SEMANTIC_METHODS:
                return True
        if isinstance(
            current,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
                ast.Return,
                ast.Expr,
                ast.keyword,
                ast.Dict,
                ast.For,
                ast.AsyncFor,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            return False
        current = parent.get(current)
    return False


def _semantic_authority_field_nodes(
    tree: ast.AST, parent: Mapping[ast.AST, ast.AST]
) -> set[ast.AST]:
    """Return exact field nodes that directly or locally-alias a decision."""
    exact_nodes = {node for node in ast.walk(tree) if _exact_field_name(node) == _AUTHORITY_FIELD}
    semantic = {node for node in exact_nodes if _is_direct_semantic_consumer(node, parent)}
    scopes: list[ast.AST] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    )
    for scope in scopes:
        nodes = _nodes_in_scope(scope)
        sources: dict[str, set[ast.AST]] = {}
        dependencies: dict[str, set[str]] = {}
        for statement in nodes:
            value: ast.AST | None = None
            targets: list[ast.AST] = []
            if isinstance(statement, ast.Assign):
                value = statement.value
                targets = list(statement.targets)
            elif isinstance(statement, ast.NamedExpr) or (
                isinstance(statement, ast.AnnAssign) and statement.value is not None
            ):
                value = statement.value
                targets = [statement.target]
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                value = statement.iter
                targets = [statement.target]
            if value is None:
                continue
            target_names = {
                item.id
                for target in targets
                for item in ast.walk(target)
                if isinstance(item, ast.Name)
            }
            if not target_names:
                continue
            field_sources = {item for item in ast.walk(value) if item in exact_nodes}
            value_names = {
                item.id
                for item in ast.walk(value)
                if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)
            }
            for target_name in target_names:
                sources.setdefault(target_name, set()).update(field_sources)
                dependencies.setdefault(target_name, set()).update(value_names)
        changed = True
        while changed:
            changed = False
            for target_name, names in dependencies.items():
                before = len(sources.setdefault(target_name, set()))
                for name in names:
                    sources[target_name].update(sources.get(name, set()))
                changed = changed or len(sources[target_name]) != before
        for node in nodes:
            if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                continue
            if _is_direct_semantic_consumer(node, parent):
                semantic.update(
                    source
                    for source in sources.get(node.id, set())
                    if getattr(source, "lineno", 0) <= node.lineno
                )
    return semantic


def _nodes_in_scope(scope: ast.AST) -> tuple[ast.AST, ...]:
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    values: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        if node is not scope and isinstance(node, nested):
            return
        values.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(scope)
    return tuple(values)


def _is_required_annotated_field(tree: ast.AST, line: int, column: int) -> bool:
    return any(
        isinstance(node, ast.AnnAssign)
        and node.value is None
        and isinstance(node.target, ast.Name)
        and node.target.id == _AUTHORITY_FIELD
        and node.target.lineno == line
        and node.target.col_offset == column
        for node in ast.walk(tree)
    )


def _literal_site(
    coordinate: SourceCoordinate,
    value: object,
    *,
    declaration_form: Literal["assignment", "keyword", "dict_key"],
) -> LiteralSite:
    wrapper: Literal["direct", "field_default", "literal_lambda_factory", "dynamic"]
    candidate = value
    wrapper = "direct"
    if isinstance(value, ast.Call) and _call_name(value.func) == "Field":
        default = next((item.value for item in value.keywords if item.arg == "default"), None)
        factory = next(
            (item.value for item in value.keywords if item.arg == "default_factory"), None
        )
        if default is not None:
            wrapper = "field_default"
            candidate = default
        elif isinstance(factory, ast.Lambda):
            wrapper = "literal_lambda_factory"
            candidate = factory.body
        else:
            wrapper = "dynamic"
    values = _literal_values(candidate)
    if values is None:
        wrapper = "dynamic"
        values = ()
        resolution = SourceResolution.RUNTIME_BOUND
    else:
        resolution = SourceResolution.RESOLVED
    return LiteralSite(
        coordinate=coordinate,
        declaration_form=declaration_form,
        wrapper_kind=wrapper,
        values=values,
        resolution=resolution,
    )


def _literal_values(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (ast.Tuple, ast.List, ast.Set)):
        return None
    strings: list[str] = []
    for item in value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return None
        strings.append(item.value)
    return tuple(sorted(strings)) if isinstance(value, ast.Set) else tuple(strings)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _build_receipt(
    *,
    method: Literal["ast", "tokenize"],
    scanned_python_count: int,
    rows: Sequence[SourceInventoryRow],
    denied_raw_members: Sequence[AdmittedSourceMember],
    denied_only_sites: Sequence[LiteralSite] = (),
) -> SourceDerivationReceipt:
    role_counts = {role: sum(row.role == role for row in rows) for role in SourceInventoryRole}
    exact_rows = [
        row
        for row in rows
        if row.role not in {SourceInventoryRole.SUBSTRING_COLLISION, SourceInventoryRole.AMBIGUOUS}
    ]
    direct_sites = [
        site
        for row in rows
        for site in row.authoritative_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind == "direct"
        and site.resolution == SourceResolution.RESOLVED
    ]
    wrapper_sites = [
        site
        for row in rows
        for site in row.authoritative_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    ]
    denied_sites = [
        site
        for row in rows
        for site in row.forbidden_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    ]
    denied_sites.extend(
        site
        for site in denied_only_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    )
    row_payload = [row.model_dump(mode="json") for row in rows]
    row_digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                row_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    return SourceDerivationReceipt(
        method=method,
        scanned_python_count=scanned_python_count,
        raw_candidate_count=len(rows),
        exact_field_file_count=len(exact_rows),
        declaring_file_count=sum(
            row.role
            in {SourceInventoryRole.DECLARES_ONLY, SourceInventoryRole.DECLARES_AND_CONSUMES}
            for row in rows
        ),
        consuming_file_count=sum(
            row.role
            in {SourceInventoryRole.CONSUMES_ONLY, SourceInventoryRole.DECLARES_AND_CONSUMES}
            for row in rows
        ),
        role_counts=role_counts,
        direct_literal_site_count=len(direct_sites),
        direct_literal_file_count=len({site.coordinate.path for site in direct_sites}),
        direct_literal_subject_count=len({value for site in direct_sites for value in site.values}),
        direct_empty_site_count=sum(not site.values for site in direct_sites),
        wrapper_literal_site_count=len(wrapper_sites),
        wrapper_literal_file_count=len({site.coordinate.path for site in wrapper_sites}),
        wrapper_literal_subject_count=len(
            {value for site in wrapper_sites for value in site.values}
        ),
        may_not_use_for_raw_file_count=len(denied_raw_members),
        may_not_use_for_literal_site_count=len(denied_sites),
        may_not_use_for_literal_file_count=len({site.coordinate.path for site in denied_sites}),
        may_not_use_for_literal_subject_count=len(
            {value for site in denied_sites for value in site.values}
        ),
        may_not_use_for_raw_members=tuple(denied_raw_members),
        may_not_use_for_sites=tuple(denied_sites),
        row_digest=row_digest,
    )


def _derive_ast_denied_sites(member: AdmittedSourceMember, raw: bytes) -> tuple[LiteralSite, ...]:
    tree = ast.parse(raw.decode("utf-8"), filename=member.path)
    parent: dict[ast.AST, ast.AST] = {}
    symbol: dict[ast.AST, str | None] = {}

    def bind(node: ast.AST, current: str | None) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            current = node.name
        symbol[node] = current
        for child in ast.iter_child_nodes(node):
            parent[child] = node
            bind(child, current)

    bind(tree, None)
    sites: list[LiteralSite] = []
    for node in ast.walk(tree):
        if _exact_field_name(node) != _DENIED_FIELD or not _is_assignment_target(node, parent):
            continue
        value = _declaration_value(node, parent, field_name=_DENIED_FIELD)
        if value is _NO_DECLARATION:
            continue
        coordinate = SourceCoordinate(
            path=member.path,
            symbol=symbol.get(node),
            line=max(getattr(node, "lineno", 1), 1),
            column=max(getattr(node, "col_offset", 0), 0),
            field_name=_DENIED_FIELD,
            use_kind="declaration",
        )
        sites.append(_literal_site(coordinate, value, declaration_form="assignment"))
    return tuple(_dedupe_sites(sites))


def _owner_for_path(path: str, owners: Mapping[str, OwnerBinding]) -> OwnerBinding:
    matches = [(prefix, owner) for prefix, owner in owners.items() if path.startswith(prefix)]
    if matches:
        return max(matches, key=lambda item: len(item[0]))[1]
    return OwnerBinding(
        owner=None,
        basis="not_established",
        source_ref=None,
        establishment_class=EstablishmentClass.NOT_ESTABLISHED,
    )


def _unestablished_predicates(owner: OwnerBinding) -> tuple[SupportPredicate, ...]:
    values: list[SupportPredicate] = []
    for kind in (
        "content_bound_source",
        "purpose_permission",
        "identity_boundary",
        "no_blocker",
    ):
        values.append(
            SupportPredicate(
                kind=kind,
                satisfied=True,
                establishment_class=EstablishmentClass.RECOMPUTED,
                evidence_refs=(),
                issue_code=None,
            )
        )
    values.extend(
        (
            SupportPredicate(
                kind="accountable_owner",
                satisfied=owner.owner is not None,
                establishment_class=owner.establishment_class,
                evidence_refs=(owner.source_ref,) if owner.source_ref else (),
                issue_code="DS11-OWNER-NOT-ESTABLISHED",
            ),
            SupportPredicate(
                kind="applicable_jurisdiction",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-JURISDICTION-NOT-ESTABLISHED",
            ),
            SupportPredicate(
                kind="current_review",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-REVIEW-MISSING",
            ),
            SupportPredicate(
                kind="content_bound_evidence",
                satisfied=False,
                establishment_class=EstablishmentClass.NOT_ESTABLISHED,
                evidence_refs=(),
                issue_code="DS11-GATE-PREDICATE-NOT-ESTABLISHED",
            ),
        )
    )
    return tuple(sorted(values, key=lambda item: item.kind))


def _planned_predicates(owner: OwnerBinding) -> tuple[SupportPredicate, ...]:
    planned = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "identity_boundary",
    }
    issues = {
        "content_bound_source": "DS11-SOURCE-CONTENT-NOT-BOUND",
        "purpose_permission": "DS11-AUTHORITY-PURPOSE-DENIED",
        "accountable_owner": "DS11-OWNER-NOT-ESTABLISHED",
        "applicable_jurisdiction": "DS11-JURISDICTION-NOT-ESTABLISHED",
        "current_review": "DS11-REVIEW-MISSING",
        "content_bound_evidence": "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
        "identity_boundary": "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
        "no_blocker": "DS11-SOURCE-BLOCKER-PRESENT",
    }
    return tuple(
        SupportPredicate(
            kind=kind,
            satisfied=kind in planned,
            establishment_class=(
                EstablishmentClass.RECOMPUTED
                if kind in planned
                else EstablishmentClass.NOT_ESTABLISHED
            ),
            evidence_refs=(owner.source_ref,)
            if kind == "accountable_owner" and owner.source_ref
            else (),
            issue_code=None if kind in planned else issue,
        )
        for kind, issue in sorted(issues.items())
    )


def _unresolved_binding(
    row: SourceInventoryRow, coordinate: SourceCoordinate, owner: OwnerBinding
) -> ClaimSourceBinding:
    return ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=row.content_digest,
        resolution=row.resolution,
        source_state=SourceClaimState.BLOCKED,
        subject=None,
        family="methodology",
        authoritative_for=(),
        may_not_use_for=tuple(
            sorted({value for site in row.forbidden_sites for value in site.values})
        ),
        authority_purpose=None,
        owner=owner,
        jurisdiction=None,
        jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
        review_on=None,
        review_due=None,
        source_as_of=None,
        evidence_refs=(),
        evidence_bindings=(),
        limitation_refs=("Unresolved source declaration",),
        prerequisite_refs=(),
        identity_boundary_ref="docs/system-design-decisions/policyos-identity-and-custody-boundary.md",
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=_unestablished_predicates(owner),
        closure_signal=None,
    )


def _dedupe_coordinates(values: Sequence[SourceCoordinate]) -> list[SourceCoordinate]:
    unique = {
        (item.path, item.line, item.column, item.field_name, item.use_kind): item for item in values
    }
    return [unique[key] for key in sorted(unique)]


def _dedupe_sites(values: Sequence[LiteralSite]) -> list[LiteralSite]:
    unique = {
        (
            item.coordinate.path,
            item.coordinate.line,
            item.coordinate.column,
            item.coordinate.field_name,
            item.declaration_form,
            item.wrapper_kind,
        ): item
        for item in values
    }
    return [unique[key] for key in sorted(unique)]
