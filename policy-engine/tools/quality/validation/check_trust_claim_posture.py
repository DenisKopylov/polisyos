"""Independent tokenizer, reconciliation, and checker for DS11 claim posture."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
import shutil  # noqa: F401 - live checker monkeypatch binding
import subprocess  # noqa: F401 - live checker monkeypatch binding
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import NoReturn

from polisyos.scientist.evidence.claims.posture import (
    CUSTODY_APPOINTMENT_DEBT_IDS,
    CUSTODY_APPOINTMENT_SOURCE_PATH,
    AccessibilityDocumentBinding,
    AdmittedSourceMember,
    ClaimPostureRegisterV1,
    GeneratedFamilyBinding,
    IdentityBoundaryBinding,
    LiteralSite,
    PageA11yReceiptBinding,
    ReconciledSourceDerivation,
    SourceCoordinate,
    SourceDerivation,
    SourceDerivationReceipt,
    SourceInventoryRole,
    SourceInventoryRow,
    SourceResolution,
)
from tools.lib.fs import (
    AdmittedPathError,
    FileReadMeasurement,
    admitted_is_dir,
    admitted_is_file,
    admitted_read_bytes,
    admitted_read_text,
    measure_file_reads,
    resolve_admitted_path,
)
from tools.quality.validation import (
    trust_claim_posture_accessibility as _accessibility_owner,
)
from tools.quality.validation import (
    trust_claim_posture_artifact_lifecycle as _lifecycle_owner,
)
from tools.quality.validation import (
    trust_claim_posture_semantics as _semantics_owner,
)
from tools.quality.validation import (
    trust_claim_posture_source_bindings as _binding_owner,
)
from tools.quality.validation import (
    trust_claim_posture_tokenizer as _tokenizer_owner,
)
from tools.quality.validation.trust_claim_posture_contracts import (
    CustodyAppointment,
    _PostureInspectionError,
    _PosturePredicateError,
)


def _tokenizer_dependencies() -> _tokenizer_owner.TokenizerDependencies:
    return _tokenizer_owner.TokenizerDependencies(
        completed_owner_predicate=_completed_owner_predicate,
        annotation_excluded_openers=_ANNOTATION_EXCLUDED_OPENERS,
        authority_field=_AUTHORITY_FIELD,
        denied_field=_DENIED_FIELD,
        producer_metadata_field=_PRODUCER_METADATA_FIELD,
        decode_string_token=_decode_string_token,
        unique_coordinates=_unique_coordinates,
        unique_sites=_unique_sites,
    )


def _binding_dependencies() -> _binding_owner.SourceBindingDependencies:
    return _binding_owner.SourceBindingDependencies(
        admitted_is_file=_admitted_is_file,
        admitted_read_bytes=_admitted_read_bytes,
        reject_owner_predicate=_reject_owner_predicate,
        require_contained_path=_require_contained_path,
        parse_accessibility_source_date=_parse_accessibility_source_date,
        slug=_slug,
        split_frontmatter=_split_frontmatter,
        a11y_path=_A11Y_PATH,
        debt_register_path=_DEBT_REGISTER_PATH,
        identity_path=_IDENTITY_PATH,
    )


def _accessibility_dependencies() -> _accessibility_owner.AccessibilityDependencies:
    return _accessibility_owner.AccessibilityDependencies(
        admitted_is_dir=_admitted_is_dir,
        admitted_is_file=_admitted_is_file,
        admitted_read_bytes=_admitted_read_bytes,
        reject_owner_predicate=_reject_owner_predicate,
        require_contained_path=_require_contained_path,
        page_receipt_path=_PAGE_RECEIPT_PATH,
    )


def _semantic_dependencies() -> _semantics_owner.SemanticDependencies:
    return _semantics_owner.SemanticDependencies(
        admitted_is_dir=_admitted_is_dir,
        admitted_is_file=_admitted_is_file,
        admitted_read_bytes=_admitted_read_bytes,
        reject_owner_predicate=_reject_owner_predicate,
        require_contained_path=_require_contained_path,
        derive_accessibility_document=derive_accessibility_document,
        derive_custody_appointments=derive_custody_appointments,
        derive_identity_boundary=derive_identity_boundary,
        derive_page_a11y_receipt=derive_page_a11y_receipt,
        derive_token_sources=derive_token_sources,
        reconcile_source_derivations=reconcile_source_derivations,
        a11y_path=_A11Y_PATH,
        default_register_as_of=_DEFAULT_REGISTER_AS_OF,
        identity_path=_IDENTITY_PATH,
        output_path=_OUTPUT_PATH,
        page_receipt_path=_PAGE_RECEIPT_PATH,
    )


def _lifecycle_dependencies() -> _lifecycle_owner.LifecycleDependencies:
    return _lifecycle_owner.LifecycleDependencies(
        admitted_is_file=_admitted_is_file,
        admitted_read_bytes=_admitted_read_bytes,
        admitted_read_text=_admitted_read_text,
        reject_owner_predicate=_reject_owner_predicate,
        require_contained_path=_require_contained_path,
        compile_claim_posture_register=compile_claim_posture_register,
        derive_accessibility_document=derive_accessibility_document,
        derive_identity_boundary=derive_identity_boundary,
        validate_claim_copy=validate_claim_copy,
        a11y_path=_A11Y_PATH,
        corruption_reason_codes=_CORRUPTION_REASON_CODES,
        debt_register_path=_DEBT_REGISTER_PATH,
        generated_manifest_path=_GENERATED_MANIFEST_PATH,
        generated_reference_path=_GENERATED_REFERENCE_PATH,
        identity_path=_IDENTITY_PATH,
        output_path=_OUTPUT_PATH,
    )


_AUTHORITY_FIELD = "authoritative_for"
_DENIED_FIELD = "may_not_use_for"
_PRODUCER_METADATA_FIELD = "trust_claim_posture"
_IDENTITY_PATH = Path("docs/system-design-decisions/policyos-identity-and-custody-boundary.md")
_A11Y_PATH = Path("docs/compliance/A11Y_AUDIT_2026Q2.md")
_PAGE_RECEIPT_PATH = Path("docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base")
_GENERATED_MANIFEST_PATH = Path("architecture/generated_artifacts.toml")
_GENERATED_REFERENCE_PATH = Path("docs/reference/generated-artifacts.md")
_OUTPUT_PATH = Path("apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json")
_DEBT_REGISTER_PATH = Path(CUSTODY_APPOINTMENT_SOURCE_PATH)
_DEFAULT_REGISTER_AS_OF = date(2026, 9, 17)


def _reject_owner_predicate(code: str, stage: str, message: str) -> NoReturn:
    """Transport a conclusive owner predicate failure without text classification."""
    raise _PosturePredicateError(
        code,
        message,
        stage=stage,
        finding_coverage=(
            f"decisive predicate failure: complete declared {stage} predicate "
            "was evaluated and rejected its input"
        ),
    )


@contextmanager
def _completed_owner_predicate(code: str, stage: str) -> Iterator[None]:
    """Transport ValueErrors from one completed semantic owner phase as typed FAIL."""
    try:
        yield
    except _PosturePredicateError:
        raise
    except ValueError as error:
        _reject_owner_predicate(code, stage, str(error))


def _require_contained_path(
    path: Path,
    root: Path,
    *,
    code: str,
    stage: str,
    label: str,
) -> Path:
    """Resolve once at the owner boundary and reject escapes before file access."""
    try:
        return resolve_admitted_path(path, root)
    except AdmittedPathError as error:
        _reject_owner_predicate(
            code,
            stage,
            f"{label} resolves outside its admitted root: {error}",
        )


def _admitted_is_file(
    path: Path,
    root: Path,
    *,
    code: str,
    stage: str,
    label: str,
) -> bool:
    """Inspect file presence only after resolving beneath the owner's root."""
    try:
        return admitted_is_file(path, root)
    except AdmittedPathError as error:
        _reject_owner_predicate(code, stage, f"{label} resolves outside its admitted root: {error}")


