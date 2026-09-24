"""Independent sealed response conformance consumer and executable audit checker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import shutil
import sqlite3
import sys
import tomllib
from collections import Counter
from pathlib import Path
from types import FunctionType, MethodType, ModuleType
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict

from polisyos.runtime.quality import constrained_response as runtime
from polisyos.runtime.quality.response_corpus_evaluator import replay_corpus
from tools import response_transition_oracle as oracle

REPO = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO / "docs/reference/response-corpus"
GUARDRAIL_COUNTERS = (
    "threshold_auto_action_escape_count",
    "diagnosis_bypass_count",
    "unauthorized_transition_count",
    "protective_action_missed_count",
    "posterior_learning_bypass_count",
    "world_write_bypass_count",
    "restart_without_evidence_count",
    "silent_version_reuse_count",
    "duplicate_irreversible_action_count",
    "historical_rewrite_count",
    "subgroup_or_spillover_mask_count",
    "owner_absence_treated_as_approval_count",
)
FAMILY_COUNTS = {
    "A0_observe": 2,
    "A1_investigate": 3,
    "A2_contain": 3,
    "A3_refresh": 3,
    "A4_adjust": 3,
    "A5_pause_or_rollback": 3,
    "A6_terminate_or_redesign": 3,
}
OPERATIONS = set(get_args(runtime.Operation.__value__))


class CorpusReport(BaseModel):
    """Local mechanical conformance result; never an appointed empirical grade."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["response-corpus-report.v1"] = "response-corpus-report.v1"
    packet_sha256: str
    packet_count: int
    event_count: int
    family_counts: dict[str, int]
    operation_coverage: list[str]
    guardrail_counters: dict[str, int]
    high_harm_declared: int
    high_harm_preserved: int
    proxy_pairs: list[dict[str, Any]]
    issues: list[str]
    external_execution_claimed: Literal[False] = False
    institutional_appointment: None = None
    scope: Literal["candidate_custody_conformance"] = "candidate_custody_conformance"


def check_operation_coverage(corpus: dict[str, Any]) -> set[str]:
    """Require actual operation-specific changes, not the operation-name census."""
    covered: set[str] = set()
    for packet in corpus["packets"]:
        first, second = packet["events"][:2]
        if first["operation"] == "observe" and first["observation"] != second["observation"]:
            covered.add("observe")
        for event in packet["events"]:
            old, new, op = event["current"], event["requested"], event["operation"]
            changed_version = event.get("requested_version") not in (
                None,
                event["intervention_version"],
            )
            predicates = {
                "early_warning": old["E"] == "E0" and new["E"] == "E1",
                "diagnose": old["E"] != new["E"] and new["E"] in ("E2", "E3"),
                "refresh": event["observation"]["health"] == "invalid",
                "recompute": event["observation"]["expected_denominator"]
                != event["observation"]["observed_denominator"],
                "recalibrate": event.get("requested_measurement_epoch")
                not in (None, event["measurement_epoch"]),
                "adjust_implementation": old["V"] != "V2" and new["V"] == "V2" and changed_version,
                "narrow_scope": old["X"] != "X2" and new["X"] == "X2",
                "partial_reissue": old["V"] != "V2" and new["V"] == "V2" and changed_version,
                "pause": old["X"] != "X3" and new["X"] == "X3",
                "rollback": old["V"] != "V4" and new["V"] == "V4",
                "redesign": old["V"] != "V3" and new["V"] == "V3" and changed_version,
                "terminate": old["X"] != "X4" and new["X"] == "X4",
                "restart": old["X"] == "X3" and new["X"] == "X0",
            }
            if predicates.get(op, False):
                covered.add(op)
    if covered != OPERATIONS:
        raise ValueError("operation_semantics_missing:" + ",".join(sorted(OPERATIONS - covered)))
    return covered


