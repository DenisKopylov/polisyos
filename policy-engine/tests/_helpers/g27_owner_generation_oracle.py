"""Independent command and disk witnesses for registered-SQL owner tests.

This test helper exercises the existing Fabric/DecisionValidityService owner;
it never issues source authority. Its independent reducer and physical hash/profile reader do not call
production digest, snapshot_facts, receipt, or index lookup helpers. Selected
Core payload grammar/conformance deliberately reuses the normative decoder;
that shared parser is not an independent codec proof. The child
entrypoint is a fresh direct owner reader, not a SimulationResult/packet reader.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RULE = "policyos.registered-sql-admission.v1"
PURPOSE = "registered_sql_materialization_admission"


def canonical_bytes(value: object) -> bytes:
    """Encode the declared source-command JSON profile independently."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: object) -> str:
    """Hash a declared JSON value without calling the implementation's helper."""
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def basis_digest(carriers: list[dict[str, Any]]) -> str:
    """Bind this exact ordered any-active query, including repeated carriers."""
    return digest(
        {
            "rule_version": RULE,
            "authority_purpose": PURPOSE,
            "require_selected": False,
            "carriers": carriers,
        }
    )


def semantic_quantity(value: object) -> object:
    """Project supported decoded Core values to the HTTP comparison quantity.

    Tags are interpreted only by the actual declared Core grammar. In particular,
    an escaped .3 raw mapping that resembles a native envelope remains a mapping.
    This fixture supports exact JSON builtins and aware datetime; other native
    descriptors are explicitly unsupported rather than guessed into scalars.
    """
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        assert math.isfinite(value), "G27_SELECTED_SEMANTIC_NONFINITE"
        return value
    if type(value) is datetime:
        assert value.tzinfo is not None and value.utcoffset() is not None, (
            "G27_SELECTED_SEMANTIC_NAIVE_DATETIME"
        )
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if type(value) is list:
        return [semantic_quantity(item) for item in value]
    if type(value) is dict:
        assert all(type(key) is str for key in value), "G27_SELECTED_SEMANTIC_KEY_UNSUPPORTED"
        return {key: semantic_quantity(item) for key, item in value.items()}
    raise AssertionError("G27_SELECTED_SEMANTIC_TYPE_UNSUPPORTED:" + type(value).__name__)


def selected_semantic_quantity(manifest_raw: bytes, raw: bytes) -> tuple[object, dict[str, Any]]:
    """Reuse Core's exact selected CAN .2/.3 grammar, then project one quantity.

    The caller independently verifies the physical selected content/profile first.
    This function confers neither independent codec proof nor producer authority.
    Imports are deferred to the actual test runtime, never author preparation.
    """
    from polisyos.core.artifacts.canonical_profile import decode_core_json_payload

    try:
        read = decode_core_json_payload(manifest_raw, raw, allow_profile_absent=False)
        value = read.value
    except Exception as exc:
        code = getattr(exc, "code", type(exc).__name__)
        raise AssertionError("G27_SELECTED_CODEC_REFUSED:" + str(code)) from exc
    return semantic_quantity(value), {
        "status": read.status,
        "reader_policy_id": read.reader_policy_id,
        "codec_independence": "shared_normative_parser_not_independent_codec_proof",
    }