def _admitted_is_dir(
    path: Path,
    root: Path,
    *,
    code: str,
    stage: str,
    label: str,
) -> bool:
    """Inspect directory presence only after resolving beneath the owner's root."""
    try:
        return admitted_is_dir(path, root)
    except AdmittedPathError as error:
        _reject_owner_predicate(code, stage, f"{label} resolves outside its admitted root: {error}")


def _admitted_read_bytes(
    path: Path,
    root: Path,
    *,
    code: str,
    stage: str,
    label: str,
) -> bytes:
    """Read bytes only from a path resolved beneath the owner's admitted root."""
    try:
        return admitted_read_bytes(path, root)
    except AdmittedPathError as error:
        _reject_owner_predicate(code, stage, f"{label} resolves outside its admitted root: {error}")


def _admitted_read_text(
    path: Path,
    root: Path,
    *,
    code: str,
    stage: str,
    label: str,
    encoding: str = "utf-8",
) -> str:
    """Read text only from a path resolved beneath the owner's admitted root."""
    try:
        return admitted_read_text(path, root, encoding=encoding)
    except AdmittedPathError as error:
        _reject_owner_predicate(code, stage, f"{label} resolves outside its admitted root: {error}")


_CORRUPTION_REASON_CODES: Mapping[str, tuple[str, ...]] = {
    "anti_role_removal": ("DS11-IDENTITY-ANTI-ROLE-DRIFT",),
    "body_fact_removal": ("DS11-A11Y-CERTIFICATION-NOT-EARNED",),
    "candidate_to_supported": ("DS11-STATUS-UPGRADE",),
    "crm_omission": ("DS11-IDENTITY-ANTI-ROLE-DRIFT",),
    "dynamic_source_silently_dropped": ("DS11-SOURCE-DERIVATION-DISAGREEMENT",),
    "forbidden_purpose_removal": ("DS11-AUTHORITY-PURPOSE-DENIED",),
    "limitation_omission": ("DS11-DOM-PARITY-DRIFT",),
    "machine_reserialization": ("DS11-MACHINE-BYTE-DRIFT",),
    "manages_your_cases": ("DS11-IDENTITY-COPY-UNBOUND",),
    "performance_relabel": ("DS11-PERFORMANCE-NOT-EARNED",),
    "planned_to_supported": ("DS11-STATUS-UPGRADE",),
    "review_refresh_without_evidence": ("DS11-REVIEW-MISSING-OR-STALE",),
    "row_reorder": ("DS11-DOM-PARITY-DRIFT",),
    "scope_assumption_change": ("DS11-GATE-PREDICATE-NOT-ESTABLISHED",),
    "source_digest_rebinding": ("DS11-SOURCE-CONTENT-NOT-BOUND",),
}


