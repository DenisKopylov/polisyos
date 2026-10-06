from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import duckdb

preflight_path, full_path, negative_path, source_root_arg, wheel_arg, output_arg = sys.argv[1:]
source_root = Path(source_root_arg).resolve()
source_package = source_root / "src" / "polisyos"
wheel_path = Path(wheel_arg).resolve()
output_path = Path(output_arg).resolve()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_installed_profile(result_path: str, expected_profile: str, expected_observations: int):
    result_file = Path(result_path).resolve()
    result = read_json(result_file)
    execution = result["execution"]
    candidate = result["candidate"]
    module_bytes = result["installed_module_bytes"]

    assert candidate["commit"] == "8dfa7f3c544461c0ff081861848fcc5d8523da5b"
    assert candidate["tree"] == "3eac9b5cf816e30f9c1bacc81d80e2dc75d81681"
    assert candidate["source_root"] == str(source_root)
    assert candidate["wheel_sha256"] == sha_file(wheel_path)
    assert len(module_bytes) == 23
    with zipfile.ZipFile(wheel_path) as wheel:
        for module_name, proof in module_bytes.items():
            origin = Path(proof["origin"]).resolve()
            assert origin.is_relative_to(source_package), (module_name, origin)
            relative = origin.relative_to(source_package).as_posix()
            assert proof["source_path"] == str(source_package / relative)
            source_bytes = (source_package / relative).read_bytes()
            wheel_bytes = wheel.read("polisyos/" + relative)
            assert origin.read_bytes() == source_bytes == wheel_bytes, module_name
            assert sha_bytes(source_bytes) == proof["frozen_source_sha256"] == proof["wheel_sha256"]
            assert proof["origin_equals_archive_source_equals_wheel"] is True

    runtime = result["runtime"]
    assert runtime["isolated_mode"] is True and runtime["safe_path"] is True
    assert runtime["PYTHONPATH"] is None
    assert runtime["sys_path_unchanged"] is True
    assert runtime["sys_path_at_start"] == runtime["sys_path_after_probe"]
    assert {str(source_root), str(source_root / "src")} <= set(runtime["sys_path"])
    editable = json.loads(result["profile"]["source_project_direct_url"])
    assert editable["dir_info"]["editable"] is True
    assert Path(editable["url"].removeprefix("file://")).resolve() == source_root
    assert result["profile"]["selection"] == "base-only locked uv profile; no dev/test/optional extra"

    for name, resource in result["resources"].items():
        path = Path(resource["path"]).resolve()
        assert path.is_file() and path.is_relative_to(source_root)
        assert sha_file(path) == resource["sha256"] == resource["archive_expected_sha256"]
        assert resource["bytes_equal"] is True

    fixture = result["fixture_scope"]
    assert fixture["run_profile"] == expected_profile
    assert fixture["registry_source"] == "worldbank"
    assert fixture["registry_publish_blocking"] is True
    assert fixture["registry_run_lane"] == "empirical"
    assert fixture["active_countries"] == ["UA"]
    assert fixture["active_year_window"] == [2020, 2020]
    assert fixture["observation_mode"] == "core"
    expected_fixture_ids = {row["id"] for row in fixture["expected_indicators"]}
    assert len(expected_fixture_ids) == 9
    assert fixture["only_worldbank_metadata_and_fetch_stubs"] is True
    assert fixture["no_production_data_or_model_weights"] is True

    raw_manifest = execution["raw_manifest"]
    raw_payload = execution["raw_payload"]
    payload_path = Path(raw_payload["path"])
    manifest_path = payload_path.parent / "manifest.json"
    payload_bytes = payload_path.read_bytes()
    raw_rows = [json.loads(line) for line in payload_bytes.decode("utf-8").splitlines() if line]
    disk_manifest = read_json(manifest_path)
    assert disk_manifest == raw_manifest
    assert raw_manifest["source"] == "worldbank"
    assert raw_manifest["count"] == len(raw_rows) == raw_payload["line_count"] == 16
    assert raw_manifest["payload"] == str(payload_path)
    assert raw_manifest["sha256"] == sha_bytes(payload_bytes) == raw_payload["sha256"]
    assert expected_fixture_ids <= {row["id"] for row in raw_rows}
    assert {row["id"] for row in raw_rows} - expected_fixture_ids == {
        "NY.GDP.PCAP.CD", "SH.DYN.MORT", "SE.SEC.ENRR", "SI.POV.NAHC",
        "GE.EST", "CC.EST", "SH.XPD.CHEX.PC.CD",
    }
    assert execution["harvest_transport"]["stub_calls"] == 1
    assert execution["harvest_transport"]["stub_return_count"] == 9
    assert execution["harvest_transport"]["manifest"]["status"] == "ok"

    for name in ("normalized", "merged"):
        item = execution[name]
        path = Path(item["path"])
        data = path.read_bytes()
        rows = [json.loads(line) for line in data.decode("utf-8").splitlines() if line]
        assert sha_bytes(data) == item["sha256"]
        assert len(rows) == item["line_count"] == 16
        assert rows == item["rows"]

    core = execution["core"]
    manifest = core["manifest"]
    assert manifest["status"] == "ok"
    assert manifest["metrics"]["observations"] == expected_observations
    assert manifest["metrics"]["observations_attempted"] == expected_observations
    assert manifest["metrics"]["failed_shards"] == 0
    assert manifest["metrics"]["publishable_core_complete"] is True
    assert manifest["metrics"]["publishable_core_pending"] == 0
    assert core["receipt_is_current"] is True
    assert core["current_receipt"]["matches_checkpoint_and_stage"] is True
    receipt = core["checkpoint"]["core_output_receipt"]
    assert receipt == core["stage_state"]["metadata"]["core_output_receipt"]
    assert receipt["publishable_core_complete"] is True
    assert receipt["publishable_core_pending"] == 0
    assert receipt["basis_digest"] == manifest["metrics"]["core_output_receipt_digest"]

    db_path = Path(core["db_path"])
    with duckdb.connect(str(db_path), read_only=True) as con:
        def query_dicts(sql: str):
            cursor = con.execute(sql)
            names = [row[0] for row in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

        datasets = query_dicts(
            "SELECT id, source, dataset_id, polisyos_metrics, title, execution_tier "
            "FROM ds_datasets ORDER BY dataset_id"
        )
        distributions = query_dicts(
            "SELECT id, dataset_id, connector_type, profile_id, source_locator, url "
            "FROM ds_distributions ORDER BY source_locator"
        )
        bindings = query_dicts(
            "SELECT metric_id, dataset_id, connector_id, profile_id, request_dataset_id, "
            "execution_tier, source FROM ds_metric_bindings ORDER BY metric_id, dataset_id"
        )
        alignments = query_dicts(
            "SELECT dataset_id, raw_variable, canonical_var, method, confidence, evidence "
            "FROM ds_variable_alignments ORDER BY raw_variable, canonical_var"
        )
        observations = query_dicts(
            "SELECT dataset_id, raw_variable, canonical_var, country_code, year, value "
            "FROM ds_observations ORDER BY raw_variable, country_code, year"
        )
        counts = {
            table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "ds_datasets", "ds_distributions", "ds_metric_bindings",
                "ds_variable_alignments", "ds_observations",
            )
        }
        joined = con.execute(
            "SELECT count(*), count(DISTINCT o.dataset_id), min(d.source), max(d.source), "
            "min(o.country_code), max(o.country_code), min(o.year), max(o.year), "
            "min(o.value), max(o.value) FROM ds_observations o "
            "JOIN ds_datasets d ON o.dataset_id=d.id"
        ).fetchone()
        canonical_counts = con.execute(
            "SELECT canonical_var, count(*) FROM ds_observations "
            "GROUP BY canonical_var ORDER BY canonical_var"
        ).fetchall()
    assert datasets == core["datasets"]
    assert distributions == core["distributions"]
    assert bindings == core["metric_bindings"]
    assert alignments == core["alignments"]
    assert observations == core["observations"]
    assert counts == core["table_counts"]
    assert counts == {
        "ds_datasets": 16, "ds_distributions": 16, "ds_metric_bindings": 25,
        "ds_variable_alignments": 26, "ds_observations": expected_observations,
    }
    expected_dataset_count = 2 if expected_profile == "preflight_core" else 16
    assert joined == (
        expected_observations, expected_dataset_count, "worldbank", "worldbank", "UA", "UA",
        2020, 2020, 1.1, 1.1
    )
    canonical_counts_dict = dict(canonical_counts)
    expected_canonical_vars = (
        {"gdp_per_capita", "health_outcomes"}
        if expected_profile == "preflight_core"
        else {
            "corruption_level", "education_outcomes", "gdp_per_capita", "health_outcomes",
            "inflation", "institutional_quality", "labor_force_participation", "migration",
            "poverty_rate", "unemployment_rate",
        }
    )
    assert set(canonical_counts_dict) == expected_canonical_vars
    expected_metrics = {
        "gdp_per_capita", "unemployment_rate", "inflation", "migration", "health_outcomes",
        "education_outcomes", "poverty_rate", "labor_force_participation", "institutional_quality",
    }
    assert expected_metrics <= {row["metric_id"] for row in bindings}
    assert sha_file(db_path) == execution["component_artifact_digests"][str(db_path)]["sha256"]

    benchmark = execution["benchmark"]
    metrics = benchmark["metrics"]
    assert benchmark["run_profile"] == expected_profile
    assert benchmark["evaluation_mode"] == "full-ready"
    assert metrics["benchmark_retrieval_metrics_total"] == 10
    assert metrics["benchmark_retrieval_ready_pct"] == 90.0
    assert metrics["benchmark_search_cases_total"] == 18
    assert metrics["benchmark_search_top5_relevance_pct"] == 88.889
    assert metrics["benchmark_source_preflight_ready_pct"] == 100.0
    expected_transport_pct = 20.0 if expected_profile == "preflight_core" else 90.0
    assert metrics["benchmark_transport_ready_pct"] == expected_transport_pct
    assert metrics["benchmark_foundry_fitness_pct"] == 100.0
    assert [row["metric_id"] for row in benchmark["retrieval"]["metrics"] if not row["ready"]] == ["social_trust"]
    failed_searches = [row["case_id"] for row in benchmark["search"]["cases"] if not row["top5_hit"]]
    assert failed_searches == ["trust_en", "trust_uk"]
    source_preflight = benchmark["source_preflight"]["sources"]
    assert len(source_preflight) == 1
    assert source_preflight[0]["source"] == "worldbank"
    assert source_preflight[0]["ready"] is True
    assert source_preflight[0]["empirical_rows"] == expected_observations
    assert source_preflight[0]["completed_shards"] == expected_observations

    component = db_path.parent.parent
    benchmark_path = component / "benchmark_report.json"
    qc_path = component / "qc_report.json"
    readiness_path = component / "publish" / "consumer_readiness.json"
    publish_path = component / "publish" / "manifest.json"
    assert read_json(benchmark_path) == benchmark
    qc = execution["qc"]
    assert read_json(qc_path) == qc
    assert qc["passed"] is True
    readiness_document = read_json(readiness_path)
    readiness = execution["consumer_readiness"]
    assert readiness_document == readiness
    assert readiness["run_profile"] == expected_profile
    assert readiness["evaluation_mode"] == "full-ready"
    if expected_profile == "preflight_core":
        assert readiness["readiness"]["transportability_ready"] is False
        assert readiness["readiness"]["consumer_ready"] is False
        assert readiness["readiness"]["full_publish_ready"] is False
        assert readiness["publish_mode"] == "blocked"
        assert publish_path.exists() is False
        assert execution["publish_manifest"] is None
        assert "transportability_ready" in execution["pipeline"]["message"]
    else:
        assert all(value is True for value in readiness["readiness"].values())
        assert readiness["publish_mode"] == "full-ready"
        assert publish_path.exists() is True
        publish_manifest = read_json(publish_path)
        assert publish_manifest == execution["publish_manifest"]
        assert publish_manifest["extra"]["consumer_ready"] is True
        assert publish_manifest["extra"]["full_publish_ready"] is True
        assert publish_manifest["extra"]["evaluation_mode"] == "full-ready"
        assert publish_manifest["extra"]["run_profile"] == "prod_full"
        for artifact in publish_manifest["artifacts"]:
            artifact_path = Path(artifact["path"])
            assert artifact_path.is_file()
            assert sha_file(artifact_path) == artifact["sha256"]

    for raw_path, info in execution["component_artifact_digests"].items():
        artifact_path = Path(raw_path)
        assert artifact_path.is_file(), raw_path
        assert artifact_path.stat().st_size == info["bytes"], raw_path
        assert sha_file(artifact_path) == info["sha256"], raw_path

    retrieval = execution["retrieval"]["value"]
    assert retrieval["lane_used"] == "catalog"
    assert retrieval["run_profile"] == expected_profile
    assert len(retrieval["plans"]) == 1
    selected = retrieval["plans"][0]
    assert selected["metric_id"] == "gdp_per_capita"
    assert selected["connector_id"] == "worldbank.wdi"
    assert selected["profile_id"] == "worldbank_wdi"
    assert selected["dataset_id"] == "NY.GDP.PCAP.PP.CD"
    controls = execution["profile_controls"]
    assert controls["missing"]["outcome"]["type"] == "CatalogSelectionError"
    assert controls["missing"]["outcome"]["message"].startswith("catalog_run_profile_unresolved")
    assert controls["unknown"]["outcome"]["type"] == "CatalogSelectionError"
    assert controls["unknown"]["outcome"]["message"].startswith("unsupported_run_profile")

    boundary = fixture["url_reachability_boundary"]
    assert boundary["fixture_http_status"] == 200
    assert boundary["live_external_url_reachability"] == "not_established"
    assert boundary["actual_network_requests"] == 0
    assert boundary["urllib_urlopen_stubbed"] is True
    assert {item["fixture_status"] for item in boundary["calls"]} == {200}

    return {
        "source_result_path": str(result_file),
        "result_sha256": sha_file(result_file),
        "profile": expected_profile,
        "candidate_commit": candidate["commit"],
        "candidate_tree": candidate["tree"],
        "wheel_sha256": candidate["wheel_sha256"],
        "module_count": len(module_bytes),
        "module_origins_match_archive_and_wheel": True,
        "runtime_isolated_no_path_mutation": runtime["isolated_mode"] and runtime["sys_path_unchanged"],
        "editable_archive_resources_match": {name: info["sha256"] for name, info in result["resources"].items()},
        "source_registry_sha256": candidate["registry_sha256"],
        "raw_manifest_sha256": sha_file(manifest_path),
        "raw_payload_sha256": raw_manifest["sha256"],
        "raw_fixture_plus_product_map_counts": {"stub_rows": 9, "product_augmented_rows": 7, "persisted_rows": 16},
        "normalized_records": 16,
        "merged_records": 16,
        "database_path": str(db_path),
        "database_sha256": sha_file(db_path),
        "database_counts": counts,
        "canonical_observation_counts": canonical_counts_dict,
        "core_observations": expected_observations,
        "core_receipt_current": core["receipt_is_current"],
        "core_receipt_digest": receipt["basis_digest"],
        "benchmark": {
            "retrieval_ready_pct": metrics["benchmark_retrieval_ready_pct"],
            "search_top5_pct": metrics["benchmark_search_top5_relevance_pct"],
            "transport_ready_pct": metrics["benchmark_transport_ready_pct"],
            "foundry_fitness_pct": metrics["benchmark_foundry_fitness_pct"],
            "source_preflight_pct": metrics["benchmark_source_preflight_ready_pct"],
            "retrieval_miss": "social_trust",
            "search_misses": failed_searches,
            "evaluation_mode": benchmark["evaluation_mode"],
        },
        "qc_passed": qc["passed"],
        "publisher": {
            "consumer_ready": readiness["readiness"]["consumer_ready"],
            "full_publish_ready": readiness["readiness"]["full_publish_ready"],
            "transportability_ready": readiness["readiness"]["transportability_ready"],
            "publish_mode": readiness["publish_mode"],
            "manifest_path": str(publish_path) if publish_path.exists() else None,
            "manifest_sha256": sha_file(publish_path) if publish_path.exists() else None,
        },
        "retrieval_plan": {
            "metric_id": selected["metric_id"],
            "connector_id": selected["connector_id"],
            "profile_id": selected["profile_id"],
            "dataset_id": selected["dataset_id"],
        },
        "missing_profile_refusal": controls["missing"]["outcome"]["message"],
        "unknown_profile_refusal": controls["unknown"]["outcome"]["message"],
        "http_status_fixture": boundary["fixture_http_status"],
        "live_url_reachability": "not_established",
        "component_artifact_count": len(execution["component_artifact_digests"]),
    }


