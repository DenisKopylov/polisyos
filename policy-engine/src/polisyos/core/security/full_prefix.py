"""Exact full-prefix builder and verifier for the policy-free chronology profile."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.contracts import chronology as contract


class _MemberFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["polisyos.chronology.full-prefix.v1"]
    profile: Literal["full_prefix_canon_json_0_2_0_sha256_256_v1"]
    proof_domain: str = Field(min_length=1)
    family: str = Field(min_length=1)
    scope_ref: contract.Digest
    authority_purpose: str = Field(min_length=1)
    native_schema_profile: str = Field(min_length=1)
    member_ordinal: int = Field(ge=0)
    member_ref: contract.Digest
    member_content_hash: contract.Digest
    member_admission_basis_ref: contract.Digest
    member_admission_context_ref: contract.Digest
    predecessor_commitment: contract.Digest


def _hash_native_view(payload: memoryview) -> contract.Digest:
    digest = hashlib.sha256()
    digest.update(contract._NATIVE_PREFIX)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def _hash_member_frame(payload: bytes) -> contract.Digest:
    return contract._sha256_digest(contract._MEMBER_PREFIX, payload)


def _read_frame(payload: memoryview, offset: int) -> tuple[memoryview, int]:
    if len(payload) - offset < 8:
        raise ValueError("truncated record length")
    size = int.from_bytes(payload[offset : offset + 8], "big")
    start = offset + 8
    end = start + size
    if end > len(payload):
        raise ValueError("truncated record payload")
    return payload[start:end], end


def _domain_from_header(
    header: contract.ChronologyBundleHeader,
) -> contract.ChronologyProofDomain:
    return contract.ChronologyProofDomain(
        format=header.format,
        profile=header.profile,
        proof_domain=header.proof_domain,
        family=header.family,
        scope_ref=header.scope_ref,
        authority_purpose=header.authority_purpose,
    )


def _mode(value: object | None) -> contract.FullPrefixInputMode:
    return (
        contract.FullPrefixInputMode.ABSENT
        if value is None
        else contract.FullPrefixInputMode.PRESENT
    )


def _build_full_prefix_result(
    *,
    result_kind: Literal[
        "verified",
        "invocation_rejected",
        "envelope_rejected",
        "member_rejected",
        "internal_consistency_rejected",
        "expected_prefix_rejected",
    ],
    expected_bundle_hash_mode: contract.FullPrefixInputMode,
    expected_prefix_mode: contract.FullPrefixInputMode,
    bundle_content_hash: contract.Digest,
    parsed_header: contract.ChronologyBundleHeader | None = None,
    verified_member_count: int = 0,
    commitment_head: contract.Digest | None = None,
    failure_codes: tuple[Any, ...] = (),
) -> contract.FullPrefixVerificationResult:
    """Construct every verifier terminal through the closed evaluation table."""
    state = contract.FULL_PREFIX_EVALUATION_TABLE[
        contract.FullPrefixEvaluationKey(
            result_kind=result_kind,
            expected_bundle_hash=expected_bundle_hash_mode,
            expected_prefix=expected_prefix_mode,
        )
    ]
    terminal = contract.FULL_PREFIX_TERMINAL_BY_RESULT_KIND[result_kind]
    common: dict[str, Any] = {
        "result_kind": result_kind,
        "bundle_content_hash": bundle_content_hash,
        "evaluation_state": state,
        "terminal_check": terminal,
    }
    if result_kind == "verified":
        if parsed_header is None or commitment_head is None:
            raise RuntimeError("verified result requires parsed header and commitment head")
        return contract.FullPrefixVerified(
            **common,
            status="verified",
            parsed_header=parsed_header,
            verified_member_count=verified_member_count,
            commitment_head=commitment_head,
        )
    if result_kind == "invocation_rejected":
        return contract.FullPrefixInvocationRejected(
            **common,
            status="rejected",
            phase="invocation",
            failure_codes=cast(
                "tuple[contract.FullPrefixInvocationFailureCode, ...]", failure_codes
            ),
        )
    if result_kind == "envelope_rejected":
        return contract.FullPrefixEnvelopeRejected(
            **common,
            status="rejected",
            phase="envelope",
            failure_codes=cast("tuple[contract.FullPrefixEnvelopeFailureCode, ...]", failure_codes),
        )
    if parsed_header is None or commitment_head is None:
        raise RuntimeError("post-envelope result requires parsed header and commitment head")
    if result_kind == "member_rejected":
        return contract.FullPrefixMemberRejected(
            **common,
            status="rejected",
            phase="member",
            parsed_header=parsed_header,
            verified_member_count=verified_member_count,
            commitment_head=commitment_head,
            failure_codes=cast("tuple[contract.FullPrefixMemberFailureCode, ...]", failure_codes),
        )
    if result_kind == "internal_consistency_rejected":
        return contract.FullPrefixInternalConsistencyRejected(
            **common,
            status="rejected",
            phase="consistency",
            parsed_header=parsed_header,
            verified_member_count=verified_member_count,
            commitment_head=commitment_head,
            failure_codes=cast(
                "tuple[contract.FullPrefixInternalConsistencyFailureCode, ...]",
                failure_codes,
            ),
        )
    return contract.FullPrefixExpectedPrefixRejected(
        **common,
        status="rejected",
        phase="expected_prefix",
        parsed_header=parsed_header,
        verified_member_count=verified_member_count,
        commitment_head=commitment_head,
        failure_codes=cast(
            "tuple[contract.FullPrefixExpectedPrefixFailureCode, ...]", failure_codes
        ),
    )


def build_full_prefix_bundle(
    request: contract.ChronologyBundleRequest,
) -> contract.FullPrefixBuildResult:
    """Build the one exact v1 bundle or return its sole capacity failure.

    Args:
        request: Strict full native prefix under one proof domain.

    Returns:
        Exact encoded bytes or ``proof_profile_capacity_exceeded``.
    """
    early_failure = contract._profile_capacity_failure(
        domain=request.domain,
        member_count=len(request.members),
        header_frame_bytes=0,
        member_frame_bytes=(),
        native_frame_bytes=(),
    )
    if early_failure is not None:
        return early_failure

    predecessor = contract._domain_genesis(request.domain)
    commitments: list[contract.Digest] = []
    member_records: list[bytes] = []
    member_frame_sizes: list[int] = []
    native_frame_sizes: list[int] = []
    native_bytes_total = 0

    for ordinal, member in enumerate(request.members):
        frame_mapping = contract._member_frame_raw_mapping(
            domain=request.domain,
            native_schema_profile=request.native_schema_profile,
            member_ordinal=ordinal,
            member=member,
            predecessor_commitment=predecessor,
        )
        frame_bytes = contract._canonical_raw_bytes(frame_mapping)
        framed_member = contract._frame_record(frame_bytes)
        framed_native = contract._frame_record(member.native_bytes)
        member_frame_sizes.append(len(framed_member))
        native_frame_sizes.append(len(framed_native))
        native_bytes_total += len(member.native_bytes)
        commitment = _hash_member_frame(frame_bytes)
        commitments.append(commitment)
        member_records.extend((framed_member, framed_native))
        predecessor = commitment

    header = contract._build_header(
        request=request,
        commitments=tuple(commitments),
        native_bytes_total=native_bytes_total,
    )
    header_bytes = contract._canonical_raw_bytes(contract._header_raw_mapping(header))
    framed_header = contract._frame_record(header_bytes)
    failure = contract._profile_capacity_failure(
        domain=request.domain,
        member_count=len(request.members),
        header_frame_bytes=len(framed_header),
        member_frame_bytes=tuple(member_frame_sizes),
        native_frame_bytes=tuple(native_frame_sizes),
    )
    if failure is not None:
        return failure

    bundle_bytes = b"".join((framed_header, *member_records))
    return contract.EncodedChronologyBundle(
        result_kind="encoded",
        bundle_bytes=bundle_bytes,
        bundle_content_hash=contract._bundle_content_hash(bundle_bytes),
        header=header,
        member_commitments=tuple(commitments),
    )


class FullPrefixVerifier:
    """Incrementally parse and recompute one exact full-prefix byte bundle."""

    def verify_bundle(
        self,
        bundle_bytes: bytes,
        *,
        expected_domain: contract.ChronologyProofDomain,
        expected_prefix: contract.ExpectedCommitmentPrefix | None = None,
        expected_bundle_content_hash: contract.Digest | None = None,
    ) -> contract.FullPrefixVerificationResult:
        """Verify raw bundle bytes without inferring native authority.

        Args:
            bundle_bytes: Exact v1 framed bytes.
            expected_domain: Family/scope/purpose domain required by the caller.
            expected_prefix: Optional earlier commitment prefix to compare.
            expected_bundle_content_hash: Optional protocol-domain bundle digest.

        Returns:
            One closed verified/rejected result shape.
        """
        expected_hash_mode = _mode(expected_bundle_content_hash)
        expected_prefix_mode = _mode(expected_prefix)
        observed_bundle_hash = contract._bundle_content_hash(bundle_bytes)
        if (
            expected_bundle_content_hash is not None
            and observed_bundle_hash != expected_bundle_content_hash
        ):
            return _build_full_prefix_result(
                result_kind="invocation_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                failure_codes=(
                    contract.FullPrefixInvocationFailureCode.BUNDLE_CONTENT_HASH_MISMATCH,
                ),
            )

        envelope_failures: list[contract.FullPrefixEnvelopeFailureCode] = []
        if len(bundle_bytes) > contract.FULL_PREFIX_MAX_BUNDLE_BYTES:
            return _build_full_prefix_result(
                result_kind="envelope_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                failure_codes=(
                    contract.FullPrefixEnvelopeFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
                ),
            )
        view = memoryview(bundle_bytes)
        try:
            header_view, offset = _read_frame(view, 0)
        except ValueError:
            return _build_full_prefix_result(
                result_kind="envelope_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                failure_codes=(contract.FullPrefixEnvelopeFailureCode.BUNDLE_MALFORMED,),
            )
        if len(header_view) + 8 > contract.FULL_PREFIX_MAX_HEADER_FRAME_BYTES:
            return _build_full_prefix_result(
                result_kind="envelope_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                failure_codes=(
                    contract.FullPrefixEnvelopeFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
                ),
            )
        header_bytes = b""
        try:
            header_bytes = bytes(header_view)
            raw_header = json.loads(header_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raw_header = None
        if not isinstance(raw_header, dict):
            envelope_failures.append(contract.FullPrefixEnvelopeFailureCode.BUNDLE_MALFORMED)
        else:
            try:
                if contract._canonical_raw_bytes(raw_header) != header_bytes:
                    envelope_failures.append(
                        contract.FullPrefixEnvelopeFailureCode.NON_CANONICAL_HEADER
                    )
            except (TypeError, ValueError):
                envelope_failures.append(
                    contract.FullPrefixEnvelopeFailureCode.NON_CANONICAL_HEADER
                )
            if raw_header.get("format") != contract.FULL_PREFIX_FORMAT:
                envelope_failures.append(
                    contract.FullPrefixEnvelopeFailureCode.UNSUPPORTED_FORMAT
                )
            if raw_header.get("profile") != contract.FULL_PREFIX_PROFILE:
                envelope_failures.append(contract.FullPrefixEnvelopeFailureCode.UNKNOWN_PROFILE)
        header: contract.ChronologyBundleHeader | None = None
        if isinstance(raw_header, dict) and not {
            contract.FullPrefixEnvelopeFailureCode.UNSUPPORTED_FORMAT,
            contract.FullPrefixEnvelopeFailureCode.UNKNOWN_PROFILE,
        }.intersection(envelope_failures):
            try:
                header = contract.ChronologyBundleHeader.model_validate(raw_header)
            except ValidationError:
                envelope_failures.append(contract.FullPrefixEnvelopeFailureCode.BUNDLE_MALFORMED)
        if header is not None:
            if _domain_from_header(header) != expected_domain:
                envelope_failures.append(
                    contract.FullPrefixEnvelopeFailureCode.PROOF_DOMAIN_MISMATCH
                )
            if (
                header.member_count > contract.FULL_PREFIX_MAX_MEMBERS
                or header.native_bytes_total > contract.FULL_PREFIX_MAX_BUNDLE_BYTES
            ):
                envelope_failures.append(
                    contract.FullPrefixEnvelopeFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED
                )
        if envelope_failures:
            ordered = tuple(
                code
                for code in contract.FullPrefixEnvelopeFailureCode
                if code in set(envelope_failures)
            )
            return _build_full_prefix_result(
                result_kind="envelope_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                failure_codes=ordered,
            )
        if header is None:
            raise RuntimeError("accepted envelope did not produce a parsed header")

        genesis = contract._domain_genesis(expected_domain)
        predecessor: contract.Digest = genesis
        first_commitment: contract.Digest | None = None
        expected_prefix_head: contract.Digest | None = (
            genesis
            if expected_prefix is not None and expected_prefix.member_count == 0
            else None
        )
        native_bytes_total = 0
        verified_count = 0
        header_domain_fields = (
            header.format,
            header.profile,
            header.proof_domain,
            header.family,
            header.scope_ref,
            header.authority_purpose,
            header.native_schema_profile,
        )

        for ordinal in range(header.member_count):
            failures: list[contract.FullPrefixMemberFailureCode] = []
            try:
                member_view, after_member = _read_frame(view, offset)
            except ValueError:
                return _build_full_prefix_result(
                    result_kind="member_rejected",
                    expected_bundle_hash_mode=expected_hash_mode,
                    expected_prefix_mode=expected_prefix_mode,
                    bundle_content_hash=observed_bundle_hash,
                    parsed_header=header,
                    verified_member_count=verified_count,
                    commitment_head=predecessor,
                    failure_codes=(
                        contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME,
                    ),
                )
            if len(member_view) + 8 > contract.FULL_PREFIX_MAX_MEMBER_FRAME_BYTES:
                return _build_full_prefix_result(
                    result_kind="member_rejected",
                    expected_bundle_hash_mode=expected_hash_mode,
                    expected_prefix_mode=expected_prefix_mode,
                    bundle_content_hash=observed_bundle_hash,
                    parsed_header=header,
                    verified_member_count=verified_count,
                    commitment_head=predecessor,
                    failure_codes=(
                        contract.FullPrefixMemberFailureCode.PROOF_PROFILE_CAPACITY_EXCEEDED,
                    ),
                )
            raw_member: object = None
            member_frame: _MemberFrame | None = None
            member_bytes = bytes(member_view)
            try:
                raw_member = json.loads(member_bytes)
                if not isinstance(raw_member, dict):
                    raise ValueError("member frame must be an object")
                if contract._canonical_raw_bytes(raw_member) != member_bytes:
                    raise ValueError("member frame is non-canonical")
                member_frame = _MemberFrame.model_validate(raw_member)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                failures.append(
                    contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME
                )
            try:
                native_view, after_native = _read_frame(view, after_member)
            except ValueError:
                failures.append(
                    contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME
                )
                native_view = memoryview(b"")
                after_native = len(view)

            if member_frame is not None:
                observed_domain_fields = (
                    member_frame.format,
                    member_frame.profile,
                    member_frame.proof_domain,
                    member_frame.family,
                    member_frame.scope_ref,
                    member_frame.authority_purpose,
                    member_frame.native_schema_profile,
                )
                if observed_domain_fields != header_domain_fields:
                    failures.append(
                        contract.FullPrefixMemberFailureCode.NON_CANONICAL_MEMBER_FRAME
                    )
                if member_frame.member_ordinal != ordinal:
                    failures.append(contract.FullPrefixMemberFailureCode.ORDINAL_MISMATCH)
                if member_frame.predecessor_commitment != predecessor:
                    failures.append(contract.FullPrefixMemberFailureCode.PREDECESSOR_MISMATCH)
                if member_frame.member_content_hash != _hash_native_view(native_view):
                    failures.append(
                        contract.FullPrefixMemberFailureCode.NATIVE_CONTENT_HASH_MISMATCH
                    )
            if failures:
                ordered = tuple(
                    code
                    for code in contract.FullPrefixMemberFailureCode
                    if code in set(failures)
                )
                return _build_full_prefix_result(
                    result_kind="member_rejected",
                    expected_bundle_hash_mode=expected_hash_mode,
                    expected_prefix_mode=expected_prefix_mode,
                    bundle_content_hash=observed_bundle_hash,
                    parsed_header=header,
                    verified_member_count=verified_count,
                    commitment_head=predecessor,
                    failure_codes=ordered,
                )
            commitment = _hash_member_frame(member_bytes)
            if verified_count == 0:
                first_commitment = commitment
            predecessor = commitment
            verified_count += 1
            if (
                expected_prefix is not None
                and expected_prefix.member_count == verified_count
            ):
                expected_prefix_head = commitment
            native_bytes_total += len(native_view)
            offset = after_native

        consistency_failures: list[
            contract.FullPrefixInternalConsistencyFailureCode
        ] = []
        if offset != len(view):
            consistency_failures.append(
                contract.FullPrefixInternalConsistencyFailureCode.MEMBER_COUNT_MISMATCH
            )
        if verified_count != header.member_count:
            consistency_failures.append(
                contract.FullPrefixInternalConsistencyFailureCode.MEMBER_COUNT_MISMATCH
            )
        if native_bytes_total != header.native_bytes_total:
            consistency_failures.append(
                contract.FullPrefixInternalConsistencyFailureCode.NATIVE_BYTES_TOTAL_MISMATCH
            )
        expected_first = first_commitment
        if header.first_commitment != expected_first:
            consistency_failures.append(
                contract.FullPrefixInternalConsistencyFailureCode.FIRST_COMMITMENT_MISMATCH
            )
        expected_head = predecessor
        if header.commitment_head != expected_head:
            consistency_failures.append(
                contract.FullPrefixInternalConsistencyFailureCode.COMMITMENT_HEAD_MISMATCH
            )
        if consistency_failures:
            ordered = tuple(
                code
                for code in contract.FullPrefixInternalConsistencyFailureCode
                if code in set(consistency_failures)
            )
            return _build_full_prefix_result(
                result_kind="internal_consistency_rejected",
                expected_bundle_hash_mode=expected_hash_mode,
                expected_prefix_mode=expected_prefix_mode,
                bundle_content_hash=observed_bundle_hash,
                parsed_header=header,
                verified_member_count=verified_count,
                commitment_head=expected_head,
                failure_codes=ordered,
            )

        if expected_prefix is not None:
            prefix_failures: list[contract.FullPrefixExpectedPrefixFailureCode] = []
            if expected_prefix.domain != expected_domain:
                prefix_failures.append(
                    contract.FullPrefixExpectedPrefixFailureCode.DOMAIN_MISMATCH
                )
            if expected_prefix.member_count > verified_count:
                prefix_failures.append(contract.FullPrefixExpectedPrefixFailureCode.OUT_OF_RANGE)
            else:
                if expected_prefix.commitment_head != expected_prefix_head:
                    prefix_failures.append(
                        contract.FullPrefixExpectedPrefixFailureCode.HEAD_MISMATCH
                    )
            if prefix_failures:
                ordered = tuple(
                    code
                    for code in contract.FullPrefixExpectedPrefixFailureCode
                    if code in set(prefix_failures)
                )
                return _build_full_prefix_result(
                    result_kind="expected_prefix_rejected",
                    expected_bundle_hash_mode=expected_hash_mode,
                    expected_prefix_mode=expected_prefix_mode,
                    bundle_content_hash=observed_bundle_hash,
                    parsed_header=header,
                    verified_member_count=verified_count,
                    commitment_head=expected_head,
                    failure_codes=ordered,
                )

        return _build_full_prefix_result(
            result_kind="verified",
            expected_bundle_hash_mode=expected_hash_mode,
            expected_prefix_mode=expected_prefix_mode,
            bundle_content_hash=observed_bundle_hash,
            parsed_header=header,
            verified_member_count=verified_count,
            commitment_head=expected_head,
        )


__all__ = ["FullPrefixVerifier", "build_full_prefix_bundle"]
