"""Independent tokenizer, reconciliation, and checker for DS11 claim posture."""

from __future__ import annotations

import argparse
import codecs
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import yaml

from polisyos.scientist.evidence.claims.posture import (
    CUSTODY_APPOINTMENT_CONTRACT,
    CUSTODY_APPOINTMENT_DEBT_IDS,
    CUSTODY_APPOINTMENT_SOURCE_PATH,
    RATIFIED_IDENTITY_CONTENT_DIGEST,
    AccessibilityDocumentBinding,
    AccessibilityEvidenceKind,
    AccessibilityPurpose,
    AdmittedSourceMember,
    AdmittedVerifier,
    AntiRoleBinding,
    ClaimPostureRegisterV1,
    ClaimPostureRow,
    ClaimPostureState,
    ClaimSourceBinding,
    CustodyAppointmentSource,
    DocumentProjectionIndex,
    EstablishmentClass,
    EvidenceBinding,
    GeneratedFamilyBinding,
    IdentityBoundaryBinding,
    LiteralSite,
    OwnerBinding,
    PageA11yFailureBinding,
    PageA11yReceiptBinding,
    ProducerPostureMetadata,
    ReconciledSourceDerivation,
    ResolvedDocumentBinding,
    SourceClaimState,
    SourceCoordinate,
    SourceDerivation,
    SourceDerivationReceipt,
    SourceInventoryRole,
    SourceInventoryRow,
    SourceResolution,
    SupportPredicate,
    build_posture_register,
    canonical_register_bytes,
    derive_admitted_verifiers,
    validate_posture_register,
)
from tools.quality.validation.trust_claim_posture_sources import (
    compile_source_claim_bindings,
    derive_ast_sources,
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
_DEFAULT_REGISTER_AS_OF = date(2026, 8, 26)
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


@dataclass(frozen=True)
class CustodyAppointment:
    """One accepted owner/closure appointment derived from the debt register."""

    debt_id: str
    owner: str
    closure_signal: str
    source_ref: str
    line: int
    source_content: str


def derive_token_sources(repo_root: Path) -> SourceDerivation:
    """Independently walk and derive source facts with :mod:`tokenize` only."""
    root = repo_root.resolve()
    source_root = (root / "src").resolve()
    if not source_root.is_dir() or not source_root.is_relative_to(root):
        raise ValueError("repo_root/src must be a contained directory")
    members: list[AdmittedSourceMember] = []
    rows: list[SourceInventoryRow] = []
    denied_raw_members: list[AdmittedSourceMember] = []
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
            denied_raw_members.append(member)
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
        raise ValueError("may_not_use_for derivations disagree at " + ", ".join(coordinates))
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
    path = (repo_root.resolve() / _IDENTITY_PATH).resolve()
    if not path.is_relative_to(repo_root.resolve()) or not path.is_file():
        raise ValueError("ratified identity document is missing or outside repo_root")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body = _split_frontmatter(text)
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError("ratified identity frontmatter is malformed")
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
        raise ValueError("ratified identity authority frontmatter is incomplete")
    identity_section = re.search(
        r"## 1\. The decision in one sentence\s+(.+?)\s+## 2\.",
        body,
        flags=re.DOTALL,
    )
    if identity_section is None:
        raise ValueError("ratified system-identity statement is absent")
    identity_statements = re.findall(r"\*\*(.+?)\*\*", identity_section.group(1), re.DOTALL)
    if len(identity_statements) != 1:
        raise ValueError("ratified system-identity statement is ambiguous")
    identity_statement = identity_statements[0]
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
    identity_start = (
        body[: identity_section.start(1)].count("\n") + text[: text.index(body)].count("\n") + 1
    )
    identity_end = identity_start + identity_section.group(1).count("\n")
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


def derive_custody_appointments(
    repo_root: Path,
) -> tuple[CustodyAppointment, ...]:
    """Derive the three accepted custody appointments from admitted debt rows."""
    root = repo_root.resolve()
    path = (root / _DEBT_REGISTER_PATH).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        raise ValueError("custody appointment debt source is missing or outside repo_root")
    raw = path.read_bytes()
    required_ids = set(CUSTODY_APPOINTMENT_DEBT_IDS)
    found: dict[str, CustodyAppointment] = {}
    for line_number, raw_line in enumerate(raw.splitlines(), 1):
        line = raw_line.decode("utf-8")
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            continue
        ids = re.findall(r"`([^`]+)`", cells[0])
        if len(ids) != 1 or ids[0] not in required_ids:
            continue
        debt_id = ids[0]
        if debt_id in found:
            raise ValueError(f"custody appointment {debt_id} is duplicated")
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
        if len(owners) != 1 or statuses != ["open"] or len(commands) != 1:
            raise ValueError(f"custody appointment {debt_id} is not exactly appointed and open")
        if (owners[0], commands[0]) != CUSTODY_APPOINTMENT_CONTRACT[debt_id]:
            raise ValueError("custody appointment source differs from the accepted contract")
        found[debt_id] = CustodyAppointment(
            debt_id=debt_id,
            owner=owners[0],
            closure_signal=commands[0],
            source_ref=(
                f"{_DEBT_REGISTER_PATH.as_posix()}#{debt_id}@sha256:"
                f"{hashlib.sha256(raw_line).hexdigest()}"
            ),
            line=line_number,
            source_content=line,
        )
    if set(found) != required_ids:
        raise ValueError("custody appointment debt source is incomplete")
    appointments = tuple(sorted(found.values(), key=lambda item: item.debt_id))
    return appointments


def derive_accessibility_document(repo_root: Path) -> AccessibilityDocumentBinding:
    """Resolve the strict accessibility projection index against complete body bytes."""
    root = repo_root.resolve()
    path = (root / _A11Y_PATH).resolve()
    if not path.is_file() or not path.is_relative_to(root):
        raise ValueError("accessibility document is missing or outside repo_root")
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    frontmatter, body = _split_frontmatter(text)
    loaded = yaml.safe_load(frontmatter)
    if not isinstance(loaded, dict) or set(loaded) != {"ds11_projection_index"}:
        raise ValueError("accessibility frontmatter must contain only ds11_projection_index")
    index = DocumentProjectionIndex.model_validate(loaded["ds11_projection_index"])
    body_bytes = body.encode("utf-8")
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    if index.body_sha256 != body_sha:
        raise ValueError("accessibility body digest differs from projection index")
    required_keys = {
        key
        for purpose in (*index.authoritative_for, *index.may_not_use_for)
        for key in purpose.basis
    }
    if not required_keys or not required_keys <= set(index.bindings):
        raise ValueError("accessibility projection basis names an unresolved binding")
    resolved: list[ResolvedDocumentBinding] = []
    for key, selector in sorted(index.bindings.items()):
        exact = selector.exact_text.encode("utf-8")
        if body_bytes.count(exact) != selector.occurrence:
            raise ValueError(f"accessibility selector {key} is absent or duplicated in body")
        start = body_bytes.index(exact)
        if selector.value.encode("utf-8") not in exact:
            raise ValueError(f"accessibility selector {key} does not bind its declared value")
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
        raise ValueError("accessibility source_as_of binding is absent")
    limitation = "It does not replace the planned third-party countersign."
    limitation_occurrences = sum(
        " ".join(paragraph.split()).count(limitation) for paragraph in re.split(r"\n[ \t]*\n", body)
    )
    if limitation_occurrences != 1:
        raise ValueError("accessibility limitation is absent or duplicated")
    return AccessibilityDocumentBinding(
        path=_A11Y_PATH.as_posix(),
        source_content=text,
        content_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
        frontmatter_digest="sha256:" + hashlib.sha256(frontmatter.encode()).hexdigest(),
        body_digest="sha256:" + body_sha,
        source_as_of=date.fromisoformat(source_selector.value),
        bindings=tuple(resolved),
        authoritative_for=index.authoritative_for,
        may_not_use_for=index.may_not_use_for,
        limitation_refs=(limitation,),
    )


def derive_page_a11y_receipt(repo_root: Path) -> PageA11yReceiptBinding:
    """Recompute the historical page-a11y receipt from its five admitted JSON files."""
    root = repo_root.resolve()
    receipt_root = (root / _PAGE_RECEIPT_PATH).resolve()
    expected = (
        Path("environment-after.json"),
        Path("environment-before.json"),
        Path("receipt.json"),
        Path("run-1/.last-run.json"),
        Path("run-1/results.json"),
    )
    files = tuple((receipt_root / item).resolve() for item in expected)
    if any(not item.is_file() or not item.is_relative_to(receipt_root) for item in files):
        raise ValueError("page-a11y receipt must contain all five admitted files")
    raw_by_name = {
        name.as_posix(): path.read_bytes() for name, path in zip(expected, files, strict=True)
    }
    admitted = tuple(
        AdmittedSourceMember(
            path=(_PAGE_RECEIPT_PATH / name).as_posix(),
            content_digest="sha256:" + hashlib.sha256(raw_by_name[name.as_posix()]).hexdigest(),
        )
        for name in expected
    )
    normalized = json.loads(raw_by_name["receipt.json"])
    expected_authority_metadata = {
        "schema_version": "policyos.ds11.page_a11y_base_receipt.v1",
        "authority_purpose": "historical_currentness_limitation",
        "status": "blocked",
        "execution_entry_commit": "8e5832bbdb0f206b6221112f4a1502b45981bd40",
        "policy_source_base_commit": "f935e0c2e9359bc1202ce5d36ea706de58f7aaab",
        "command": "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm "
        "--filter @polisyos/runtime-dashboard exec playwright test e2e/a11y "
        "--project=chromium --reporter=json",
    }
    if {
        key: normalized.get(key) for key in expected_authority_metadata
    } != expected_authority_metadata:
        raise ValueError(
            "page-a11y authority/base/command metadata differs from the admitted basis"
        )
    results = json.loads(raw_by_name["run-1/results.json"])
    last_run = json.loads(raw_by_name["run-1/.last-run.json"])
    for name in ("environment-before.json", "environment-after.json"):
        environment = json.loads(raw_by_name[name])
        if not isinstance(environment, dict) or not {
            "captured_at",
            "node",
            "platform",
            "arch",
            "cwd",
        } <= set(environment):
            raise ValueError("page-a11y environment receipt is malformed")
    identities, failures = _derive_page_result_rows(results.get("suites", ()))
    stats = results.get("stats", {})
    observed = {
        "collected": len(identities),
        "passed": sum(item[1] == "passed" for item in identities),
        "failed": sum(item[1] == "failed" for item in identities),
        "skipped": sum(item[1] == "skipped" for item in identities),
        "duration_ms": stats.get("duration"),
        "exit_code": 1 if failures else 0,
    }
    authored_identities = tuple(
        (item["identity"], item["status"]) for item in normalized.get("collected_identities", ())
    )
    authored_failures = tuple(
        (item["identity"], item["status"])
        for item in normalized.get("inherited_failure_identities", ())
    )
    if normalized.get("result") != observed or authored_identities != identities:
        raise ValueError("page-a11y receipt result/identity differs from recomputation")
    if authored_failures != tuple((item.identity, "failed") for item in failures):
        raise ValueError("page-a11y receipt failure identities differ from recomputation")
    raw_receipts = normalized.get("raw_receipts", {})
    if (
        raw_receipts.get("results_sha256")
        != hashlib.sha256(raw_by_name["run-1/results.json"]).hexdigest()
    ):
        raise ValueError("page-a11y results receipt digest differs")
    if (
        raw_receipts.get("last_run_sha256")
        != hashlib.sha256(raw_by_name["run-1/.last-run.json"]).hexdigest()
    ):
        raise ValueError("page-a11y last-run receipt digest differs")
    failure_ids = {item.test_id for item in failures}
    if last_run.get("status") != "failed" or set(last_run.get("failedTests", ())) != failure_ids:
        raise ValueError("page-a11y last-run failures differ from results")
    replay = normalized.get("replay_agreement", {})
    if replay.get("admissibility") != "not_established" or replay.get("committed_raw_runs") != 1:
        raise ValueError("page-a11y replay receipt overstates establishment")
    return PageA11yReceiptBinding(
        **expected_authority_metadata,
        path=_PAGE_RECEIPT_PATH.as_posix(),
        source_contents={
            (_PAGE_RECEIPT_PATH / Path(name)).as_posix(): raw.decode("utf-8")
            for name, raw in raw_by_name.items()
        },
        content_digest="sha256:" + hashlib.sha256(raw_by_name["receipt.json"]).hexdigest(),
        admitted_sources=admitted,
        source_as_of=date.fromisoformat(str(stats["startTime"])[:10]),
        collected=observed["collected"],
        passed=observed["passed"],
        failed=observed["failed"],
        skipped=observed["skipped"],
        duration_ms=float(observed["duration_ms"]),
        exit_code=observed["exit_code"],
        failures=failures,
        replay_establishment=EstablishmentClass.NOT_ESTABLISHED,
        limitation_refs=(str(replay.get("limitation")),),
    )


def _derive_page_result_rows(
    suites: Sequence[Mapping[str, object]],
) -> tuple[tuple[tuple[str, str], ...], tuple[PageA11yFailureBinding, ...]]:
    identities: list[tuple[str, str]] = []
    failures: list[PageA11yFailureBinding] = []
    for suite in suites:
        for spec in suite.get("specs", ()):  # type: ignore[union-attr]
            if not isinstance(spec, dict):
                continue
            identity = f"{spec.get('file')}::{spec.get('title')}"
            for test in spec.get("tests", ()):
                if not isinstance(test, dict):
                    continue
                raw_status = str(test.get("status"))
                status = (
                    "passed"
                    if raw_status == "expected"
                    else "skipped"
                    if raw_status == "skipped"
                    else "failed"
                )
                identities.append((identity, status))
                if status == "failed":
                    message = " ".join(
                        str(result.get("error", {}).get("message", ""))
                        for result in test.get("results", ())
                        if isinstance(result, dict)
                    )
                    failures.append(
                        PageA11yFailureBinding(
                            identity=identity,
                            test_id=str(spec.get("id")),
                            issue_signature=_page_issue_signature(message),
                        )
                    )
        nested = suite.get("suites", ())
        if isinstance(nested, list):
            nested_identities, nested_failures = _derive_page_result_rows(nested)
            identities.extend(nested_identities)
            failures.extend(nested_failures)
    return tuple(identities), tuple(failures)


def _page_issue_signature(message: str) -> str:
    plain = re.sub(r"\x1b\[[0-9;]*m", "", message)
    axe = re.search(r'"id"\s*:\s*"([^"]+)"', plain)
    if axe:
        return f"axe:{axe.group(1)}"
    expected = re.search(r'Expected substring:\s*"(?:link|button) \\"([^"\\]+)\\""', plain)
    if expected:
        return f"accessible_name:{expected.group(1)}"
    raise ValueError("page-a11y failure has no admitted semantic issue signature")


def validate_claim_copy(
    copy: str,
    *,
    source_row: object | None,
    admitted_sources: Sequence[AdmittedSourceMember] = (),
    requested_purpose: str = "capability_claim",
) -> tuple[str, ...]:
    """Require copy to bind a strict, supported, admitted posture object."""
    del copy
    if not isinstance(source_row, (ClaimPostureRow, ClaimSourceBinding)):
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    admitted = {item.path: item.content_digest for item in admitted_sources}
    bindings = (
        source_row.source_bindings if isinstance(source_row, ClaimPostureRow) else (source_row,)
    )
    state = (
        source_row.effective_state
        if isinstance(source_row, ClaimPostureRow)
        else source_row.source_state
    )
    if state != ClaimPostureState.SUPPORTED and state != "supported":
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    if not bindings or any(
        binding.resolution != SourceResolution.RESOLVED
        or admitted.get(binding.coordinate.path) != binding.content_digest
        or requested_purpose not in binding.authoritative_for
        or requested_purpose in binding.may_not_use_for
        for binding in bindings
    ):
        return ("DS11-IDENTITY-COPY-UNBOUND",)
    return ()


def evaluate_accessibility_evidence(
    *,
    evidence_kind: str,
    requested_purpose: str,
    source_as_of: date,
    countersign_ref: str | None,
    register_as_of: date = date(2026, 8, 26),
) -> AccessibilityEvaluation:
    """Prevent internal historical evidence from minting current certification."""
    issues: set[str] = set()
    try:
        kind = AccessibilityEvidenceKind(evidence_kind)
    except ValueError:
        kind = None
        issues.add("DS11-A11Y-EVIDENCE-KIND-UNKNOWN")
    try:
        purpose = AccessibilityPurpose(requested_purpose)
    except ValueError:
        purpose = None
        issues.add("DS11-A11Y-PURPOSE-UNKNOWN")
    if source_as_of > register_as_of or register_as_of - source_as_of > timedelta(days=365):
        issues.add("DS11-A11Y-EVIDENCE-STALE")
    external = purpose in {
        AccessibilityPurpose.EXTERNAL_CERTIFICATION,
        AccessibilityPurpose.CURRENT_CONFORMANCE,
    }
    if external and (
        kind != AccessibilityEvidenceKind.EXTERNAL_COUNTERSIGNED_AUDIT or not countersign_ref
    ):
        issues.add("DS11-A11Y-CERTIFICATION-NOT-EARNED")
    if purpose == AccessibilityPurpose.HISTORICAL_INTERNAL_PRE_AUDIT and kind not in {
        AccessibilityEvidenceKind.INTERNAL_PRE_AUDIT,
        AccessibilityEvidenceKind.EXTERNAL_COUNTERSIGNED_AUDIT,
    }:
        issues.add("DS11-A11Y-EVIDENCE-NOT-ADMITTED")
    return AccessibilityEvaluation(
        state=ClaimPostureState.BLOCKED if issues else ClaimPostureState.SUPPORTED,
        issue_codes=tuple(sorted(issues)),
    )


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


def _semantic_predicates(
    *,
    satisfied: set[str],
    evidence_refs: tuple[str, ...],
) -> tuple[SupportPredicate, ...]:
    issues = {
        "content_bound_source": "DS11-SOURCE-CONTENT-NOT-BOUND",
        "purpose_permission": "DS11-AUTHORITY-PURPOSE-DENIED",
        "accountable_owner": "DS11-OWNER-NOT-ESTABLISHED",
        "applicable_jurisdiction": "DS11-JURISDICTION-NOT-ESTABLISHED",
        "current_review": "DS11-REVIEW-MISSING-OR-STALE",
        "content_bound_evidence": "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
        "identity_boundary": "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
        "no_blocker": "DS11-SOURCE-BLOCKER-PRESENT",
    }
    return tuple(
        SupportPredicate(
            kind=kind,
            satisfied=kind in satisfied,
            establishment_class=(
                EstablishmentClass.RECOMPUTED
                if kind in satisfied
                else EstablishmentClass.NOT_ESTABLISHED
            ),
            evidence_refs=evidence_refs if kind in satisfied else (),
            issue_code=None if kind in satisfied else issues[kind],
        )
        for kind in sorted(issues)
    )


def _semantic_evidence(
    *,
    subject: str,
    verifier: AdmittedVerifier,
    source_as_of: date,
    establishment_class: EstablishmentClass = EstablishmentClass.RECOMPUTED,
) -> EvidenceBinding:
    return EvidenceBinding(
        ref=verifier.content_ref,
        content_digest=verifier.content_digest,
        subject_binding=subject,
        verifier_ref=verifier.ref,
        verifier_provenance_ref=verifier.provenance_ref,
        establishment_class=establishment_class,
        source_as_of=source_as_of,
        supersession_ref=None,
    )


def _semantic_binding(
    *,
    coordinate: SourceCoordinate,
    content_digest: str,
    source_state: SourceClaimState,
    subject: str,
    family: str,
    authoritative_for: tuple[str, ...],
    may_not_use_for: tuple[str, ...],
    owner: OwnerBinding,
    jurisdiction: str | None,
    jurisdiction_establishment: EstablishmentClass,
    review_on: date | None,
    review_due: date | None,
    source_as_of: date | None,
    evidence: EvidenceBinding | None,
    limitation_refs: tuple[str, ...],
    prerequisite_refs: tuple[str, ...] = (),
    closure_signal: str | None = None,
    predicate_facts: set[str] | None = None,
) -> ClaimSourceBinding:
    evidence_bindings = () if evidence is None else (evidence,)
    evidence_refs = () if evidence is None else (evidence.ref,)
    return ClaimSourceBinding(
        coordinate=coordinate,
        content_digest=content_digest,
        resolution=SourceResolution.RESOLVED,
        source_state=source_state,
        subject=subject,
        family=family,
        authoritative_for=authoritative_for,
        may_not_use_for=may_not_use_for,
        authority_purpose=subject,
        owner=owner,
        jurisdiction=jurisdiction,
        jurisdiction_establishment=jurisdiction_establishment,
        review_on=review_on,
        review_due=review_due,
        source_as_of=source_as_of,
        evidence_refs=evidence_refs,
        evidence_bindings=evidence_bindings,
        limitation_refs=limitation_refs,
        prerequisite_refs=prerequisite_refs,
        identity_boundary_ref=_IDENTITY_PATH.as_posix(),
        declared_scope_assumption=None,
        supersedes_ref=None,
        superseded_by_ref=None,
        predicates=_semantic_predicates(
            satisfied=predicate_facts or set(),
            evidence_refs=evidence_refs,
        ),
        closure_signal=closure_signal,
    )


def _compile_semantic_bindings(
    *,
    identity: IdentityBoundaryBinding,
    custody_appointments: Sequence[CustodyAppointment],
    accessibility_document: AccessibilityDocumentBinding | None,
    page_receipt: PageA11yReceiptBinding | None,
) -> tuple[ClaimSourceBinding, ...]:
    """Produce the fixed C02 posture rows from admitted typed facts."""
    verifiers = derive_admitted_verifiers(
        identity_boundary=identity,
        accessibility_document=accessibility_document,
        page_a11y_receipt=page_receipt,
    )
    verifier_by_kind = {item.verifier_kind: item for item in verifiers}
    identity_verifier = verifier_by_kind["identity_boundary_derivation"]
    identity_coordinate = SourceCoordinate(
        path=identity.path,
        symbol="ratified_system_identity",
        line=identity.identity_statement_start_line,
        column=0,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    identity_owner = OwnerBinding(
        owner=identity.owner,
        basis="ratified_document",
        source_ref=identity.path,
        establishment_class=EstablishmentClass.RECOMPUTED,
    )
    identity_is_exact_ratified_source = identity.content_digest == RATIFIED_IDENTITY_CONTENT_DIGEST
    review_due = identity.last_reviewed + timedelta(days=365)
    complete_facts = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "applicable_jurisdiction",
        "current_review",
        "content_bound_evidence",
        "identity_boundary",
        "no_blocker",
    }
    identity_evidence = _semantic_evidence(
        subject="system_identity",
        verifier=identity_verifier,
        source_as_of=identity.last_reviewed,
        establishment_class=EstablishmentClass.INDEPENDENTLY_RECONCILED,
    )
    bindings: list[ClaimSourceBinding] = [
        _semantic_binding(
            coordinate=identity_coordinate,
            content_digest=identity.content_digest,
            source_state=(
                SourceClaimState.SUPPORTED
                if identity_is_exact_ratified_source
                else SourceClaimState.BLOCKED
            ),
            subject="system_identity",
            family="methodology",
            authoritative_for=identity.authoritative_for,
            may_not_use_for=identity.may_not_use_for,
            owner=identity_owner,
            jurisdiction="non_jurisdiction_specific",
            jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
            review_on=identity.last_reviewed,
            review_due=review_due,
            source_as_of=identity.last_reviewed,
            evidence=identity_evidence,
            limitation_refs=(
                "Bounded to non-jurisdiction-specific system identity."
                if identity_is_exact_ratified_source
                else "System identity source differs from the ratified byte boundary.",
            ),
            predicate_facts=(
                complete_facts
                if identity_is_exact_ratified_source
                else complete_facts - {"no_blocker"}
            ),
        )
    ]

    custody_facts = {
        "content_bound_source",
        "purpose_permission",
        "accountable_owner",
        "identity_boundary",
    }
    for appointment in custody_appointments:
        bindings.append(
            _semantic_binding(
                coordinate=identity_coordinate,
                content_digest=identity.content_digest,
                source_state=(
                    SourceClaimState.PLANNED
                    if identity_is_exact_ratified_source
                    else SourceClaimState.BLOCKED
                ),
                subject="universal_custody_commitment",
                family="custody",
                authoritative_for=("universal_custody_commitment",),
                may_not_use_for=identity.may_not_use_for,
                owner=OwnerBinding(
                    owner=appointment.owner,
                    basis="closure_commitment",
                    source_ref=appointment.source_ref,
                    establishment_class=EstablishmentClass.RECOMPUTED,
                ),
                jurisdiction="non_jurisdiction_specific",
                jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
                review_on=identity.last_reviewed,
                review_due=review_due,
                source_as_of=identity.last_reviewed,
                evidence=None,
                limitation_refs=(f"Planned prerequisite: {appointment.debt_id}",),
                prerequisite_refs=(appointment.debt_id,),
                closure_signal=appointment.closure_signal,
                predicate_facts=custody_facts,
            )
        )

    unavailable_digest = "sha256:" + "0" * 64
    a11y_path = _A11Y_PATH.as_posix()
    a11y_coordinate = SourceCoordinate(
        path=a11y_path,
        symbol="ds11_projection_index",
        line=1,
        column=0,
        field_name="authoritative_for",
        use_kind="declaration",
    )
    if accessibility_document is not None:
        selector_values = {item.key: item.value for item in accessibility_document.bindings}
        a11y_owner = OwnerBinding(
            owner=selector_values.get("assessment_owner"),
            basis="ratified_document",
            source_ref=accessibility_document.path,
            establishment_class=EstablishmentClass.RECOMPUTED,
        )
        a11y_verifier = verifier_by_kind["accessibility_document_derivation"]
        historical_evidence = _semantic_evidence(
            subject="historical_internal_accessibility_pre_audit",
            verifier=a11y_verifier,
            source_as_of=accessibility_document.source_as_of,
        )
        a11y_authoritative = tuple(
            item.purpose for item in accessibility_document.authoritative_for
        )
        a11y_denied = tuple(item.purpose for item in accessibility_document.may_not_use_for)
        historical_facts = complete_facts - {"applicable_jurisdiction"}
        a11y_digest = accessibility_document.content_digest
        a11y_source_as_of = accessibility_document.source_as_of
        a11y_review_due = accessibility_document.source_as_of + timedelta(days=365)
    else:
        a11y_owner = OwnerBinding(
            owner=None,
            basis="not_established",
            source_ref=None,
            establishment_class=EstablishmentClass.NOT_ESTABLISHED,
        )
        historical_evidence = None
        a11y_authoritative = ()
        a11y_denied = (
            "current_accessibility_conformance",
            "external_accessibility_certification",
        )
        historical_facts = {"identity_boundary"}
        a11y_digest = unavailable_digest
        a11y_source_as_of = None
        a11y_review_due = None
    bindings.append(
        _semantic_binding(
            coordinate=a11y_coordinate,
            content_digest=a11y_digest,
            source_state=(
                SourceClaimState.SUPPORTED
                if accessibility_document is not None
                else SourceClaimState.BLOCKED
            ),
            subject="historical_internal_accessibility_pre_audit",
            family="accessibility",
            authoritative_for=a11y_authoritative,
            may_not_use_for=a11y_denied,
            owner=a11y_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=a11y_source_as_of,
            review_due=a11y_review_due,
            source_as_of=a11y_source_as_of,
            evidence=historical_evidence,
            limitation_refs=(
                "Historical internal pre-audit only; jurisdiction is not established."
                if accessibility_document is not None
                else "Accessibility document projection basis is unavailable.",
            ),
            predicate_facts=historical_facts,
        )
    )

    if page_receipt is not None:
        current_evidence = None
        receipt_path = f"{page_receipt.path}/receipt.json"
        current_coordinate = a11y_coordinate.model_copy(
            update={"path": receipt_path, "symbol": "page_a11y_receipt"}
        )
        current_digest = page_receipt.content_digest
        current_date = page_receipt.source_as_of
    else:
        current_evidence = None
        current_coordinate = a11y_coordinate
        current_digest = unavailable_digest
        current_date = None
    blocked_owner = OwnerBinding(
        owner="team-design",
        basis="closure_commitment",
        source_ref=identity.path,
        establishment_class=EstablishmentClass.RECOMPUTED,
    )
    bindings.append(
        _semantic_binding(
            coordinate=current_coordinate,
            content_digest=current_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="current_accessibility_conformance",
            family="accessibility",
            authoritative_for=("historical_page_accessibility_result",),
            may_not_use_for=("current_accessibility_conformance",),
            owner=blocked_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=current_date,
            review_due=current_date,
            source_as_of=current_date,
            evidence=current_evidence,
            limitation_refs=(
                "Current accessibility conformance is blocked by the admitted failing page suite."
                if page_receipt is not None
                else "Current page-accessibility evidence is unavailable.",
            ),
            predicate_facts={"identity_boundary"},
        )
    )
    bindings.append(
        _semantic_binding(
            coordinate=a11y_coordinate,
            content_digest=a11y_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="external_accessibility_certification",
            family="accessibility",
            authoritative_for=a11y_authoritative,
            may_not_use_for=tuple(sorted({*a11y_denied, "external_accessibility_certification"})),
            owner=blocked_owner,
            jurisdiction=None,
            jurisdiction_establishment=EstablishmentClass.NOT_ESTABLISHED,
            review_on=a11y_source_as_of,
            review_due=a11y_review_due,
            source_as_of=a11y_source_as_of,
            evidence=None,
            limitation_refs=("External accessibility countersign is absent.",),
            prerequisite_refs=("DS11-EXTERNAL-A11Y-COUNTERSIGN",),
            predicate_facts={"identity_boundary"},
        )
    )
    bindings.append(
        _semantic_binding(
            coordinate=identity_coordinate,
            content_digest=identity.content_digest,
            source_state=SourceClaimState.BLOCKED,
            subject="grounded_performance",
            family="grounded_performance",
            authoritative_for=(),
            may_not_use_for=("grounded_performance",),
            owner=OwnerBinding(
                owner="team-runtime",
                basis="closure_commitment",
                source_ref=identity.path,
                establishment_class=EstablishmentClass.RECOMPUTED,
            ),
            jurisdiction="non_jurisdiction_specific",
            jurisdiction_establishment=EstablishmentClass.RECOMPUTED,
            review_on=identity.last_reviewed,
            review_due=review_due,
            source_as_of=identity.last_reviewed,
            evidence=None,
            limitation_refs=("No governed grounded-performance evidence is admitted.",),
            predicate_facts={
                "content_bound_source",
                "accountable_owner",
                "applicable_jurisdiction",
                "current_review",
                "identity_boundary",
            },
        )
    )
    return tuple(bindings)


def compile_claim_posture_register(
    repo_root: Path,
    *,
    register_as_of: date = _DEFAULT_REGISTER_AS_OF,
) -> tuple[ClaimPostureRegisterV1, bytes]:
    """Compile, reconcile, assemble, validate, and canonically serialize live sources."""
    root = repo_root.resolve()
    ast_result = derive_ast_sources(root)
    token_result = derive_token_sources(root)
    reconciled = reconcile_source_derivations(ast_result, token_result)
    identity = derive_identity_boundary(root)
    custody_appointments = derive_custody_appointments(root)
    source_bindings = compile_source_claim_bindings(reconciled, package_owners={})
    identity_member = AdmittedSourceMember(
        path=identity.path,
        content_digest=identity.content_digest,
    )
    accessibility_document = None
    accessibility_members: tuple[AdmittedSourceMember, ...] = ()
    accessibility_path = root / _A11Y_PATH
    if accessibility_path.is_file() and accessibility_path.read_bytes().startswith(b"---\n"):
        accessibility_document = derive_accessibility_document(root)
        accessibility_members = (
            AdmittedSourceMember(
                path=accessibility_document.path,
                content_digest=accessibility_document.content_digest,
            ),
        )
    page_receipt = None
    page_members: tuple[AdmittedSourceMember, ...] = ()
    if (root / _PAGE_RECEIPT_PATH).is_dir():
        page_receipt = derive_page_a11y_receipt(root)
        page_members = page_receipt.admitted_sources
    semantic_bindings = _compile_semantic_bindings(
        identity=identity,
        custody_appointments=custody_appointments,
        accessibility_document=accessibility_document,
        page_receipt=page_receipt,
    )
    register = build_posture_register(
        register_as_of=register_as_of,
        admitted_sources=(
            *reconciled.admitted_sources,
            identity_member,
            *accessibility_members,
            *page_members,
        ),
        ast_derivation=ast_result.receipt,
        token_derivation=token_result.receipt,
        may_not_use_for_denied_only_sites=reconciled.may_not_use_for_denied_only_sites,
        identity_boundary=identity,
        custody_appointment_sources=tuple(
            CustodyAppointmentSource(
                path=CUSTODY_APPOINTMENT_SOURCE_PATH,
                debt_id=item.debt_id,
                source_content=item.source_content,
                content_digest="sha256:"
                + hashlib.sha256(item.source_content.encode("utf-8")).hexdigest(),
            )
            for item in custody_appointments
        ),
        accessibility_document=accessibility_document,
        page_a11y_receipt=page_receipt,
        source_inventory=reconciled.rows,
        source_bindings=(*source_bindings, *semantic_bindings),
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


def validate_generated_family(repo_root: Path) -> GeneratedFamilyBinding:
    """Parse the existing manifest owner and admit only the strict posture family."""
    from tools.devx.architecture import guardrails

    root = repo_root.resolve()
    manifest = (root / _GENERATED_MANIFEST_PATH).resolve()
    if not manifest.is_file() or not manifest.is_relative_to(root):
        raise ValueError("generated-artifact manifest is missing or outside repo_root")
    families = guardrails._parse_generated_artifacts(manifest)
    matches = [item for item in families if item.family_id == "trust-claim-posture-register"]
    if len(matches) != 1:
        raise ValueError("trust posture generated family must appear exactly once")
    family = matches[0]
    outputs = tuple(path.relative_to(guardrails.REPO_ROOT).as_posix() for path in family.outputs)
    probe = family.output_probe_command
    if (
        family.lifecycle != "generated_committed"
        or family.stale_output_behavior != "fail"
        or outputs != (_OUTPUT_PATH.as_posix(),)
        or family.default_freshness_check is not True
        or probe is None
        or sum("{output_root}" in item for item in probe) != 1
        or "--write" not in probe
        or "--output-root" not in probe
        or family.check_git_diff_paths
    ):
        raise ValueError("trust posture generated family violates the strict writer contract")
    return GeneratedFamilyBinding(
        family_id="trust-claim-posture-register",
        lifecycle="generated_committed",
        stale_output_behavior="fail",
        outputs=outputs,
        default_freshness_check=True,
        output_probe_command=probe,
    )


def run_generated_family_output_probe(
    repo_root: Path,
    *,
    source_root: Path,
    output_root: Path,
) -> tuple[str, ...]:
    """Execute the manifest probe in an isolated source and prove exact output bytes."""
    from tools.devx.architecture import guardrails

    family = validate_generated_family(repo_root)
    repo = repo_root.resolve()
    source = source_root.resolve()
    output = output_root.resolve()
    if source.parent != output.parent or source == output:
        raise ValueError("output probe source_root and output_root must be dedicated siblings")
    if source.exists() or output.exists():
        raise ValueError("output probe source_root and output_root must not already exist")
    if source.is_relative_to(repo) or output.is_relative_to(repo):
        raise ValueError("output probe scratch roots must be outside repo_root")

    guardrails._copy_isolated_probe_source(repo, source)
    if (source / ".git").exists():
        raise ValueError("output probe source_root must not contain .git")
    output.mkdir(parents=True)
    temporary_root = output / ".tmp"
    temporary_root.mkdir()

    rendered_command = tuple(
        item.replace("{output_root}", str(output)) for item in family.output_probe_command
    )
    executable_path = os.pathsep.join(
        (str(source / ".venv/bin"), str(Path(sys.executable).parent), "/usr/bin", "/bin")
    )
    if shutil.which(rendered_command[0], path=executable_path) is None:
        raise ValueError(
            f"generated-family output probe executable is unavailable: {rendered_command[0]}"
        )
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": executable_path,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join((str(source / "src"), str(source))),
        "TMPDIR": str(temporary_root),
        "TZ": "UTC",
    }

    scratch_root = source.parent
    output_prefix = output.relative_to(scratch_root).as_posix()

    def outside_output_snapshot() -> dict[str, str]:
        return {
            relative: state
            for relative, state in guardrails._snapshot_filesystem_tree(scratch_root).items()
            if relative != output_prefix and not relative.startswith(f"{output_prefix}/")
        }

    repo_before = guardrails._snapshot_filesystem_tree(repo)
    scratch_before = outside_output_snapshot()
    completed = subprocess.run(  # noqa: S603 - exact trusted manifest argv; no shell.
        rendered_command,
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    repo_changes = guardrails._changed_snapshot_paths(
        repo_before,
        guardrails._snapshot_filesystem_tree(repo),
    )
    scratch_changes = guardrails._changed_snapshot_paths(
        scratch_before,
        outside_output_snapshot(),
    )
    escaped = tuple(sorted({*repo_changes, *(f"scratch/{item}" for item in scratch_changes)}))
    if escaped:
        raise ValueError(
            "generated-family output probe wrote outside output_root: " + ", ".join(escaped)
        )
    if completed.returncode != 0:
        command_output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        raise ValueError(
            "generated-family output probe command failed "
            f"with exit {completed.returncode}: {command_output}"
        )

    observed = tuple(
        sorted(path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file())
    )
    if observed != family.outputs:
        raise ValueError("generated-family output probe differs from declared outputs")
    for relative in observed:
        expected = repo / relative
        candidate = output / relative
        if not expected.is_file():
            raise ValueError(f"generated-family committed artifact is missing: {relative}")
        if candidate.read_bytes() != expected.read_bytes():
            raise ValueError(f"generated-family output differs from committed artifact: {relative}")
    return observed


def write_generated_reference(repo_root: Path, *, output_root: Path | None = None) -> Path:
    """Render only the generated-artifact reference through its existing owner."""
    from tools.devx.architecture import guardrails

    root = repo_root.resolve()
    target_root = (output_root or root).resolve()
    manifest = (root / _GENERATED_MANIFEST_PATH).resolve()
    validate_generated_family(root)
    target = (target_root / _GENERATED_REFERENCE_PATH).resolve()
    if not target.is_relative_to(target_root):
        raise ValueError("generated reference target escapes output_root")
    rendered = guardrails.render_generated_artifacts_markdown(
        guardrails._parse_generated_artifacts(manifest)
    ).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rendered)
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


def run_corruption_probes(
    *,
    repo_root: Path,
    register_as_of: date,
) -> dict[str, object]:
    """Run the closed C05 semantic mutation wave entirely in scratch roots."""
    root = repo_root.resolve()
    before = _bounded_filesystem_snapshot(root)
    register, canonical = compile_claim_posture_register(root, register_as_of=register_as_of)
    outcomes: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="ds11-corruption-") as temporary:
        scratch = Path(temporary).resolve()
        outcomes["planned_to_supported"] = _status_projection_is_rejected(
            register, source_state="planned"
        )
        outcomes["candidate_to_supported"] = _candidate_projection_is_rejected(
            root,
            scratch / "candidate",
            register_as_of=register_as_of,
        )
        outcomes["forbidden_purpose_removal"] = _live_payload_mutation_is_rejected(
            register,
            root,
            _remove_forbidden_purpose,
            register_as_of=register_as_of,
        )
        outcomes["review_refresh_without_evidence"] = _live_payload_mutation_is_rejected(
            register,
            root,
            _refresh_review_without_evidence,
            register_as_of=register_as_of,
        )
        outcomes["source_digest_rebinding"] = _source_digest_rebinding_is_rejected(
            root,
            scratch / "source-rebinding",
            register_as_of=register_as_of,
        )
        outcomes["body_fact_removal"] = _body_fact_removal_is_rejected(root, scratch / "body-fact")
        outcomes["scope_assumption_change"] = _payload_mutation_is_rejected(
            register, _change_scope_assumption
        )
        outcomes["anti_role_removal"] = _anti_role_mutation_is_rejected(
            root, scratch / "anti-role", ", not an executor"
        )
        outcomes["crm_omission"] = _anti_role_mutation_is_rejected(
            root, scratch / "crm", "\nnot a CRM"
        )
        outcomes["manages_your_cases"] = validate_claim_copy(
            "manages your cases", source_row=None
        ) == ("DS11-IDENTITY-COPY-UNBOUND",)
        outcomes["performance_relabel"] = _payload_mutation_is_rejected(
            register, _relabel_as_performance
        )
        outcomes["limitation_omission"] = _payload_mutation_is_rejected(register, _omit_limitation)
        outcomes["row_reorder"] = _payload_mutation_is_rejected(register, _reorder_rows)
        outcomes["machine_reserialization"] = _machine_reserialization_is_rejected(
            register, canonical
        )
        outcomes["dynamic_source_silently_dropped"] = _dynamic_source_drop_is_rejected(
            root,
            scratch / "dynamic",
            register_as_of=register_as_of,
        )
    after = _bounded_filesystem_snapshot(root)
    escaped = sorted(
        path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
    )
    results = []
    for probe_id in sorted(_CORRUPTION_REASON_CODES):
        rejected = outcomes.get(probe_id, False)
        results.append(
            {
                "probe_id": probe_id,
                "outcome": "rejected" if rejected else "escaped",
                "reason_codes": list(_CORRUPTION_REASON_CODES[probe_id]) if rejected else [],
                "declared_outputs": [],
                "write_set": [],
            }
        )
    return {
        "probe_count": len(results),
        "rejected_count": sum(item["outcome"] == "rejected" for item in results),
        "scratch_escape_count": len(escaped),
        "scratch_escape_paths": escaped,
        "results": results,
    }