class FixtureCAS:
    """Independently bind selected filesystem bytes and preserve each member once."""

    def __init__(self, root: Path, evidence: Path) -> None:
        self.root, self.evidence = root, evidence
        self.inventory: dict[str, dict[str, Any]] = {}
        self.observation_sequence = 0
        (evidence / "members").mkdir(parents=True, exist_ok=False)

    def preserve(self, data: bytes) -> str:
        key = hashlib.sha256(data).hexdigest()
        path = self.evidence / "members" / key
        if path.exists():
            assert path.read_bytes() == data
        else:
            with path.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        return key

    def note(self, value: dict[str, Any]) -> int:
        """Append an observed/reconciled event without replacing earlier facts."""
        self.observation_sequence += 1
        with (self.evidence / "observations.jsonl").open("ab") as output:
            output.write(canonical_bytes({"sequence": self.observation_sequence, **value}) + b"\n")
            output.flush()
            os.fsync(output.fileno())
        return self.observation_sequence

    def begin_command(self, endpoint: str, body: dict[str, Any]) -> int:
        """Retain the submitted public command before invoking the protected path."""
        return self.note(
            {
                "kind": "http_command",
                "endpoint": endpoint,
                "body": copy.deepcopy(body),
                "predicate_provenance": "consumer_asserted",
            }
        )

    def observe_response(
        self,
        command: int,
        *,
        status: int | None,
        raw: bytes | None,
        transport_error: str | None = None,
    ) -> int:
        """Retain exact response/root bytes before any oracle or status assertion."""
        row: dict[str, Any] = {
            "kind": "http_response",
            "command_sequence": command,
            "status": status,
            "transport_error_type": transport_error,
            "predicate_provenance": "not_established",
        }
        if raw is not None:
            row["response_member"] = self.preserve(raw)
            try:
                value = json.loads(raw)
                row["selected_refs_observed"] = list(_refs(value))
                row["response_json"] = "parsed_for_selection_only"
            except (UnicodeDecodeError, ValueError, TypeError):
                row["response_json"] = "unparseable"
        root = self.root / "decision_validity/committed_source_root.json"
        try:
            row["committed_root_member"] = self.preserve(root.read_bytes())
        except FileNotFoundError:
            row["committed_root_read"] = "absent"
        except OSError as exc:
            row["committed_root_read"] = "error:" + type(exc).__name__
        return self.note(row)

    def finish_response(self, response: int, *, reconciled: bool) -> None:
        """Record success or an incomplete/failing oracle without erasing observation."""
        error = sys.exc_info()[0]
        self.note(
            {
                "kind": "http_reconciliation",
                "response_sequence": response,
                "predicate_provenance": "independently_reconciled"
                if reconciled
                else "not_established",
                "error_type": None if error is None else error.__name__,
            }
        )

    def selected(self, ref: dict[str, Any]) -> dict[str, Any]:
        attempt = self.note(
            {
                "kind": "selected_attempt",
                "ref": copy.deepcopy(ref),
                "predicate_provenance": "not_established",
            }
        )
        reconciled = False
        try:
            artifact_hex = ref["artifact_id"].removeprefix("sha256:")
            profile_hex = ref["manifest_profile_sha256"].removeprefix("sha256:")
            assert len(artifact_hex) == len(profile_hex) == 64
            assert not (set(artifact_hex + profile_hex) - set("0123456789abcdef"))
            base = self.root / "artifacts/sha256" / artifact_hex[:2] / artifact_hex[2:4]
            raw = (base / (artifact_hex + ".blob")).read_bytes()
            self.note(
                {
                    "kind": "selected_bytes",
                    "attempt_sequence": attempt,
                    "part": "payload",
                    "member": self.preserve(raw),
                }
            )
            path = base / (artifact_hex + ".view." + profile_hex + ".manifest.json")
            if not path.exists():
                path = base / (artifact_hex + ".manifest.json")
            manifest_raw = path.read_bytes()
            self.note(
                {
                    "kind": "selected_bytes",
                    "attempt_sequence": attempt,
                    "part": "manifest",
                    "member": self.preserve(manifest_raw),
                }
            )
            manifest = json.loads(manifest_raw)
            assert manifest["artifact_id"] == ref["artifact_id"]
            assert (manifest["kind"], manifest["media_type"]) == (ref["kind"], ref["media_type"])
            assert hashlib.sha256(raw).hexdigest() == artifact_hex, "G27_SELECTED_CONTENT_MISMATCH"
            assert len(raw) == manifest["byte_size"]
            assert manifest["integrity"]["sha256"] == artifact_hex, "G27_SELECTED_CONTENT_MISMATCH"
            version = manifest.get("manifest_schema_version", "v1")
            assert version in {"v1", "v2", "v3"}
            projection = {
                key: value
                for key, value in manifest.items()
                if key not in {"artifact_id", "byte_size", "created_at"}
                and not (version != "v3" and key == "integrity")
            }
            if version == "v3":
                projection["integrity"] = {
                    key: value for key, value in projection["integrity"].items() if key != "sha256"
                }
            # These controlled fixture profiles contain no floating metadata. JSON
            # payload floats are allowed; a future float profile is an explicit limit.
            assert not any(isinstance(value, float) for value in _values(projection)), (
                "G27_PROFILE_FLOAT_UNSUPPORTED"
            )
            profile_bytes = json.dumps(
                projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            domain = (
                "polisyos.cas.manifest-profile." + ("v2" if version == "v3" else "v1") + "\0"
            ).encode()
            assert hashlib.sha256(domain + profile_bytes).hexdigest() == profile_hex, (
                "G27_SELECTED_PROFILE_MISMATCH"
            )
            identity = canonical_bytes(ref).decode()
            record = {
                "ref": ref,
                "raw_sha256": "sha256:" + artifact_hex,
                "manifest_profile_sha256": ref["manifest_profile_sha256"],
            }
            self.inventory[identity] = {
                **record,
                "blob_member": self.preserve(raw),
                "manifest_member": self.preserve(manifest_raw),
            }
            (self.evidence / "selected-inventory.json").write_bytes(
                canonical_bytes(list(self.inventory.values()))
            )
            value, decoding = selected_semantic_quantity(manifest_raw, raw)
            reconciled = True
            return {
                "raw": raw,
                "value": value,
                "manifest": manifest,
                "verification": record,
                "decoding": decoding,
            }
        finally:
            error = sys.exc_info()[0]
            self.note(
                {
                    "kind": "selected_result",
                    "attempt_sequence": attempt,
                    "predicate_provenance": "independently_reconciled"
                    if reconciled
                    else "not_established",
                    "error_type": None if error is None else error.__name__,
                }
            )

    def verified(self, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique = {
            tuple(
                ref[key] for key in ("artifact_id", "kind", "media_type", "manifest_profile_sha256")
            ): ref
            for ref in refs
        }
        return [self.selected(unique[key])["verification"] for key in sorted(unique)]


def _values(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _values(child)


def _refs(value: object):
    if isinstance(value, dict):
        if {"artifact_id", "kind", "media_type", "manifest_profile_sha256"} <= value.keys():
            yield value
        else:
            for child in value.values():
                yield from _refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _refs(child)


class CommandOracle:
    """Reconcile complete committed facts against protected inputs and CAS bytes."""

    def __init__(self, cas: FixtureCAS, slots: dict[str, dict[str, Any]]) -> None:
        self.cas, self.slots = cas, slots
        self.generation = 0
        self.active: set[str] = set()
        self.withdrawn: set[str] = set()
        self.commands: dict[str, bytes] = {}
        self.responses: dict[str, dict[str, Any]] = {}
        self.scope_heads: dict[str, str] = {}
        self.registrations: dict[str, dict[str, Any]] = {}
        self.expected_index: dict[str, dict[str, Any]] = {}
        self.expected_events: dict[str, dict[str, Any]] = {}
        self.materializations: dict[str, dict[str, Any]] = {}
        self.last_event_ref: str | None = None

    def accept(
        self,
        endpoint: str,
        body: dict[str, Any],
        result: dict[str, Any],
        expected_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        event_id = body["event_id"]
        public = canonical_bytes({"endpoint": endpoint, "body": body})
        if event_id in self.commands:
            assert public == self.commands[event_id], "G27_RETRY_CHANGED_COMMAND"
            assert result == self.responses[event_id], "G27_RETRY_CHANGED_ORIGINAL_RECEIPT"
            self.reconcile(committed_snapshot(self.cas.root))
            return
        generation = self.generation + 1
        slot = self.slots[body["slot_id"]]
        authority = {
            key: slot[key] for key in ("issuer_key", "tenant_id", "cell_id", "provider_id")
        }
        receipt = result["registration"] if endpoint == "registrations" else result["receipt"]
        event_hex = receipt["event_ref"].removeprefix("sha256:")
        event_raw = (
            self.cas.root / "decision_validity/committed_source_objects" / (event_hex + ".json")
        ).read_bytes()
        assert hashlib.sha256(event_raw).hexdigest() == event_hex
        actual_event = json.loads(event_raw)
        stamp = actual_event["committed_at"]
        assert datetime.fromisoformat(stamp) == datetime.fromisoformat(
            receipt["committed_at"].replace("Z", "+00:00")
        )
        operation = {
            "registrations": "genesis",
            "materializations": "admit",
            "withdrawals": "withdraw",
        }[endpoint]
        meta = {
            "event_id": event_id,
            "event_ref": receipt["event_ref"],
            "generation": generation,
            "committed_at": receipt["committed_at"],
        }
        if operation == "genesis":
            source = {
                **authority,
                "registration_key": slot["registration_key"],
                "source_incarnation_id": receipt["source_incarnation_id"],
            }
            assert source["source_incarnation_id"] and all(
                old["source_incarnation_id"] != source["source_incarnation_id"]
                for old in self.registrations.values()
            )
            raw_registration = {
                **source,
                "effective_view_contract_ref": slot["effective_view_contract_ref"],
                "use_contract_ref": slot["use_contract_ref"],
                "rule_version": RULE,
            }
            scope = digest(
                {
                    key: raw_registration[key]
                    for key in (
                        "tenant_id",
                        "cell_id",
                        "source_incarnation_id",
                        "effective_view_contract_ref",
                        "use_contract_ref",
                    )
                }
            )
            raw_registration["admission_scope_digest"] = scope
            expected_registration = {
                "schema_version": "polisyos.source-registration.v1",
                **raw_registration,
                **meta,
            }
            assert receipt == expected_registration, "G27_COMMITTED_QUANTITY_MISMATCH"
            command = {
                "event_id": event_id,
                "operation": operation,
                "authority": authority,
                "registration_key": slot["registration_key"],
                "effective_view_contract_ref": slot["effective_view_contract_ref"],
                "use_contract_ref": slot["use_contract_ref"],
                "verified_refs": self.cas.verified(
                    [slot["effective_view_contract_ref"], slot["use_contract_ref"]]
                ),
                "rule_version": RULE,
            }
            event_result = {"operation": operation, "source_registration": raw_registration}
            self.expected_index[
                "source:" + digest({**authority, "registration_key": slot["registration_key"]})
            ] = source
            self.expected_index["registration:" + scope] = expected_registration
            self.registrations[slot["registration_key"]] = expected_registration
        elif operation == "admit":
            binding = self.cas.selected(result["binding_ref"])["value"]
            binding_receipt = copy.deepcopy(binding["receipt"])
            binding_receipt.setdefault("source_registration", None)
            assert binding_receipt == receipt
            assert binding["expected_predecessor"] == body["expected_predecessor"]
            materialization = copy.deepcopy(binding["materialization"])
            materialization.setdefault("upstream_asserted_at", None)
            assert materialization["upstream_asserted_at"] is None
            registration = self.registrations[slot["registration_key"]]
            assert materialization["registration"] == registration
            assert materialization["schema_version"] == "polisyos.registered-materialization.v1"
            assert materialization["occurrence_id"] == body["occurrence_id"]
            assert materialization["request_ref"] == body["request_ref"]
            assert (
                materialization["producer_rule_version"] == "policyos.registered-sql-execution.v1"
            )
            snapshot = self.cas.selected(materialization["snapshot_ref"])
            payload = self.cas.selected(materialization["payload_ref"])
            assert payload["value"] == expected_rows
            quality = self.cas.selected(materialization["quality_ref"])["value"]
            assert datetime.fromisoformat(
                materialization["observed_at"].replace("Z", "+00:00")
            ) == datetime.fromisoformat(
                quality["freshness_status"]["fetched_at"].replace("Z", "+00:00")
            )
            expected_links = {
                "data_ref": materialization["payload_ref"],
                "data_schema_ref": materialization["schema_ref"],
                "quality_report_ref": materialization["quality_ref"],
            }
            for key, ref in expected_links.items():
                assert snapshot["value"][key] == ref
            assert (
                snapshot["value"]["source_lineage"]["data_view_request_ref"] == body["request_ref"]
            )
            view = self.cas.selected(slot["effective_view_contract_ref"])["value"]
            capture = self.cas.selected(materialization["producer_capture_ref"])["value"]
            for key, expected in {
                "connector_id": slot["connector_id"],
                "config_fingerprint": view["config_fingerprint"],
                "statement": view["statement"],
                "parameters": [],
                "page_size": view["page_size"],
                "request_ref": body["request_ref"],
                "snapshot_ref": materialization["snapshot_ref"],
                "payload_ref": materialization["payload_ref"],
                "schema_ref": materialization["schema_ref"],
                "quality_ref": materialization["quality_ref"],
                "view_ref": slot["effective_view_contract_ref"],
                "use_ref": slot["use_contract_ref"],
                "external_currentness": "not_established",
                "external_completeness": "not_established",
                "execution_mode": "one_direct_query_no_retry_cache_or_fallback",
            }.items():
                assert capture[key] == expected, "G27_COMMITTED_QUANTITY_MISMATCH"
            output_raw = json.dumps(
                expected_rows,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            assert capture["output_sha256"] == "sha256:" + hashlib.sha256(output_raw).hexdigest()
            scope = registration["admission_scope_digest"]
            assert body["expected_predecessor"] == self.scope_heads[scope]
            verified = self.cas.verified(
                [
                    materialization["snapshot_ref"],
                    materialization["producer_capture_ref"],
                    slot["effective_view_contract_ref"],
                    slot["use_contract_ref"],
                    *list(_refs(snapshot["value"])),
                ]
            )
            command = {
                "event_id": event_id,
                "operation": operation,
                "materialization": materialization,
                "expected_predecessor": body["expected_predecessor"],
                "verified_refs": verified,
                "rule_version": RULE,
            }
            carrier_raw = {
                key: registration[key]
                for key in (
                    "tenant_id",
                    "cell_id",
                    "source_incarnation_id",
                    "admission_scope_digest",
                )
            }
            carrier_raw.update(
                {
                    "occurrence_id": body["occurrence_id"],
                    "revision_digest": digest(materialization),
                    "admission_epoch": receipt["carrier"]["admission_epoch"],
                    "snapshot_ref": materialization["snapshot_ref"],
                    "use_contract_ref": slot["use_contract_ref"],
                }
            )
            assert carrier_raw["admission_epoch"]
            carrier = {
                "schema_version": "polisyos.source-admission-carrier.v1",
                **carrier_raw,
                "admission_event_ref": receipt["event_ref"],
            }
            event_result = {"operation": operation, "carrier": carrier_raw}
            revision_key = "revision:" + scope + ":" + body["occurrence_id"]
            self.expected_index[revision_key] = {
                "materialization": materialization,
                "verified_refs": verified,
                "revision_digest": digest(materialization),
                "producer_relation": "canonical_capture",
                "rule_version": RULE,
                "current_carrier": carrier,
            }
            self.expected_index["carrier:" + digest(carrier)] = {
                "status": "active",
                "carrier": carrier,
                "revision_key": revision_key,
            }
            self.materializations[event_id] = materialization
            self.active.add(canonical_bytes(carrier).decode())
        else:
            carrier = body["target"]
            key = canonical_bytes(carrier).decode()
            assert key in self.active
            scope = carrier["admission_scope_digest"]
            assert body["expected_predecessor"] == self.scope_heads[scope]
            command = {
                "event_id": event_id,
                "operation": operation,
                "authority": authority,
                "expected_predecessor": body["expected_predecessor"],
                "target": carrier,
                "rule_version": RULE,
            }
            event_result = {"operation": operation, "carrier": carrier}
            self.expected_index["carrier:" + digest(carrier)]["status"] = "withdrawn"
            self.active.remove(key)
            self.withdrawn.add(key)
        if operation != "genesis":
            expected_receipt = {
                "schema_version": "polisyos.source-admission-receipt.v1",
                **meta,
                "operation": operation,
                "scope_head": receipt["event_ref"],
                "carrier": carrier,
                "source_registration": None,
                "rule_version": RULE,
            }
            assert receipt == expected_receipt, "G27_COMMITTED_QUANTITY_MISMATCH"
        expected_event = {
            "schema_version": "source-event.v1",
            "rule_version": RULE,
            "generation": generation,
            "committed_at": stamp,
            "command": command,
            "command_digest": digest(command),
            "result": event_result,
        }
        assert actual_event == expected_event, "G27_COMMITTED_QUANTITY_MISMATCH"
        self.expected_events[event_id] = expected_event
        self.expected_index["event:" + event_id] = {
            "event_ref": event_hex,
            "command_digest": digest(command),
        }
        self.expected_index["head:" + scope] = {"event_ref": receipt["event_ref"]}
        self.generation, self.last_event_ref = generation, receipt["event_ref"]
        self.scope_heads[scope] = receipt["event_ref"]
        self.commands[event_id], self.responses[event_id] = public, result
        self.reconcile(committed_snapshot(self.cas.root))

    def reconcile(self, snapshot: dict[str, Any]) -> None:
        assert snapshot["indexed"] == self.expected_index, "G27_COMMITTED_QUANTITY_MISMATCH"
        assert snapshot["events"] == self.expected_events, "G27_COMMITTED_QUANTITY_MISMATCH"
        assert snapshot["root"]["generation"] == self.generation
        assert "sha256:" + snapshot["root"]["event_ref"] == self.last_event_ref

    def check_projection(
        self, value: dict[str, Any], carriers: list[dict[str, Any]], disk: dict[str, Any]
    ) -> None:
        self.reconcile(disk)
        identities = [canonical_bytes(item).decode() for item in carriers]
        expected = "withdrawn" if any(item in self.withdrawn for item in identities) else "current"
        assert identities and all(item in self.active | self.withdrawn for item in identities)
        assert value["status"] == expected, "G27_WITHDRAWN_A_FALSE_CURRENT"
        assert value["reason_codes"] == (
            [] if expected == "current" else ["source_admission_withdrawn"]
        )
        assert value["generation"] == self.generation
        assert value["committed_root"] == disk["root_digest"]
        assert value["basis_digest"] == basis_digest(carriers)
        assert value["selection_checked"] is False
        assert value["rule_version"] == RULE and value["authority_purpose"] == PURPOSE
        assert value["read_boundary"] == "owner_fence_linearization_point"
        assert value["predicate_provenance"] == (
            "recomputed" if expected == "current" else "not_established"
        )


def committed_snapshot(cas_root: Path) -> dict[str, Any]:
    """Resolve the actual root and every reachable index/event object by its bytes.

    This independently decodes the committed format, without constructing a
    production state store. It never treats unreachable orphan objects as facts.
    """
    base = cas_root / "decision_validity"
    raw = (base / "committed_source_root.json").read_bytes()
    root = json.loads(raw)
    assert set(root) == {"schema_version", "generation", "index_ref", "event_ref"}
    assert root["schema_version"] == "source-admission-root.v1"
    assert raw == canonical_bytes(root)
    seen: dict[str, dict[str, Any]] = {}
    indexed: dict[str, dict[str, Any]] = {}

    def read_object(ref: str) -> dict[str, Any]:
        assert len(ref) == 64 and set(ref) <= set("0123456789abcdef")
        if ref not in seen:
            payload = (base / "committed_source_objects" / f"{ref}.json").read_bytes()
            assert hashlib.sha256(payload).hexdigest() == ref
            value = json.loads(payload)
            assert isinstance(value, dict) and payload == canonical_bytes(value)
            seen[ref] = value
        return seen[ref]

    def visit(ref: str, prefix: str = "") -> None:
        item = read_object(ref)
        if item["type"] == "branch":
            assert set(item) == {"type", "children", "value"}
            for digit, child in item["children"].items():
                assert len(digit) == 1 and digit in "0123456789abcdef" and len(prefix) < 64
                visit(child, prefix + digit)
            if item["value"] is not None:
                visit(item["value"], prefix)
        else:
            assert item["type"] == "value" and set(item) == {"type", "key", "value"}
            assert hashlib.sha256(item["key"].encode()).hexdigest() == prefix
            assert item["key"] not in indexed
            indexed[item["key"]] = item["value"]

    visit(root["index_ref"])
    events = {}
    for key, value in indexed.items():
        if key.startswith("event:"):
            event = read_object(value["event_ref"])
            assert event["command"]["event_id"] == key.removeprefix("event:")
            assert digest(event["command"]) == value["command_digest"] == event["command_digest"]
            events[key.removeprefix("event:")] = event
    assert read_object(root["event_ref"])["generation"] == root["generation"]
    assert sorted(event["generation"] for event in events.values()) == list(
        range(1, root["generation"] + 1)
    )
    return {
        "root": root,
        "root_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "events": events,
        "indexed": indexed,
        "reachable_object_count": len(seen),
    }


def fresh_owner_reads(
    cas_root: Path,
    vectors: dict[str, list[dict[str, Any]]],
    evidence: Path,
    *,
    tenant_id: str,
    cell_id: str,
) -> dict[str, Any]:
    """Launch the existing interpreter in a fresh process and retain full streams."""
    evidence.mkdir(exist_ok=False)
    request = evidence / "request.json"
    response = evidence / "response.json"
    request.write_bytes(
        canonical_bytes(
            {
                "cas_root": str(cas_root),
                "vectors": vectors,
                "tenant_id": tenant_id,
                "cell_id": cell_id,
            }
        )
    )
    argv = [
        sys.executable,
        "-B",
        "-m",
        "tests._helpers.g27_owner_generation_oracle",
        str(request),
        str(response),
    ]
    child_env = {**os.environ, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    # Preserve any source observer at the front of the inherited import path.
    child_env["PYTHONPYCACHEPREFIX"] = str(evidence / "private-pycache")
    journal = {
        "argv": argv,
        "cwd": os.getcwd(),
        "pid": None,
        "exit": None,
        "status": "SPAWN_PENDING",
        "termination": None,
    }
    command_path = evidence / "command.json"
    command_path.write_bytes(canonical_bytes(journal))
    process = None
    try:
        with (evidence / "stdout").open("xb") as stdout, (evidence / "stderr").open("xb") as stderr:
            process = subprocess.Popen(argv, env=child_env, stdout=stdout, stderr=stderr)
            journal.update(pid=process.pid, status="RUNNING")
            command_path.write_bytes(canonical_bytes(journal))
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                journal.update(status="TIMEOUT", termination="terminate_then_kill_if_needed")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise
            journal.update(status="EXITED", exit=process.returncode)
    except BaseException as exc:
        if journal["status"] != "TIMEOUT":
            journal["status"] = "ERROR"
        journal["exception"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if process is not None:
            journal["exit"] = process.poll()
        command_path.write_bytes(canonical_bytes(journal))
    assert journal["exit"] == 0, (evidence / "stderr").read_text()
    value = json.loads(response.read_bytes())
    assert value["pid"] == journal["pid"] and value["ppid"] == os.getpid()
    return value


def _child_main(request: Path, response: Path) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.contracts.decision_validity import SourceAdmissionCarrier
    from polisyos.core.security import tenant_scope
    from polisyos.scientist.validation.decision_validity import DecisionValidityService

    value = json.loads(request.read_bytes())
    cas_root = Path(value["cas_root"])
    tenant_id, cell_id = value["tenant_id"], value["cell_id"]
    owner = DecisionValidityService(FileSystemCAS(cas_root, tenant_id=tenant_id, cell_id=cell_id))
    projections = {}
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        for name, rows in value["vectors"].items():
            carriers = tuple(
                SourceAdmissionCarrier.model_validate_json(json.dumps(row), strict=True)
                for row in rows
            )
            projections[name] = owner.read_source_current_use(
                carriers, require_selected=False
            ).model_dump(mode="json")
    response.write_bytes(
        canonical_bytes({"pid": os.getpid(), "ppid": os.getppid(), "projections": projections})
    )


if __name__ == "__main__":
    _child_main(Path(sys.argv[1]), Path(sys.argv[2]))
