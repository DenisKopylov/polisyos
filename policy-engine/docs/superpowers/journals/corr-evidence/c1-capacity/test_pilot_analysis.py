"""Independent marked six-work accounting fixtures; no provider or runtime import."""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Iterator

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."


def _equal(actual: object, expected: object) -> None:
    if actual != expected:
        raise AssertionError(f"{actual!r} != {expected!r}")


@contextmanager
def _refuses(reason: str) -> Iterator[None]:
    try:
        yield
    except ValueError as exc:
        if reason not in str(exc):
            raise AssertionError("refused for wrong reason") from exc
    else:
        raise AssertionError("missing required refusal: " + reason)


def digest(value: object) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )


def write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sealed(path: Path, body: dict[str, Any]) -> None:
    write(path, {**body, "content_hash": digest(body)})


def fixture(root: Path) -> Path:
    """Write the existing checkpoint schema independently of the analysis reader."""
    output = root / "campaign"
    output.mkdir()
    works = [
        {"id": f"synthetic:work:{n}", "abstract": f"synthetic abstract {n}", "synthetic": True}
        for n in range(6)
    ]
    keys = [digest(work) for work in works]
    members = [
        {
            "work_id": work["id"],
            "stratum": n // 2,
            "synthetic": True,
            "abstract_content_hash": "sha256:"
            + hashlib.sha256(work["abstract"].encode()).hexdigest(),
        }
        for n, work in enumerate(works)
    ]
    declaration = {
        "synthetic": True,
        "model_id": "synthetic:model",
        "selected_members": members,
        "execution_members": members,
        "live_pricing_usd_per_token": {"input": 0.01, "output": 0.02},
        "full_pass_authorized": False,
    }
    sealed(root / "declaration.json", declaration)
    plan = {
        "synthetic": True,
        "campaign_id": "synthetic:campaign",
        "input_count": 6,
        "input_digest": "sha256:"
        + hashlib.sha256("".join(key + "\n" for key in keys).encode()).hexdigest(),
        "provider_profile_hash": digest(declaration),
        "screening_model": "synthetic:model",
        "extraction_model": "synthetic:model",
    }
    binding = {
        "synthetic": True,
        "authority_status": "candidate_only",
        "transport_observation_epoch": "policyos.academic.extraction_attempt.v3",
        "campaign_plan": plan,
        "pilot_declaration_path": "declaration.json",
        "pilot_declaration_hash": digest(declaration),
        "output_root": "campaign",
        "full_pass_authorized": False,
    }
    sealed(root / "binding.json", binding)

    def packet(kind: str, **body: object) -> dict[str, Any]:
        return {
            "schema_version": "policyos.academic.extraction_campaign.v1",
            "artifact_kind": kind,
            "campaign_binding": digest(plan),
            "synthetic": True,
            "scope": "candidate_only",
            **body,
        }

    write(output / "plan.json", packet("plan", plan=plan))
    con = sqlite3.connect(output / "checkpoint.sqlite3")
    con.executescript("""
      CREATE TABLE works(work_key TEXT PRIMARY KEY, ordinal INTEGER, source_hash TEXT,
        state TEXT, output_hash TEXT, output_status TEXT, intended_output_hash TEXT);
      CREATE TABLE attempts(attempt_id TEXT PRIMARY KEY, work_key TEXT, phase TEXT,
        phase_key TEXT, ordinal INTEGER, state TEXT, intent_hash TEXT, output_hash TEXT,
        usage_known INTEGER);
      CREATE TABLE work_identities(identity_hash TEXT PRIMARY KEY, work_key TEXT);
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE artifact_provenance(synthetic INTEGER, authority_status TEXT);
      INSERT INTO artifact_provenance VALUES(1,'candidate_only');
    """)
    con.execute("INSERT INTO metadata VALUES('frame_admitted',?)", (plan["input_digest"],))
    for n, (work, key) in enumerate(zip(works, keys, strict=True)):
        source_hash = write(
            output / "inputs" / (key[7:] + ".json"), packet("input", work_key=key, work=work)
        )
        phases = []
        for phase in ["screening", "extraction"] if n == 0 else ["screening"]:
            prompt_hash = digest({"synthetic": True, "prompt": phase, "work_id": work["id"]})
            phase_key = digest((digest(plan), key, phase, "synthetic:model", prompt_hash))
            attempt_id = digest((phase_key, 1))[7:]
            context = {
                "campaign_id": plan["campaign_id"],
                "work_id": work["id"],
                "work_key": key,
                "phase": phase,
                "phase_key": phase_key,
                "attempt_id": attempt_id,
                "attempt_ordinal": 1,
                "model_id": "synthetic:model",
                "prompt_hash": prompt_hash,
                "synthetic": True,
                "scope": "candidate_only",
            }
            failed = phase == "extraction"
            usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
            parsed = {"relevant": n == 0, "synthetic": True}
            intent_hash = write(
                output / "intents" / (attempt_id + ".json"),
                packet("attempt_intent", context=context),
            )
            result = packet(
                "attempt_result",
                context=context,
                status="failed" if failed else "returned",
                usage=None if failed else usage,
            )
            result.update(
                {"error_kind": "malformed_output", "retryable": True, "status_code": 200}
                if failed
                else {"parsed": parsed}
            )
            result_hash = write(output / "attempts" / (attempt_id + ".json"), result)
            observation = {
                "schema_version": "policyos.academic.extraction_attempt.v3",
                "synthetic": True,
                "authority_status": "candidate_only",
                "context": context,
                "model_id": "synthetic:model",
                "reported_model_id": "synthetic:model",
                "prompt_hash": prompt_hash,
                "usage": usage,
                "provider_usage": usage,
                "local_prompt_token_estimate": 80,
                "transport_elapsed_seconds": 2.0,
                "status": "failed" if failed else "returned",
                "error_kind": "malformed_output" if failed else None,
            }
            if not failed:
                observation["parsed_response_hash"] = digest(parsed)
            write(output / "provider_attempts" / (attempt_id + ".json"), observation)
            state = "failed" if failed else "returned"
            con.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?)",
                (attempt_id, key, phase, phase_key, 1, state, intent_hash, result_hash, not failed),
            )
            phases.append(
                {
                    "attempt_id": attempt_id,
                    "intent_hash": intent_hash,
                    "output_hash": result_hash,
                    "state": state,
                }
            )
        phases.sort(
            key=lambda row: json.loads(
                (output / "intents" / (row["attempt_id"] + ".json")).read_text()
            )["context"]["phase"]
        )
        status = "provider_failed" if n == 0 else "screening_rejected"
        outcome = packet(
            "work_outcome", work_key=key, status=status, record=None, phase_artifacts=phases
        )
        output_hash = write(output / "works" / (key[7:] + ".json"), outcome)
        con.execute(
            "INSERT INTO works VALUES(?,?,?,?,?,?,?)",
            (key, n, source_hash, "complete", output_hash, status, digest(outcome)),
        )
        con.execute("INSERT INTO work_identities VALUES(?,?)", (digest(work["id"]), key))
    con.commit()
    con.close()
    write(
        output / "observations" / "synthetic-summary.json",
        packet(
            "summary",
            works={"complete": 6},
            attempts={"returned": 6, "failed": 1},
            outcomes={"provider_failed": 1, "screening_rejected": 5},
            unknown_usage_attempts=1,
        ),
    )
    return root / "binding.json"


