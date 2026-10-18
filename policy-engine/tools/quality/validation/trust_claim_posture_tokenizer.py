"""Owner for extracted DS11 trust-claim posture logic."""

from __future__ import annotations

import hashlib
import io
import json
import tokenize
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from polisyos.scientist.evidence.claims.posture import (
    AdmittedSourceMember,
    LiteralSite,
    ProducerPostureMetadata,
    SourceCoordinate,
    SourceDerivationReceipt,
    SourceInventoryRole,
    SourceInventoryRow,
    SourceResolution,
)


@dataclass(frozen=True, slots=True)
class TokenizerDependencies:
    """Bind this owner to the active facade collaborators."""

    completed_owner_predicate: Callable[..., Any]
    annotation_excluded_openers: frozenset[str]
    authority_field: str
    denied_field: str
    producer_metadata_field: str
    decode_string_token: Callable[..., Any]
    unique_coordinates: Callable[..., Any]
    unique_sites: Callable[..., Any]


def _derive_token_row(
    member: AdmittedSourceMember, raw: bytes, *, dependencies: TokenizerDependencies
) -> SourceInventoryRow:
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(raw).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        line = getattr(exc, "args", (None, (1, 0)))[1][0] if len(exc.args) > 1 else 1
        coordinate = SourceCoordinate(
            path=member.path,
            symbol=None,
            line=max(int(line), 1),
            column=0,
            field_name=dependencies.authority_field,
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
    statements = _logical_statements(tokens, dependencies=dependencies)
    symbols = _token_symbols(tokens, dependencies=dependencies)
    with dependencies.completed_owner_predicate(
        "DS11-PRODUCER-METADATA",
        "producer_metadata_contract",
    ):
        producer_metadata = _derive_token_producer_metadata(
            statements, symbols, dependencies=dependencies
        )
    semantic_fields = _token_semantic_field_positions(
        statements, symbols, dependencies=dependencies
    )
    declarations: list[SourceCoordinate] = []
    carriers: list[SourceCoordinate] = []
    consumers: list[SourceCoordinate] = []
    authoritative_sites: list[LiteralSite] = []
    forbidden_sites: list[LiteralSite] = []
    exact_authority = False
    for statement in statements:
        for index, token in enumerate(statement):
            field = _token_field(token, dependencies=dependencies)
            if field is None:
                continue
            exact_authority = exact_authority or field == dependencies.authority_field
            symbol = symbols.get(token.start[0])
            declaration, value_tokens = _token_declaration(
                statement, index, dependencies=dependencies
            )
            copies_field = value_tokens is not None and any(
                _token_field(item, dependencies=dependencies) == field for item in value_tokens
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
                if value_tokens is not None:
                    site = _token_literal_site(
                        coordinate,
                        value_tokens,
                        declaration_form=_token_declaration_form(
                            statement, index, dependencies=dependencies
                        ),
                        dependencies=dependencies,
                    )
                    (
                        authoritative_sites
                        if field == dependencies.authority_field
                        else forbidden_sites
                    ).append(site)
            elif field == dependencies.authority_field and token.start in semantic_fields:
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
            elif field == dependencies.authority_field:
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
    declarations = dependencies.unique_coordinates(declarations)
    carriers = dependencies.unique_coordinates(carriers)
    consumers = dependencies.unique_coordinates(consumers)
    authoritative_sites = dependencies.unique_sites(authoritative_sites)
    forbidden_sites = dependencies.unique_sites(forbidden_sites)
    with dependencies.completed_owner_predicate(
        "DS11-PRODUCER-METADATA",
        "producer_metadata_binding",
    ):
        _validate_token_producer_metadata_bindings(
            producer_metadata, authoritative_sites, dependencies=dependencies
        )
    if not exact_authority:
        text = raw.decode("utf-8")
        line = next(
            (
                index
                for index, value in enumerate(text.splitlines(), 1)
                if dependencies.authority_field in value
            ),
            1,
        )
        collision = SourceCoordinate(
            path=member.path,
            symbol=None,
            line=line,
            column=max(text.splitlines()[line - 1].find(dependencies.authority_field), 0),
            field_name=dependencies.authority_field,
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
    if has_consumer and not any(
        item.field_name == dependencies.authority_field for item in declarations
    ):
        promoted = next(
            (
                item
                for item in carriers
                if item.field_name == dependencies.authority_field
                and _token_is_required_annotation(
                    statements, item.line, item.column, dependencies=dependencies
                )
            ),
            None,
        )
        if promoted is not None:
            carriers.remove(promoted)
            declarations.append(promoted.model_copy(update={"use_kind": "declaration"}))
            declarations = dependencies.unique_coordinates(declarations)
    has_declaration = any(item.field_name == dependencies.authority_field for item in declarations)
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
        producer_metadata=producer_metadata,
        runtime_bound=runtime_bound,
        issue_codes=("DS11-SOURCE-RUNTIME-BOUND",) if runtime_bound else (),
    )


def _derive_token_producer_metadata(
    statements: Sequence[Sequence[tokenize.TokenInfo]],
    symbols: Mapping[int, str | None],
    *,
    dependencies: TokenizerDependencies,
) -> tuple[ProducerPostureMetadata, ...]:
    """Independently derive strict metadata from token structure only."""
    declarations: list[ProducerPostureMetadata] = []
    seen: set[tuple[int, int]] = set()
    admitted: set[tuple[int, int]] = set()
    for statement in statements:
        for index, token in enumerate(statement):
            if token.type != tokenize.NAME or token.string != dependencies.producer_metadata_field:
                continue
            seen.add(token.start)
            is_declaration, value_tokens = _token_declaration(
                statement, index, dependencies=dependencies
            )
            if not is_declaration or value_tokens is None:
                continue
            admitted.add(token.start)
            try:
                decoded = _token_literal_mapping(value_tokens, dependencies=dependencies)
                declarations.append(
                    ProducerPostureMetadata.model_validate(
                        {
                            **decoded,
                            "source_symbol": symbols.get(token.start[0]),
                            "line": token.start[0],
                            "column": token.start[1],
                        }
                    )
                )
            except ValueError as exc:
                raise ValueError(f"DS11-PRODUCER-METADATA: {exc}") from exc
    if seen != admitted:
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


def _token_literal_mapping(
    tokens: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> dict[str, object]:
    meaningful = [
        item
        for item in tokens
        if item.type not in {tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT}
    ]
    if len(meaningful) < 2 or meaningful[0].string != "{" or meaningful[-1].string != "}":
        raise ValueError("metadata must be a literal mapping")
    values: dict[str, object] = {}
    index = 1
    while index < len(meaningful) - 1:
        key_token = meaningful[index]
        key = (
            dependencies.decode_string_token(key_token.string)
            if key_token.type == tokenize.STRING
            else None
        )
        if key is None or key in values:
            raise ValueError("metadata keys must be unique literal strings")
        index += 1
        if index >= len(meaningful) - 1 or meaningful[index].string != ":":
            raise ValueError("metadata literal key is missing ':'")
        index += 1
        if index >= len(meaningful) - 1:
            raise ValueError("metadata literal key is missing a value")
        token = meaningful[index]
        if token.type == tokenize.STRING:
            decoded = dependencies.decode_string_token(token.string)
            if decoded is None:
                raise ValueError("metadata values must be plain literal strings")
            values[key] = decoded
            index += 1
        elif token.string in {"(", "["}:
            closing = ")" if token.string == "(" else "]"
            index += 1
            items: list[str] = []
            while index < len(meaningful) - 1 and meaningful[index].string != closing:
                item = meaningful[index]
                if item.string == ",":
                    index += 1
                    continue
                decoded = (
                    dependencies.decode_string_token(item.string)
                    if item.type == tokenize.STRING
                    else None
                )
                if decoded is None:
                    raise ValueError("metadata sequence values must be literal strings")
                items.append(decoded)
                index += 1
            if index >= len(meaningful) - 1 or meaningful[index].string != closing:
                raise ValueError("metadata sequence is unterminated")
            values[key] = tuple(items)
            index += 1
        else:
            raise ValueError("metadata values must be literal strings or string sequences")
        if index < len(meaningful) - 1:
            if meaningful[index].string != ",":
                raise ValueError("metadata entries must be comma separated")
            index += 1
    return values


def _validate_token_producer_metadata_bindings(
    metadata: Sequence[ProducerPostureMetadata],
    authority_sites: Sequence[LiteralSite],
    *,
    dependencies: TokenizerDependencies,
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


def _logical_statements(
    tokens: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> list[list[tokenize.TokenInfo]]:
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


def _token_symbols(
    tokens: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> dict[int, str | None]:
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
    token: tokenize.TokenInfo, *, dependencies: TokenizerDependencies
) -> Literal["authoritative_for", "may_not_use_for"] | None:
    if token.type == tokenize.NAME and token.string in {
        dependencies.authority_field,
        dependencies.denied_field,
    }:
        return token.string  # type: ignore[return-value]
    if token.type == tokenize.STRING:
        decoded = dependencies.decode_string_token(token.string)
        if decoded in {dependencies.authority_field, dependencies.denied_field}:
            return decoded  # type: ignore[return-value]
    return None


def _token_declaration(
    statement: Sequence[tokenize.TokenInfo], index: int, *, dependencies: TokenizerDependencies
) -> tuple[bool, Sequence[tokenize.TokenInfo] | None]:
    if statement and (
        statement[0].string == "def"
        or (len(statement) > 1 and statement[0].string == "async" and statement[1].string == "def")
    ):
        return False, None
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
        return True, _token_value_span(
            statement, following + 1, target_depth, depths, dependencies=dependencies
        )
    if following < len(statement) and statement[following].string == ":":
        if statement[index].type == tokenize.STRING:
            return True, _token_value_span(
                statement, following + 1, target_depth, depths, dependencies=dependencies
            )
        assignment = next(
            (
                position
                for position in range(following + 1, len(statement))
                if statement[position].string == "=" and depths[position] == target_depth
            ),
            None,
        )
        if assignment is not None:
            return True, _token_value_span(
                statement, assignment + 1, target_depth, depths, dependencies=dependencies
            )
    return False, None


def _token_declaration_form(
    statement: Sequence[tokenize.TokenInfo], index: int, *, dependencies: TokenizerDependencies
) -> Literal["assignment", "keyword", "dict_key"]:
    if statement[index].type == tokenize.STRING:
        return "dict_key"
    depth = 0
    for position, item in enumerate(statement):
        if position == index:
            return "keyword" if depth else "assignment"
        if item.string in {"(", "[", "{"}:
            depth += 1
        elif item.string in {")", "]", "}"} and depth:
            depth -= 1
    return "assignment"


def _token_value_span(
    statement: Sequence[tokenize.TokenInfo],
    start: int,
    target_depth: int,
    depths: Sequence[int],
    *,
    dependencies: TokenizerDependencies,
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


def _token_is_assignment_site(
    statement: Sequence[tokenize.TokenInfo], index: int, *, dependencies: TokenizerDependencies
) -> bool:
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
    *,
    dependencies: TokenizerDependencies,
) -> set[tuple[int, int]]:
    """Derive direct and bounded local-alias decisions without AST input."""
    semantic: set[tuple[int, int]] = set()
    sources: dict[tuple[str | None, str], set[tuple[int, int]]] = {}
    dependencies: dict[tuple[str | None, str], set[tuple[str | None, str]]] = {}
    for statement in statements:
        depths = _token_depths(statement, dependencies=dependencies)
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
                and item.string not in {dependencies.authority_field, dependencies.denied_field}
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
            item.start
            for item in value_tokens
            if _token_field(item, dependencies=dependencies) == dependencies.authority_field
        }
        value_names = {
            item.string
            for item in value_tokens
            if item.type == tokenize.NAME
            and item.string not in {dependencies.authority_field, dependencies.denied_field}
        }
        for target_name in target_names:
            key = (symbol, target_name)
            sources.setdefault(key, set()).update(field_sources)
            dependencies.setdefault(key, set()).update(
                (symbol, name) for name in value_names if name != target_name
            )
        for index, item in enumerate(statement):
            if _token_field(
                item, dependencies=dependencies
            ) == dependencies.authority_field and _token_use_is_semantic(
                statement, index, dependencies=dependencies
            ):
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
            if item.type != tokenize.NAME or not _token_use_is_semantic(
                statement, index, dependencies=dependencies
            ):
                continue
            semantic.update(
                coordinate
                for coordinate in sources.get((symbol, item.string), set())
                if coordinate[0] < item.start[0]
            )
    return semantic


def _token_depths(
    statement: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> list[int]:
    depths: list[int] = []
    depth = 0
    for item in statement:
        depths.append(depth)
        if item.string in {"(", "[", "{"}:
            depth += 1
        elif item.string in {")", "]", "}"} and depth:
            depth -= 1
    return depths


def _token_annotation_span(
    statement: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> tuple[int, int] | None:
    """The annotated-assignment type span, which is syntax rather than semantic evidence.

    ``metrics: dict[str, int | float] = {...}`` carries a PEP 604 union whose ``|`` is type
    syntax, not a set operation. The AST owner never confuses the two because it walks the
    value and never the annotation; the tokenizer has no such structure, so without this
    span every name in such a statement reads as a semantic use and the two derivations
    disagree. Returns ``None`` when the statement is not an annotated assignment.
    """

    if not statement or statement[0].string in dependencies.annotation_excluded_openers:
        return None
    depths = _token_depths(statement, dependencies=dependencies)
    colon = next(
        (
            position
            for position, item in enumerate(statement)
            if item.string == ":" and depths[position] == 0
        ),
        None,
    )
    if not colon:
        return None
    target_is_dotted_name = all(
        item.type == tokenize.NAME or item.string == "." for item in statement[:colon]
    )
    if not target_is_dotted_name:
        return None
    assignment = next(
        (
            position
            for position in range(colon + 1, len(statement))
            if statement[position].string == "=" and depths[position] == 0
        ),
        None,
    )
    return (colon + 1, assignment if assignment is not None else len(statement))


def _token_use_is_semantic(
    statement: Sequence[tokenize.TokenInfo], index: int, *, dependencies: TokenizerDependencies
) -> bool:
    if not statement:
        return False
    declaration, _ = _token_declaration(statement, index, dependencies=dependencies)
    if declaration:
        return False
    annotation = _token_annotation_span(statement, dependencies=dependencies)
    if annotation is not None and annotation[0] <= index < annotation[1]:
        return False
    strings = [item.string for item in statement]
    depths = _token_depths(statement, dependencies=dependencies)
    if strings[0] in {"for", "async", "def", "class"}:
        return False
    if strings[0] in {"if", "elif", "while", "assert"}:
        return True
    if index > 0 and strings[index - 1] in {"not", "~"}:
        return True
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
    expression = {
        item.string
        for position, item in enumerate(statement[left:right], start=left)
        if annotation is None or not annotation[0] <= position < annotation[1]
    }
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
    statements: Sequence[Sequence[tokenize.TokenInfo]],
    line: int,
    column: int,
    *,
    dependencies: TokenizerDependencies,
) -> bool:
    for statement in statements:
        for index, item in enumerate(statement):
            if item.start != (line, column) or item.string != dependencies.authority_field:
                continue
            declaration, _ = _token_declaration(statement, index, dependencies=dependencies)
            return (
                not declaration
                and index + 1 < len(statement)
                and statement[index + 1].string == ":"
                and statement[0].string not in {"def", "async"}
            )
    return False


def _token_literal_site(
    coordinate: SourceCoordinate,
    tokens: Sequence[tokenize.TokenInfo],
    *,
    declaration_form: Literal["assignment", "keyword", "dict_key"],
    dependencies: TokenizerDependencies,
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
    values = _token_literal_values(candidate, dependencies=dependencies)
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


def _token_literal_values(
    tokens: Sequence[tokenize.TokenInfo], *, dependencies: TokenizerDependencies
) -> tuple[str, ...] | None:
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
        value = dependencies.decode_string_token(token.string)
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
    denied_raw_members: Sequence[AdmittedSourceMember],
    denied_only_sites: Sequence[LiteralSite] = (),
    dependencies: TokenizerDependencies,
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
        if site.declaration_form == "assignment"
        and site.wrapper_kind == "direct"
        and site.resolution == SourceResolution.RESOLVED
    ]
    wrapper = [
        site
        for row in rows
        for site in row.authoritative_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    ]
    denied = [
        site
        for row in rows
        for site in row.forbidden_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
    ]
    denied.extend(
        site
        for site in denied_only_sites
        if site.declaration_form == "assignment"
        and site.wrapper_kind != "dynamic"
        and site.resolution == SourceResolution.RESOLVED
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
        may_not_use_for_raw_file_count=len(denied_raw_members),
        may_not_use_for_literal_site_count=len(denied),
        may_not_use_for_literal_file_count=len({site.coordinate.path for site in denied}),
        may_not_use_for_literal_subject_count=len(
            {value for site in denied for value in site.values}
        ),
        may_not_use_for_raw_members=tuple(denied_raw_members),
        may_not_use_for_sites=tuple(denied),
        row_digest="sha256:" + hashlib.sha256(encoded).hexdigest(),
    )