def derive_token_sources(repo_root: Path) -> SourceDerivation:
    """Independently derive and bind authority/denial candidates with tokenize."""
    root = repo_root.resolve()
    with measure_file_reads(root) as reads:
        source_root = (root / "src").resolve()
        _require_contained_path(
            source_root,
            root,
            code="DS11-SOURCE-SET-CONTAINMENT",
            stage="source_root_containment",
            label="repo_root/src",
        )
        present = _admitted_is_dir(
            source_root,
            root,
            code="DS11-SOURCE-SET-CONTAINMENT",
            stage="source_root_presence",
            label="repo_root/src",
        )
        if not present:
            raise ValueError("repo_root/src is missing or is not a directory")
        members: list[AdmittedSourceMember] = []
        rows: list[SourceInventoryRow] = []
        denied_raw_members: list[AdmittedSourceMember] = []
        denied_only_sites: list[LiteralSite] = []
        candidates = sorted(source_root.rglob("*.py"), key=lambda item: item.as_posix())
        reads.record(
            source_root,
            "rglob",
            status="enumerated",
            pattern="*.py",
            candidate_count=len(candidates),
        )
        for candidate in candidates:
            path = candidate.resolve()
            if not path.is_relative_to(source_root):
                reads.record(
                    candidate, "source_selection", status="excluded", reason="outside contained src"
                )
                continue
            if "__pycache__" in path.parts:
                reads.record(candidate, "source_selection", status="excluded", reason="__pycache__")
                continue
            if not _admitted_is_file(
                path,
                source_root,
                code="DS11-SOURCE-SET-CONTAINMENT",
                stage="source_member_presence",
                label="token source member",
            ):
                reads.record(candidate, "source_selection", status="excluded", reason="non-file")
                continue
            raw = _admitted_read_bytes(
                path,
                source_root,
                code="DS11-SOURCE-SET-CONTAINMENT",
                stage="token_source_member_read",
                label="token source member",
            )
            raw.decode("utf-8")
            member = AdmittedSourceMember(
                path=path.relative_to(root).as_posix(),
                content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
            )
            members.append(member)
            if _DENIED_FIELD.encode() in raw:
                denied_raw_members.append(member)
            if _AUTHORITY_FIELD.encode() in raw:
                rows.append(_derive_token_row(member, raw))
            elif _DENIED_FIELD.encode() in raw:
                denied_only_sites.extend(_derive_token_row(member, raw).forbidden_sites)
        ordered_rows = tuple(sorted(rows, key=lambda row: row.path))
        candidate_paths = {row.path for row in ordered_rows} | {
            member.path for member in denied_raw_members
        }
        admitted = tuple(member for member in members if member.path in candidate_paths)
        return SourceDerivation(
            admitted_sources=admitted,
            rows=ordered_rows,
            receipt=_token_receipt(
                scanned_python_count=len(admitted),
                rows=ordered_rows,
                denied_raw_members=denied_raw_members,
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
                producer_metadata=(),
                runtime_bound=True,
                issue_codes=("DS11-SOURCE-DERIVATION-DISAGREEMENT",),
            )
        )
    member_paths = set(ast_members) | set(token_members)
    for path in sorted(member_paths):
        if ast_members.get(path) != token_members.get(path):
            disagreements.append(path)
    admitted = tuple(ast_members.get(path) or token_members[path] for path in sorted(member_paths))
    if ast_result.receipt.may_not_use_for_sites != token_result.receipt.may_not_use_for_sites:
        ast_sites = set(ast_result.receipt.may_not_use_for_sites)
        token_sites = set(token_result.receipt.may_not_use_for_sites)
        coordinates = sorted(
            {
                f"{site.coordinate.path}:{site.coordinate.line}:{site.coordinate.column}"
                for site in ast_sites ^ token_sites
            }
        )
        _reject_owner_predicate(
            "DS11-SOURCE-DERIVATION-CONTRACT",
            "source_derivation_reconciliation",
            "may_not_use_for derivations disagree at " + ", ".join(coordinates),
        )
    inventory_paths = {row.path for row in rows}
    denied_only_sites = tuple(
        site
        for site in ast_result.receipt.may_not_use_for_sites
        if site.coordinate.path not in inventory_paths
    )
    return ReconciledSourceDerivation(
        admitted_sources=admitted,
        rows=tuple(rows),
        ast_receipt=ast_result.receipt,
        token_receipt=token_result.receipt,
        may_not_use_for_denied_only_sites=denied_only_sites,
        disagreements=tuple(sorted(set(disagreements))),
    )


