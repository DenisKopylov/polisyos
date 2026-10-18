"""Journal, terminal, CAS, and generated-family custody projections."""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from polisyos.core.artifacts import ArtifactManifest, ManifestLifecycle
from polisyos.fabric.data_plane import (
    canonical_json_bytes,
    content_sha256,
    resolve_live_attempt_terminals,
    resolve_raw_response_body,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import AcceptanceCaseReceipt

from .acquisition_contract_support import (
    DEFAULT_DERIVED_ACCEPTANCE,
    DEFAULT_GENERATED_ARTIFACTS,
    DEFAULT_N13B_CAS,
    DEFAULT_N13B_JOURNAL,
    N13B_FAMILY_ID,
    N13B_SOURCE_FAMILY_ID,
    SHA256_PATTERN,
    N13bContractError,
    _bytes_sha256,
    _file_sha256,
    _json_value,
    _read_model,
    _StrictModel,
)


@dataclass(frozen=True)
class N13bGeneratedRegistryUpdate:
    """Canonical generated-artifact registry update for the live CAS closure."""

    registry_bytes: bytes
    required_cas_artifact_ids: tuple[str, ...]
    required_cas_output_paths: tuple[str, ...]
    obsolete_cas_output_paths: tuple[str, ...]


class LiveAttemptProjection(_StrictModel):
    """Path-stable journal/CAS projection for one paid live attempt."""

    attempt_id: str = Field(min_length=1)
    request_sequence: int = Field(ge=1)
    call_class: Literal["data_fetch", "indicator_metadata"]
    request_variables: tuple[str, ...] = Field(min_length=1, max_length=1)
    request_event_sha256: str = Field(pattern=SHA256_PATTERN)
    failure_code: str = Field(min_length=1)
    outcome_code: str = Field(min_length=1)
    terminal_sha256: str = Field(pattern=SHA256_PATTERN)
    raw_evidence_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_body_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_byte_count: int | None = Field(default=None, ge=0)
    raw_cas_persisted: bool
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    quarantine: Literal[True]
    response_admitted: Literal[False]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _attempt_is_content_bound(self) -> Self:
        raw = (
            self.raw_evidence_event_sha256,
            self.raw_body_sha256,
            self.raw_byte_count,
        )
        if any(value is None for value in raw) != all(value is None for value in raw):
            raise ValueError("attempt raw evidence projection must be complete or absent")
        if self.raw_body_sha256 is None and self.raw_cas_persisted:
            raise ValueError("an absent raw response cannot claim CAS persistence")
        if self.raw_body_sha256 is not None and not self.raw_cas_persisted:
            raise ValueError("journaled raw response bytes must persist in quarantine CAS")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("live-attempt projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class JournalEvidenceProjection(_StrictModel):
    """Full journal denominator proving request/terminal/raw evidence persistence."""

    journal_ref: Literal[
        "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
    ]
    journal_byte_sha256: str = Field(pattern=SHA256_PATTERN)
    event_count: int = Field(ge=1)
    request_count: int = Field(ge=1)
    terminal_count: int = Field(ge=1)
    raw_response_count: int = Field(ge=0)
    persisted_raw_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    quarantine_count: int = Field(ge=0)
    attempts: tuple[LiveAttemptProjection, ...] = Field(min_length=1)
    journal_raw_evidence_persistence_missing_closed: bool
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _denominator_is_recomputed(self) -> Self:
        attempts = self.attempts
        if tuple(row.request_sequence for row in attempts) != tuple(
            sorted(row.request_sequence for row in attempts)
        ):
            raise ValueError("live attempts must preserve journal request order")
        if len({row.attempt_id for row in attempts}) != len(attempts):
            raise ValueError("live attempt denominator contains duplicates")
        expected_raw = sum(row.raw_body_sha256 is not None for row in attempts)
        expected_persisted = sum(row.raw_cas_persisted for row in attempts)
        expected_admitted = sum(row.response_admitted for row in attempts)
        expected_quarantine = sum(row.quarantine for row in attempts)
        if (
            self.request_count != len(attempts)
            or self.terminal_count != len(attempts)
            or self.raw_response_count != expected_raw
            or self.persisted_raw_response_count != expected_persisted
            or self.response_admitted_count != expected_admitted
            or self.quarantine_count != expected_quarantine
        ):
            raise ValueError("journal evidence counts must cover the complete attempt denominator")
        expected_closed = (
            self.request_count == self.terminal_count
            and self.raw_response_count == self.persisted_raw_response_count
            and self.response_admitted_count == 0
        )
        if self.journal_raw_evidence_persistence_missing_closed != expected_closed:
            raise ValueError("journal persistence residual must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("journal projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_journal_evidence_projection(
    *,
    journal_path: Path,
    cas_root: Path,
) -> JournalEvidenceProjection:
    """Reopen every exact request/terminal and bind raw bytes into quarantine CAS."""

    journal = Path(journal_path)
    events = _read_canonical_jsonl(journal)
    terminals = resolve_live_attempt_terminals(journal)
    requests = {
        int(event["sequence"]): event for event in events if event.get("event_kind") == "request"
    }
    if len(requests) != len(terminals):
        raise N13bContractError("journal_attempt_denominator_incomplete")
    rows: list[LiveAttemptProjection] = []
    for terminal in terminals:
        request_event = requests.get(terminal.request_ref.sequence)
        if request_event is None or request_event.get("attempt_id") != terminal.attempt_id:
            raise N13bContractError("journal_terminal_request_unresolved", terminal.attempt_id)
        request = request_event.get("request")
        if not isinstance(request, dict):
            raise N13bContractError("journal_request_payload_invalid", terminal.attempt_id)
        request_variables = request.get("request_variables")
        if not isinstance(request_variables, list) or len(request_variables) != 1:
            raise N13bContractError("journal_request_variable_budget_drift", terminal.attempt_id)
        call_class = (
            "indicator_metadata"
            if request.get("call_class") == "indicator_metadata"
            else "data_fetch"
        )
        raw_body: bytes | None = None
        raw_body_sha: str | None = None
        raw_byte_count: int | None = None
        raw_event_sha: str | None = None
        raw_persisted = False
        if terminal.raw_evidence_ref is not None:
            raw_body = resolve_raw_response_body(terminal.raw_evidence_ref)
            raw_body_sha = _bytes_sha256(raw_body)
            raw_byte_count = len(raw_body)
            raw_event_sha = terminal.raw_evidence_ref.event_sha256
            blob = _cas_blob_path(Path(cas_root), raw_body_sha)
            raw_persisted = blob.is_file() and _file_sha256(blob) == raw_body_sha
        values = {
            "attempt_id": terminal.attempt_id,
            "request_sequence": terminal.request_ref.sequence,
            "call_class": call_class,
            "request_variables": tuple(str(value) for value in request_variables),
            "request_event_sha256": terminal.request_ref.event_sha256,
            "failure_code": terminal.failure_code,
            "outcome_code": terminal.outcome_code,
            "terminal_sha256": terminal.terminal_sha256,
            "raw_evidence_event_sha256": raw_event_sha,
            "raw_body_sha256": raw_body_sha,
            "raw_byte_count": raw_byte_count,
            "raw_cas_persisted": raw_persisted,
            "http_status_code": terminal.http_status_code,
            "quarantine": terminal.quarantine,
            "response_admitted": terminal.response_admitted,
        }
        rows.append(
            LiveAttemptProjection(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    values = {
        "journal_ref": (
            "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        "journal_byte_sha256": _file_sha256(journal),
        "event_count": len(events),
        "request_count": len(requests),
        "terminal_count": len(terminals),
        "raw_response_count": sum(row.raw_body_sha256 is not None for row in rows),
        "persisted_raw_response_count": sum(row.raw_cas_persisted for row in rows),
        "response_admitted_count": sum(row.response_admitted for row in rows),
        "quarantine_count": sum(row.quarantine for row in rows),
        "attempts": tuple(rows),
        "journal_raw_evidence_persistence_missing_closed": (
            len(requests) == len(terminals)
            and all(row.raw_body_sha256 is None or row.raw_cas_persisted for row in rows)
            and not any(row.response_admitted for row in rows)
        ),
    }
    return JournalEvidenceProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


def derive_cas_artifact_closure(
    cas_root: Path,
    root_artifact_ids: Sequence[str],
) -> tuple[str, ...]:
    """Resolve and content-validate the complete CAS input graph from exact roots."""

    roots = tuple(sorted({str(value) for value in root_artifact_ids}))
    if not roots:
        raise N13bContractError("n13b_cas_root_denominator_empty")
    pending = list(reversed(roots))
    visited: set[str] = set()
    while pending:
        artifact_id = pending.pop()
        if artifact_id in visited:
            continue
        _require_artifact_id(artifact_id)
        blob = _cas_blob_path(Path(cas_root), artifact_id)
        manifest_path = _cas_manifest_path(Path(cas_root), artifact_id)
        if not blob.is_file() or not manifest_path.is_file():
            raise N13bContractError("n13b_cas_artifact_missing", artifact_id)
        if _file_sha256(blob) != artifact_id:
            raise N13bContractError("n13b_cas_blob_content_drift", artifact_id)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise N13bContractError("n13b_cas_manifest_invalid", artifact_id) from exc
        if not isinstance(manifest, dict) or manifest.get("artifact_id") != artifact_id:
            raise N13bContractError("n13b_cas_manifest_identity_drift", artifact_id)
        digest = artifact_id.removeprefix("sha256:")
        integrity = manifest.get("integrity")
        if (
            not isinstance(integrity, dict)
            or integrity.get("sha256") not in {digest, artifact_id}
            or manifest.get("byte_size") != blob.stat().st_size
        ):
            raise N13bContractError("n13b_cas_manifest_integrity_drift", artifact_id)
        inputs = manifest.get("inputs")
        if not isinstance(inputs, list):
            raise N13bContractError("n13b_cas_manifest_inputs_invalid", artifact_id)
        input_ids: list[str] = []
        for row in inputs:
            if not isinstance(row, dict) or not isinstance(row.get("artifact_id"), str):
                raise N13bContractError("n13b_cas_manifest_input_invalid", artifact_id)
            input_id = str(row["artifact_id"])
            _require_artifact_id(input_id)
            input_ids.append(input_id)
        visited.add(artifact_id)
        pending.extend(
            reversed(
                tuple(sorted(input_id for input_id in set(input_ids) if input_id not in visited))
            )
        )
    return tuple(sorted(visited))


def derive_n13b_generated_registry_update(repo_root: Path) -> N13bGeneratedRegistryUpdate:
    """Derive the exact N13b CAS closure and its registry-only textual update."""

    root = Path(repo_root)
    acceptance = _read_model(root / DEFAULT_DERIVED_ACCEPTANCE, AcceptanceCaseReceipt)
    journal = derive_journal_evidence_projection(
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    raw_artifact_ids = tuple(
        str(row.raw_body_sha256) for row in journal.attempts if row.raw_body_sha256 is not None
    )
    artifact_ids = derive_cas_artifact_closure(
        root / DEFAULT_N13B_CAS,
        (*raw_artifact_ids, acceptance.certificate_artifact_id),
    )
    view_paths = tuple(
        _verify_cas_manifest_view(root / DEFAULT_N13B_CAS, artifact_id)
        for artifact_id in artifact_ids
    )
    required_paths = tuple(
        sorted(
            [
                path
                for artifact_id in artifact_ids
                for path in (
                    _cas_blob_relative(artifact_id),
                    _cas_manifest_relative(artifact_id),
                )
            ]
            + list(view_paths)
        )
    )
    registry_path = root / DEFAULT_GENERATED_ARTIFACTS
    try:
        original = registry_path.read_bytes()
        parsed = tomllib.loads(original.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    _n13b_lifecycle_families(parsed)
    family, other_output_paths = _n13b_generated_family(parsed, family_id=N13B_SOURCE_FAMILY_ID)
    output_values = family.get("outputs")
    if not isinstance(output_values, list) or not output_values:
        raise N13bContractError("n13b_generated_outputs_missing")
    current_outputs = tuple(str(value) for value in output_values)
    cas_prefix = (DEFAULT_N13B_CAS / "artifacts/sha256").as_posix() + "/"
    non_cas_outputs = tuple(path for path in current_outputs if not path.startswith(cas_prefix))
    next_outputs = tuple(sorted((*non_cas_outputs, *required_paths)))
    original_integrity = family.get("source_integrity_sha256")
    if not isinstance(original_integrity, dict):
        raise N13bContractError("n13b_source_integrity_missing")
    cas_integrity = {
        path: (
            str(original_integrity[path])
            if path in original_integrity
            else _file_sha256(root / path)
        )
        for path in required_paths
    }
    next_integrity = {
        path: digest
        for path, digest in original_integrity.items()
        if not path.startswith(cas_prefix)
    }
    next_integrity.update(cas_integrity)
    _verify_n13b_source_integrity(
        root,
        {**family, "outputs": list(next_outputs), "source_integrity_sha256": next_integrity},
    )
    registry_bytes = _replace_n13b_generated_outputs(
        original,
        next_outputs,
        family_id=N13B_SOURCE_FAMILY_ID,
        cas_integrity=cas_integrity,
    )
    stale = set(current_outputs) - set(next_outputs)
    removable_stale = tuple(
        sorted(
            path for path in stale if path.startswith(cas_prefix) and path not in other_output_paths
        )
    )
    return N13bGeneratedRegistryUpdate(
        registry_bytes=registry_bytes,
        required_cas_artifact_ids=artifact_ids,
        required_cas_output_paths=required_paths,
        obsolete_cas_output_paths=removable_stale,
    )


def _n13b_generated_family(
    parsed: Mapping[str, Any],
    *,
    family_id: str = N13B_FAMILY_ID,
) -> tuple[Mapping[str, Any], frozenset[str]]:
    unresolved_code = (
        "n13b_source_family_unresolved"
        if family_id == N13B_SOURCE_FAMILY_ID
        else "n13b_generated_family_unresolved"
    )
    families = parsed.get("family")
    if not isinstance(families, list):
        raise N13bContractError(unresolved_code)
    matches = [row for row in families if isinstance(row, dict) and row.get("id") == family_id]
    if len(matches) != 1:
        raise N13bContractError(unresolved_code)
    other_outputs = frozenset(
        str(output)
        for row in families
        if isinstance(row, dict) and row.get("id") != family_id
        for output in (row.get("outputs") or ())
    )
    return matches[0], other_outputs


def _n13b_lifecycle_families(
    parsed: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Resolve both custody owners and reject loss of exact single ownership."""

    generated, _ = _n13b_generated_family(parsed)
    source, _ = _n13b_generated_family(parsed, family_id=N13B_SOURCE_FAMILY_ID)
    for family, expected_lifecycle, label in (
        (generated, "generated_committed", "generated"),
        (source, "source_committed", "source"),
    ):
        if family.get("lifecycle") != expected_lifecycle:
            raise N13bContractError(f"n13b_{label}_family_lifecycle_invalid")
        outputs = family.get("outputs")
        if (
            not isinstance(outputs, list)
            or not outputs
            or any(not isinstance(output, str) or not output for output in outputs)
        ):
            raise N13bContractError("n13b_generated_outputs_missing")
    output_counts = Counter(
        str(output)
        for row in parsed["family"]
        if isinstance(row, dict)
        for output in (row.get("outputs") or ())
    )
    owned_outputs = (*generated["outputs"], *source["outputs"])
    if any(output_counts[output] != 1 for output in owned_outputs):
        raise N13bContractError("n13b_lifecycle_output_multiple_owners")
    return generated, source


def _replace_n13b_generated_outputs(
    registry_bytes: bytes,
    outputs: Sequence[str],
    *,
    family_id: str = N13B_FAMILY_ID,
    cas_integrity: Mapping[str, str] | None = None,
) -> bytes:
    """Replace one resolved N13b owner output list, preserving all other bytes."""

    try:
        text = registry_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "[[family]]"]
    starts.append(len(lines))
    matching_blocks: list[tuple[int, int]] = []
    id_pattern = re.compile(r'id\s*=\s*"' + re.escape(family_id) + r'"\s*')
    for start, end in pairwise(starts):
        if any(id_pattern.fullmatch(line.strip()) for line in lines[start:end]):
            matching_blocks.append((start, end))
    if len(matching_blocks) != 1:
        raise N13bContractError("n13b_generated_family_unresolved")
    start, end = matching_blocks[0]
    output_starts = [
        index
        for index in range(start, end)
        if re.fullmatch(r"outputs\s*=\s*\[\s*", lines[index].strip())
    ]
    if len(output_starts) != 1:
        raise N13bContractError("n13b_generated_outputs_missing")
    output_start = output_starts[0]
    output_ends = [index for index in range(output_start + 1, end) if lines[index].strip() == "]"]
    if not output_ends:
        raise N13bContractError("n13b_generated_outputs_missing")
    output_end = output_ends[0]
    newline = "\r\n" if lines[output_start].endswith("\r\n") else "\n"
    replacement = [lines[output_start]]
    replacement.extend(f"  {json.dumps(path)}," + newline for path in outputs)
    replacement.append(lines[output_end])
    family_lines = [*lines[start:output_start], *replacement, *lines[output_end + 1 : end]]
    if cas_integrity is not None:
        if family_id != N13B_SOURCE_FAMILY_ID:
            raise N13bContractError("n13b_generated_registry_update_scope_drift")
        cas_prefix = (DEFAULT_N13B_CAS / "artifacts/sha256").as_posix() + "/"
        original_family, _ = _n13b_generated_family(tomllib.loads(text), family_id=family_id)
        expected_existing = {
            path
            for path in original_family["source_integrity_sha256"]
            if path.startswith(cas_prefix)
        }
        expected_required = {path for path in outputs if path.startswith(cas_prefix)}
        if set(cas_integrity) != expected_required:
            raise N13bContractError("n13b_generated_cas_output_denominator_drift")
        retained_lines: list[str] = []
        seen: set[str] = set()
        for line in family_lines:
            if line.lstrip().startswith("source_integrity_sha256."):
                try:
                    bindings = tomllib.loads(line)["source_integrity_sha256"]
                except (KeyError, tomllib.TOMLDecodeError) as exc:
                    raise N13bContractError("n13b_source_integrity_layout_invalid") from exc
                if len(bindings) != 1:
                    raise N13bContractError("n13b_source_integrity_layout_invalid")
                path, digest = next(iter(bindings.items()))
                if path.startswith(cas_prefix):
                    seen.add(path)
                    if path not in cas_integrity:
                        continue
                    if digest != cas_integrity[path]:
                        raise N13bContractError("n13b_source_integrity_drift", path)
            retained_lines.append(line)
        if seen != expected_existing:
            raise N13bContractError("n13b_source_integrity_layout_invalid")
        retained_lines.extend(
            f"source_integrity_sha256.{json.dumps(path)} = {json.dumps(cas_integrity[path])}"
            + newline
            for path in sorted(set(cas_integrity) - seen)
        )
        family_lines = retained_lines
    rewritten = "".join((*lines[:start], *family_lines, *lines[end:])).encode()
    try:
        before = tomllib.loads(text)
        after = tomllib.loads(rewritten.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    before_family, _before_other = _n13b_generated_family(before, family_id=family_id)
    after_family, _after_other = _n13b_generated_family(after, family_id=family_id)
    mutable = {"outputs"}
    if cas_integrity is not None:
        mutable.add("source_integrity_sha256")
        before_non_cas = {
            path: digest
            for path, digest in before_family["source_integrity_sha256"].items()
            if not path.startswith(cas_prefix)
        }
        expected_integrity = {**before_non_cas, **cas_integrity}
        if after_family.get("source_integrity_sha256") != expected_integrity:
            raise N13bContractError("n13b_generated_registry_update_scope_drift")
    before_without_outputs = {
        key: value for key, value in before_family.items() if key not in mutable
    }
    after_without_outputs = {
        key: value for key, value in after_family.items() if key not in mutable
    }
    if before_without_outputs != after_without_outputs or after_family.get("outputs") != list(
        outputs
    ):
        raise N13bContractError("n13b_generated_registry_update_scope_drift")
    before_others = [row for row in before["family"] if row.get("id") != family_id]
    after_others = [row for row in after["family"] if row.get("id") != family_id]
    if before_others != after_others:
        raise N13bContractError("n13b_generated_registry_update_scope_drift")
    return rewritten


def _verify_n13b_source_integrity(repo_root: Path, source_family: Mapping[str, Any]) -> None:
    """Consult the lifecycle integrity owner before accepting frozen evidence."""

    from tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit import (
        _validate_source_integrity,
    )

    if not isinstance(source_family.get("source_integrity_sha256"), dict):
        raise N13bContractError("n13b_source_integrity_missing")
    issues: list[dict[str, Any]] = []
    _validate_source_integrity(
        repo_root, dict(source_family), list(source_family["outputs"]), issues
    )
    if issues:
        raise N13bContractError("n13b_source_integrity_drift", json.dumps(issues, sort_keys=True))


def _require_artifact_id(artifact_id: str) -> None:
    if re.fullmatch(SHA256_PATTERN, artifact_id) is None:
        raise N13bContractError("n13b_cas_artifact_id_invalid", artifact_id)


def _read_canonical_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    payload = path.read_bytes()
    if not payload.endswith(b"\n"):
        raise N13bContractError("journal_not_newline_terminated")
    events: list[dict[str, Any]] = []
    for expected_sequence, line in enumerate(payload.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise N13bContractError("journal_event_invalid") from exc
        if not isinstance(event, dict) or event.get("sequence") != expected_sequence:
            raise N13bContractError("journal_event_sequence_drift")
        if canonical_json_bytes(event).rstrip(b"\n") != line:
            raise N13bContractError("journal_event_not_canonical")
        events.append(event)
    return tuple(events)


def _cas_blob_path(cas_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.removeprefix("sha256:")
    return Path(cas_root) / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"


def _cas_manifest_path(cas_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.removeprefix("sha256:")
    return (
        Path(cas_root) / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.manifest.json"
    )


def _cas_blob_relative(artifact_id: str) -> str:
    digest = artifact_id.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    ).as_posix()


def _cas_manifest_relative(artifact_id: str) -> str:
    digest = artifact_id.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.manifest.json"
    ).as_posix()


def _cas_manifest_profile(cas_root: Path, artifact_id: str) -> tuple[ArtifactManifest, str]:
    """Read the exact typed manifest and derive its selected CAS profile."""

    _require_artifact_id(artifact_id)
    try:
        manifest = ArtifactManifest.model_validate_json(
            _cas_manifest_path(cas_root, artifact_id).read_bytes()
        )
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_cas_manifest_invalid", artifact_id) from exc
    if str(manifest.artifact_id) != artifact_id:
        raise N13bContractError("n13b_cas_manifest_identity_drift", artifact_id)
    return manifest, ManifestLifecycle.profile_sha256(manifest)


def _cas_manifest_view_relative(artifact_id: str, profile_sha256: str) -> str:
    """Return the selected manifest-view path for one exact artifact profile."""

    _require_artifact_id(artifact_id)
    if re.fullmatch(SHA256_PATTERN, profile_sha256) is None:
        raise N13bContractError("n13b_cas_manifest_profile_invalid", artifact_id)
    digest = artifact_id.removeprefix("sha256:")
    profile = profile_sha256.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS
        / "artifacts/sha256"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.view.{profile}.manifest.json"
    ).as_posix()


def _verify_cas_manifest_view(cas_root: Path, artifact_id: str) -> str:
    """Require a persisted selected view matching the default manifest profile."""

    default_manifest, profile_sha256 = _cas_manifest_profile(cas_root, artifact_id)
    relative = _cas_manifest_view_relative(artifact_id, profile_sha256)
    digest = artifact_id.removeprefix("sha256:")
    view_path = (
        Path(cas_root)
        / "artifacts/sha256"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.view.{profile_sha256.removeprefix('sha256:')}.manifest.json"
    )
    if not view_path.is_file():
        raise N13bContractError("n13b_cas_manifest_view_missing", artifact_id)
    try:
        view_manifest = ArtifactManifest.model_validate_json(view_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_cas_manifest_view_invalid", artifact_id) from exc
    if (
        str(view_manifest.artifact_id) != artifact_id
        or ManifestLifecycle.profile_sha256(view_manifest) != profile_sha256
        or ManifestLifecycle.profile_projection(view_manifest)
        != ManifestLifecycle.profile_projection(default_manifest)
    ):
        raise N13bContractError("n13b_cas_manifest_view_drift", artifact_id)
    return relative
