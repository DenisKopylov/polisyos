"""Immutable source-admission quantity inside the existing validity owner.

Only one constant-sized root is authoritative. Trie parts, fact/event objects and
receipts are immutable and reusable; unreachable pre-publication objects have no
authority. The caller supplies the existing owner's transaction, not a new lock.
This private storage engine does not verify a Fabric producer or appoint issuers.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from polisyos.core.contracts.decision_validity import (
    RegisteredMaterialization,
    SourceAdmissionCarrier,
    SourceAdmissionReceipt,
    SourceRegistrationReceipt,
)

_RULE = "policyos.registered-sql-admission.v1"
_HEX = frozenset("0123456789abcdef")


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_bytes(value)).hexdigest()


def _typed[T: BaseModel](model: type[T], value: object) -> T:
    return model.model_validate_json(_bytes(value), strict=True)


def _ref_text(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or set(value) - _HEX:
        raise RuntimeError("source_admission_committed_state_corrupt")
    return value


@dataclass(frozen=True, slots=True)
class _Root:
    generation: int
    index_ref: str | None
    event_ref: str | None

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": "source-admission-root.v1",
            "generation": self.generation,
            "index_ref": self.index_ref,
            "event_ref": self.event_ref,
        }


class _SourceAdmissionStateStore:
    """Path-copy a bounded hash trie and publish once under the owner fence."""

    def __init__(
        self,
        base: Path,
        transaction: Callable[[], AbstractContextManager[object]],
    ) -> None:
        self.root_path = base / "committed_source_root.json"
        self.objects = base / "committed_source_objects"
        self._transaction = transaction
        self._fault: Callable[[str], None] | None = None
        self._cache: dict[str, dict[str, Any]] = {}
        self.last_io = {"read_objects": 0, "new_objects": 0}

    def _point(self, name: str) -> None:
        if self._fault is not None:
            self._fault(name)

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _begin(self) -> None:
        self._cache = {}
        self.last_io = {"read_objects": 0, "new_objects": 0}

    def _object(self, ref: str) -> dict[str, Any]:
        ref = _ref_text(ref)
        if ref in self._cache:
            return self._cache[ref]
        try:
            raw = (self.objects / (ref + ".json")).read_bytes()
            if hashlib.sha256(raw).hexdigest() != ref:
                raise ValueError("immutable object digest")
            value = json.loads(raw)
            if type(value) is not dict:
                raise ValueError("immutable object shape")
        except (OSError, ValueError, TypeError) as exc:
            raise RuntimeError("source_admission_committed_state_corrupt") from exc
        self.last_io["read_objects"] += 1
        self._cache[ref] = value
        return value

    def _put(self, payload: dict[str, Any]) -> str:
        raw = _bytes(payload)
        ref = hashlib.sha256(raw).hexdigest()
        if ref in self._cache:
            return ref
        if not self.objects.exists():
            self.objects.mkdir()
            self._fsync_dir(self.objects.parent)
        path = self.objects / (ref + ".json")
        if path.exists():
            if path.read_bytes() != raw:
                raise RuntimeError("source_admission_immutable_object_conflict")
            # A prior failed attempt may have linked this orphan before its
            # directory fsync failed. Reconcile it before publishing a new root.
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._fsync_dir(self.objects)
        else:
            temp = self.objects / (".object-" + uuid.uuid4().hex)
            descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    descriptor = -1
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temp, path)
                except FileExistsError:
                    if path.read_bytes() != raw:
                        raise RuntimeError("source_admission_immutable_object_conflict") from None
                self._fsync_dir(self.objects)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                temp.unlink(missing_ok=True)
            self.last_io["new_objects"] += 1
            self._point("after_immutable_object_fsync")
        self._cache[ref] = payload
        return ref

    def _branch(self, ref: str | None) -> tuple[dict[str, str], str | None]:
        if ref is None:
            return {}, None
        node = self._object(ref)
        if set(node) != {"type", "children", "value"} or node["type"] != "branch":
            raise RuntimeError("source_admission_committed_state_corrupt")
        children = node["children"]
        if type(children) is not dict or any(
            type(key) is not str or len(key) != 1 or key not in _HEX for key in children
        ):
            raise RuntimeError("source_admission_committed_state_corrupt")
        checked = {key: _ref_text(value) for key, value in children.items()}
        value = node["value"]
        return checked, _ref_text(value) if value is not None else None

    def _lookup(self, index: str | None, key: str) -> dict[str, Any] | None:
        ref = index
        for char in hashlib.sha256(key.encode()).hexdigest():
            children, _ = self._branch(ref)
            ref = children.get(char)
            if ref is None:
                return None
        _, value_ref = self._branch(ref)
        if value_ref is None:
            return None
        item = self._object(value_ref)
        if set(item) != {"type", "key", "value"} or item["type"] != "value" or item["key"] != key:
            raise RuntimeError("source_admission_committed_state_corrupt")
        if type(item["value"]) is not dict:
            raise RuntimeError("source_admission_committed_state_corrupt")
        return item["value"]

    def _update(self, index: str | None, key: str, value: dict[str, Any]) -> str:
        digits = hashlib.sha256(key.encode()).hexdigest()
        value_ref = self._put({"type": "value", "key": key, "value": value})

        def rewrite(ref: str | None, depth: int) -> str:
            children, old_value = self._branch(ref)
            if depth == len(digits):
                old_value = value_ref
            else:
                char = digits[depth]
                children[char] = rewrite(children.get(char), depth + 1)
            return self._put({"type": "branch", "children": children, "value": old_value})

        return rewrite(index, 0)

    def _root(self) -> _Root:
        if not self.root_path.exists():
            return _Root(0, None, None)
        try:
            payload = json.loads(self.root_path.read_bytes())
            if (
                set(payload) != {"schema_version", "generation", "index_ref", "event_ref"}
                or payload["schema_version"] != "source-admission-root.v1"
                or type(payload["generation"]) is not int
                or payload["generation"] < 1
            ):
                raise ValueError("root shape")
            root = _Root(
                payload["generation"],
                _ref_text(payload["index_ref"]),
                _ref_text(payload["event_ref"]),
            )
            event = self._object(root.event_ref)
            if (
                event["generation"] != root.generation
                or event["schema_version"] != "source-event.v1"
            ):
                raise ValueError("root event")
            return root
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError("source_admission_committed_state_corrupt") from exc

    def _durabilize(self, root: _Root) -> None:
        if root.generation == 0:
            return
        # A previous replace may have succeeded before a directory fsync failed.
        # Re-establish actual root/object directory durability before ACK/positive.
        descriptor = os.open(self.root_path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self._fsync_dir(self.objects)
        self._fsync_dir(self.root_path.parent)
        self._fsync_dir(self.root_path.parent.parent)
        self._point("after_root_durability_reconciliation")

    def _publish(self, root: _Root) -> None:
        temp = self.root_path.with_name(".source-root-" + uuid.uuid4().hex)
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(_bytes(root.payload()))
                stream.flush()
                os.fsync(stream.fileno())
            self._point("before_root_publish")
            os.replace(temp, self.root_path)
            self._point("after_root_replace")
            self._fsync_dir(self.root_path.parent)
            self._fsync_dir(self.root_path.parent.parent)
            self._point("after_root_fsync")
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temp.unlink(missing_ok=True)

    def _receipt(self, event_ref: str) -> SourceAdmissionReceipt:
        body = self._object(event_ref)
        fields = dict(body["result"])
        meta = {
            "event_id": body["command"]["event_id"],
            "event_ref": "sha256:" + event_ref,
            "generation": body["generation"],
            "committed_at": body["committed_at"],
        }
        if fields.get("source_registration") is not None:
            fields["source_registration"] = {**fields["source_registration"], **meta}
        if fields.get("carrier") is not None:
            fields["carrier"] = dict(fields["carrier"])
            fields["carrier"].setdefault("admission_event_ref", meta["event_ref"])
        return _typed(
            SourceAdmissionReceipt,
            {
                **fields,
                **meta,
                "scope_head": meta["event_ref"],
                "rule_version": _RULE,
            },
        )

    def _commit(
        self,
        command: dict[str, Any],
        prepare: Callable[[_Root], tuple[str, dict[str, dict[str, Any]], dict[str, Any]]],
        validate_origin: Callable[[], None] | None = None,
    ) -> SourceAdmissionReceipt:
        with self._transaction():
            self._begin()
            if validate_origin is not None and validate_origin() is not None:
                raise ValueError("source_admission_origin_not_established")
            root = self._root()
            self._durabilize(root)
            event_key = "event:" + command["event_id"]
            prior = self._lookup(root.index_ref, event_key)
            command_digest = _digest(command)
            if prior is not None:
                if prior["command_digest"] != command_digest:
                    raise ValueError("source_admission_conflicting_event_id")
                return self._receipt(prior["event_ref"])
            scope, updates, result = prepare(root)
            body = {
                "schema_version": "source-event.v1",
                "rule_version": _RULE,
                "generation": root.generation + 1,
                "committed_at": datetime.now(UTC).isoformat(),
                "command": command,
                "command_digest": command_digest,
                "result": result,
            }
            event_ref = self._put(body)
            receipt = self._receipt(event_ref)
            updates[event_key] = {
                "event_ref": event_ref,
                "command_digest": command_digest,
            }
            updates["head:" + scope] = {"event_ref": receipt.event_ref}
            # Resolve only the original event's generated references, not arbitrary strings.
            if receipt.source_registration is not None:
                registration = receipt.source_registration.model_dump(mode="json")
                updates["registration:" + scope] = registration
            if receipt.carrier is not None and command["operation"] in {
                "admit",
                "readmit",
            }:
                carrier = receipt.carrier.model_dump(mode="json")
                carrier_key = "carrier:" + _digest(carrier)
                updates[carrier_key] = {
                    "status": "active",
                    "carrier": carrier,
                    "revision_key": updates.pop("$revision_key")["value"],
                }
                revision_key = updates[carrier_key]["revision_key"]
                updates[revision_key]["current_carrier"] = carrier
            index = root.index_ref
            for key, value in sorted(updates.items()):
                index = self._update(index, key, value)
            assert index is not None
            if validate_origin is not None and validate_origin() is not None:
                raise ValueError("source_admission_origin_not_established")
            self._publish(_Root(root.generation + 1, index, event_ref))
            self._point("before_commit_acknowledgement")
            return receipt

    @staticmethod
    def _registration_lookup(authority: dict[str, str], registration_key: str) -> str:
        return "source:" + _digest({**authority, "registration_key": registration_key})

    @staticmethod
    def _scope(registration: dict[str, Any]) -> str:
        return _digest(
            {
                key: registration[key]
                for key in (
                    "tenant_id",
                    "cell_id",
                    "source_incarnation_id",
                    "effective_view_contract_ref",
                    "use_contract_ref",
                )
            }
        )

    def register(
        self,
        *,
        authority: dict[str, str],
        event_id: str,
        registration_key: str,
        view_ref: dict[str, Any],
        use_ref: dict[str, Any],
        verified_refs: list[dict[str, Any]],
        validate_origin: Callable[[], None] | None = None,
    ) -> SourceRegistrationReceipt:
        command = {
            "event_id": event_id,
            "operation": "genesis",
            "authority": authority,
            "registration_key": registration_key,
            "effective_view_contract_ref": view_ref,
            "use_contract_ref": use_ref,
            "verified_refs": verified_refs,
            "rule_version": _RULE,
        }

        def prepare(root: _Root):
            source_key = self._registration_lookup(authority, registration_key)
            source = self._lookup(root.index_ref, source_key)
            if source is None:
                source = {
                    **authority,
                    "registration_key": registration_key,
                    "source_incarnation_id": uuid.uuid4().hex,
                }
            registration = {
                **source,
                "effective_view_contract_ref": view_ref,
                "use_contract_ref": use_ref,
                "rule_version": _RULE,
            }
            scope = self._scope(registration)
            if self._lookup(root.index_ref, "registration:" + scope) is not None:
                raise ValueError("source_admission_genesis_already_committed")
            registration["admission_scope_digest"] = scope
            return (
                scope,
                {source_key: source},
                {"operation": "genesis", "source_registration": registration},
            )

        receipt = self._commit(command, prepare, validate_origin)
        assert receipt.source_registration is not None
        return receipt.source_registration

    def _require_registration(
        self, root: _Root, registration: SourceRegistrationReceipt
    ) -> dict[str, Any]:
        payload = registration.model_dump(mode="json")
        current = self._lookup(
            root.index_ref, "registration:" + registration.admission_scope_digest
        )
        if current != payload or self._scope(payload) != registration.admission_scope_digest:
            raise ValueError("source_admission_registration_not_committed")
        return payload

    def _predecessor(self, root: _Root, scope: str, expected: str) -> None:
        head = self._lookup(root.index_ref, "head:" + scope)
        if not isinstance(expected, str) or head is None or head["event_ref"] != expected:
            raise ValueError("source_admission_predecessor_gap")

    def admit(
        self,
        *,
        materialization: RegisteredMaterialization,
        event_id: str,
        expected_predecessor: str,
        verified_refs: list[dict[str, Any]],
        validate_origin: Callable[[], None] | None = None,
    ) -> SourceAdmissionReceipt:
        frozen = materialization.model_dump(mode="json")
        scope = materialization.registration.admission_scope_digest
        revision_key = "revision:" + scope + ":" + materialization.occurrence_id
        revision_digest = _digest(frozen)
        command = {
            "event_id": event_id,
            "operation": "admit",
            "materialization": frozen,
            "expected_predecessor": expected_predecessor,
            "verified_refs": verified_refs,
            "rule_version": _RULE,
        }

        def prepare(root: _Root):
            self._require_registration(root, materialization.registration)
            self._predecessor(root, scope, expected_predecessor)
            if self._lookup(root.index_ref, revision_key) is not None:
                raise ValueError("source_admission_occurrence_requires_explicit_readmit")
            carrier = {
                "tenant_id": materialization.registration.tenant_id,
                "cell_id": materialization.registration.cell_id,
                "source_incarnation_id": materialization.registration.source_incarnation_id,
                "admission_scope_digest": scope,
                "occurrence_id": materialization.occurrence_id,
                "revision_digest": revision_digest,
                "admission_epoch": uuid.uuid4().hex,
                "snapshot_ref": materialization.snapshot_ref.model_dump(mode="json"),
                "use_contract_ref": materialization.registration.use_contract_ref.model_dump(
                    mode="json"
                ),
            }
            fact = {
                "materialization": frozen,
                "verified_refs": verified_refs,
                "revision_digest": revision_digest,
                "producer_relation": "canonical_capture",
                "rule_version": _RULE,
            }
            return (
                scope,
                {revision_key: fact, "$revision_key": {"value": revision_key}},
                {
                    "operation": "admit",
                    "carrier": carrier,
                },
            )

        return self._commit(command, prepare, validate_origin)

    def transition(
        self,
        *,
        authority: dict[str, str],
        event_id: str,
        expected_predecessor: str,
        operation: Literal["withdraw", "readmit", "supersede"],
        target: SourceAdmissionCarrier,
        validate_origin: Callable[[], None] | None = None,
    ) -> SourceAdmissionReceipt:
        if operation not in {"withdraw", "readmit", "supersede"}:
            raise ValueError("source_admission_operation_unsupported")
        carrier = target.model_dump(mode="json")
        scope = target.admission_scope_digest
        carrier_key = "carrier:" + _digest(carrier)
        command = {
            "event_id": event_id,
            "operation": operation,
            "authority": authority,
            "expected_predecessor": expected_predecessor,
            "target": carrier,
            "rule_version": _RULE,
        }

        def prepare(root: _Root):
            registration = self._lookup(root.index_ref, "registration:" + scope)
            if registration is None or any(
                registration.get(key) != value for key, value in authority.items()
            ):
                raise ValueError("source_admission_wrong_authority_scope")
            self._predecessor(root, scope, expected_predecessor)
            current = self._lookup(root.index_ref, carrier_key)
            if current is None or current["carrier"] != carrier:
                raise ValueError("source_admission_carrier_not_committed")
            revision_key = current["revision_key"]
            fact = self._lookup(root.index_ref, revision_key)
            if fact is None or fact["revision_digest"] != target.revision_digest:
                raise ValueError("source_admission_revision_not_committed")
            changes = {}
            if operation == "readmit":
                if current["status"] != "withdrawn" or fact["current_carrier"] != carrier:
                    raise ValueError("source_admission_readmit_requires_latest_withdrawn_epoch")
                new_carrier = {
                    key: value for key, value in carrier.items() if key != "admission_event_ref"
                }
                new_carrier["admission_epoch"] = uuid.uuid4().hex
                changes[revision_key] = dict(fact)
                changes["$revision_key"] = {"value": revision_key}
                return scope, changes, {"operation": "readmit", "carrier": new_carrier}
            if current["status"] != "active":
                raise ValueError("source_admission_target_not_active")
            if operation == "withdraw":
                changes[carrier_key] = {**current, "status": "withdrawn"}
                selected = self._lookup(root.index_ref, "selected:" + scope)
                if selected is not None and selected.get("carrier") == carrier:
                    changes["selected:" + scope] = {"carrier": None}
            else:
                changes["selected:" + scope] = {"carrier": carrier}
            return scope, changes, {"operation": operation, "carrier": carrier}

        return self._commit(command, prepare, validate_origin)

    def event_receipt(
        self, *, authority: dict[str, str], event_id: str
    ) -> SourceAdmissionReceipt | None:
        """Resolve original committed history after an uncertain ACK, without replaying acquisition.

        This is a protected history query, not permission to skip/accept a changed
        command. An actual repeated write still compares the complete command.
        """
        with self._transaction():
            self._begin()
            root = self._root()
            self._durabilize(root)
            row = self._lookup(root.index_ref, "event:" + event_id)
            if row is None:
                return None
            body = self._object(row["event_ref"])
            command = body["command"]
            actual = command.get("authority")
            if actual is None:
                actual = command["materialization"]["registration"]
            if any(actual.get(key) != value for key, value in authority.items()):
                raise ValueError("source_admission_wrong_authority_scope")
            return self._receipt(row["event_ref"])

    def fact_for_carrier(self, target: SourceAdmissionCarrier) -> dict[str, Any]:
        """Get a committed revision for exact readmission integrity checks, even if withdrawn."""
        with self._transaction():
            self._begin()
            root = self._root()
            self._durabilize(root)
            carrier = target.model_dump(mode="json")
            current = self._lookup(root.index_ref, "carrier:" + _digest(carrier))
            if current is None or current.get("carrier") != carrier:
                raise ValueError("source_admission_carrier_not_committed")
            fact = self._lookup(root.index_ref, current["revision_key"])
            if fact is None or fact.get("revision_digest") != target.revision_digest:
                raise ValueError("source_admission_revision_not_committed")
            return fact

    def snapshot_facts(
        self,
        carriers: tuple[SourceAdmissionCarrier, ...],
        *,
        require_selected: bool = False,
    ) -> tuple[_Root, list[dict[str, Any]], tuple[str, ...]]:
        """Read only committed facts under the same fence, including durable retry."""
        with self._transaction():
            self._begin()
            root = self._root()
            self._durabilize(root)
            reasons: list[str] = []
            facts: list[dict[str, Any]] = []
            if not carriers:
                reasons.append("source_admission_required_basis_not_established")
            for target in carriers:
                carrier = target.model_dump(mode="json")
                current = self._lookup(root.index_ref, "carrier:" + _digest(carrier))
                if current is None or current.get("carrier") != carrier:
                    reasons.append("source_admission_carrier_not_committed")
                    continue
                if current["status"] != "active":
                    reasons.append("source_admission_withdrawn")
                    continue
                fact = self._lookup(root.index_ref, current["revision_key"])
                if (
                    fact is None
                    or fact.get("current_carrier") != carrier
                    or fact.get("revision_digest") != target.revision_digest
                    or fact.get("producer_relation") != "canonical_capture"
                    or fact.get("rule_version") != _RULE
                ):
                    reasons.append("source_admission_required_basis_not_established")
                    continue
                registration = self._lookup(
                    root.index_ref, "registration:" + target.admission_scope_digest
                )
                expected_registration = fact["materialization"]["registration"]
                if (
                    registration != expected_registration
                    or self._scope(registration) != target.admission_scope_digest
                ):
                    reasons.append("source_admission_registration_not_committed")
                    continue
                if require_selected:
                    selected = self._lookup(
                        root.index_ref, "selected:" + target.admission_scope_digest
                    )
                    if selected is None or selected.get("carrier") != carrier:
                        reasons.append("source_admission_not_selected_for_use")
                        continue
                facts.append(fact)
            return root, facts, tuple(dict.fromkeys(reasons))