def derive_identity_boundary(repo_root: Path) -> IdentityBoundaryBinding:
    """Derive and content-bind the complete ratified anti-role paragraph twice."""
    return _binding_owner.derive_identity_boundary(repo_root, dependencies=_binding_dependencies())


def derive_custody_appointments(
    repo_root: Path,
) -> tuple[CustodyAppointment, ...]:
    """Derive the three accepted custody appointments from admitted debt rows."""
    return _binding_owner.derive_custody_appointments(
        repo_root, dependencies=_binding_dependencies()
    )


def derive_accessibility_document(repo_root: Path) -> AccessibilityDocumentBinding:
    """Resolve the strict accessibility projection index against complete body bytes."""
    return _binding_owner.derive_accessibility_document(
        repo_root, dependencies=_binding_dependencies()
    )


def _parse_accessibility_source_date(value: str) -> date:
    return _accessibility_owner._parse_accessibility_source_date(
        value, dependencies=_accessibility_dependencies()
    )


def derive_page_a11y_receipt(repo_root: Path) -> PageA11yReceiptBinding:
    """Recompute the historical page-a11y receipt from its five admitted JSON files."""
    return _accessibility_owner.derive_page_a11y_receipt(
        repo_root, dependencies=_accessibility_dependencies()
    )


def validate_claim_copy(
    copy: str,
    *,
    source_row: object | None,
    admitted_sources: Sequence[AdmittedSourceMember] = (),
    requested_purpose: str = "capability_claim",
) -> tuple[str, ...]:
    """Require copy to bind a strict, supported, admitted posture object."""
    return _accessibility_owner.validate_claim_copy(
        copy,
        source_row=source_row,
        admitted_sources=admitted_sources,
        requested_purpose=requested_purpose,
        dependencies=_accessibility_dependencies(),
    )