class _SyntheticWriter:
    def __init__(self) -> None:
        self.scanned = 0

    def check_payload(self, payload: object) -> None:
        if "synthetic-sensitive-sentinel" in repr(payload):
            raise ValueError("synthetic_scan_refused")
        self.scanned += 1

    def __call__(self, path: Path, payload: object) -> None:
        self.check_payload(payload)
        write(path, payload)


class PilotAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = Path.cwd() / ".tmp"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="pilot-analysis-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.owner = importlib.import_module(PREFIX + "pilot_analysis")

    def test_full_six_attempts_failed_usage_and_missing_identity(self) -> None:
        binding = fixture(self.root)
        result = self.owner.reconcile_pilot(binding, project_root=self.root)
        report = result["report"]
        _equal(report["work_count"], 6)
        _equal(report["attempt_count"], 7)
        _equal(report["usage"]["total_tokens"], 2100)
        _equal(report["usage"]["checkpoint_unknown_provider_known"], 1)
        _equal(report["usage"]["observed_cost_usd"], 35.0)
        extra = self.root / "campaign" / "inputs" / "unbound.json"
        write(extra, {"synthetic": True})
        with _refuses("pilot_input_identity_mismatch"):
            self.owner.reconcile_pilot(binding, project_root=self.root)
        extra.unlink()
        missing = next((self.root / "campaign" / "inputs").iterdir())
        missing.unlink()
        with _refuses("pilot_input_identity_mismatch"):
            self.owner.reconcile_pilot(binding, project_root=self.root)

    def test_missing_usage_never_becomes_zero_or_exact(self) -> None:
        binding = fixture(self.root)
        path = next((self.root / "campaign" / "provider_attempts").iterdir())
        observation = json.loads(path.read_text())
        observation["usage"] = None
        observation["provider_usage"] = None
        write(path, observation)
        report = self.owner.reconcile_pilot(binding, project_root=self.root)["report"]
        _equal(report["usage"]["unknown_provider_usage_attempts"], 1)
        _equal(report["usage"]["total_tokens"], None)
        _equal(report["usage"]["cost_status"], "observed_lower_bound")
        _equal(report["usage"]["known_total_tokens"], 1800)

    def test_mutual_exclusion_is_boolean_only_not_textual_difference(self) -> None:
        left = {
            "synthetic": True,
            "judgments": {
                "one": {
                    "screening": True,
                    "screening_prompt_hash": "same",
                    "input_hash": "synthetic:same-input",
                    "extraction_hash": "textA",
                },
                "two": {
                    "screening": "false",
                    "screening_prompt_hash": "same",
                    "input_hash": "synthetic:same-input",
                },
            },
        }
        right = {
            "synthetic": True,
            "judgments": {
                "one": {
                    "screening": False,
                    "screening_prompt_hash": "same",
                    "input_hash": "synthetic:same-input",
                    "extraction_hash": "textB",
                },
                "two": {
                    "screening": False,
                    "screening_prompt_hash": "same",
                    "input_hash": "synthetic:same-input",
                },
            },
        }
        comparison = self.owner.compare_models(left, right)
        _equal(comparison["paired_boolean_documents"], 1)
        _equal(comparison["disagreements"], 1)
        _equal(comparison["document_union_error_lower_bound"], 1.0)
        _equal(comparison["pooled_judgment_error_lower_bound"], 0.5)
        _equal(comparison["joint_extraction_documents"], 0)
        _equal(len(comparison["not_established"]), 1)
        right["judgments"]["one"]["screening"] = True
        comparison = self.owner.compare_models(left, right)
        _equal(comparison["disagreements"], 0)
        _equal(comparison["extraction_structural_differences"], 1)

    def test_primary_archive_and_forecast_preserve_scope_and_full_chain(self) -> None:
        binding = fixture(self.root)
        result = self.owner.reconcile_pilot(binding, project_root=self.root)
        _equal(result["report"]["authority_granted"], False)
        destination = self.root / "archive"
        writer = _SyntheticWriter()
        refs = self.owner.archive_primary(result, destination, writer=writer)
        expected = {str(destination / name) for name in result["primaries"]}
        _equal({row["path"] for row in refs}, expected)
        _equal({str(path) for path in destination.rglob("*.json")}, expected)
        _equal(any("/inputs/" in path or "/works/" in path for path in expected), False)
        for row in refs:
            _equal(
                row["sha256"],
                "sha256:" + hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest(),
            )
            _equal(json.loads(Path(row["path"]).read_text())["synthetic"], True)
        target = {
            "synthetic": True,
            "strata": [
                {
                    "stratum": n,
                    "complete_eligible_member_count": 20,
                    "secondary_target_member_count": n + 2,
                    "unchanged_pilot_member_count": 2,
                }
                for n in range(3)
            ],
            "denominators": {
                "primary_eligible_abstract_work_ids": 60,
                "secondary_target_work_ids": 9,
            },
            "conditional_forecast_assumption": "synthetic exchangeability assumption",
            "unavailable_abstract_cost": "not_established",
            "occurrence_reextraction_cost": "not_established",
        }
        target_path = self.root / "target.json"
        write(target_path, {**target, "declaration_digest": digest(target)})
        forecast = self.owner.forecast(result["report"], target_path)
        _equal(forecast["primary_cost_usd"], 350.0)
        _equal(forecast["secondary_cost_usd"], 50.0)
        _equal(forecast["primary_known_tokens"], 21000.0)
        _equal(forecast["primary_provider_service_seconds"], 140.0)
        _equal(forecast["full_pass_authorized"], False)
        first = result["primaries"][sorted(result["primaries"])[-1]]
        value = json.loads(first.read_text())
        value["synthetic_marker_for_refusal"] = "synthetic-sensitive-sentinel"
        write(first, value)
        with _refuses("synthetic_scan_refused"):
            self.owner.archive_primary(result, self.root / "refused-archive", writer=writer)
        _equal((self.root / "refused-archive").exists(), False)

    def test_complete_storage_and_removal_and_warm_slope(self) -> None:
        with _refuses("storage_root_not_established"):
            self.owner.storage_inventory(self.root / "missing", completed=6, wall_seconds=2.0)
        write(self.root / "artifact.json", {"synthetic": True, "body": "x" * 100})
        write(self.root / "writer.lock", {"synthetic": True})
        report = self.owner.storage_inventory(self.root, completed=6, wall_seconds=2.0)
        expected = sum(path.stat().st_size for path in self.root.iterdir())
        _equal(report["logical_file_bytes"], expected)
        _equal(report["entry_count"], 2)
        _equal(report["categories"]["lock"]["count"], 1)
        with (
            patch.object(self.owner, "_walk_inventory", return_value=({}, [])),
            _refuses("storage_identity_value_mismatch"),
        ):
            self.owner.storage_inventory(self.root, completed=6, wall_seconds=2.0)
        samples = [
            {
                "synthetic": True,
                "elapsed_seconds": n,
                "completed_work_count": n,
                "measurement_status": "measured",
                "summed_rss_bytes": 10 + n * 5,
            }
            for n in range(4)
        ]
        trace = self.root / "samples.jsonl"
        trace.write_text("".join(json.dumps(value) + "\n" for value in samples))
        resource = self.owner.warm_memory(trace, expected_count=4)
        _equal(resource["warm_sample_count"], 3)
        _equal(resource["rss_slope_bytes_per_completed"], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
