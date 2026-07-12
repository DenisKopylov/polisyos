"""Focused behavioral checks for the GY-N10a second-domain substrate pack."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistry,
    build_substrate_registry,
)
from tools.quality.validation import check_layer3_gy_second_domain_pack as second_domain_pack

REPO_ROOT = Path(__file__).resolve().parents[4]
N10A_BASE_COMMIT = "26cc7cc03efc9da44362dc2914a5bde8ac8f7e73"
N10A_PROOF_HEAD_COMMIT = "d8a8cf076da6233c66b0a90010647c0d437e81c4"


def _git_head_sha(repo_root: Path) -> str:
    """Resolve the checkout head for the moving-range adversarial probe."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _rehash_pack_manifest(bundle: dict[str, object]) -> None:
    """Keep a pack mutation internally content-consistent for behavioral probes."""

    pack = bundle["pack"]
    bundle["pack"] = second_domain_pack._with_content_hash(
        pack,
        "manifest_content_hash",
        excluded_fields=("runtime_metrics",),
    )


def _rehash_gap_report_and_pack(bundle: dict[str, object]) -> None:
    """Keep gap and manifest hashes coherent while probing a seam witness."""

    gaps = bundle["gaps"]
    gaps["gaps"] = [
        second_domain_pack._with_content_hash(gap, "gap_content_hash")
        for gap in gaps["gaps"]
    ]
    bundle["gaps"] = second_domain_pack._with_content_hash(gaps, "gap_report_content_hash")
    bundle["pack"]["gap_report_content_hash"] = bundle["gaps"]["gap_report_content_hash"]
    _rehash_pack_manifest(bundle)