def compile_claim_posture_register(
    repo_root: Path,
    *,
    register_as_of: date = _DEFAULT_REGISTER_AS_OF,
) -> tuple[ClaimPostureRegisterV1, bytes]:
    """Compile, reconcile, assemble, validate, and canonically serialize live sources."""
    return _semantics_owner.compile_claim_posture_register(
        repo_root, register_as_of=register_as_of, dependencies=_semantic_dependencies()
    )


def write_claim_posture_register(
    register: ClaimPostureRegisterV1,
    *,
    output_root: Path,
) -> Path:
    """Write only the fixed generated target contained by ``output_root``."""
    return _semantics_owner.write_claim_posture_register(
        register, output_root=output_root, dependencies=_semantic_dependencies()
    )


def validate_generated_family(repo_root: Path) -> GeneratedFamilyBinding:
    """Parse the existing manifest owner and admit only the strict posture family."""
    return _lifecycle_owner.validate_generated_family(
        repo_root, dependencies=_lifecycle_dependencies()
    )


def run_generated_family_output_probe(
    repo_root: Path,
    *,
    source_root: Path,
    output_root: Path,
) -> tuple[str, ...]:
    """Execute the manifest probe in an isolated source and prove exact output bytes."""
    return _lifecycle_owner.run_generated_family_output_probe(
        repo_root,
        source_root=source_root,
        output_root=output_root,
        dependencies=_lifecycle_dependencies(),
    )


def write_generated_reference(repo_root: Path, *, output_root: Path | None = None) -> Path:
    """Render only the generated-artifact reference through its existing owner."""
    return _lifecycle_owner.write_generated_reference(
        repo_root, output_root=output_root, dependencies=_lifecycle_dependencies()
    )


def validate_register_against_live_sources(
    payload: bytes,
    *,
    repo_root: Path,
    register_as_of: date,
) -> ClaimPostureRegisterV1:
    """Validate strict bytes and require equality with a live recompilation."""
    return _lifecycle_owner.validate_register_against_live_sources(
        payload,
        repo_root=repo_root,
        register_as_of=register_as_of,
        dependencies=_lifecycle_dependencies(),
    )


def run_corruption_probe(
    kind: str,
    *,
    repo_root: Path,
    register_as_of: date,
) -> bool:
    """Require a corrupted live payload to fail strict validation."""
    return _lifecycle_owner.run_corruption_probe(
        kind,
        repo_root=repo_root,
        register_as_of=register_as_of,
        dependencies=_lifecycle_dependencies(),
    )


def run_corruption_probes(
    *,
    repo_root: Path,
    register_as_of: date,
) -> dict[str, object]:
    """Run the closed C05 semantic mutation wave entirely in scratch roots."""
    return _lifecycle_owner.run_corruption_probes(
        repo_root=repo_root, register_as_of=register_as_of, dependencies=_lifecycle_dependencies()
    )


def _minimal_probe_repo(
    root: Path,
    source: str,
    *,
    basis_root: Path,
    source_name: str = "probe.py",
) -> Path:
    """Preserve the journal probe signature and bind current facade dependencies."""
    return _lifecycle_owner._minimal_probe_repo(
        root,
        source,
        basis_root=basis_root,
        source_name=source_name,
        dependencies=_lifecycle_dependencies(),
    )