def _semantic_closure(*roots: object) -> set[object]:
    """Walk actual reachable project callables, including aliases and closures."""
    pending = list(roots)
    seen: set[int] = set()
    found: set[object] = set()
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, MethodType):
            pending.append(value.__func__)
        elif isinstance(value, FunctionType):
            filename = Path(value.__code__.co_filename).resolve()
            found.add(value.__code__)
            if not filename.is_relative_to(REPO):
                continue
            for name in value.__code__.co_names:
                if name not in value.__globals__:
                    continue
                dependency = value.__globals__[name]
                pending.append(dependency)
                # Resolve actual attributes named by the caller, including inherited
                # model decoders and aliased external JSON/comparison functions.
                for attribute in value.__code__.co_names:
                    if isinstance(dependency, ModuleType):
                        pending.append(vars(dependency).get(attribute))
                    elif inspect.isclass(dependency):
                        pending.append(getattr(dependency, attribute, None))
            pending.extend(value.__defaults__ or ())
            pending.extend((value.__kwdefaults__ or {}).values())
            pending.extend(cell.cell_contents for cell in value.__closure__ or ())
        elif isinstance(value, ModuleType):
            filename = getattr(value, "__file__", None)
            if filename and Path(filename).resolve().is_relative_to(REPO):
                pending.extend(vars(value).values())
        elif inspect.isclass(value) and getattr(value, "__module__", "").startswith("polisyos"):
            for member in vars(value).values():
                if isinstance(member, classmethod | staticmethod):
                    pending.append(member.__func__)
                elif isinstance(member, FunctionType):
                    pending.append(member)
    return found


def assert_independent() -> None:
    """Reject real shared interpretation dependencies instead of owner-name claims."""
    producer = _semantic_closure(
        runtime.decode_packet,
        runtime.assess_response,
        runtime.ConstrainedResponseRuntime.append,
        runtime.ConstrainedResponseRuntime.read,
    )
    evaluator = _semantic_closure(oracle.decode_packet, oracle.expectation)
    if not producer or not evaluator or producer.intersection(evaluator):
        raise ValueError("oracle_independence_dependency_shared")