def _historical_census_payload() -> dict[str, object]:
    """Load the immutable N10a census for adversarial receipt probes."""

    prefix = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    historical_path = f"{prefix}{second_domain_pack.CENSUS_OUTPUT}"
    raw = subprocess.run(
        [
            "git",
            "show",
            f"{N10A_PROOF_HEAD_COMMIT}:{historical_path}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(raw)


@pytest.fixture(scope="module")
def live_bundle() -> dict[str, object]:
    """Build the expensive owner-derived bundle once for this focused module."""

    return second_domain_pack.build_live_bundle(REPO_ROOT)


def test_pack_rederives_owner_facts_and_is_content_addressed(
    live_bundle: dict[str, object],
) -> None:
    """Rebuild the pack from the real DCAT/SKG/S0/N6 owners."""

    bundle = live_bundle

    assert bundle["census"]["decision"]["chosen_candidate"] == "education"
    assert bundle["pack"]["manifest_content_hash"].startswith("sha256:")
    assert not second_domain_pack.validate_bundle_payloads(bundle, REPO_ROOT)


def test_frozen_pack_persists_content_bound_registry_for_cycle_intake() -> None:
    """Persist the canonical registry payload and derive the L2 selection by source."""

    pack = second_domain_pack._load_frozen_bundle(REPO_ROOT)["pack"]
    component = pack["components"]["substrate_registry"]
    owner_registry = pack["owner_query_results"]["s0_registry"]
    registry = SubstrateRegistry.model_validate(owner_registry["registry_payload"])
    selected_hashes = tuple(component["selected_entry_hashes"])
    query_source_ref = component["selection_evidence"]["owner_query_source_ref"]
    selected_entries = [
        entry for entry in registry.entries if entry.entry_content_hash in selected_hashes
    ]

    assert component["content_hash"] == registry.content_hash
    assert owner_registry["content_hash"] == registry.content_hash
    assert component["substrate_version_id"] == registry.substrate_version_id
    assert "registry_payload" not in component
    assert component["content_hash"] == pack["components"]["owner_writability"][
        "s0_registry_content_hash"
    ]
    assert len(selected_entries) == len(selected_hashes) == 1
    assert selected_entries[0].layer.value == "L2"
    assert {
        entry["selected_registry_entry_hash"]
        for entry in pack["components"]["lever_vocabulary"]["entries"]
    } == set(selected_hashes)
    assert any(
        ref.split("#", 1)[0] == query_source_ref
        for ref in (*selected_entries[0].provenance_refs, *selected_entries[0].authority_refs)
    )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("registry_payload", "cycle_substrate_registry_payload_invalid"),
        ("registry_producer", "cycle_substrate_registry_producer_mismatch"),
        ("registry_version", "cycle_substrate_registry_version_id_mismatch"),
        ("selected_hash", "cycle_substrate_registry_selected_entry_unresolved"),
        ("query_source", "cycle_substrate_registry_selection_evidence_mismatch"),
    ],
)
def test_cycle_registry_intake_rejects_shaped_or_repointed_evidence(
    mutation: str,
    expected_code: str,
) -> None:
    """Resolve and verify S0 evidence instead of trusting registry-shaped JSON."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    component = corrupted["pack"]["components"]["substrate_registry"]
    if mutation == "registry_payload":
        corrupted["pack"]["owner_query_results"]["s0_registry"]["registry_payload"][
            "entries"
        ][0]["family_id"] = "shaped_family"
    elif mutation == "registry_producer":
        corrupted["pack"]["owner_query_results"]["s0_registry"]["registry_payload"][
            "producer_ref"
        ] = "shaped.parallel_registry_producer"
    elif mutation == "registry_version":
        shaped_version = "substrate_version_ffffffffffffffff"
        corrupted["pack"]["owner_query_results"]["s0_registry"][
            "substrate_version_id"
        ] = shaped_version
        corrupted["pack"]["owner_query_results"]["s0_registry"]["registry_payload"][
            "substrate_version_id"
        ] = shaped_version
        component["substrate_version_id"] = shaped_version
    elif mutation == "selected_hash":
        component["selected_entry_hashes"] = ["sha256:" + "0" * 64]
    else:
        component["selection_evidence"]["owner_query_source_ref"] = (
            "repo://production_data/unrelated.duckdb"
        )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert expected_code in codes


def test_cycle_registry_query_evidence_is_bound_to_independent_census() -> None:
    """Reject a coordinated pack-side query receipt rewrite."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    pack = corrupted["pack"]
    query = pack["owner_query_results"]["l2_selected_levers"]
    original_query_id = query["query_id"]
    shaped_query_id = "coordinated_shaped_query"
    owner_query = corrupted["census"]["owner_queries"].pop(original_query_id)
    owner_query["query_id"] = shaped_query_id
    owner_query["sql"] += "\n-- coordinated query rewrite"
    owner_query["query_content_hash"] = second_domain_pack._hash(
        {
            "sql": owner_query["sql"],
            "parameters": owner_query["parameters"],
        }
    )
    corrupted["census"]["owner_queries"][shaped_query_id] = owner_query
    query["query_id"] = shaped_query_id
    query["query_content_hash"] = owner_query["query_content_hash"]
    query["response_content_hash"] = owner_query["response_content_hash"]
    chosen = pack["selected_domain"]
    census_query = corrupted["census"]["candidates"][chosen]["l2_scholar_kg"]
    census_query["query_id"] = query["query_id"]
    census_query["query_content_hash"] = query["query_content_hash"]
    census_query["response_content_hash"] = query["response_content_hash"]
    corrupted["census"] = second_domain_pack._with_content_hash(
        corrupted["census"],
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    pack["census_content_hash"] = corrupted["census"]["census_content_hash"]
    selection = pack["components"]["substrate_registry"]["selection_evidence"]
    selection["query_id"] = query["query_id"]
    selection["query_content_hash"] = query["query_content_hash"]
    selection["query_response_content_hash"] = query["response_content_hash"]
    pack["components"]["grounding_reference_coverage"]["owner_query"] = {
        "query_id": query["query_id"],
        "query_content_hash": query["query_content_hash"],
        "response_content_hash": query["response_content_hash"],
    }
    for lever in pack["components"]["lever_vocabulary"]["entries"]:
        evidence = lever["owner_evidence"]
        evidence["query_id"] = query["query_id"]
        evidence["query_content_hash"] = query["query_content_hash"]
        evidence["query_response_content_hash"] = query["response_content_hash"]
        rehashed = second_domain_pack._with_content_hash(
            lever,
            "entry_content_hash",
        )
        lever.clear()
        lever.update(rehashed)
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_pack.second_domain_substrate_input_content_hash(pack)
    )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_registry_query_census_mismatch" in codes