def _derive_token_row(member: AdmittedSourceMember, raw: bytes) -> SourceInventoryRow:
    return _tokenizer_owner._derive_token_row(member, raw, dependencies=_tokenizer_dependencies())


#: Statement keywords that own a depth-0 colon which is not an annotation.
_ANNOTATION_EXCLUDED_OPENERS = frozenset(
    {
        "async",
        "class",
        "def",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "if",
        "lambda",
        "try",
        "while",
        "with",
    }
)


def _token_receipt(
    *,
    scanned_python_count: int,
    rows: Sequence[SourceInventoryRow],
    denied_raw_members: Sequence[AdmittedSourceMember],
    denied_only_sites: Sequence[LiteralSite] = (),
) -> SourceDerivationReceipt:
    return _tokenizer_owner._token_receipt(
        scanned_python_count=scanned_python_count,
        rows=rows,
        denied_raw_members=denied_raw_members,
        denied_only_sites=denied_only_sites,
        dependencies=_tokenizer_dependencies(),
    )


def _rows_agree(left: SourceInventoryRow, right: SourceInventoryRow) -> bool:
    def sites(
        row: SourceInventoryRow, field: str
    ) -> tuple[tuple[int, str, str, tuple[str, ...], str], ...]:
        values = row.authoritative_sites if field == _AUTHORITY_FIELD else row.forbidden_sites
        return tuple(
            (
                site.coordinate.line,
                site.declaration_form,
                site.wrapper_kind,
                site.values,
                site.resolution.value,
            )
            for site in values
        )

    return (
        left.content_digest == right.content_digest
        and left.role == right.role
        and left.resolution == right.resolution
        and sites(left, _AUTHORITY_FIELD) == sites(right, _AUTHORITY_FIELD)
        and sites(left, _DENIED_FIELD) == sites(right, _DENIED_FIELD)
        and left.producer_metadata == right.producer_metadata
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
            item.declaration_form,
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
    receipt_exclusions = {
        "may_not_use_for_raw_members",
        "may_not_use_for_sites",
    }
    return {
        "schema_version": register.schema_version,
        "source_set_digest": register.source_set_digest,
        "payload_digest": register.payload_digest,
        "ast": register.ast_derivation.model_dump(mode="json", exclude=receipt_exclusions),
        "tokenize": register.token_derivation.model_dump(mode="json", exclude=receipt_exclusions),
        "issue_codes": sorted(
            {code for row in register.source_inventory for code in row.issue_codes}
        ),
        "declared_outputs": [],
        "write_set": [],
    }


def _measurement_receipt(
    reads: FileReadMeasurement,
    *,
    complete_verdict: bool,
    finding_coverage: str,
) -> dict[str, object]:
    receipt = reads.snapshot(complete_verdict=complete_verdict)
    receipt["finding_coverage"] = finding_coverage
    receipt["source_python_read_count"] = len(
        {
            item["path"]
            for item in receipt["inputs"]
            if item["operation"] == "read_bytes"
            and item["status"] == "read"
            and item["path"].startswith("src/")
            and item["path"].endswith(".py")
        }
    )
    receipt["selectors"] = {
        "source": "contained src/**/*.py regular files, excluding __pycache__; case-sensitive authoritative_for/may_not_use_for byte candidates, then AST/tokenize reconciliation",
        "custody_path": _DEBT_REGISTER_PATH.as_posix(),
        "custody_ids": list(CUSTODY_APPOINTMENT_DEBT_IDS),
        "custody_rows": "lines beginning | whose tokenized first cell names an accepted ID; exactly five cells and one ID required",
        "identity": _IDENTITY_PATH.as_posix(),
        "accessibility": _A11Y_PATH.as_posix() + " if present with frontmatter",
        "page_receipt": _PAGE_RECEIPT_PATH.as_posix()
        + " if directory present; five fixed JSON members",
        "path_containment": "every checker-owned file-presence, byte-read, and text-read operation resolves its path beneath the admitted owner root before access; an escape is typed FAIL before the read or write",
    }
    receipt["unresolved_by_construction"].extend(
        [
            "schema_and_evidence_only: this is a declared schema/source and evidence-binding check; runtime execution, external evidence truth, whole-tree capability completeness and current certification remain undecided.",
            "unselected_authority_documents: documents outside the named identity/accessibility/page-receipt/custody selectors cannot establish or refute this verdict; their authority claims remain undecided.",
            "unselected_custody_rows: the register is read as bytes, but only appointed IDs are interpreted; other rows and sections do not receive a custody verdict.",
            "source_discovery: the current filesystem src/**/*.py selector is not a tracked whole-repository denominator; excluded paths, other languages, unsupported/dynamic semantics and inaccessible traversal remain unresolved.",
            "delegated_reads: the AST owner receives the shared admitted byte-reader, and generated-family parsing receives the already-admitted manifest bytes; guardrails copytree/snapshot internals and the declared generator subprocess remain delegated operations outside this explicit reader receipt, so their internal I/O is unresolved.",
            "untyped_derivation_failures: source derivation ValueError/SyntaxError without a typed owner predicate remains UNRUN; its semantic classification is not established by this CLI.",
            "probe_preconditions: unavailable executables, invalid scratch roots, unsupported internal corruption-probe arguments, or unavailable corruption targets prevent the probe from running and remain UNRUN.",
        ]
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic C01 no-writer check or bounded writer seam."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check-sources", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check-a11y-receipt", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--register-as-of", type=_parse_date, default=_DEFAULT_REGISTER_AS_OF)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--write-generated-reference", action="store_true")
    parser.add_argument("--corruption-probes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report: dict[str, object] = {
        "verdict": "UNRUN",
        "declared_outputs": [],
        "write_set": [],
        "issue_codes": [],
        "write_attempted": False,
        "write_set_complete": True,
    }
    exit_code = 2
    complete_verdict = False
    finding_coverage = "partial coverage; deciding run UNRUN"
    inspection_stage = "compile_live_sources"
    with measure_file_reads(args.repo_root) as reads:
        try:
            inspection_stage = "compile_live_sources"
            register, payload = compile_claim_posture_register(
                args.repo_root,
                register_as_of=args.register_as_of,
            )
            report = _report(register)
            report["write_attempted"] = False
            report["write_set_complete"] = True
            if args.write:
                inspection_stage = "write_generated_outputs"
                target_root = (args.output_root or args.repo_root).resolve()
                declared_outputs = [_OUTPUT_PATH.as_posix()]
                if args.write_generated_reference:
                    declared_outputs.append(_GENERATED_REFERENCE_PATH.as_posix())
                report["declared_outputs"] = declared_outputs
                report["write_attempted"] = True
                report["write_set_complete"] = False
                target = write_claim_posture_register(register, output_root=target_root)
                report["write_set"] = [target.relative_to(target_root).as_posix()]
                if args.write_generated_reference:
                    reference = write_generated_reference(args.repo_root, output_root=target_root)
                    report["write_set"].append(reference.relative_to(target_root).as_posix())
                report["write_set_complete"] = True
            elif args.check:
                target_root = args.repo_root.resolve()
                target = target_root / _OUTPUT_PATH
                inspection_stage = "generated_artifact_presence"
                if not _admitted_is_file(
                    target,
                    target_root,
                    code="DS11-GENERATED-DRIFT",
                    stage="generated_artifact_containment",
                    label="generated posture artifact",
                ):
                    raise _PosturePredicateError(
                        "DS11-GENERATED-DRIFT",
                        "generated posture artifact is absent",
                        stage="generated_artifact_presence",
                        finding_coverage=(
                            "complete declared freshness check: required generated output is absent"
                        ),
                    )
                inspection_stage = "generated_artifact_byte_read"
                if (
                    _admitted_read_bytes(
                        target,
                        target_root,
                        code="DS11-GENERATED-DRIFT",
                        stage="generated_artifact_byte_read",
                        label="generated posture artifact",
                    )
                    != payload
                ):
                    raise _PosturePredicateError(
                        "DS11-GENERATED-DRIFT",
                        "generated posture artifact differs from live compilation",
                        stage="generated_artifact_byte_equality",
                        finding_coverage=(
                            "complete declared freshness check through byte comparison; "
                            "the generated output is stale"
                        ),
                    )
            elif args.corrupt_field_drift_check:
                inspection_stage = "corruption_probe"
                if not run_corruption_probe(
                    "extra_field", repo_root=args.repo_root, register_as_of=args.register_as_of
                ):
                    raise _PosturePredicateError(
                        "DS11-CORRUPTION-PROBE-FAIL",
                        "corruption probe did not reject the artifact",
                        stage="corruption_probe",
                        finding_coverage=(
                            "complete declared corruption-probe check; an invalid artifact was accepted"
                        ),
                    )
            elif args.check_a11y_receipt:
                inspection_stage = "page_accessibility_receipt"
                derive_page_a11y_receipt(args.repo_root)
            if args.corruption_probes:
                if not args.check:
                    parser.error("--corruption-probes requires --check")
                corruption = run_corruption_probes(
                    repo_root=args.repo_root,
                    register_as_of=args.register_as_of,
                )
                report["corruption_probes"] = corruption
                if (
                    corruption["probe_count"] != len(_CORRUPTION_REASON_CODES)
                    or corruption["rejected_count"] != len(_CORRUPTION_REASON_CODES)
                    or corruption["scratch_escape_count"] != 0
                ):
                    raise _PosturePredicateError(
                        "DS11-CORRUPTION-PROBE-WAVE-FAIL",
                        "DS11 corruption probe wave escaped its semantic boundary",
                        stage="corruption_probe_wave",
                        finding_coverage=(
                            "complete declared corruption-probe wave; one or more expected "
                            "rejections or scratch bounds failed"
                        ),
                    )
            if args.write_generated_reference and not args.write:
                parser.error("--write-generated-reference requires --write")
        except _PosturePredicateError as error:
            report["verdict"] = "FAIL"
            report["failure_code"] = error.code
            report["error"] = f"{error.code}: {error}"
            report["failure_stage"] = error.stage
            exit_code = 1
            complete_verdict = True
            finding_coverage = error.finding_coverage
        except _PostureInspectionError as error:
            report["verdict"] = "UNRUN"
            report["failure_stage"] = error.stage
            report["unrun_code"] = "DS11-INSPECTION-INCOMPLETE"
            report["error"] = f"{type(error).__name__}: {error}"
            finding_coverage = (
                f"inspection incomplete at {error.stage}; no verdict predicate was established"
            )
            exit_code = 2
        except (OSError, ValueError, SyntaxError) as error:
            report["verdict"] = "UNRUN"
            report["failure_stage"] = inspection_stage
            report["unrun_code"] = "DS11-INSPECTION-INCOMPLETE"
            report["error"] = f"{type(error).__name__}: {error}"
            finding_coverage = (
                f"inspection incomplete at {inspection_stage}; no verdict predicate was established"
            )
            exit_code = 2
        except Exception as error:
            # A valid invocation that cannot be inspected gets a typed UNRUN result,
            # never an uncaught traceback in place of the instrument verdict.
            report["verdict"] = "UNRUN"
            report["failure_stage"] = inspection_stage
            report["unrun_code"] = "DS11-INSPECTION-INCOMPLETE"
            report["error"] = f"{type(error).__name__}: {error}"
            finding_coverage = (
                f"inspection incomplete at {inspection_stage}; no verdict predicate was established"
            )
            exit_code = 2
        else:
            report["verdict"] = "PASS"
            exit_code = 0
            complete_verdict = True
            finding_coverage = (
                "complete declared check over selected schema/source and evidence bindings"
            )
        finally:
            report["measurement"] = _measurement_receipt(
                reads,
                complete_verdict=complete_verdict,
                finding_coverage=finding_coverage,
            )
            if args.json:
                json.dump(
                    report, sys.stdout, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                sys.stdout.write("\n")
            else:
                print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
