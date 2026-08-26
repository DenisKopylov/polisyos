"""Independent tokenizer, reconciliation, and checker for DS11 claim posture."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import io
import json
import re
import sys
import tokenize
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from polisyos.scientist.evidence.claims.posture import (
    AdmittedSourceMember,
    AntiRoleBinding,
    ClaimPostureRegisterV1,
    ClaimPostureState,
    EstablishmentClass,
    IdentityBoundaryBinding,
    LiteralSite,
    ProjectionGroup,
    ReconciledSourceDerivation,
    SourceCoordinate,
    SourceDerivation,
    SourceDerivationReceipt,
    SourceInventoryRole,
    SourceInventoryRow,
    SourceResolution,
    build_posture_register,
    canonical_register_bytes,
    validate_posture_register,
)
from tools.quality.validation.trust_claim_posture_sources import (
    compile_source_claim_bindings,
    derive_ast_sources,
)

_AUTHORITY_FIELD = "authoritative_for"
_DENIED_FIELD = "may_not_use_for"
_IDENTITY_PATH = Path("docs/system-design-decisions/policyos-identity-and-custody-boundary.md")
_OUTPUT_PATH = Path("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")


@dataclass(frozen=True)
class AccessibilityEvaluation:
    """Bounded accessibility-purpose evaluation."""

    state: ClaimPostureState
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class ScopeEvaluation:
    """Fail-closed result for a declared scope assumption."""

    state: ClaimPostureState
    establishment_class: EstablishmentClass
    limitations: tuple[str, ...]


def derive_token_sources(repo_root: Path) -> SourceDerivation:
    """Independently walk and derive source facts with :mod:`tokenize` only."""
    root = repo_root.resolve()
    source_root = (root / "src").resolve()
    if not source_root.is_dir() or not source_root.is_relative_to(root):
        raise ValueError("repo_root/src must be a contained directory")
    members: list[AdmittedSourceMember] = []
    rows: list[SourceInventoryRow] = []
    denied_raw_files = 0
    denied_only_sites: list[LiteralSite] = []
    for candidate in sorted(source_root.rglob("*.py"), key=lambda item: item.as_posix()):
        path = candidate.resolve()
        if not path.is_file() or not path.is_relative_to(source_root):
            continue
        if "__pycache__" in path.parts:
            continue
        raw = path.read_bytes()
        raw.decode("utf-8")
        member = AdmittedSourceMember(
            path=path.relative_to(root).as_posix(),
            content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
        )
        members.append(member)
        if _DENIED_FIELD.encode() in raw:
            denied_raw_files += 1
        if _AUTHORITY_FIELD.encode() in raw:
            rows.append(_derive_token_row(member, raw))
        elif _DENIED_FIELD.encode() in raw:
            denied_only_sites.extend(_derive_token_row(member, raw).forbidden_sites)
    ordered_rows = tuple(sorted(rows, key=lambda row: row.path))
    return SourceDerivation(
        admitted_sources=tuple(members),
        rows=ordered_rows,
        receipt=_token_receipt(
            scanned_python_count=len(members),
            rows=ordered_rows,
            denied_raw_files=denied_raw_files,
            denied_only_sites=denied_only_sites,
        ),
    )


def reconcile_source_derivations(
    ast_result: SourceDerivation,
    token_result: SourceDerivation,
) -> ReconciledSourceDerivation:
    """Reconcile both complete walks file-for-file and preserve disagreements."""
    ast_members = {item.path: item for item in ast_result.admitted_sources}
    token_members = {item.path: item for item in token_result.admitted_sources}
    ast_rows = {row.path: row for row in ast_result.rows}
    token_rows = {row.path: row for row in token_result.rows}
    disagreements: list[str] = []
    rows: list[SourceInventoryRow] = []
    for path in sorted(set(ast_rows) | set(token_rows)):
        ast_row = ast_rows.get(path)
        token_row = token_rows.get(path)
        if ast_row is not None and token_row is not None and _rows_agree(ast_row, token_row):
            rows.append(ast_row)
            continue
        disagreements.append(path)
        available = ast_row or token_row
        if available is None:
            raise AssertionError("union path must have a derivation row")
        coordinates = tuple(
            sorted(
                {
                    *available.declaration_coordinates,
                    *available.carrier_coordinates,
                    *available.consumer_coordinates,
                    *(() if token_row is None else token_row.declaration_coordinates),
                    *(() if token_row is None else token_row.carrier_coordinates),
                    *(() if token_row is None else token_row.consumer_coordinates),
                },
                key=lambda item: (item.line, item.column, item.use_kind),
            )
        )
        rows.append(
            SourceInventoryRow(
                path=path,
                content_digest=available.content_digest,
                role=SourceInventoryRole.AMBIGUOUS,
                resolution=SourceResolution.AMBIGUOUS,
                declaration_coordinates=tuple(
                    item for item in coordinates if item.use_kind == "declaration"
                ),
                carrier_coordinates=tuple(
                    item for item in coordinates if item.use_kind in {"carrier", "collision"}
                ),
                consumer_coordinates=tuple(
                    item for item in coordinates if item.use_kind == "consumer"
                ),
                authoritative_sites=available.authoritative_sites,
                forbidden_sites=available.forbidden_sites,
                runtime_bound=True,
                issue_codes=("DS11-SOURCE-DERIVATION-DISAGREEMENT",),
            )
        )
    member_paths = set(ast_members) | set(token_members)
    for path in sorted(member_paths):
        if ast_members.get(path) != token_members.get(path):
            disagreements.append(path)
    admitted = tuple(ast_members.get(path) or token_members[path] for path in sorted(member_paths))
    return ReconciledSourceDerivation(
        admitted_sources=admitted,
        rows=tuple(rows),
        ast_receipt=ast_result.receipt,
        token_receipt=token_result.receipt,
        disagreements=tuple(sorted(set(disagreements))),
    )


def derive_identity_boundary(repo_root: Path) -> IdentityBoundaryBinding:
    """Derive and content-bind the complete ratified anti-role paragraph twice."""
    path = (repo_root.resolve() / _IDENTITY_PATH).resolve()
    if not path.is_relative_to(repo_root.resolve()) or not path.is_file():
        raise ValueError("ratified identity document is missing or outside repo_root")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body = _split_frontmatter(text)
    match = re.search(
        r"\*\*Anti-roles \(binding\):\*\*\s*(.+?)(?:\n\n|\Z)",
        body,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("binding anti-role paragraph is absent")
    paragraph = " ".join(match.group(1).split())
    role_sentence = paragraph.split(".", 1)[0] + "."
    repeated = tuple(
        item.strip().rstrip(".")
        for item in re.findall(r"\bnot (?:an? )?(.+?)(?=, not |,? or not |\.)", role_sentence)
    )
    stripped = re.sub(r"^PolicyOS is\s+", "", role_sentence)
    stripped = re.sub(r"\bnot (?:an? )?", "", stripped)
    delimited = tuple(
        part.strip().rstrip(".") for part in re.split(r",\s*|\s+or\s+", stripped) if part.strip()
    )
    if repeated != delimited:
        raise ValueError("independent anti-role normalizers disagree")
    paragraph_start = body[: match.start(1)].count("\n") + text[: text.index(body)].count("\n") + 1
    paragraph_end = paragraph_start + match.group(1).count("\n")
    source_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    paragraph_digest = "sha256:" + hashlib.sha256(match.group(1).encode("utf-8")).hexdigest()
    anti_roles = tuple(
        AntiRoleBinding(
            role=_slug(role),
            display_label=role,
            source_path=_IDENTITY_PATH.as_posix(),
            source_digest=source_digest,
            line=paragraph_start,
            column=0,
        )
        for role in repeated
    )
    method_a = (
        "sha256:"
        + hashlib.sha256(json.dumps(repeated, separators=(",", ":")).encode("utf-8")).hexdigest()
    )
    method_b = (
        "sha256:"
        + hashlib.sha256(json.dumps(delimited, separators=(",", ":")).encode("utf-8")).hexdigest()
    )
    return IdentityBoundaryBinding(
        path=_IDENTITY_PATH.as_posix(),
        content_digest=source_digest,
        frontmatter_digest="sha256:" + hashlib.sha256(frontmatter.encode("utf-8")).hexdigest(),
        paragraph_digest=paragraph_digest,
        paragraph_start_line=paragraph_start,
        paragraph_end_line=paragraph_end,
        anti_roles=anti_roles,
        derivation_receipt_digests=(method_a, method_b),
    )


def validate_claim_copy(
    copy: str,
    *,
    source_row: object | None,
) -> tuple[str, ...]:
    """Require claim-bearing copy to pass through a validated source row."""
    del copy
    if source_row is None:
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    return ()


def evaluate_accessibility_evidence(
    *,
    evidence_kind: str,
    requested_purpose: str,
    source_as_of: date,
    countersign_ref: str | None,
) -> AccessibilityEvaluation:
    """Prevent internal historical evidence from minting current certification."""
    del source_as_of
    external = requested_purpose in {
        "external_accessibility_certification",
        "current_accessibility_conformance",
    }
    if evidence_kind == "internal_pre_audit" and (external or not countersign_ref):
        return AccessibilityEvaluation(
            state=ClaimPostureState.BLOCKED,
            issue_codes=("DS11-A11Y-CERTIFICATION-NOT-EARNED",),
        )
    return AccessibilityEvaluation(state=ClaimPostureState.SUPPORTED, issue_codes=())


def evaluate_scope_assumption(
    *,
    scope_assumption: str,
    adjudication_ref: str | None,
) -> ScopeEvaluation:
    """Freeze a declared, unadjudicated scope as a visible limitation."""
    if not adjudication_ref:
        return ScopeEvaluation(
            state=ClaimPostureState.BLOCKED,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
            limitations=(f"Declared scope assumption: {scope_assumption}",),
        )
    return ScopeEvaluation(
        state=ClaimPostureState.BLOCKED,
        establishment_class=EstablishmentClass.INSTITUTIONALLY_SUPPLIED,
        limitations=(f"Institutionally supplied scope: {scope_assumption}",),
    )


def compile_claim_posture_register(
    repo_root: Path,
    *,
    register_as_of: date,
) -> tuple[ClaimPostureRegisterV1, bytes]:
    """Compile, reconcile, assemble, validate, and canonically serialize live sources."""
    root = repo_root.resolve()
    ast_result = derive_ast_sources(root)
    token_result = derive_token_sources(root)
    reconciled = reconcile_source_derivations(ast_result, token_result)
    identity = derive_identity_boundary(root)
    bindings = compile_source_claim_bindings(reconciled, package_owners={})
    identity_member = AdmittedSourceMember(
        path=identity.path,
        content_digest=identity.content_digest,
    )
    register = build_posture_register(
        register_as_of=register_as_of,
        admitted_sources=(*reconciled.admitted_sources, identity_member),
        ast_derivation=ast_result.receipt,
        token_derivation=token_result.receipt,
        identity_boundary=identity,
        source_inventory=reconciled.rows,
        source_bindings=bindings,
        projection_groups=tuple(
            ProjectionGroup(group_id=group_id, claim_ids=())
            for group_id in (
                "methodology",
                "evidence_envelope",
                "limitations",
                "accessibility",
                "custody",
            )
        ),
    )
    payload = canonical_register_bytes(register)
    validate_posture_register(payload)
    return register, payload


def write_claim_posture_register(
    register: ClaimPostureRegisterV1,
    *,
    output_root: Path,
) -> Path:
    """Write only the fixed generated target contained by ``output_root``."""
    root = output_root.resolve()
    target = (root / _OUTPUT_PATH).resolve()
    if not target.is_relative_to(root):
        raise ValueError("DS11-GENERATOR-ESCAPE: output target escapes output_root")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_register_bytes(register))
    return target


def validate_register_against_live_sources(
    payload: bytes,
    *,
    repo_root: Path,
    register_as_of: date,
) -> ClaimPostureRegisterV1:
    """Validate strict bytes and require equality with a live recompilation."""
    parsed = validate_posture_register(payload)
    live, live_bytes = compile_claim_posture_register(repo_root, register_as_of=register_as_of)
    if payload != live_bytes:
        raise ValueError("DS11-GENERATED-DRIFT")
    return live if parsed == live else parsed


def run_corruption_probe(
    kind: str,
    *,
    repo_root: Path,
    register_as_of: date,
) -> bool:
    """Require a corrupted live payload to fail strict validation."""
    register, _ = compile_claim_posture_register(repo_root, register_as_of=register_as_of)
    payload = register.model_dump(mode="json")
    if kind == "extra_field":
        payload["unexpected"] = True
    elif kind == "payload_digest":
        payload["payload_digest"] = "sha256:" + "0" * 64
    else:
        raise ValueError(f"unsupported corruption probe: {kind}")
    try:
        validate_posture_register(payload)
    except ValueError:
        return True
    return False


def _derive_token_row(member: AdmittedSourceMember, raw: bytes) -> SourceInventoryRow:
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(raw).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        line = getattr(exc, "args", (None, (1, 0)))[1][0] if len(exc.args) > 1 else 1
        coordinate = SourceCoordinate(
            path=member.path,
            symbol=None,
            line=max(int(line), 1),
            column=0,
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
    statements = _logical_statements(tokens)
    symbols = _token_symbols(tokens)
    semantic_fields = _token_semantic_field_positions(statements, symbols)
    declarations: list[SourceCoordinate] = []
    carriers: list[SourceCoordinate] = []
    consumers: list[SourceCoordinate] = []
    authoritative_sites: list[LiteralSite] = []
    forbidden_sites: list[LiteralSite] = []
    exact_authority = False
    for statement in statements:
        for index, token in enumerate(statement):
            field = _token_field(token)
            if field is None:
                continue
            exact_authority = exact_authority or field == _AUTHORITY_FIELD
            symbol = symbols.get(token.start[0])
            declaration, value_tokens = _token_declaration(statement, index)
            copies_field = value_tokens is not None and any(
                _token_field(item) == field for item in value_tokens
            )
            if declaration and not copies_field:
                coordinate = SourceCoordinate(
                    path=member.path,
                    symbol=symbol,
                    line=token.start[0],
                    column=token.start[1],
                    field_name=field,
                    use_kind="declaration",
                )
                declarations.append(coordinate)
                if value_tokens is not None and _token_is_assignment_site(statement, index):
                    site = _token_literal_site(coordinate, value_tokens)
                    (authoritative_sites if field == _AUTHORITY_FIELD else forbidden_sites).append(
                        site
                    )
            elif field == _AUTHORITY_FIELD and token.start in semantic_fields:
                consumers.append(
                    SourceCoordinate(
                        path=member.path,
                        symbol=symbol,
                        line=token.start[0],
                        column=token.start[1],
                        field_name=field,
                        use_kind="consumer",
                    )
                )
            elif field == _AUTHORITY_FIELD:
                carriers.append(
                    SourceCoordinate(
                        path=member.path,
                        symbol=symbol,
                        line=token.start[0],
                        column=token.start[1],
                        field_name=field,
                        use_kind="carrier",
                    )
                )
    declarations = _unique_coordinates(declarations)
    carriers = _unique_coordinates(carriers)
    consumers = _unique_coordinates(consumers)
    authoritative_sites = _unique_sites(authoritative_sites)
    forbidden_sites = _unique_sites(forbidden_sites)
    if not exact_authority:
        text = raw.decode("utf-8")
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
        promoted = next(
            (
                item
                for item in carriers
                if item.field_name == _AUTHORITY_FIELD
                and _token_is_required_annotation(statements, item.line, item.column)
            ),
            None,
        )
        if promoted is not None:
            carriers.remove(promoted)
            declarations.append(promoted.model_copy(update={"use_kind": "declaration"}))
            declarations = _unique_coordinates(declarations)
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
        site.resolution == SourceResolution.RUNTIME_BOUND for site in authoritative_sites
    )
    return SourceInventoryRow(
        path=member.path,
        content_digest=member.content_digest,
        role=role,
        resolution=SourceResolution.RUNTIME_BOUND if runtime_bound else SourceResolution.RESOLVED,
        declaration_coordinates=tuple(declarations),
        carrier_coordinates=tuple(carriers),
        consumer_coordinates=tuple(consumers),
        authoritative_sites=tuple(authoritative_sites),
        forbidden_sites=tuple(forbidden_sites),
        runtime_bound=runtime_bound,
        issue_codes=("DS11-SOURCE-RUNTIME-BOUND",) if runtime_bound else (),
    )


def _logical_statements(tokens: Sequence[tokenize.TokenInfo]) -> list[list[tokenize.TokenInfo]]:
    statements: list[list[tokenize.TokenInfo]] = []
    current: list[tokenize.TokenInfo] = []
    depth = 0
    for token in tokens:
        if token.type in {tokenize.ENCODING, tokenize.COMMENT, tokenize.NL}:
            continue
        if token.string in {"(", "[", "{"}:
            depth += 1
        elif token.string in {")", "]", "}"} and depth:
            depth -= 1
        if token.type in {tokenize.NEWLINE, tokenize.ENDMARKER} and depth == 0:
            if current:
                statements.append(current)
                current = []
            continue
        if token.type not in {tokenize.INDENT, tokenize.DEDENT}:
            current.append(token)
    return statements


def _token_symbols(tokens: Sequence[tokenize.TokenInfo]) -> dict[int, str | None]:
    line_symbols: dict[int, str | None] = {}
    current: str | None = None
    pending: str | None = None
    stack: list[str | None] = []
    significant = [token for token in tokens if token.type not in {tokenize.ENCODING, tokenize.NL}]
    for index, token in enumerate(significant):
        if token.string in {"class", "def"} and index + 1 < len(significant):
            pending = significant[index + 1].string
        elif token.type == tokenize.INDENT:
            stack.append(current)
            if pending:
                current = pending
                pending = None
        elif token.type == tokenize.DEDENT:
            current = stack.pop() if stack else None
        line_symbols[token.start[0]] = current or pending
    return line_symbols


def _token_field(
    token: tokenize.TokenInfo,
) -> Literal["authoritative_for", "may_not_use_for"] | None:
    if token.type == tokenize.NAME and token.string in {_AUTHORITY_FIELD, _DENIED_FIELD}:
        return token.string  # type: ignore[return-value]
    if token.type == tokenize.STRING:
        decoded = _decode_string_token(token.string)
        if decoded in {_AUTHORITY_FIELD, _DENIED_FIELD}:
            return decoded  # type: ignore[return-value]
    return None


def _token_declaration(
    statement: Sequence[tokenize.TokenInfo], index: int
) -> tuple[bool, Sequence[tokenize.TokenInfo] | None]:
    depths: list[int] = []
    depth = 0
    for item in statement:
        depths.append(depth)
        if item.string in {"(", "[", "{"}:
            depth += 1
        elif item.string in {")", "]", "}"} and depth:
            depth -= 1
    target_depth = depths[index]
    following = index + 1
    if following < len(statement) and statement[following].string == "=":
        return True, _token_value_span(statement, following + 1, target_depth, depths)
    if following < len(statement) and statement[following].string == ":":
        if statement[index].type == tokenize.STRING:
            return True, _token_value_span(statement, following + 1, target_depth, depths)
        assignment = next(
            (
                position
                for position in range(following + 1, len(statement))
                if statement[position].string == "=" and depths[position] == target_depth
            ),
            None,
        )
        if assignment is not None:
            return True, _token_value_span(statement, assignment + 1, target_depth, depths)
    return False, None


def _token_value_span(
    statement: Sequence[tokenize.TokenInfo],
    start: int,
    target_depth: int,
    depths: Sequence[int],
) -> Sequence[tokenize.TokenInfo]:
    end = len(statement)
    if target_depth:
        end = next(
            (
                position
                for position in range(start, len(statement))
                if depths[position] == target_depth
                and statement[position].string in {",", ")", "]", "}"}
            ),
            len(statement),
        )
    return statement[start:end]


def _token_is_assignment_site(statement: Sequence[tokenize.TokenInfo], index: int) -> bool:
    depth = 0
    for position, item in enumerate(statement):
        if position == index:
            return depth == 0
        if item.string in {"(", "[", "{"}:
            depth += 1
        elif (
            item.string
            in {
                ")",
                "]",
                "}",
            }
            and depth
        ):
            depth -= 1
    return False


def _token_semantic_field_positions(
    statements: Sequence[Sequence[tokenize.TokenInfo]],
    symbols: Mapping[int, str | None],
) -> set[tuple[int, int]]:
    """Derive direct and bounded local-alias decisions without AST input."""
    semantic: set[tuple[int, int]] = set()
    sources: dict[tuple[str | None, str], set[tuple[int, int]]] = {}
    dependencies: dict[tuple[str | None, str], set[tuple[str | None, str]]] = {}
    for statement in statements:
        depths = _token_depths(statement)
        assignment = next(
            (
                index
                for index, item in enumerate(statement)
                if item.string == "=" and depths[index] == 0
            ),
            None,
        )
        target_names: set[str] = set()
        value_start = 0
        if assignment is not None:
            target_names = {
                item.string
                for item in statement[:assignment]
                if item.type == tokenize.NAME
                and item.string not in {_AUTHORITY_FIELD, _DENIED_FIELD}
            }
            value_start = assignment + 1
        elif statement and statement[0].string in {"for", "async"}:
            for_index = 1 if statement[0].string == "for" else 2
            in_index = next(
                (index for index, item in enumerate(statement) if item.string == "in"),
                None,
            )
            if in_index is not None:
                target_names = {
                    item.string
                    for item in statement[for_index:in_index]
                    if item.type == tokenize.NAME
                }
                value_start = in_index + 1
        symbol = symbols.get(statement[0].start[0]) if statement else None
        value_tokens = statement[value_start:]
        field_sources = {
            item.start for item in value_tokens if _token_field(item) == _AUTHORITY_FIELD
        }
        value_names = {
            item.string
            for item in value_tokens
            if item.type == tokenize.NAME and item.string not in {_AUTHORITY_FIELD, _DENIED_FIELD}
        }
        for target_name in target_names:
            key = (symbol, target_name)
            sources.setdefault(key, set()).update(field_sources)
            dependencies.setdefault(key, set()).update(
                (symbol, name) for name in value_names if name != target_name
            )
        for index, item in enumerate(statement):
            if _token_field(item) == _AUTHORITY_FIELD and _token_use_is_semantic(statement, index):
                semantic.add(item.start)
    changed = True
    while changed:
        changed = False
        for key, names in dependencies.items():
            before = len(sources.setdefault(key, set()))
            for name in names:
                sources[key].update(sources.get(name, set()))
            changed = changed or len(sources[key]) != before
    for statement in statements:
        symbol = symbols.get(statement[0].start[0]) if statement else None
        for index, item in enumerate(statement):
            if item.type != tokenize.NAME or not _token_use_is_semantic(statement, index):
                continue
            semantic.update(
                coordinate
                for coordinate in sources.get((symbol, item.string), set())
                if coordinate[0] < item.start[0]
            )
    return semantic


def _token_depths(statement: Sequence[tokenize.TokenInfo]) -> list[int]:
    depths: list[int] = []
    depth = 0
    for item in statement:
        depths.append(depth)
        if item.string in {"(", "[", "{"}:
            depth += 1
        elif item.string in {")", "]", "}"} and depth:
            depth -= 1
    return depths


def _token_use_is_semantic(statement: Sequence[tokenize.TokenInfo], index: int) -> bool:
    if not statement:
        return False
    declaration, _ = _token_declaration(statement, index)
    if declaration:
        return False
    strings = [item.string for item in statement]
    if strings[0] in {"for", "async", "def", "class"}:
        return False
    if strings[0] in {"if", "elif", "while", "assert"}:
        return True
    if index > 0 and strings[index - 1] in {"not", "~"}:
        return True
    depths = _token_depths(statement)
    target_depth = depths[index]
    left = 0
    for position in range(index - 1, -1, -1):
        if depths[position] == target_depth and statement[position].string == ",":
            left = position + 1
            break
    right = len(statement)
    for position in range(index + 1, len(statement)):
        if depths[position] == target_depth and statement[position].string == ",":
            right = position
            break
    expression = {item.string for item in statement[left:right]}
    return bool(
        expression
        & {
            "==",
            "!=",
            "<",
            "<=",
            ">",
            ">=",
            "&",
            "|",
            "intersection",
            "difference",
            "isdisjoint",
            "issubset",
            "issuperset",
        }
    )


def _token_is_required_annotation(
    statements: Sequence[Sequence[tokenize.TokenInfo]], line: int, column: int
) -> bool:
    for statement in statements:
        for index, item in enumerate(statement):
            if item.start != (line, column) or item.string != _AUTHORITY_FIELD:
                continue
            declaration, _ = _token_declaration(statement, index)
            return (
                not declaration
                and index + 1 < len(statement)
                and statement[index + 1].string == ":"
                and statement[0].string not in {"def", "async"}
            )
    return False


def _token_literal_site(
    coordinate: SourceCoordinate, tokens: Sequence[tokenize.TokenInfo]
) -> LiteralSite:
    strings = [item.string for item in tokens]
    wrapper: Literal["direct", "field_default", "literal_lambda_factory", "dynamic"] = "direct"
    candidate = list(tokens)
    if strings and strings[0] == "Field":
        if "default_factory" in strings and "lambda" in strings:
            wrapper = "literal_lambda_factory"
            start = strings.index("lambda") + 1
            colon = strings.index(":", start)
            candidate = candidate[colon + 1 :]
        elif "default" in strings:
            wrapper = "field_default"
            start = strings.index("default") + 1
            while start < len(candidate) and candidate[start].string != "=":
                start += 1
            candidate = candidate[start + 1 :]
        else:
            wrapper = "dynamic"
    values = _token_literal_values(candidate)
    if values is None:
        wrapper = "dynamic"
        values = ()
        resolution = SourceResolution.RUNTIME_BOUND
    else:
        resolution = SourceResolution.RESOLVED
    return LiteralSite(
        coordinate=coordinate,
        wrapper_kind=wrapper,
        values=values,
        resolution=resolution,
    )


def _token_literal_values(tokens: Sequence[tokenize.TokenInfo]) -> tuple[str, ...] | None:
    meaningful = [
        token
        for token in tokens
        if token.type not in {tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT}
    ]
    if len(meaningful) < 2 or meaningful[0].string not in {"(", "[", "{"}:
        return None
    closing = {"(": ")", "[": "]", "{": "}"}[meaningful[0].string]
    depth = 0
    values: list[str] = []
    closing_index: int | None = None
    for index, token in enumerate(meaningful):
        if token.string in {"(", "[", "{"}:
            depth += 1
            continue
        if token.string in {")", "]", "}"}:
            depth -= 1
            if depth == 0 and token.string == closing:
                closing_index = index
                break
            continue
        if depth != 1 or token.string == ",":
            continue
        if token.type != tokenize.STRING:
            return None
        value = _decode_string_token(token.string)
        if value is None:
            return None
        values.append(value)
    if closing_index is None or any(
        item.string in {"if", "else"} for item in meaningful[closing_index + 1 :]
    ):
        return None
    return tuple(sorted(values)) if meaningful[0].string == "{" else tuple(values)


def _token_receipt(
    *,
    scanned_python_count: int,
    rows: Sequence[SourceInventoryRow],
    denied_raw_files: int,
    denied_only_sites: Sequence[LiteralSite] = (),
) -> SourceDerivationReceipt:
    role_counts = {role: sum(row.role == role for row in rows) for role in SourceInventoryRole}
    exact_rows = [
        row
        for row in rows
        if row.role not in {SourceInventoryRole.SUBSTRING_COLLISION, SourceInventoryRole.AMBIGUOUS}
    ]
    direct = [
        site
        for row in rows
        for site in row.authoritative_sites
        if site.wrapper_kind == "direct" and site.resolution == SourceResolution.RESOLVED
    ]
    wrapper = [
        site
        for row in rows
        for site in row.authoritative_sites
        if site.wrapper_kind != "dynamic" and site.resolution == SourceResolution.RESOLVED
    ]
    denied = [
        site
        for row in rows
        for site in row.forbidden_sites
        if site.wrapper_kind != "dynamic" and site.resolution == SourceResolution.RESOLVED
    ]
    denied.extend(
        site
        for site in denied_only_sites
        if site.wrapper_kind != "dynamic" and site.resolution == SourceResolution.RESOLVED
    )
    encoded = json.dumps(
        [row.model_dump(mode="json") for row in rows],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return SourceDerivationReceipt(
        method="tokenize",
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
        direct_literal_site_count=len(direct),
        direct_literal_file_count=len({site.coordinate.path for site in direct}),
        direct_literal_subject_count=len({value for site in direct for value in site.values}),
        direct_empty_site_count=sum(not site.values for site in direct),
        wrapper_literal_site_count=len(wrapper),
        wrapper_literal_file_count=len({site.coordinate.path for site in wrapper}),
        wrapper_literal_subject_count=len({value for site in wrapper for value in site.values}),
        may_not_use_for_raw_file_count=denied_raw_files,
        may_not_use_for_literal_site_count=len(denied),
        may_not_use_for_literal_file_count=len({site.coordinate.path for site in denied}),
        may_not_use_for_literal_subject_count=len(
            {value for site in denied for value in site.values}
        ),
        row_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
    )


def _rows_agree(left: SourceInventoryRow, right: SourceInventoryRow) -> bool:
    def sites(
        row: SourceInventoryRow, field: str
    ) -> tuple[tuple[int, str, tuple[str, ...], str], ...]:
        values = row.authoritative_sites if field == _AUTHORITY_FIELD else row.forbidden_sites
        return tuple(
            (site.coordinate.line, site.wrapper_kind, site.values, site.resolution.value)
            for site in values
        )

    return (
        left.content_digest == right.content_digest
        and left.role == right.role
        and left.resolution == right.resolution
        and sites(left, _AUTHORITY_FIELD) == sites(right, _AUTHORITY_FIELD)
        and sites(left, _DENIED_FIELD) == sites(right, _DENIED_FIELD)
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("identity document frontmatter is absent")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("identity document frontmatter is unterminated")
    return text[4:end], text[end + 5 :]


def _decode_string_token(value: str) -> str | None:
    match = re.fullmatch(r"(?i:([rubf]*))(['\"])(.*)\2", value, flags=re.DOTALL)
    if match is None or "f" in match.group(1).casefold() or "b" in match.group(1).casefold():
        return None
    body = match.group(3)
    if "r" in match.group(1).casefold():
        return body
    try:
        return codecs.decode(body, "unicode_escape")
    except UnicodeDecodeError:
        return None


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _unique_coordinates(values: Sequence[SourceCoordinate]) -> list[SourceCoordinate]:
    unique = {
        (item.path, item.line, item.column, item.field_name, item.use_kind): item for item in values
    }
    return [unique[key] for key in sorted(unique)]


def _unique_sites(values: Sequence[LiteralSite]) -> list[LiteralSite]:
    unique = {
        (
            item.coordinate.path,
            item.coordinate.line,
            item.coordinate.column,
            item.coordinate.field_name,
            item.wrapper_kind,
        ): item
        for item in values
    }
    return [unique[key] for key in sorted(unique)]


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("register-as-of must be YYYY-MM-DD") from exc


def _report(register: ClaimPostureRegisterV1) -> dict[str, object]:
    return {
        "schema_version": register.schema_version,
        "source_set_digest": register.source_set_digest,
        "payload_digest": register.payload_digest,
        "ast": register.ast_derivation.model_dump(mode="json"),
        "tokenize": register.token_derivation.model_dump(mode="json"),
        "issue_codes": sorted(
            {code for row in register.source_inventory for code in row.issue_codes}
        ),
        "declared_outputs": [],
        "write_set": [],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic C01 no-writer check or bounded writer seam."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-sources", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--register-as-of", type=_parse_date, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    register, payload = compile_claim_posture_register(
        args.repo_root,
        register_as_of=args.register_as_of,
    )
    report = _report(register)
    if args.write:
        if args.output_root is None:
            parser.error("--write requires --output-root")
        target = write_claim_posture_register(register, output_root=args.output_root)
        report["declared_outputs"] = [_OUTPUT_PATH.as_posix()]
        report["write_set"] = [target.relative_to(args.output_root.resolve()).as_posix()]
    elif args.check:
        target = args.repo_root.resolve() / _OUTPUT_PATH
        if not target.is_file() or target.read_bytes() != payload:
            raise ValueError("DS11-GENERATED-DRIFT")
    elif args.corrupt_field_drift_check and not run_corruption_probe(
        "extra_field", repo_root=args.repo_root, register_as_of=args.register_as_of
    ):
        raise ValueError("corruption probe did not reject the artifact")
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