def test_current_census_owner_query_is_recomputed_not_self_attested() -> None:
    """Reject changed current SQL even when every recorded receipt hash is retained."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    query_id = corrupted["pack"]["owner_query_results"]["l2_selected_levers"][
        "query_id"
    ]
    corrupted["census"]["owner_queries"][query_id]["sql"] += (
        "\n-- shaped current query with stale self-attested hash"
    )
    corrupted["census"] = second_domain_pack._with_content_hash(
        corrupted["census"],
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    corrupted["pack"]["census_content_hash"] = corrupted["census"][
        "census_content_hash"
    ]
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_registry_query_census_mismatch" in codes


def test_historical_l2_query_evidence_binds_immutable_owner_source() -> None:
    """Carry the proof-head owner path into the historical query receipt."""

    second_domain_pack._historical_n10a_l2_query_evidence.cache_clear()
    evidence = second_domain_pack._historical_n10a_l2_query_evidence(
        REPO_ROOT.resolve().as_posix()
    )

    assert evidence.owner_query_source_ref == (
        "repo://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
        "academic/graph/scholar_knowledge.duckdb"
    )


def test_historical_l2_query_rejects_self_attested_owner_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a re-hashed census whose owner rows no longer match its receipt."""

    payload = _historical_census_payload()
    query_id = payload["candidates"]["education"]["l2_scholar_kg"]["query_id"]
    payload["owner_queries"][query_id]["rows"][0]["variable_count"] += 1
    payload = second_domain_pack._with_content_hash(
        payload,
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    tampered_raw = json.dumps(payload)
    real_git = second_domain_pack._git

    def _tampered_git(root: Path, *args: str) -> str:
        if args and args[0] == "show" and second_domain_pack.CENSUS_OUTPUT in args[1]:
            return tampered_raw
        return real_git(root, *args)

    second_domain_pack._historical_n10a_l2_query_evidence.cache_clear()
    monkeypatch.setattr(second_domain_pack, "_git", _tampered_git)
    try:
        with pytest.raises(RuntimeError, match="owner query receipt"):
            second_domain_pack._historical_n10a_l2_query_evidence(
                REPO_ROOT.resolve().as_posix()
            )
    finally:
        second_domain_pack._historical_n10a_l2_query_evidence.cache_clear()


def test_cycle_registry_intake_rederives_the_live_s0_owner() -> None:
    """Reject a coherent, canonically hashed registry not emitted by the live owner."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    pack = corrupted["pack"]
    registry = SubstrateRegistry.model_validate(
        pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    selected = set(
        pack["components"]["substrate_registry"]["selected_entry_hashes"]
    )
    removable = next(
        entry for entry in registry.entries if entry.entry_content_hash not in selected
    )
    forged = build_substrate_registry(
        (entry for entry in registry.entries if entry != removable),
        producer_ref=registry.producer_ref,
        source_catalog_refs=registry.source_catalog_refs,
    )
    owner = pack["owner_query_results"]["s0_registry"]
    owner["registry_payload"] = forged.model_dump(mode="json")
    owner["content_hash"] = forged.content_hash
    owner["substrate_version_id"] = forged.substrate_version_id
    component = pack["components"]["substrate_registry"]
    component["content_hash"] = forged.content_hash
    component["substrate_version_id"] = forged.substrate_version_id
    pack["components"]["owner_writability"]["s0_registry_content_hash"] = (
        forged.content_hash
    )
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_pack.second_domain_substrate_input_content_hash(pack)
    )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_registry_owner_rederive_mismatch" in codes


def test_cycle_registry_intake_rejects_another_valid_l2_entry() -> None:
    """Bind lever selection to the queried L2 owner, not merely any valid L2 row."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    pack = corrupted["pack"]
    registry = SubstrateRegistry.model_validate(
        pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    selected_hash = pack["components"]["substrate_registry"][
        "selected_entry_hashes"
    ][0]
    other_l2 = next(
        entry
        for entry in registry.entries
        if entry.layer.value == "L2" and entry.entry_content_hash != selected_hash
    )
    component = pack["components"]["substrate_registry"]
    component["selected_entry_hashes"] = [other_l2.entry_content_hash]
    other_source_ref = other_l2.provenance_refs[0].split("#", 1)[0]
    component["selection_evidence"]["owner_query_source_ref"] = other_source_ref
    pack["owner_query_results"]["l2_selected_levers"][
        "owner_query_source_ref"
    ] = other_source_ref
    chosen = pack["selected_domain"]
    corrupted["census"]["candidates"][chosen]["l2_scholar_kg"][
        "owner_query_source_ref"
    ] = other_source_ref
    corrupted["census"] = second_domain_pack._with_content_hash(
        corrupted["census"],
        "census_content_hash",
        excluded_fields=("runtime_metrics",),
    )
    pack["census_content_hash"] = corrupted["census"]["census_content_hash"]
    for lever in pack["components"]["lever_vocabulary"]["entries"]:
        lever["selected_registry_entry_hash"] = other_l2.entry_content_hash
        rehashed = second_domain_pack._with_content_hash(
            lever,
            "entry_content_hash",
        )
        lever.clear()
        lever.update(rehashed)
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_pack.second_domain_substrate_input_content_hash(pack)
    )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_registry_selected_entry_not_query_owner" in codes


def test_cycle_registry_intake_rejects_l5_observation_as_lever_owner() -> None:
    """Never substitute a valid education L5 observation row for L2 lever evidence."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    pack = corrupted["pack"]
    registry = SubstrateRegistry.model_validate(
        pack["owner_query_results"]["s0_registry"]["registry_payload"]
    )
    l5_entry = next(entry for entry in registry.entries if entry.layer.value == "L5")
    pack["components"]["substrate_registry"]["selected_entry_hashes"] = [
        l5_entry.entry_content_hash
    ]
    for lever in pack["components"]["lever_vocabulary"]["entries"]:
        lever["selected_registry_entry_hash"] = l5_entry.entry_content_hash
        rehashed = second_domain_pack._with_content_hash(
            lever,
            "entry_content_hash",
        )
        lever.clear()
        lever.update(rehashed)
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_pack.second_domain_substrate_input_content_hash(pack)
    )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_registry_selected_entry_not_l2" in codes


def test_cycle_registry_intake_rejects_a_repointed_lever_binding() -> None:
    """Require every lever to inherit the one resolved registry entry hash."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    pack = corrupted["pack"]
    lever = pack["components"]["lever_vocabulary"]["entries"][0]
    lever["selected_registry_entry_hash"] = "sha256:" + "0" * 64
    rehashed = second_domain_pack._with_content_hash(lever, "entry_content_hash")
    lever.clear()
    lever.update(rehashed)
    pack["content_addressing"]["substrate_input_content_hash"] = (
        second_domain_pack.second_domain_substrate_input_content_hash(pack)
    )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "cycle_substrate_lever_registry_binding_mismatch" in codes


def test_pack_binds_historical_source_and_pretrace_substrate_input() -> None:
    """Keep historical pack identity immutable and downstream traces out of input."""

    pack = second_domain_pack._load_frozen_bundle(REPO_ROOT)["pack"]
    addressing = pack["content_addressing"]
    historical_hash = second_domain_pack._historical_n10a_pack_content_hash(
        REPO_ROOT
    )
    substrate_hash = second_domain_pack.second_domain_substrate_input_content_hash(
        pack
    )

    assert historical_hash == "sha256:078ab1b32f5f634855f8e8694a22c7a864a3d66650c386ab05c87ebe90ddc664"
    assert addressing["historical_source_pack_content_hash"] == historical_hash
    assert addressing["substrate_input_content_hash"] == substrate_hash

    downstream_shift = copy.deepcopy(pack)
    downstream_shift["cycle_trace_content_hash"] = "sha256:" + "1" * 64
    downstream_shift["gap_report_content_hash"] = "sha256:" + "2" * 64
    downstream_shift["n7_acquisition"] = {"runtime_probe": True}
    downstream_shift["runtime_metrics"] = {"wall_time_seconds": 999.0}
    assert (
        second_domain_pack.second_domain_substrate_input_content_hash(
            downstream_shift
        )
        == substrate_hash
    )

    owner_shift = copy.deepcopy(pack)
    owner_shift["components"]["lever_vocabulary"]["entries"][0]["instrument"] = (
        "third_shape.changed_lever"
    )
    assert (
        second_domain_pack.second_domain_substrate_input_content_hash(owner_shift)
        != substrate_hash
    )


@pytest.mark.parametrize("mutation", ["missing", "repointed"])
def test_cached_n7_receipt_rejects_an_invalid_input_key(mutation: str) -> None:
    """Treat the E1 cache key as a recomputed input binding, never a marker."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    if mutation == "missing":
        corrupted["pack"]["n7_acquisition"].pop("attempt_input_content_hash")
    else:
        corrupted["pack"]["n7_acquisition"]["attempt_input_content_hash"] = (
            "sha256:" + "0" * 64
        )
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "n7_attempt_input_content_hash_mismatch" in codes


def test_cached_n7_receipt_binds_effective_owner_config_without_duplication() -> None:
    """Bind the timeout-producing config and keep runtime metadata timing-only."""

    pack = second_domain_pack._load_frozen_bundle(REPO_ROOT)["pack"]
    attempt = pack["n7_acquisition"]
    effective = attempt["attempt_effective_owner_config"]
    operational = pack["runtime_metrics"]["n7_acquisition"]

    assert effective == second_domain_pack._n7_effective_owner_config()
    assert effective["receipt_proof_head_commit"] == N10A_PROOF_HEAD_COMMIT
    assert effective["explore_limits"]["time_budget_ms"] == 5_000
    assert "receipt" not in operational
    assert set(operational) == {
        "receipt_generated_at",
        "planner_report_generated_at",
        "owner_capture_times",
    }


def test_cached_n7_receipt_rejects_effective_owner_config_drift() -> None:
    """Never reuse a truncated receipt under a different retrieval deadline."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    corrupted["pack"]["n7_acquisition"]["attempt_effective_owner_config"] = (
        second_domain_pack._n7_effective_owner_config()
    )
    corrupted["pack"]["n7_acquisition"]["attempt_effective_owner_config"][
        "explore_limits"
    ]["time_budget_ms"] = 1
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "n7_attempt_effective_owner_config_mismatch" in codes