def _sealed_expectations(corpus_root: Path, raw: bytes) -> dict[tuple[str, int], dict[str, Any]]:
    sealed = tomllib.loads((corpus_root / "oracle.toml").read_text())
    if sealed.get("owner") != oracle.OWNER or sealed.get("version") != "response-oracle.v1":
        raise ValueError("oracle_owner_or_version_mismatch")
    if sealed["packet_sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("packet_seal_mismatch")
    if (
        sealed["oracle_source_sha256"]
        != hashlib.sha256(Path(oracle.__file__).read_bytes()).hexdigest()
    ):
        raise ValueError("oracle_source_seal_mismatch")
    corpus = oracle.decode_packet(raw)
    expected = {}
    for row in sealed["expectations"]:
        payload = row["payload"]
        if row["sha256"] != hashlib.sha256(payload.encode()).hexdigest():
            raise ValueError("oracle_seal_mismatch")
        key = (row["scenario_id"], row["offset"])
        if key in expected:
            raise ValueError("oracle_duplicate_expectation")
        expected[key] = json.loads(payload)
    actual_keys = set()
    for packet in corpus["packets"]:
        for offset, event in enumerate(packet["events"]):
            key = (packet["scenario_id"], offset)
            actual_keys.add(key)
            if expected.get(key) != oracle.expectation(event):
                raise ValueError("oracle_recompute_mismatch")
    if actual_keys != set(expected):
        raise ValueError("oracle_expectation_denominator_mismatch")
    return expected


def _escape_counters(
    event: dict[str, Any], expected: dict[str, Any], observed: dict[str, Any]
) -> dict[str, int]:
    actual = observed["assessment"]
    reasons = set(actual["reasons"])
    failures = {
        "threshold_auto_action_escape_count": event.get("charter_ref") is None
        and (actual["execution_authorized"] or "transition_charter_missing" not in reasons),
        "diagnosis_bypass_count": "diagnosis_unresolved_for_action" in expected["reasons"]
        and "diagnosis_unresolved_for_action" not in reasons,
        "unauthorized_transition_count": actual["execution_authorized"],
        "protective_action_missed_count": expected["protective_containment_required"]
        and not (
            actual["protective_containment_required"]
            and actual["conservative_posture"] == "no_authority_expansion"
        ),
        "posterior_learning_bypass_count": actual["posterior_learning_allowed"],
        "world_write_bypass_count": actual["world_write_allowed"],
        "restart_without_evidence_count": event["operation"] == "restart"
        and actual["candidate_admissible"],
        "silent_version_reuse_count": "version_identity_reused" in expected["reasons"]
        and ("version_identity_reused" not in reasons or actual["candidate_admissible"]),
        "duplicate_irreversible_action_count": observed["duplicate_irreversible_actions"] > 0,
        "historical_rewrite_count": not observed["history_intact"],
        "subgroup_or_spillover_mask_count": "subgroup_guardrail_block" in expected["reasons"]
        and "subgroup_guardrail_block" not in reasons,
        "owner_absence_treated_as_approval_count": actual["execution_authorized"]
        or observed["authority_predicate"] != "not_established",
    }
    return {name: int(value) for name, value in failures.items()}


def _mutate(counter: str, observation: dict[str, Any]) -> None:
    """Consumer-boundary fault injection; never alters persisted runtime artifacts."""
    actual = observation["assessment"]
    if counter == "threshold_auto_action_escape_count":
        actual["reasons"] = [r for r in actual["reasons"] if r != "transition_charter_missing"]
    elif counter == "diagnosis_bypass_count":
        actual["reasons"] = [r for r in actual["reasons"] if r != "diagnosis_unresolved_for_action"]
    elif counter == "unauthorized_transition_count":
        actual["execution_authorized"] = True
    elif counter == "protective_action_missed_count":
        actual["protective_containment_required"] = False
    elif counter == "posterior_learning_bypass_count":
        actual["posterior_learning_allowed"] = True
    elif counter == "world_write_bypass_count":
        actual["world_write_allowed"] = True
    elif counter == "restart_without_evidence_count":
        actual["candidate_admissible"] = True
    elif counter == "silent_version_reuse_count":
        actual["reasons"] = [r for r in actual["reasons"] if r != "version_identity_reused"]
    elif counter == "duplicate_irreversible_action_count":
        observation["duplicate_irreversible_actions"] = 1
    elif counter == "historical_rewrite_count":
        observation["history_intact"] = False
    elif counter == "subgroup_or_spillover_mask_count":
        actual["reasons"] = [r for r in actual["reasons"] if r != "subgroup_guardrail_block"]
    elif counter == "owner_absence_treated_as_approval_count":
        observation["authority_predicate"] = "consumer_asserted"
    else:
        raise ValueError("unknown_guardrail_mutant")


def evaluate_corpus(
    *, root: Path, corpus_root: Path = CORPUS_ROOT, mutant: str | None = None
) -> CorpusReport:
    """Independently grade complete real-owner replay against sealed expectations."""
    assert_independent()
    raw = (corpus_root / "packets.json").read_bytes()
    _sealed_expectations(corpus_root, raw)
    independent = oracle.decode_packet(raw)
    # Independent denominator: Pydantic objects versus stdlib raw dictionaries.
    typed = runtime.decode_packet(raw)
    if not isinstance(typed, runtime.ResponseCorpus):
        raise ValueError("runtime_packet_decode_invalid")
    left = {(p.scenario_id, p.family, len(p.events)) for p in typed.packets}
    right = {(p["scenario_id"], p["family"], len(p["events"])) for p in independent["packets"]}
    if left != right or len(left) != len(typed.packets):
        raise ValueError("corpus_denominator_disagreement")
    families = dict(Counter(p["family"] for p in independent["packets"]))
    operations = {e["operation"] for p in independent["packets"] for e in p["events"]}
    if families != FAMILY_COUNTS or operations != OPERATIONS:
        raise ValueError("corpus_family_or_operation_denominator")
    check_operation_coverage(independent)
    observations = replay_corpus(root=root, raw=raw)
    return grade_replay(
        root=root, raw=raw, observations=observations, corpus_root=corpus_root, mutant=mutant
    )


def grade_replay(
    *,
    root: Path,
    raw: bytes,
    observations: list[dict[str, Any]],
    corpus_root: Path = CORPUS_ROOT,
    mutant: str | None = None,
) -> CorpusReport:
    """Grade raw observed facts, independently reconciling persistent publications."""
    assert_independent()
    sealed = _sealed_expectations(corpus_root, raw)
    independent = oracle.decode_packet(raw)
    left = {(p["scenario_id"], p["family"], len(p["events"])) for p in independent["packets"]}
    families = dict(Counter(p["family"] for p in independent["packets"]))
    observations = copy.deepcopy(observations)
    indexed = {(o["scenario_id"], o["offset"]): o for o in observations}
    if set(indexed) != set(sealed) or len(indexed) != len(observations):
        raise ValueError("replay_denominator_disagreement")
    # Verify the complete persisted publication denominator independently of the producer.
    for packet in independent["packets"]:
        database = root / packet["scenario_id"] / "control.sqlite"
        with sqlite3.connect(database) as connection:
            rows = connection.execute(
                "SELECT event_id, topic, payload_json FROM control_outbox_events"
            ).fetchall()
        requests = {row[0] for row in rows if row[1] == "polisyos.runtime.adaptation.request.v1"}
        decisions = [
            json.loads(row[2])["request_ref"]
            for row in rows
            if row[1] == "polisyos.runtime.adaptation.decision.v1"
        ]
        expected_tickets = {
            indexed[(packet["scenario_id"], i)]["ticket"] for i in range(len(packet["events"]))
        }
        expected_refs = {
            indexed[(packet["scenario_id"], i)]["request_ref"] for i in range(len(packet["events"]))
        }
        if requests != expected_tickets or set(decisions) != expected_refs:
            raise ValueError("persisted_publication_denominator_mismatch")
        excess = len(decisions) - len(expected_refs)
        for i in range(len(packet["events"])):
            indexed[(packet["scenario_id"], i)]["duplicate_irreversible_actions"] = excess
    counters = dict.fromkeys(GUARDRAIL_COUNTERS, 0)
    issues = []
    pairs = []
    high_declared = high_preserved = 0
    for packet in independent["packets"]:
        outcomes = []
        for offset, event in enumerate(packet["events"]):
            key = (packet["scenario_id"], offset)
            expected, observation = sealed[key], indexed[key]
            if mutant:
                _mutate(mutant, observation)
            escapes = _escape_counters(event, expected, observation)
            for name, value in escapes.items():
                counters[name] += value
            if observation["assessment"] != expected:
                issues.append(f"{key[0]}:{offset}:transition_oracle_mismatch")
            if any(escapes.values()):
                issues.extend(
                    f"{key[0]}:{offset}:{name}" for name, value in escapes.items() if value
                )
            if expected["protective_containment_required"]:
                high_declared += 1
                high_preserved += int(
                    observation["assessment"]["protective_containment_required"]
                    and observation["assessment"]["conservative_posture"]
                    == "no_authority_expansion"
                )
            outcomes.append(observation)
        first, second = outcomes[:2]
        same_metric = (
            packet["events"][0]["observation"]["movement"]
            == (packet["events"][1]["observation"]["movement"])
        )
        differences = set(first["assessment"]["reasons"]) ^ set(second["assessment"]["reasons"])
        if packet["proxy_dimension"] == "duplicate":
            different = first["duplicate"] is False and second["duplicate"] is True
            if first["ticket"] != second["ticket"]:
                counters["duplicate_irreversible_action_count"] += 1
                issues.append(f"{packet['scenario_id']}:duplicate_ticket_changed")
        else:
            different = bool(differences - {"institutional_signer_not_established"})
        pairs.append(
            {
                "scenario_id": packet["scenario_id"],
                "dimension": packet["proxy_dimension"],
                "same_metric_movement": same_metric,
                "distinct_decisive_reasons": different,
                "reason_difference": sorted(differences),
            }
        )
        if not same_metric or not different:
            issues.append(f"{packet['scenario_id']}:proxy_pair_not_discriminated")
    return CorpusReport(
        packet_sha256=hashlib.sha256(raw).hexdigest(),
        packet_count=len(left),
        event_count=len(indexed),
        family_counts=families,
        operation_coverage=sorted(check_operation_coverage(independent)),
        guardrail_counters=counters,
        high_harm_declared=high_declared,
        high_harm_preserved=high_preserved,
        proxy_pairs=pairs,
        issues=issues,
    )


def oracle_corruption_probe(root: Path) -> tuple[str, str]:
    """Exercise both byte-seal and semantic-content divergence with real checker."""
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CORPUS_ROOT / "packets.json", root / "packets.json")
    text = (CORPUS_ROOT / "oracle.toml").read_text()
    original = tomllib.loads(text)["expectations"][0]["payload"]
    corrupted = original.replace('"candidate_admissible":true', '"candidate_admissible":false')
    if corrupted == original:
        raise ValueError("corruption_probe_not_distinguishing")
    changed = text.replace(json.dumps(original), json.dumps(corrupted), 1)
    (root / "oracle.toml").write_text(changed)
    errors = []
    for content in (
        changed,
        changed.replace(
            hashlib.sha256(original.encode()).hexdigest(),
            hashlib.sha256(corrupted.encode()).hexdigest(),
            1,
        ),
    ):
        (root / "oracle.toml").write_text(content)
        try:
            _sealed_expectations(root, (root / "packets.json").read_bytes())
        except ValueError as error:
            errors.append(str(error))
    return tuple(errors)


def main() -> int:
    """Run one complete deciding gate and emit its full recomputed audit report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--mutant", choices=GUARDRAIL_COUNTERS)
    parser.add_argument("--corrupt-oracle", action="store_true")
    args = parser.parse_args()
    if args.corrupt_oracle:
        result = oracle_corruption_probe(args.root)
        sys.stdout.write(json.dumps({"corruption_refusals": result}) + "\n")
        return 1
    report = evaluate_corpus(root=args.root, mutant=args.mutant)
    sys.stdout.write(report.model_dump_json(indent=2) + "\n")
    return int(bool(report.issues) or any(report.guardrail_counters.values()))


if __name__ == "__main__":
    raise SystemExit(main())
