"""Independent fresh-process federation and registered SQL kernel witnesses."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def _child(tmp_path: Path, phase: str, expected: Path) -> dict:
    """Observe each deciding interpreter before any project import."""
    root = Path(__file__).resolve().parents[4]
    observer = root / "tests/observers/c93_same_pid_pytest.py"
    cache = tmp_path / f"cache-{phase}"
    cache.mkdir()
    receipt = tmp_path / f"{phase}-receipt.json"
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
            "PYTHONPYCACHEPREFIX",
        }
        and not key.startswith(("E02_", "POLISYOS_"))
    }
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    cmd = [
        sys.executable,
        "-B",
        str(observer),
        "--receipt",
        str(receipt),
        "--project-root",
        str(root),
        "--expected-sources",
        str(expected),
        "--script",
        str(Path(__file__).resolve()),
        "--",
        phase,
        str(tmp_path),
    ]
    if phase != "producer":
        cmd[cmd.index("--script") : cmd.index("--script")] = [
            "--input",
            str(
                tmp_path
                / (
                    "nested-selection.json"
                    if phase == "nested"
                    else "forge-selection.json"
                    if phase == "forged"
                    else "selection.json"
                )
            ),
        ]
    run = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, check=False)
    (tmp_path / f"{phase}-stdout.txt").write_text(run.stdout)
    (tmp_path / f"{phase}-stderr.txt").write_text(run.stderr)
    assert run.returncode == 0, f"{cmd!r}\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"
    record = json.loads(receipt.read_text())
    assert record["exit_code"] == 0
    assert not record["source_mismatches"]
    assert not record["unbound_project_sources"]
    assert record["pre_import"]["cache_files"] == []
    return record


def test_actual_producer_cold_nested_reader_and_registered_sql(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[4]
    # Exact file contents are bound inside each deciding interpreter. This is a
    # declared input set; the observer separately records the actual readset.
    files = [p for directory in ("src", "tests", "tools") for p in (root / directory).rglob("*.py")]
    expected = tmp_path / "expected.json"
    expected.write_text(
        json.dumps(
            {
                p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files
            }
        )
    )
    a = _child(tmp_path, "producer", expected)
    b = _child(tmp_path, "reader", expected)
    c = _child(tmp_path, "nested", expected)
    d = _child(tmp_path, "tamper", expected)
    e = _child(tmp_path, "forge", expected)
    f = _child(tmp_path, "forged", expected)
    assert len({a["pid"], b["pid"], c["pid"], d["pid"], e["pid"], f["pid"]}) == 6
    assert any(
        row["qualname"].endswith("persist_federation_derivation")
        for row in a["executed_project_calls"]
    )
    assert any(
        row["qualname"].endswith("read_verified_federation_derivation")
        for row in b["executed_project_calls"]
    )
    assert any(
        row["qualname"].endswith("read_verified_federation_derivation")
        for row in c["executed_project_calls"]
    )


def _metadata(name: str, trust):
    from datetime import UTC, datetime

    from polisyos.fabric.connectors.federation.types import SourceMetadata
    from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier

    spec = ConnectorMetadataSpec(
        connector_id=name,
        namespace="cold_test",
        version="1.0.0",
        source_name=name,
        source_organization="declared candidate",
        trust_level=trust,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
    )
    return SourceMetadata(spec.fully_qualified_id, spec, datetime(2026, 1, 1, tzinfo=UTC), 0)


def _worker(phase: str, base: Path) -> None:
    from dataclasses import replace
    from datetime import timedelta

    import duckdb
    import pandas as pd

    from polisyos.fabric.connectors.federation import (
        AuditLevel,
        CompositionRequest,
        CompositionStrategy,
        ConflictPolicy,
        ConflictResolver,
        DataComposer,
        FederationArtifactRef,
        SelectedFederationInput,
        persist_federation_derivation,
        read_verified_federation_derivation,
    )
    from polisyos.ir.connectors import TrustLevel

    def request(strategy):
        return CompositionRequest(
            dataset_pattern="cold_test.values",
            strategy=strategy,
            conflict_policy=ConflictPolicy.TRUST_HIGHEST,
            join_keys=["id"],
            join_validate="one_to_one",
            join_max_rows=2,
            audit_level=AuditLevel.SUMMARY,
        )

    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    if phase == "producer":
        a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
        b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
        parent = persist_federation_derivation(
            base / "parent", composer, [a, b], request(CompositionStrategy.JOIN)
        )
        # Execute an actual registered DuckDB relation and capture its real frame.
        con = duckdb.connect(":memory:")
        con.register(
            "empty_input",
            pd.DataFrame(
                {"id": pd.Series([], dtype="int64"), "value": pd.Series([], dtype="float64")}
            ),
        )
        assert [
            (row[0], row[1])
            for row in con.execute("DESCRIBE SELECT id, value FROM empty_input").fetchall()
        ] == [("id", "BIGINT"), ("value", "DOUBLE")]
        empty_frame = con.execute("SELECT id, value FROM empty_input").fetchdf()
        empty = persist_federation_derivation(
            base / "empty",
            composer,
            [(empty_frame, _metadata("empty", TrustLevel.HIGH))],
            replace(request(CompositionStrategy.UNION), key_columns=["id"]),
        )
        mode_refs = {}
        for mode in CompositionStrategy:
            left = (
                pd.DataFrame(
                    {
                        "id": pd.Series([2**53 + 1, 2**53 + 3], dtype="int64"),
                        "value": pd.Series([1.5, 2.5], dtype="float64"),
                    }
                ),
                _metadata("a", TrustLevel.HIGH),
            )
            right = (
                pd.DataFrame(
                    {
                        "id": pd.Series([2**53 + 1, 2**53 + 3], dtype="int64"),
                        "value": pd.Series([3.5, 4.5], dtype="float64"),
                    }
                ),
                _metadata("b", TrustLevel.LOW),
            )
            req = replace(
                request(mode),
                key_columns=["id"],
                aggregation_func="mode",
                primary_source=left[1].connector_id,
            )
            ref = persist_federation_derivation(
                base / ("mode-" + mode.value), composer, [left, right], req
            )
            mode_refs[mode.value] = ref.manifest_sha256
        rule_a = (pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("a", TrustLevel.HIGH))
        rule_b = (pd.DataFrame({"id": [1], "value": [20.0]}), _metadata("b", TrustLevel.LOW))
        rule_b[1].fetched_at += timedelta(days=1)
        rule_request = replace(
            request(CompositionStrategy.JOIN), column_policies={"value": ConflictPolicy.MOST_RECENT}
        )
        rule = persist_federation_derivation(
            base / "policy", composer, [rule_a, rule_b], rule_request
        )
        (base / "selection.json").write_text(
            json.dumps(
                {
                    "parent": parent.manifest_sha256,
                    "empty": empty.manifest_sha256,
                    "modes": mode_refs,
                    "policy": rule.manifest_sha256,
                }
            )
        )
    elif phase == "reader":
        selection = json.loads((base / "selection.json").read_text())
        parent_ref = FederationArtifactRef(selection["parent"])
        reopened = read_verified_federation_derivation(base / "parent", parent_ref)
        assert reopened.data["id"].tolist() == [1, 2]
        assert reopened.data["value"].tolist() == [10.0, 20.0]
        assert reopened.data["value"].dtype == "float64"
        assert reopened.data["value"].isna().tolist() == [False, False]
        assert "cold_test.a@" in reopened.source_ids_by_cell[0]["value"]
        assert "cold_test.b@" in reopened.source_ids_by_cell[1]["value"]
        declarations = [json.loads(row) for _, row in reopened.source_declarations]
        assert {row["connector_id"] for row in declarations} == {
            "cold_test.a@1.0.0",
            "cold_test.b@1.0.0",
        }
        assert reopened.assurance == "software_derivation_candidate"
        assert reopened.basis_status.selected_bytes == "recomputed"
        assert reopened.basis_status.limitation == "limited_candidate_unverified_leaf_history"
        rule = read_verified_federation_derivation(
            base / "policy", FederationArtifactRef(selection["policy"])
        )
        assert rule.data["value"].tolist() == [20.0]
        assert rule.merge_summary["by_policy"] == {"most_recent": 1}
        empty = read_verified_federation_derivation(
            base / "empty", FederationArtifactRef(selection["empty"])
        )
        con = duckdb.connect(":memory:")
        con.register("result", empty.data)
        assert [
            (row[0], row[1])
            for row in con.execute("DESCRIBE SELECT id, value FROM result").fetchall()
        ] == [("id", "BIGINT"), ("value", "DOUBLE")]
        assert con.execute("SELECT COUNT(*) FROM result").fetchone() == (0,)
        c = (
            pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}),
            _metadata("c", TrustLevel.MEDIUM),
        )
        selected = SelectedFederationInput(
            base / "parent", parent_ref, _metadata("a", TrustLevel.HIGH)
        )
        ref = persist_federation_derivation(
            base / "nested", composer, [selected, c], request(CompositionStrategy.JOIN)
        )
        selection["nested"] = ref.manifest_sha256
        selection["mode_children"] = {}
        for mode in CompositionStrategy:
            selected_mode = FederationArtifactRef(selection["modes"][mode.value])
            mode_root = base / ("mode-" + mode.value)
            actual = read_verified_federation_derivation(mode_root, selected_mode)
            expected_frame = pd.DataFrame(
                {
                    "id": pd.Series([2**53 + 1, 2**53 + 3], dtype="int64"),
                    "value": pd.Series([1.5, 2.5], dtype="float64"),
                }
            )
            pd.testing.assert_frame_equal(actual.data[["id", "value"]], expected_frame)
            assert actual.data.isna().sum().to_dict() == {"id": 0, "value": 0}
            assert len(actual.source_declarations) == 2
            assert actual.basis_status.limitation == "limited_candidate_unverified_leaf_history"
            req = replace(
                request(mode),
                key_columns=["id"],
                aggregation_func="mode",
                primary_source=_metadata("a", TrustLevel.HIGH).connector_id,
            )
            child = persist_federation_derivation(
                base / ("mode-child-" + mode.value),
                composer,
                [
                    SelectedFederationInput(
                        mode_root, selected_mode, _metadata("a", TrustLevel.HIGH)
                    )
                ],
                req,
            )
            selection["mode_children"][mode.value] = child.manifest_sha256
        (base / "nested-selection.json").write_text(json.dumps(selection))
    elif phase == "nested":
        selection = json.loads((base / "nested-selection.json").read_text())
        result = read_verified_federation_derivation(
            base / "nested",
            FederationArtifactRef(selection["nested"]),
            held_parents={selection["parent"]: base / "parent"},
        )
        assert result.data["id"].tolist() == [1, 2]
        assert result.data["value"].tolist() == [10.0, 200.0]
        assert "cold_test.a@" in result.source_ids_by_cell[0]["value"]
        assert "cold_test.c@" in result.source_ids_by_cell[1]["value"]
        assert {json.loads(row)["connector_id"] for _, row in result.source_declarations} == {
            "cold_test.a@1.0.0",
            "cold_test.b@1.0.0",
            "cold_test.c@1.0.0",
        }
        assert result.basis_status.limitation == "limited_candidate_unverified_leaf_history"
        for mode in CompositionStrategy:
            mode_root = base / ("mode-" + mode.value)
            selected_mode = selection["modes"][mode.value]
            child = read_verified_federation_derivation(
                base / ("mode-child-" + mode.value),
                FederationArtifactRef(selection["mode_children"][mode.value]),
                held_parents={selected_mode: mode_root},
            )
            expected_frame = pd.DataFrame(
                {
                    "id": pd.Series([2**53 + 1, 2**53 + 3], dtype="int64"),
                    "value": pd.Series([1.5, 2.5], dtype="float64"),
                }
            )
            pd.testing.assert_frame_equal(child.data[["id", "value"]], expected_frame)
            assert len(child.source_declarations) == 2
            assert child.basis_status.limitation == "limited_candidate_unverified_leaf_history"
    elif phase == "forge":
        # Recompute every output from a forged leaf, then bind a NEW selector
        # whose first member additionally declares the separately held parent.
        selection = json.loads((base / "selection.json").read_text())
        forged = (
            pd.DataFrame({"id": [1, 2], "value": [10.0, 20.0]}),
            _metadata("a", TrustLevel.HIGH),
        )
        c = (
            pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}),
            _metadata("c", TrustLevel.MEDIUM),
        )
        raw_root = base / "forged-raw"
        persist_federation_derivation(
            raw_root, composer, [forged, c], request(CompositionStrategy.JOIN)
        )
        manifest = json.loads((raw_root / "manifest.json").read_bytes())
        attack = base / "forged-selected"
        attack.mkdir()
        result_record = manifest["result"]
        (attack / result_record["path"]).write_bytes(
            (raw_root / result_record["path"]).read_bytes()
        )
        for position, record in enumerate(manifest["sources"]):
            source = json.loads((raw_root / record["path"]).read_bytes())
            if position == 0:
                source["parent"] = selection["parent"]
            payload = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(payload).hexdigest()
            name = f"source-{position}-{digest}.json"
            (attack / name).write_bytes(payload)
            manifest["sources"][position] = {"position": position, "path": name, "sha256": digest}
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        (attack / "manifest.json").write_bytes(payload)
        (base / "forge-selection.json").write_text(
            json.dumps(
                {"parent": selection["parent"], "forged": hashlib.sha256(payload).hexdigest()}
            )
        )
    elif phase == "forged":
        from polisyos.fabric.connectors.federation import FederationError

        selection = json.loads((base / "forge-selection.json").read_text())
        parent = read_verified_federation_derivation(
            base / "parent", FederationArtifactRef(selection["parent"])
        )
        assert parent.data["value"].tolist() == [10.0, 20.0]
        import pytest

        with pytest.raises(
            FederationError, match="Selected parent cannot supply child-asserted frame or lineage"
        ):
            read_verified_federation_derivation(
                base / "forged-selected",
                FederationArtifactRef(selection["forged"]),
                held_parents={selection["parent"]: base / "parent"},
            )
    elif phase == "tamper":
        # Build a separately selected, internally rehashed hostile source. The
        # intended negative is lossy dtype admission, not an old digest mismatch.
        selection = json.loads((base / "selection.json").read_text())
        parent = base / "parent"
        manifest = json.loads((parent / "manifest.json").read_bytes())
        attack = base / "attack"
        attack.mkdir()
        result_record = manifest["result"]
        (attack / result_record["path"]).write_bytes((parent / result_record["path"]).read_bytes())
        for position, record in enumerate(manifest["sources"]):
            source = json.loads((parent / record["path"]).read_bytes())
            if position == 0:
                assert source["frame"]["dtypes"][0] == "int64"
                source["frame"]["rows"][0][0] = {"t": "float64", "v": (1.5).hex()}
            payload = json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(payload).hexdigest()
            name = f"source-{position}-{digest}.json"
            (attack / name).write_bytes(payload)
            manifest["sources"][position] = {"position": position, "path": name, "sha256": digest}
        payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        (attack / "manifest.json").write_bytes(payload)
        ref = FederationArtifactRef(hashlib.sha256(payload).hexdigest())
        assert ref.manifest_sha256 != selection["parent"]
        import pytest

        from polisyos.fabric.connectors.federation import FederationError

        with pytest.raises(FederationError, match="cannot represent the held scalar exactly"):
            read_verified_federation_derivation(attack, ref)
    else:
        raise ValueError(phase)


if __name__ == "__main__":
    _worker(sys.argv[1], Path(sys.argv[2]))
