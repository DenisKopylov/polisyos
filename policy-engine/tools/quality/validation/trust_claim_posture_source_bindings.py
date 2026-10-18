"""Owner for extracted DS11 trust-claim posture logic."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from polisyos.common.markdown import split_markdown_table_row
from polisyos.scientist.evidence.claims.posture import (
    CUSTODY_APPOINTMENT_CONTRACT,
    CUSTODY_APPOINTMENT_DEBT_IDS,
    AccessibilityDocumentBinding,
    AntiRoleBinding,
    CustodyAppointmentStatus,
    DocumentProjectionIndex,
    EstablishmentClass,
    IdentityBoundaryBinding,
    ResolvedDocumentBinding,
)


@dataclass(frozen=True, slots=True)
class SourceBindingDependencies:
    """Bind this owner to the active facade collaborators."""

    admitted_is_file: Callable[..., Any]
    admitted_read_bytes: Callable[..., Any]
    reject_owner_predicate: Callable[..., Any]
    require_contained_path: Callable[..., Any]
    parse_accessibility_source_date: Callable[..., Any]
    slug: Callable[..., Any]
    split_frontmatter: Callable[..., Any]
    a11y_path: Path
    debt_register_path: Path
    identity_path: Path


from tools.quality.validation.trust_claim_posture_contracts import (
    CustodyAppointment,
)


def derive_identity_boundary(
    repo_root: Path, *, dependencies: SourceBindingDependencies
) -> IdentityBoundaryBinding:
    """Derive and content-bind the complete ratified anti-role paragraph twice."""
    root = repo_root.resolve()
    path = (root / dependencies.identity_path).resolve()
    dependencies.require_contained_path(
        path,
        root,
        code="DS11-IDENTITY-BOUNDARY-CONTRACT",
        stage="identity_source_containment",
        label="ratified identity document",
    )
    if not dependencies.admitted_is_file(
        path,
        root,
        code="DS11-IDENTITY-BOUNDARY-CONTRACT",
        stage="identity_source_presence",
        label="ratified identity document",
    ):
        raise ValueError("ratified identity document is missing")
    raw = dependencies.admitted_read_bytes(
        path,
        root,
        code="DS11-IDENTITY-BOUNDARY-CONTRACT",
        stage="identity_source_read",
        label="ratified identity document",
    )
    text = raw.decode("utf-8")
    try:
        frontmatter, body = dependencies.split_frontmatter(text)
    except ValueError:
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_frontmatter_delimiters",
            "ratified identity frontmatter is absent or unterminated",
        )
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_frontmatter_shape",
            "ratified identity frontmatter is malformed",
        )
    owner = metadata.get("owner")
    last_reviewed = metadata.get("last_reviewed")
    decision_status = metadata.get("decision_status")
    authoritative_for = metadata.get("authoritative_for")
    may_not_use_for = metadata.get("may_not_use_for")
    if (
        not isinstance(owner, str)
        or not isinstance(last_reviewed, date)
        or not isinstance(decision_status, str)
        or not isinstance(authoritative_for, list)
        or not all(isinstance(item, str) for item in authoritative_for)
        or not isinstance(may_not_use_for, list)
        or not all(isinstance(item, str) for item in may_not_use_for)
    ):
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_authority_fields",
            "ratified identity authority frontmatter is incomplete",
        )
    identity_section = re.search(
        r"## 1\. The decision in one sentence\s+(.+?)\s+## 2\.",
        body,
        flags=re.DOTALL,
    )
    if identity_section is None:
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_statement_presence",
            "ratified system-identity statement is absent",
        )
    identity_statements = re.findall(r"\*\*(.+?)\*\*", identity_section.group(1), re.DOTALL)
    if len(identity_statements) != 1:
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_statement_cardinality",
            "ratified system-identity statement is ambiguous",
        )
    identity_statement = identity_statements[0]
    match = re.search(
        r"\*\*Anti-roles \(binding\):\*\*\s*(.+?)(?:\n\n|\Z)",
        body,
        flags=re.DOTALL,
    )
    if match is None:
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_anti_role_presence",
            "binding anti-role paragraph is absent",
        )
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
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_anti_role_normalizers",
            "independent anti-role normalizers disagree",
        )
    paragraph_start = body[: match.start(1)].count("\n") + text[: text.index(body)].count("\n") + 1
    paragraph_end = paragraph_start + match.group(1).count("\n")
    identity_start = (
        body[: identity_section.start(1)].count("\n") + text[: text.index(body)].count("\n") + 1
    )
    identity_end = identity_start + identity_section.group(1).count("\n")
    source_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    paragraph_digest = "sha256:" + hashlib.sha256(match.group(1).encode("utf-8")).hexdigest()
    anti_roles = tuple(
        AntiRoleBinding(
            role=dependencies.slug(role),
            display_label=role,
            source_path=dependencies.identity_path.as_posix(),
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
    try:
        return IdentityBoundaryBinding(
            path=dependencies.identity_path.as_posix(),
            content_digest=source_digest,
            frontmatter_digest="sha256:" + hashlib.sha256(frontmatter.encode("utf-8")).hexdigest(),
            paragraph_digest=paragraph_digest,
            paragraph_start_line=paragraph_start,
            paragraph_end_line=paragraph_end,
            anti_roles=anti_roles,
            derivation_receipt_digests=(method_a, method_b),
            owner=owner,
            last_reviewed=last_reviewed,
            decision_status=decision_status,
            authoritative_for=tuple(authoritative_for),
            may_not_use_for=tuple(may_not_use_for),
            identity_statement=identity_statement,
            identity_statement_digest="sha256:"
            + hashlib.sha256(identity_statement.encode("utf-8")).hexdigest(),
            identity_statement_start_line=identity_start,
            identity_statement_end_line=identity_end,
        )
    except ValidationError:
        dependencies.reject_owner_predicate(
            "DS11-IDENTITY-BOUNDARY-CONTRACT",
            "identity_typed_artifact",
            "ratified identity boundary violates its typed artifact schema",
        )


def derive_custody_appointments(
    repo_root: Path, *, dependencies: SourceBindingDependencies
) -> tuple[CustodyAppointment, ...]:
    """Derive the three accepted custody appointments from admitted debt rows."""
    root = repo_root.resolve()
    path = (root / dependencies.debt_register_path).resolve()
    dependencies.require_contained_path(
        path,
        root,
        code="DS11-CUSTODY-APPOINTMENT-CONTRACT",
        stage="custody_source_containment",
        label="custody appointment debt source",
    )
    if not dependencies.admitted_is_file(
        path,
        root,
        code="DS11-CUSTODY-APPOINTMENT-CONTRACT",
        stage="custody_source_presence",
        label="custody appointment debt source",
    ):
        raise ValueError("custody appointment debt source is missing")
    raw = dependencies.admitted_read_bytes(
        path,
        root,
        code="DS11-CUSTODY-APPOINTMENT-CONTRACT",
        stage="custody_source_read",
        label="custody appointment debt source",
    )
    required_ids = set(CUSTODY_APPOINTMENT_DEBT_IDS)
    found: dict[str, CustodyAppointment] = {}
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        line = raw_line.decode("utf-8")
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in split_markdown_table_row(line)]
        ids = re.findall(r"`([^`]+)`", cells[0])
        if not required_ids.intersection(ids):
            continue
        if len(cells) != 5:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_row_shape",
                "custody appointment source row must contain exactly five cells",
            )
        if len(ids) != 1:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_id_cardinality",
                "custody appointment source row must name exactly one accepted ID",
            )
        debt_id = ids[0]
        if debt_id in found:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_duplicate_id",
                f"custody appointment {debt_id} is duplicated",
            )
        owners = tuple(
            token
            for token in re.findall(r"`([^`]+)`", cells[2])
            if re.fullmatch(r"team-[a-z0-9-]+", token)
        )
        statuses = re.findall(r"`([^`]+)`", cells[3])
        commands = tuple(
            token
            for token in re.findall(r"`([^`]+)`", cells[4])
            if token.startswith(("uv run pytest ", "pytest ", "python ", ".venv/bin/python "))
        )
        if len(owners) != 1 or len(statuses) != 1 or len(commands) != 1:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_cardinality",
                f"custody appointment {debt_id} is not exactly appointed",
            )
        try:
            status = CustodyAppointmentStatus(statuses[0])
        except ValueError:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_status",
                f"custody appointment {debt_id} has an unsupported status",
            )
        if (owners[0], commands[0]) != CUSTODY_APPOINTMENT_CONTRACT[debt_id]:
            dependencies.reject_owner_predicate(
                "DS11-CUSTODY-APPOINTMENT-CONTRACT",
                "custody_appointment_contract",
                "custody appointment source differs from the accepted contract",
            )
        found[debt_id] = CustodyAppointment(
            debt_id=debt_id,
            owner=owners[0],
            status=status,
            closure_signal=commands[0],
            source_ref=(
                f"{dependencies.debt_register_path.as_posix()}#{debt_id}@sha256:"
                f"{hashlib.sha256(raw_line).hexdigest()}"
            ),
            line=line_number,
            source_content=line,
            dependencies=dependencies,
        )
    if set(found) != required_ids:
        dependencies.reject_owner_predicate(
            "DS11-CUSTODY-APPOINTMENT-CONTRACT",
            "custody_appointment_completeness",
            "custody appointment debt source is incomplete",
        )
    appointments = tuple(sorted(found.values(), key=lambda item: item.debt_id))
    return appointments


def derive_accessibility_document(
    repo_root: Path, *, dependencies: SourceBindingDependencies
) -> AccessibilityDocumentBinding:
    """Resolve the strict accessibility projection index against complete body bytes."""
    root = repo_root.resolve()
    path = (root / dependencies.a11y_path).resolve()
    dependencies.require_contained_path(
        path,
        root,
        code="DS11-ACCESSIBILITY-CONTRACT",
        stage="accessibility_source_containment",
        label="accessibility document",
    )
    if not dependencies.admitted_is_file(
        path,
        root,
        code="DS11-ACCESSIBILITY-CONTRACT",
        stage="accessibility_source_presence",
        label="accessibility document",
    ):
        raise ValueError("accessibility document is missing")
    raw = dependencies.admitted_read_bytes(
        path,
        root,
        code="DS11-ACCESSIBILITY-CONTRACT",
        stage="accessibility_source_read",
        label="accessibility document",
    )
    text = raw.decode("utf-8")
    try:
        frontmatter, body = dependencies.split_frontmatter(text)
    except ValueError:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_frontmatter_delimiters",
            "accessibility frontmatter is absent or unterminated",
        )
    loaded = yaml.safe_load(frontmatter)
    if not isinstance(loaded, dict) or set(loaded) != {"ds11_projection_index"}:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_frontmatter_shape",
            "accessibility frontmatter must contain only ds11_projection_index",
        )
    try:
        index = DocumentProjectionIndex.model_validate(loaded["ds11_projection_index"])
    except ValidationError:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_projection_index_schema",
            "accessibility projection index violates its typed schema",
        )
    body_bytes = body.encode("utf-8")
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    if index.body_sha256 != body_sha:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_body_digest",
            "accessibility body digest differs from projection index",
        )
    required_keys = {
        key
        for purpose in (*index.authoritative_for, *index.may_not_use_for)
        for key in purpose.basis
    }
    if not required_keys or not required_keys <= set(index.bindings):
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_projection_basis",
            "accessibility projection basis names an unresolved binding",
        )
    resolved: list[ResolvedDocumentBinding] = []
    for key, selector in sorted(index.bindings.items()):
        exact = selector.exact_text.encode("utf-8")
        if body_bytes.count(exact) != selector.occurrence:
            dependencies.reject_owner_predicate(
                "DS11-ACCESSIBILITY-CONTRACT",
                "accessibility_selector_cardinality",
                f"accessibility selector {key} is absent or duplicated in body",
            )
        start = body_bytes.index(exact)
        if selector.value.encode("utf-8") not in exact:
            dependencies.reject_owner_predicate(
                "DS11-ACCESSIBILITY-CONTRACT",
                "accessibility_selector_value",
                f"accessibility selector {key} does not bind its declared value",
            )
        resolved.append(
            ResolvedDocumentBinding(
                key=key,
                value=selector.value,
                exact_text=selector.exact_text,
                exact_text_digest="sha256:" + hashlib.sha256(exact).hexdigest(),
                byte_start=start,
                byte_end=start + len(exact),
                establishment_class=EstablishmentClass.RECOMPUTED,
            )
        )
    source_selector = index.bindings.get("source_as_of")
    if source_selector is None:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_source_as_of_presence",
            "accessibility source_as_of binding is absent",
        )
    limitation = "It does not replace the planned third-party countersign."
    limitation_occurrences = sum(
        " ".join(paragraph.split()).count(limitation) for paragraph in re.split(r"\n[ \t]*\n", body)
    )
    if limitation_occurrences != 1:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_limitation_cardinality",
            "accessibility limitation is absent or duplicated",
        )
    try:
        return AccessibilityDocumentBinding(
            path=dependencies.a11y_path.as_posix(),
            source_content=text,
            content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
            frontmatter_digest="sha256:" + hashlib.sha256(frontmatter.encode()).hexdigest(),
            body_digest="sha256:" + body_sha,
            source_as_of=dependencies.parse_accessibility_source_date(source_selector.value),
            bindings=tuple(resolved),
            authoritative_for=index.authoritative_for,
            may_not_use_for=index.may_not_use_for,
            limitation_refs=(limitation,),
        )
    except ValidationError:
        dependencies.reject_owner_predicate(
            "DS11-ACCESSIBILITY-CONTRACT",
            "accessibility_typed_artifact",
            "accessibility document violates its typed artifact schema",
        )