def test_live_bundle_never_reads_current_pack_as_n7_cache_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Derive E1 receipt reuse from immutable history, never the output under audit."""

    real_read_json = second_domain_pack._read_json

    def _reject_current_pack(path: Path) -> dict[str, object]:
        if path == REPO_ROOT / second_domain_pack.PACK_OUTPUT:
            raise AssertionError("current output pack used as N7 cache authority")
        return real_read_json(path)

    monkeypatch.setattr(second_domain_pack, "_read_json", _reject_current_pack)

    bundle = second_domain_pack.build_live_bundle(REPO_ROOT)

    assert bundle["pack"]["n7_acquisition"]["receipt_content_hash"] == (
        "sha256:6b523c44caaa2894a8447d9e4bba9f6c115b200fca727151a59bbfb6011b2da2"
    )


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        (
            "historical_source_pack_content_hash",
            "current_manifest",
            "historical_source_pack_content_hash_mismatch",
        ),
        (
            "substrate_input_content_hash",
            "sha256:" + "0" * 64,
            "cycle_substrate_input_content_hash_mismatch",
        ),
    ],
)
def test_pack_content_addressing_rejects_moving_or_tampered_inputs(
    field: str,
    value: str,
    expected_code: str,
) -> None:
    """Reject moving-head identity and a forged pre-trace input checksum."""

    corrupted = copy.deepcopy(second_domain_pack._load_frozen_bundle(REPO_ROOT))
    if value == "current_manifest":
        value = corrupted["pack"]["manifest_content_hash"]
    corrupted["pack"]["content_addressing"][field] = value
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert expected_code in codes


def test_corrupt_drift_covers_cycle_registry_and_historical_identity() -> None:
    """Keep the checker-level corruption denominator aligned with cycle intake."""

    report = second_domain_pack.corrupt_field_drift_check(REPO_ROOT)
    detected = set(report["issues"][0]["detected"])

    assert {
        "cycle_substrate_registry_payload_invalid",
        "cycle_substrate_registry_owner_rederive_mismatch",
        "cycle_substrate_registry_query_census_mismatch",
        "cycle_substrate_registry_version_id_mismatch",
        "cycle_substrate_lever_registry_binding_mismatch",
        "cycle_substrate_registry_selected_entry_not_query_owner",
        "cycle_substrate_input_content_hash_mismatch",
        "historical_source_pack_content_hash_mismatch",
        "n7_attempt_input_content_hash_mismatch",
        "n7_operational_receipt_duplicate",
    } <= detected


def test_corrupt_drift_requires_each_mutation_to_hit_its_own_witness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not let alternate-L2 collateral mask a broken query-rewrite probe."""

    real_mutations = second_domain_pack._cycle_substrate_corruption_bundles

    def _drop_query_witness(
        bundle: dict[str, object],
    ) -> list[tuple[str, dict[str, object]]]:
        mutations = real_mutations(bundle)
        return [
            (mutation_id, copy.deepcopy(bundle) if mutation_id == "coordinated_query_rewrite" else payload)
            for mutation_id, payload in mutations
        ]

    monkeypatch.setattr(
        second_domain_pack,
        "_cycle_substrate_corruption_bundles",
        _drop_query_witness,
    )

    report = second_domain_pack.corrupt_field_drift_check(REPO_ROOT)
    missing = {
        item
        for issue in report["issues"]
        if issue["code"] == "corrupt_field_drift_not_detected"
        for item in issue["missing"]
    }

    assert report["status"] == "pass"
    assert (
        "coordinated_query_rewrite:cycle_substrate_registry_query_census_mismatch"
        in missing
    )


