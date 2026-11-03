"""Bind the finite translator input profile to selected CAS bytes and a call."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.scientist.policy_design.prompts import (
    build_policy_translator_user_payload,
    get_policy_translator_prompt,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactReader, ArtifactRef


TRANSLATOR_MATERIALIZATION_PROFILE = "policy_translator_plain_completion.v1"
TRANSLATOR_INPUT_KIND = "scientist.policy_translator.input.v1"
TRANSLATOR_ROLES = (
    "dossier",
    "readiness_contract",
    "constraint_report",
    "subgroup_report",
    "uncertainty_report",
    "implementation_plan",
)


@dataclass(frozen=True, slots=True)
class TranslatorMaterialization:
    """Selected views for the translator's six known input roles.

    The optional implementation plan alone can be absent. References are only
    selectors; the cache binder rereads and checks the selected bytes and the
    current authorizer must independently resolve the evidence on every reuse.
    """

    store: ArtifactReader
    role_refs: tuple[tuple[str, ArtifactRef | None], ...]


_MATERIALIZATION: ContextVar[TranslatorMaterialization | None] = ContextVar(
    "policy_translator_materialization", default=None
)


@contextmanager
def translator_materialization_scope(
    materialization: TranslatorMaterialization | None,
) -> Iterator[None]:
    """Limit a materialization selector to one translator invocation."""
    token = _MATERIALIZATION.set(materialization)
    try:
        yield
    finally:
        _MATERIALIZATION.reset(token)


def bind_current_translator_materialization(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    model: str,
    prepared_wire_payload: bytes | None,
) -> tuple[bool, dict[str, Any] | None]:
    """Recompute the finite closure and its exact translator request.

    The first result records whether this invocation requested the profile;
    an invalid requested profile must remain physical-only. No caller-supplied
    cache flag, unrelated snapshot, or textual URL decides closure.
    """
    selected = _MATERIALIZATION.get()
    if selected is None:
        return False, None
    if type(selected) is not TranslatorMaterialization:
        return True, None
    try:
        role_refs = selected.role_refs
        if tuple(role for role, _ in role_refs) != TRANSLATOR_ROLES:
            return True, None
        allowed = {"system", "user", "response_format", "temperature", "max_tokens", "_run_id"}
        if (
            args
            or set(kwargs) - allowed
            or kwargs.get("system") != get_policy_translator_prompt()
            or kwargs.get("response_format") != {"type": "json_object"}
        ):
            return True, None

        values: dict[str, Any] = {}
        roles: list[dict[str, Any]] = []
        for role, ref in role_refs:
            if ref is None:
                if role != "implementation_plan":
                    return True, None
                values[role] = None
                roles.append({"role": role, "absent": True})
                continue
            # Revalidate mutable DTOs and preserve the selected manifest profile.
            from polisyos.core.artifacts import ArtifactRef

            if type(ref) is not ArtifactRef:
                return True, None
            ref = ArtifactRef.model_validate(ref.model_dump(mode="python"))
            if (
                ref.kind != TRANSLATOR_INPUT_KIND
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                return True, None
            try:
                manifest = selected.store.get_manifest(ref)
                content = selected.store.get_bytes(ref)
            except Exception:
                # A missing/denied selected view cannot support reuse; the
                # ordinary producer admission still governs physical work.
                return True, None
            if type(content) is not bytes:
                return True, None
            digest = hashlib.sha256(content).hexdigest()
            if (
                manifest.artifact_id != ref.artifact_id
                or manifest.kind != ref.kind
                or manifest.media_type != ref.media_type
                or manifest.byte_size != len(content)
                or manifest.integrity.sha256 != digest
                or str(ref.artifact_id) != f"sha256:{digest}"
                or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
            ):
                return True, None
            envelope = json.loads(content)
            if type(envelope) is not dict or set(envelope) != {"role", "value"}:
                return True, None
            if envelope["role"] != role or not isinstance(envelope["value"], dict):
                return True, None
            values[role] = envelope["value"]
            roles.append(
                {
                    "role": role,
                    "ref": str(ref.artifact_id),
                    "version": ref.manifest_profile_sha256,
                    "kind": ref.kind,
                    "media_type": ref.media_type,
                    "immutable": True,
                    "content": content,
                    "content_hash": f"sha256:{digest}",
                }
            )
        if kwargs.get("user") != build_policy_translator_user_payload(values):
            return True, None
        # The Gateway's actual frozen body, not just its caller kwargs, must
        # be plain. Configured presets/plugins can otherwise add a live route.
        if type(prepared_wire_payload) is not bytes:
            return True, None
        wire = json.loads(prepared_wire_payload)
        expected_wire = {
            "model": model,
            "messages": [
                {"role": "system", "content": kwargs["system"]},
                {"role": "user", "content": kwargs["user"]},
            ],
            "response_format": kwargs["response_format"],
            "temperature": kwargs.get("temperature"),
            "max_tokens": kwargs.get("max_tokens"),
        }
        if "_run_id" in kwargs:
            expected_wire["_run_id"] = kwargs["_run_id"]
        if wire != expected_wire:
            return True, None
        return True, {"profile": TRANSLATOR_MATERIALIZATION_PROFILE, "roles": roles}
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        # Failed or incomplete materialization affects this optimization only.
        return True, None