preflight = verify_installed_profile(preflight_path, "preflight_core", 2)
full = verify_installed_profile(full_path, "prod_full", 26)
negative = read_json(negative_path)
negative_execution = negative["execution"]
negative_boundary = negative["fixture_scope"]["url_reachability_boundary"]
assert negative["candidate"]["commit"] == "8dfa7f3c544461c0ff081861848fcc5d8523da5b"
assert negative["candidate"]["tree"] == "3eac9b5cf816e30f9c1bacc81d80e2dc75d81681"
assert negative_boundary["fixture_http_status"] == 503
assert negative_boundary["live_external_url_reachability"] == "not_established"
assert negative_boundary["actual_network_requests"] == 0
assert len(negative_boundary["calls"]) == 32
assert {item["fixture_status"] for item in negative_boundary["calls"]} == {503}
assert all(item["fixture_body_utf8"] == "fixture response at external HTTP reachability boundary" for item in negative_boundary["calls"])
assert all(item["fixture_headers"] == {"content-length": "55", "content-type": "text/plain"} for item in negative_boundary["calls"])
assert negative_execution["pipeline"]["status"] == "raised"
assert negative_execution["pipeline"]["message"].startswith("QC failed: url_sample_reachability_pct")
assert negative_execution["qc"]["passed"] is False
negative_check = next(row for row in negative_execution["qc"]["checks"] if row["name"] == "url_sample_reachability_pct")
assert negative_check["passed"] is False and negative_check["value"] == 0.0
assert negative_execution["direct_publish_after_pipeline"]["type"] == "RuntimeError"
assert negative_execution["direct_publish_after_pipeline"]["message"] == "Dataset publish blocked: no current qc content-bound receipt"
negative_component = Path(negative_execution["core"]["db_path"]).parent.parent
assert not (negative_component / "publish" / "manifest.json").exists()
assert not (negative_component / "publish" / "consumer_readiness.json").exists()

summary = {
    "candidate": {
        "commit": "8dfa7f3c544461c0ff081861848fcc5d8523da5b",
        "tree": "3eac9b5cf816e30f9c1bacc81d80e2dc75d81681",
        "wheel_sha256": sha_file(wheel_path),
        "source_archive_root": str(source_root),
    },
    "standalone_wheel_boundary": "catalog workspace resources resolve only under the documented editable source-workspace install; this oracle tested that profile, not a wheel-only resource promise",
    "preflight_core": preflight,
    "prod_full": full,
    "http_503_negative_control": {
        "result_path": str(Path(negative_path).resolve()),
        "result_sha256": sha_file(Path(negative_path)),
        "requests": len(negative_boundary["calls"]),
        "qc_value": negative_check["value"],
        "publisher_refusal": negative_execution["direct_publish_after_pipeline"]["message"],
        "live_url_reachability": "not_established",
    },
    "oracle_imports": ["stdlib json/hashlib/zipfile/pathlib", "duckdb for read-only database queries"],
    "oracle_product_runtime_imports": [],
}
output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, sort_keys=True))