def test_n10a_zero_engine_receipt_is_pinned_to_historical_proof_head(
    live_bundle: dict[str, object],
) -> None:
    """Keep the N10a code-scope receipt immutable after later commits land."""

    receipt = live_bundle["pack"]["zero_engine_code"]

    assert receipt["scope_semantics"] == "historical_commit_range"
    assert receipt["task_base_commit"] == N10A_BASE_COMMIT
    assert receipt["proof_head_commit"] == N10A_PROOF_HEAD_COMMIT
    assert receipt["changed_engine_paths"] == []


@pytest.mark.parametrize(
    "moving_head",
    ["HEAD", _git_head_sha(REPO_ROOT)],
    ids=["symbolic-head", "resolved-current-head"],
)
def test_n10a_receipt_rebased_to_moving_head_is_rejected(moving_head: str) -> None:
    """Reject symbolic and resolved attempts to make the frozen range move."""

    payloads = second_domain_pack._load_frozen_bundle(REPO_ROOT)
    payloads["pack"]["zero_engine_code"]["proof_head_commit"] = moving_head
    _rehash_pack_manifest(payloads)

    issues = second_domain_pack.validate_bundle_payloads(payloads, REPO_ROOT)

    assert "historical_receipt_rebased_to_moving_head" in {
        issue["code"] for issue in issues
    }