def _bounded_filesystem_snapshot(root: Path) -> dict[str, str]:
    excluded = {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_build",
        "_cache",
        "node_modules",
        "production_data",
    }
    snapshot: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        if path.is_symlink():
            snapshot[relative.as_posix()] = "link:" + os.readlink(path)
        elif path.is_file():
            snapshot[relative.as_posix()] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return snapshot


def _minimal_probe_repo(
    root: Path,
    source: str,
    *,
    basis_root: Path,
    source_name: str = "probe.py",
) -> Path:
    source_path = root / "src/polisyos" / source_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(source, encoding="utf-8")
    identity = root / _IDENTITY_PATH
    identity.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(basis_root.resolve() / _IDENTITY_PATH, identity)
    debt_register = root / _DEBT_REGISTER_PATH
    debt_register.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(basis_root.resolve() / _DEBT_REGISTER_PATH, debt_register)
    return root


def _payload_with_digest(payload: Mapping[str, object]) -> dict[str, object]:
    rebound = json.loads(json.dumps(payload, ensure_ascii=False))
    unsigned = {key: value for key, value in rebound.items() if key != "payload_digest"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    rebound["payload_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return rebound


def _payload_mutation_is_rejected(
    register: ClaimPostureRegisterV1,
    mutate: Callable[[dict[str, object]], None],
) -> bool:
    payload = register.model_dump(mode="json")
    mutate(payload)
    try:
        validate_posture_register(_payload_with_digest(payload))
    except ValueError:
        return True
    return False


def _live_payload_mutation_is_rejected(
    register: ClaimPostureRegisterV1,
    repo_root: Path,
    mutate: Callable[[dict[str, object]], None],
    *,
    register_as_of: date,
) -> bool:
    payload = register.model_dump(mode="json")
    mutate(payload)
    rebound = _payload_with_digest(payload)
    encoded = (
        json.dumps(rebound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        validate_register_against_live_sources(
            encoded,
            repo_root=repo_root,
            register_as_of=register_as_of,
        )
    except ValueError:
        return True
    return False


def _claim(payload: Mapping[str, object], subject: str) -> dict[str, object]:
    claims = payload.get("claims")
    if not isinstance(claims, list):
        raise ValueError("corruption payload has no claims")
    matches = [item for item in claims if isinstance(item, dict) and item.get("subject") == subject]
    if len(matches) != 1:
        raise ValueError(f"corruption payload requires one {subject} claim")
    return matches[0]


def _status_projection_is_rejected(
    register: ClaimPostureRegisterV1,
    *,
    source_state: str,
) -> bool:
    payload = register.model_dump(mode="json")
    claims = payload["claims"]
    if not isinstance(claims, list):
        return False
    row = next(
        (
            item
            for item in claims
            if isinstance(item, dict)
            and any(
                isinstance(binding, dict) and binding.get("source_state") == source_state
                for binding in item.get("source_bindings", [])
            )
        ),
        None,
    )
    if row is None:
        return False
    row["effective_state"] = "supported"
    try:
        validate_posture_register(_payload_with_digest(payload))
    except ValueError:
        return True
    return False


def _candidate_projection_is_rejected(
    basis_root: Path,
    root: Path,
    *,
    register_as_of: date,
) -> bool:
    repo = _minimal_probe_repo(
        root,
        '"""Candidate posture corruption probe."""\n\n'
        "class CandidateProbe:\n"
        '    authoritative_for = ("candidate_probe",)\n'
        '    may_not_use_for = ("publication_authority",)\n'
        '    trust_claim_posture = {"schema_version": '
        '"policyos.trust.producer_posture.v1", "subject": "candidate_probe", '
        '"source_state": "candidate", "owner": "team-scientist", '
        '"closure_signal": "pytest://candidate_probe"}\n',
        basis_root=basis_root,
    )
    register, _ = compile_claim_posture_register(repo, register_as_of=register_as_of)
    return _status_projection_is_rejected(register, source_state="candidate")


def _remove_forbidden_purpose(payload: dict[str, object]) -> None:
    binding = _claim(payload, "system_identity")["source_bindings"][0]
    binding["may_not_use_for"] = [
        value for value in binding["may_not_use_for"] if value != "capability_claim"
    ]


def _refresh_review_without_evidence(payload: dict[str, object]) -> None:
    row = _claim(payload, "current_accessibility_conformance")
    row["review_on"] = "2026-08-26"
    row["review_due"] = "2027-08-26"
    binding = row["source_bindings"][0]
    binding["review_on"] = "2026-08-26"
    binding["review_due"] = "2027-08-26"


def _change_scope_assumption(payload: dict[str, object]) -> None:
    binding = _claim(payload, "system_identity")["source_bindings"][0]
    binding["declared_scope_assumption"] = "global"


def _relabel_as_performance(payload: dict[str, object]) -> None:
    _claim(payload, "system_identity")["family"] = "grounded_performance"


def _omit_limitation(payload: dict[str, object]) -> None:
    claims = payload["claims"]
    row = next(item for item in claims if item["limitations"])
    row["limitations"] = row["limitations"][1:]


def _reorder_rows(payload: dict[str, object]) -> None:
    payload["claims"] = list(reversed(payload["claims"]))


def _source_digest_rebinding_is_rejected(
    repo_root: Path,
    scratch: Path,
    *,
    register_as_of: date,
) -> bool:
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
    )
    identity = repo / _IDENTITY_PATH
    text = identity.read_text(encoding="utf-8")
    changed = text.replace("across the whole life of a", "throughout the whole life of a", 1)
    if changed == text:
        return False
    identity.write_text(changed, encoding="utf-8")
    try:
        register, _ = compile_claim_posture_register(repo, register_as_of=register_as_of)
    except ValueError:
        return True
    row = next(item for item in register.claims if item.subject == "system_identity")
    return row.effective_state == ClaimPostureState.BLOCKED


def _body_fact_removal_is_rejected(repo_root: Path, scratch: Path) -> bool:
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
    )
    source = repo_root.resolve() / _A11Y_PATH
    target = repo / _A11Y_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    text = target.read_text(encoding="utf-8")
    boundary = text.find("\n---\n", 4)
    if boundary < 0:
        return False
    frontmatter, body = text[: boundary + 5], text[boundary + 5 :]
    mutated = body.replace("- Audit status: Internal pre-audit complete", "", 1)
    if mutated == body:
        return False
    target.write_text(frontmatter + mutated, encoding="utf-8")
    try:
        derive_accessibility_document(repo)
    except ValueError:
        return True
    return False


def _anti_role_mutation_is_rejected(
    repo_root: Path,
    scratch: Path,
    fragment: str,
) -> bool:
    baseline = derive_identity_boundary(repo_root)
    repo = _minimal_probe_repo(
        scratch,
        'class Probe:\n    authoritative_for = ("probe",)\n',
        basis_root=repo_root,
    )
    identity = repo / _IDENTITY_PATH
    text = identity.read_text(encoding="utf-8")
    changed = text.replace(fragment, "", 1)
    if changed == text:
        return False
    identity.write_text(changed, encoding="utf-8")
    try:
        mutated = derive_identity_boundary(repo)
    except ValueError:
        return True
    return tuple(item.role for item in mutated.anti_roles) != tuple(
        item.role for item in baseline.anti_roles
    )


def _machine_reserialization_is_rejected(
    register: ClaimPostureRegisterV1,
    canonical: bytes,
) -> bool:
    reserialized = (json.dumps(register.model_dump(mode="json"), indent=2) + "\n").encode("utf-8")
    return reserialized != canonical and validate_posture_register(reserialized) == register


def _dynamic_source_drop_is_rejected(
    basis_root: Path,
    root: Path,
    *,
    register_as_of: date,
) -> bool:
    repo = _minimal_probe_repo(
        root,
        'subjects = ("dynamic_probe",)\n\n'
        "class DynamicProbe:\n"
        "    authoritative_for = tuple(subjects)\n",
        basis_root=basis_root,
        source_name="dynamic_probe.py",
    )
    register, _ = compile_claim_posture_register(repo, register_as_of=register_as_of)
    path = "src/polisyos/dynamic_probe.py"
    inventory = next((row for row in register.source_inventory if row.path == path), None)
    if inventory is None or inventory.resolution != SourceResolution.RUNTIME_BOUND:
        return False
    payload = register.model_dump(mode="json")
    removed_ids = {
        row["claim_id"]
        for row in payload["claims"]
        if any(binding["coordinate"]["path"] == path for binding in row["source_bindings"])
    }
    payload["source_inventory"] = [
        row for row in payload["source_inventory"] if row["path"] != path
    ]
    payload["claims"] = [row for row in payload["claims"] if row["claim_id"] not in removed_ids]
    for group in payload["projection_groups"]:
        group["claim_ids"] = [
            claim_id for claim_id in group["claim_ids"] if claim_id not in removed_ids
        ]
    rebound = _payload_with_digest(payload)
    encoded = (
        json.dumps(rebound, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    try:
        validate_register_against_live_sources(
            encoded,
            repo_root=repo,
            register_as_of=register_as_of,
        )
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
    producer_metadata = _derive_token_producer_metadata(statements, symbols)
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
                if value_tokens is not None:
                    site = _token_literal_site(
                        coordinate,
                        value_tokens,
                        declaration_form=_token_declaration_form(statement, index),
                    )
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
    _validate_token_producer_metadata_bindings(producer_metadata, authoritative_sites)
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
        producer_metadata=producer_metadata,
        runtime_bound=runtime_bound,
        issue_codes=("DS11-SOURCE-RUNTIME-BOUND",) if runtime_bound else (),
    )


def _derive_token_producer_metadata(
    statements: Sequence[Sequence[tokenize.TokenInfo]],
    symbols: Mapping[int, str | None],
) -> tuple[ProducerPostureMetadata, ...]:
    """Independently derive strict metadata from token structure only."""
    declarations: list[ProducerPostureMetadata] = []
    seen: set[tuple[int, int]] = set()
    admitted: set[tuple[int, int]] = set()
    for statement in statements:
        for index, token in enumerate(statement):
            if token.type != tokenize.NAME or token.string != _PRODUCER_METADATA_FIELD:
                continue
            seen.add(token.start)
            is_declaration, value_tokens = _token_declaration(statement, index)
            if not is_declaration or value_tokens is None:
                continue
            admitted.add(token.start)
            try:
                decoded = _token_literal_mapping(value_tokens)
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


def _token_literal_mapping(tokens: Sequence[tokenize.TokenInfo]) -> dict[str, object]:
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
        key = _decode_string_token(key_token.string) if key_token.type == tokenize.STRING else None
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
            decoded = _decode_string_token(token.string)
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
                    _decode_string_token(item.string) if item.type == tokenize.STRING else None
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


def _token_declaration_form(
    statement: Sequence[tokenize.TokenInfo], index: int
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


def _token_annotation_span(
    statement: Sequence[tokenize.TokenInfo],
) -> tuple[int, int] | None:
    """The annotated-assignment type span, which is syntax rather than semantic evidence.

    ``metrics: dict[str, int | float] = {...}`` carries a PEP 604 union whose ``|`` is type
    syntax, not a set operation. The AST owner never confuses the two because it walks the
    value and never the annotation; the tokenizer has no such structure, so without this
    span every name in such a statement reads as a semantic use and the two derivations
    disagree. Returns ``None`` when the statement is not an annotated assignment.
    """

    if not statement or statement[0].string in _ANNOTATION_EXCLUDED_OPENERS:
        return None
    depths = _token_depths(statement)
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
    annotation = _token_annotation_span(statement)
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
    coordinate: SourceCoordinate,
    tokens: Sequence[tokenize.TokenInfo],
    *,
    declaration_form: Literal["assignment", "keyword", "dict_key"],
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
        declaration_form=declaration_form,
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
    denied_raw_members: Sequence[AdmittedSourceMember],
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
    register, payload = compile_claim_posture_register(
        args.repo_root,
        register_as_of=args.register_as_of,
    )
    report = _report(register)
    if args.write:
        target_root = (args.output_root or args.repo_root).resolve()
        target = write_claim_posture_register(register, output_root=target_root)
        report["declared_outputs"] = [_OUTPUT_PATH.as_posix()]
        report["write_set"] = [target.relative_to(target_root).as_posix()]
        if args.write_generated_reference:
            reference = write_generated_reference(args.repo_root, output_root=target_root)
            report["write_set"].append(reference.relative_to(target_root).as_posix())
    elif args.check:
        target = args.repo_root.resolve() / _OUTPUT_PATH
        if not target.is_file() or target.read_bytes() != payload:
            raise ValueError("DS11-GENERATED-DRIFT")
    elif args.corrupt_field_drift_check and not run_corruption_probe(
        "extra_field", repo_root=args.repo_root, register_as_of=args.register_as_of
    ):
        raise ValueError("corruption probe did not reject the artifact")
    elif args.check_a11y_receipt:
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
            raise ValueError("DS11 corruption probe wave escaped its semantic boundary")
    if args.write_generated_reference and not args.write:
        parser.error("--write-generated-reference requires --write")
    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
    else:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