def test_census_records_operational_query_timings(live_bundle: dict[str, object]) -> None:
    """Keep E5 query timing evidence without making the census hash time-dependent."""

    census = live_bundle["census"]
    timings = census["runtime_metrics"]["query_timings_seconds"]

    assert set(timings) == {
        "l1_candidate_aggregate",
        "l2_candidate_aggregate",
        "l2_candidate_exact_measure_names",
    }
    assert all(value >= 0.0 for value in timings.values())
    assert census["content_hash_excluded_fields"] == ["runtime_metrics"]


def test_hand_authored_entry_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a well-shaped entry that lacks rederivable owner evidence."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["lever_vocabulary"]["entries"].append(
        {
            "lever_id": "hand_authored_lever",
            "instrument": "hand.authored",
            "status": "candidate_unbound",
        }
    )

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "pack_entry_not_owner_derived" in codes


def test_owner_projection_drift_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a shape-valid entry whose copied provenance no longer binds its owner row."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["outcomes"]["entries"][0]["dataset_ids"] = [
        "spoofed-dataset-id"
    ]

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "pack_entry_owner_projection_drift" in codes


def test_n7_attempt_is_journal_first_but_not_pack_authority(
    live_bundle: dict[str, object],
) -> None:
    """Persist one real N7 attempt without laundering its registry projection."""

    pack = live_bundle["pack"]
    attempt = pack["n7_acquisition"]
    operational = pack["runtime_metrics"]["n7_acquisition"]
    receipt = second_domain_pack._reconstruct_n7_receipt_payload(
        attempt["receipt_content"],
        operational,
    )

    assert attempt["receipt_count"] == 1
    assert attempt["pack_entry_eligible"] is False
    assert attempt["owner_rederive_status"] == "pass"
    assert len(receipt["journal_entries"]) == 1
    assert receipt["journal_entries"][0]["status"] == "journaled"
    assert receipt["owner_artifacts"][0]["payload"]["raw_owner_response_hash"].startswith(
        "sha256:"
    )


def test_n7_capture_time_is_operational_and_owner_evidence_is_time_stable(
    live_bundle: dict[str, object],
) -> None:
    """Keep real N7 capture time outside the content-bound owner projection."""

    pack = live_bundle["pack"]
    attempt = pack["n7_acquisition"]
    operational = pack["runtime_metrics"]["n7_acquisition"]
    assert "receipt" not in operational
    first_receipt = second_domain_pack._reconstruct_n7_receipt_payload(
        attempt["receipt_content"],
        operational,
    )
    second_receipt = copy.deepcopy(first_receipt)
    assert "content_hash" not in first_receipt
    second_receipt["generated_at"] = "2026-07-10T00:00:00Z"
    second_receipt["planner_report"]["generated_at"] = "2026-07-10T00:00:00Z"
    second_receipt["owner_artifacts"][0]["capture_provenance"]["captured_at"] = (
        "2026-07-10T00:00:00Z"
    )
    second_receipt["content_hash"] = ""

    first_projection = second_domain_pack._n7_owner_evidence_projection(first_receipt)
    second_projection = second_domain_pack._n7_owner_evidence_projection(second_receipt)

    assert first_projection == second_projection == attempt["receipt_content"]
    assert second_domain_pack._n7_owner_evidence_hash(first_receipt) == attempt[
        "receipt_content_hash"
    ]
    assert second_domain_pack._n7_owner_evidence_hash(first_receipt) == (
        second_domain_pack._n7_owner_evidence_hash(second_receipt)
    )
    assert "2018-2022" in json.dumps(first_projection, sort_keys=True)
    reconstructed = second_domain_pack.AcquisitionReceipt.model_validate(second_receipt)
    assert not second_domain_pack.validate_acquisition_receipt(reconstructed)

    shifted_bundle = copy.deepcopy(live_bundle)
    shifted_pack = shifted_bundle["pack"]
    shifted_operational = shifted_pack["runtime_metrics"]["n7_acquisition"]
    shifted_operational["receipt_generated_at"] = second_receipt["generated_at"]
    shifted_operational["planner_report_generated_at"] = second_receipt["planner_report"][
        "generated_at"
    ]
    shifted_operational["owner_capture_times"] = [
        second_receipt["owner_artifacts"][0]["capture_provenance"]["captured_at"]
    ]
    assert pack["manifest_content_hash"] == shifted_pack["manifest_content_hash"]
    assert second_domain_pack._content_bound_canonical_json(pack) == (
        second_domain_pack._content_bound_canonical_json(shifted_pack)
    )
    assert not second_domain_pack.validate_bundle_payloads(shifted_bundle, REPO_ROOT)


def test_capture_time_reentering_content_projection_is_rejected(
    live_bundle: dict[str, object],
) -> None:
    """Fail closed when a capture timestamp returns to content-bound N7 evidence."""

    corrupted = copy.deepcopy(live_bundle)
    attempt = corrupted["pack"]["n7_acquisition"]
    attempt["receipt_content"]["generated_at"] = "2026-07-10T00:00:00Z"
    attempt["receipt_content_hash"] = second_domain_pack._hash(attempt["receipt_content"])
    _rehash_pack_manifest(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "capture_time_content_bound" in codes


def test_source_content_hash_is_repo_relative_and_path_invariant(tmp_path: Path) -> None:
    """Preserve source identity without allowing the checkout path into the hash."""

    canonical = REPO_ROOT / "src/polisyos/runtime/quality/generation_cycle.py"
    dotted = canonical.parent / ".." / "quality" / canonical.name
    expected = second_domain_pack._source_content_hash(REPO_ROOT, canonical)

    relocated_root = tmp_path / "relocated"
    relocated = relocated_root / "src/polisyos/runtime/quality/generation_cycle.py"
    relocated.parent.mkdir(parents=True)
    relocated.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
    same_text_different_path = relocated_root / "other.py"
    same_text_different_path.write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")

    assert expected == second_domain_pack._source_content_hash(REPO_ROOT, dotted)
    assert expected == second_domain_pack._source_content_hash(relocated_root, relocated)
    assert expected != second_domain_pack._source_content_hash(
        relocated_root, same_text_different_path
    )


def test_owner_query_source_ref_preserves_repo_relative_mount_identity(
    tmp_path: Path,
) -> None:
    """Allow read-only symlink mounts without leaking their target checkout path."""

    root = tmp_path / "worktree"
    target = tmp_path / "owner-store"
    (target / "academic/graph").mkdir(parents=True)
    owner_file = target / "academic/graph/scholar_knowledge.duckdb"
    owner_file.write_bytes(b"owner evidence")
    root.mkdir()
    (root / "production_data").symlink_to(target, target_is_directory=True)
    mounted = root / "production_data/academic/graph/scholar_knowledge.duckdb"

    assert second_domain_pack._repo_relative_mounted_evidence_path(
        mounted,
        root,
    ) == "production_data/academic/graph/scholar_knowledge.duckdb"
    with pytest.raises(second_domain_pack.SourceHashCheckoutPathError):
        second_domain_pack._repo_relative_mounted_evidence_path(owner_file, root)


def test_all_gaps_have_resolvable_seam_witnesses(live_bundle: dict[str, object]) -> None:
    """Require a real, segment-scoped source witness for every emitted gap."""

    gap_ids = {gap["gap_id"] for gap in live_bundle["gaps"]["gaps"]}

    assert set(second_domain_pack.GAP_WITNESS_SPECS) == gap_ids
    for _gap_id, spec in second_domain_pack.GAP_WITNESS_SPECS.items():
        witness = second_domain_pack._resolve_gap_witness(REPO_ROOT, spec)
        assert witness["symbol"] == spec.symbol
        assert witness["segment_content_hash"].startswith("sha256:")
    n5 = next(gap for gap in live_bundle["gaps"]["gaps"] if gap["gap_id"] == "s0_to_n5_wmr_bridge_missing")
    assert "build_substrate_registry_from_existing_catalogs" in n5["owner_evidence"][
        "seam_witness"
    ]["observed_call_names"]


def test_missing_gap_witness_target_fails_closed_for_every_gap(
    live_bundle: dict[str, object],
) -> None:
    """Never treat an unresolved seam symbol as an empty-but-valid witness."""

    for gap_id in sorted(second_domain_pack.GAP_WITNESS_SPECS):
        corrupted = copy.deepcopy(live_bundle)
        gap = next(item for item in corrupted["gaps"]["gaps"] if item["gap_id"] == gap_id)
        gap["owner_evidence"]["seam_witness"]["symbol"] = "__gy_n10a_missing_target__"
        _rehash_gap_report_and_pack(corrupted)
        codes = {
            str(issue["code"])
            for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
        }
        assert "gap_witness_target_missing" in codes


def test_absolute_gap_witness_source_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject an absolute checkout path reintroduced into seam hash identity."""

    corrupted = copy.deepcopy(live_bundle)
    witness = corrupted["gaps"]["gaps"][0]["owner_evidence"]["seam_witness"]
    witness["source_path"] = str(REPO_ROOT / witness["source_path"])
    _rehash_gap_report_and_pack(corrupted)

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "source_hash_checkout_path_dependent" in codes


def test_gap_segment_hash_ignores_unrelated_edits_and_detects_seam_edits(tmp_path: Path) -> None:
    """Pin a seam segment, not the entire owner module, for merge stability."""

    relative = "src/polisyos/runtime/quality/generation_cycle.py"
    source = REPO_ROOT / relative
    copied_root = tmp_path / "copy"
    copied = copied_root / relative
    copied.parent.mkdir(parents=True)
    source_text = source.read_text(encoding="utf-8")
    copied.write_text(source_text, encoding="utf-8")
    spec = second_domain_pack.GAP_WITNESS_SPECS["s0_to_n5_wmr_bridge_missing"]

    original = second_domain_pack._resolve_gap_witness(copied_root, spec)
    copied.write_text(source_text + "\n# unrelated audit probe\n", encoding="utf-8")
    unrelated = second_domain_pack._resolve_gap_witness(copied_root, spec)
    copied.write_text(
        source_text.replace(
            "registry = build_substrate_registry_from_existing_catalogs(repo_root)",
            "registry = build_substrate_registry_from_existing_catalogs(repo_root)  # seam probe",
            1,
        ),
        encoding="utf-8",
    )
    seam_changed = second_domain_pack._resolve_gap_witness(copied_root, spec)

    assert original["segment_content_hash"] == unrelated["segment_content_hash"]
    assert original["segment_content_hash"] != seam_changed["segment_content_hash"]


def test_first_vertical_contamination_is_rejected(live_bundle: dict[str, object]) -> None:
    """Compute, rather than trust, the all-axis distinctness check."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["components"]["outcomes"]["entries"][0]["canonical_var"] = "avg_income"
    corrupted["pack"]["components"]["transport_context"]["covariates"][0][
        "canonical_var"
    ] = "state_capacity"
    corrupted["pack"]["components"]["lever_vocabulary"]["entries"][0][
        "instrument"
    ] = "policy.credit_access"

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "distinctness_outcome_overlap" in codes
    assert "distinctness_covariate_overlap" in codes
    assert "distinctness_lever_overlap" in codes


def test_crash_or_mismatch_trace_cannot_be_labeled_honest(
    live_bundle: dict[str, object],
) -> None:
    """Reject a recorded crash/mismatch that is dressed as a typed terminal."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["cycle_trace"]["smoke_status"] = "typed_terminal_pass"
    corrupted["cycle_trace"]["generation_cycle_run"]["cycles"][0]["terminal_kind"] = "crash"

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "smoke_terminal_not_honest" in codes


def test_smoke_trace_must_bind_the_frozen_design_problem(
    live_bundle: dict[str, object],
) -> None:
    """Reject a typed trace that points at a different DesignProblem payload."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["cycle_trace"]["generation_cycle_run"]["design_problem_ref"] = "sha256:" + "0" * 64

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "smoke_design_problem_ref_drift" in codes


def test_non_pack_diff_scope_is_rejected(live_bundle: dict[str, object]) -> None:
    """Reject a recorded change outside the declared data-only task surface."""

    bundle = live_bundle
    corrupted = copy.deepcopy(bundle)
    corrupted["pack"]["zero_engine_code"]["out_of_scope_paths"] = ["README.md"]

    codes = {
        str(issue["code"])
        for issue in second_domain_pack.validate_bundle_payloads(corrupted, REPO_ROOT)
    }

    assert "free_grow_violated_by_scope_change" in codes
