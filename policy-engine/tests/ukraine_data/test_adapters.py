from __future__ import annotations

import json
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pandas as pd

from polisyos.ukraine_data.adapters import SourceExecutionContext, TabularSourceAdapter
from polisyos.ukraine_data.manifests import SkippedSourceManifest, SourceSnapshotManifest
from polisyos.ukraine_data.models import BuildRootConfig, SourceConfig, StageId

if TYPE_CHECKING:
    from pathlib import Path


def test_tabular_adapter_normalize_generates_agent_id_and_lineage(tmp_path: Path) -> None:
    input_path = tmp_path / "edr.csv"
    pd.DataFrame(
        {
            "registration_code": ["12345678", "87654321"],
            "region_code": ["80", "46"],
            "sector_id": ["A", "B"],
        }
    ).to_csv(input_path, index=False)
    source = SourceConfig(
        source_id="edr_current",
        display_name="EDR",
        stage_id=StageId.D0_P0,
        local_path=input_path,
        raw_format="csv",
        normalized_artifact="agent_registry_full.parquet",
        required_columns=["agent_id", "registration_code", "region_code", "sector_id"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    assert isinstance(snapshot, SourceSnapshotManifest)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert {"agent_id", "source_snapshot_id", "schema_version", "record_hash"}.issubset(
        frame.columns
    )
    assert len(frame) == 2


def test_tabular_adapter_optional_source_returns_skipped_manifest(tmp_path: Path) -> None:
    source = SourceConfig(
        source_id="land_cadastre",
        display_name="Land Cadastre",
        stage_id=StageId.D3,
        required=False,
        optional_reason="Exploratory optional land-use proxy connector.",
        normalized_artifact="land_use_proxy_baseline.parquet",
        required_columns=["cell_id", "period_id", "land_use_proxy"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)

    assert isinstance(snapshot, SkippedSourceManifest)
    assert "Exploratory optional" in snapshot.reason


def test_tabular_adapter_fetches_directory_and_normalizes_edr_seed(tmp_path: Path) -> None:
    source_dir = tmp_path / "incoming_edr"
    source_dir.mkdir()
    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<DATA>
  <SUBJECT>
    <EDRPOU>12345678</EDRPOU>
    <NAME>Example LLC</NAME>
    <OPF>ТОВ</OPF>
    <REGISTRATION>13.09.2024; 13.09.2024; 1010351020000011182</REGISTRATION>
  </SUBJECT>
</DATA>
"""
    with ZipFile(source_dir / "UO.zip", "w") as archive:
        archive.writestr("UO.xml", xml_payload)
    source = SourceConfig(
        source_id="edr_current",
        display_name="EDR",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="agent_registry_full.parquet",
        required_columns=["agent_id", "registration_code", "region_code", "sector_id"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    assert isinstance(snapshot, SourceSnapshotManifest)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "registration_code"] == "12345678"
    assert frame.loc[0, "sector_id"] == "ТОВ"


def test_tabular_adapter_normalizes_spending_seed_from_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "spending_seed"
    source_dir.mkdir()
    payload = [
        {
            "payer_edrpou": "11111111",
            "recipt_edrpou": "22222222",
            "amount": 10.5,
            "trans_date": "2023-12-10",
        },
        {
            "payer_edrpou": "11111111",
            "recipt_edrpou": "22222222",
            "amount": 1.5,
            "trans_date": "2023-12-11",
        },
    ]
    (source_dir / "transactions_sample_2023-12-10.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    source = SourceConfig(
        source_id="spending_full",
        display_name="Spending",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="budget_flows_monthly_sparse.parquet",
        required_columns=[
            "source_agent_id",
            "target_agent_id",
            "amount",
            "period_id",
            "registration_code",
        ],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    assert isinstance(snapshot, SourceSnapshotManifest)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "source_agent_id"] == "11111111"
    assert frame.loc[0, "target_agent_id"] == "22222222"
    assert frame.loc[0, "amount"] == 12.0
    assert frame.loc[0, "period_id"] == "2023-12"


def test_tabular_adapter_normalizes_prozorro_contracts_feed_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "prozorro_seed"
    feed_dir = source_dir / "contracts_feed"
    feed_dir.mkdir(parents=True)
    (feed_dir / "page_0000001.json").write_text(
        json.dumps(
            {
                "data": [
                    {"id": "contract-a", "dateModified": "2024-01-15T10:00:00+02:00"},
                    {"id": "contract-b", "dateModified": "2024-01-20T10:00:00+02:00"},
                ],
                "next_page": {"offset": "x"},
            }
        ),
        encoding="utf-8",
    )
    source = SourceConfig(
        source_id="prozorro_full",
        display_name="Prozorro",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="procurement_contracts_monthly.parquet",
        required_columns=[
            "buyer_agent_id",
            "supplier_agent_id",
            "amount",
            "period_id",
            "registration_code",
        ],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    assert isinstance(snapshot, SourceSnapshotManifest)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert list(frame["registration_code"]) == ["contracts_feed::2024-01"]
    assert set(frame["period_id"]) == {"2024-01"}
    assert frame.loc[0, "amount"] == 2.0


def test_tabular_adapter_prefers_prozorro_contract_details_when_present(tmp_path: Path) -> None:
    source_dir = tmp_path / "prozorro_details"
    details_dir = source_dir / "contracts_details"
    details_dir.mkdir(parents=True)
    (details_dir / "page_0000001.json").write_text(
        json.dumps(
            {
                "contracts": [
                    {
                        "id": "contract-a",
                        "dateSigned": "2024-01-15T10:00:00+02:00",
                        "value": {"amount": 1250.5},
                        "buyer": {"identifier": {"id": "11111111"}},
                        "suppliers": [{"identifier": {"id": "22222222"}}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    source = SourceConfig(
        source_id="prozorro_full",
        display_name="Prozorro",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="procurement_contracts_monthly.parquet",
        required_columns=[
            "buyer_agent_id",
            "supplier_agent_id",
            "amount",
            "period_id",
            "registration_code",
        ],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "buyer_agent_id"] == "11111111"
    assert frame.loc[0, "supplier_agent_id"] == "22222222"
    assert frame.loc[0, "amount"] == 1250.5
    assert frame.loc[0, "period_id"] == "2024-01"


def test_tabular_adapter_normalizes_spending_contracts_procurement_proxy(tmp_path: Path) -> None:
    source_dir = tmp_path / "spending_contracts"
    source_dir.mkdir()
    (source_dir / "contracts_endpoint_seed.json").write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "id": 101,
                        "edrpou": "11111111",
                        "amount": 1200.0,
                        "signDate": "2024-01-15",
                        "idTenderProzorro": "UA-2024-01-15-000001-a",
                        "contractors": [
                            {"identifier": "22222222", "name": "Supplier A"},
                            {"identifier": "33333333", "name": "Supplier B"},
                        ],
                    },
                    {
                        "id": 102,
                        "edrpou": "11111111",
                        "amount": 500.0,
                        "documentDate": "2024-01-20",
                        "contractors": [
                            {"identifier": "HIDDEN", "name": "Hidden Supplier"},
                        ],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source = SourceConfig(
        source_id="spending_contracts_procurement_proxy",
        display_name="Spending contracts proxy",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="procurement_contracts_monthly.parquet",
        required_columns=[
            "buyer_agent_id",
            "supplier_agent_id",
            "amount",
            "period_id",
            "registration_code",
        ],
        identity_columns=["buyer_agent_id", "supplier_agent_id", "registration_code"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path).sort_values(
        ["buyer_agent_id", "supplier_agent_id", "period_id"], na_position="last"
    )

    assert len(frame) == 3
    visible_amounts = (
        frame[frame["supplier_agent_id"].notna()].set_index("supplier_agent_id")["amount"].to_dict()
    )
    assert visible_amounts == {"22222222": 600.0, "33333333": 600.0}
    visible_names = (
        frame[frame["supplier_agent_id"].notna()]
        .set_index("supplier_agent_id")["supplier_name"]
        .to_dict()
    )
    assert visible_names == {"22222222": "Supplier A", "33333333": "Supplier B"}
    hidden_row = frame[frame["supplier_agent_id"].isna()].iloc[0]
    assert hidden_row["buyer_agent_id"] == "11111111"
    assert hidden_row["amount"] == 500.0
    assert hidden_row["period_id"] == "2024-01"
    assert hidden_row["supplier_name"] == "Hidden Supplier"
    assert hidden_row["contract_count"] == 1


def test_tabular_adapter_normalizes_macro_sdmx_payload(tmp_path: Path) -> None:
    source_dir = tmp_path / "macro_seed"
    source_dir.mkdir()
    payload = {
        "meta": {},
        "data": {
            "dataSets": [
                {
                    "series": {
                        "0:0": {
                            "observations": {
                                "0": ["123.4"],
                                "1": ["150.6"],
                            }
                        }
                    }
                }
            ],
            "structures": [
                {
                    "dimensions": {
                        "series": [
                            {"id": "INDICATOR", "values": [{"id": "GDP_CUR_PRC"}]},
                            {"id": "REGION", "values": [{"id": "UA00000000000000000"}]},
                        ],
                        "observation": [
                            {"id": "TIME_PERIOD", "values": [{"value": "2022"}, {"value": "2023"}]}
                        ],
                    }
                }
            ],
        },
    }
    (source_dir / "derzhstat_annual_national_accounts_latest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    source = SourceConfig(
        source_id="macro_nbu_derzhstat",
        display_name="Macro",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="macro_panel_monthly.parquet",
        required_columns=["period_id", "metric_id", "observed_value", "region_code"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert list(frame["period_id"]) == ["2022-12", "2023-12"]
    assert all(value == "UA00000000000000000" for value in frame["region_code"])


def test_tabular_adapter_normalizes_dps_signed_xml_with_regex_extraction(tmp_path: Path) -> None:
    source_dir = tmp_path / "dps_seed"
    source_dir.mkdir()
    balance_payload = (
        'UA1_SIGN\x00garbage<?xml version="1.0" encoding="UTF-8"?>'
        "<DECLAR><DECLARBODY>"
        "<FIRM_EDRPOU>12345678</FIRM_EDRPOU>"
        "<A1300>100</A1300>"
        "<A1595>40</A1595>"
        "<FIRM_TELORG>7</FIRM_TELORG>"
        "</DECLARBODY></DECLAR>"
    )
    income_payload = (
        'UA1_SIGN\x00garbage<?xml version="1.0" encoding="UTF-8"?>'
        "<DECLAR><DECLARBODY>"
        "<FIRM_EDRPOU>12345678</FIRM_EDRPOU>"
        "<B2000>250</B2000>"
        "</DECLARBODY></DECLAR>"
    )
    with ZipFile(source_dir / "f_i_ric_2022.zip", "w") as archive:
        archive.writestr("balance.xml", balance_payload)
    with ZipFile(source_dir / "f_ii_ric_2022.zip", "w") as archive:
        archive.writestr("income.xml", income_payload)
    source = SourceConfig(
        source_id="dps_financials",
        display_name="DPS",
        stage_id=StageId.D0_P0,
        local_path=source_dir,
        normalized_artifact="firm_fundamentals_annual.parquet",
        required_columns=["agent_id", "period_id", "revenue", "assets", "liabilities", "employees"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "registration_code"] == "12345678"
    assert frame.loc[0, "revenue"] == 250.0
    assert frame.loc[0, "assets"] == 100.0
    assert frame.loc[0, "liabilities"] == 40.0
    assert frame.loc[0, "employees"] == 0.0
    assert [finding.code for finding in manifest.findings] == ["dps_employment_not_available"]


def test_tabular_adapter_normalizes_household_microdata_from_manual_drop(tmp_path: Path) -> None:
    source_dir = tmp_path / "manual_microdata_drop" / "mic_doch_i_umovy"
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "rik_fa_1": [2018, 2018],
            "kvart_kd": [4, 2],
            "code_fam": [100001, 100002],
            "w_q": [10.0, 20.0],
            "cod_obl": ["Вінницька", "Київ"],
            "cashinc": [1000.0, 1500.0],
            "totalinc": [1200.0, 1800.0],
            "totalexp": [900.0, 1100.0],
        }
    ).to_excel(source_dir / "Households_microdani_anonimni_2018.xlsx", index=False)

    source = SourceConfig(
        source_id="household_microdata",
        display_name="Household microdata",
        stage_id=StageId.D3,
        local_path=tmp_path / "manual_microdata_drop",
        normalized_artifact="household_synthetic_targets.parquet",
        required_columns=["household_id", "cell_id", "period_id", "income", "weight"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 2
    assert set(frame["period_id"]) == {"2018-12", "2018-06"}
    assert set(frame["region_code"]) == {"05", "80"}
    assert set(frame["income"]) == {1200.0, 1800.0}


def test_tabular_adapter_normalizes_labor_force_microdata_from_manual_drop(tmp_path: Path) -> None:
    source_dir = tmp_path / "manual_microdata_drop" / "mic_poc_rob_syly_18"
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "Kod_obs": [111, 222],
            "Rik": [2018, 2018],
            "wes_rik": [1.0, 2.0],
            "RG": ["Вінницька", "Київ"],
            "labour_force": ["Зайняте населення", "Економічно неактивне населення"],
            "stat_empl": ["Працюючі за наймом", "#NULL!"],
            "informal_empl": ["Формальна зайнятість", "#NULL!"],
        }
    ).to_excel(source_dir / "LFS_2018.xlsx", index=False)

    source = SourceConfig(
        source_id="labor_force_microdata",
        display_name="Labor-force microdata",
        stage_id=StageId.D3,
        local_path=tmp_path / "manual_microdata_drop",
        normalized_artifact="labor_force_micro_targets.parquet",
        required_columns=["household_id", "cell_id", "period_id", "participation_rate"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 2
    assert set(frame["period_id"]) == {"2018-12"}
    assert set(frame["region_code"]) == {"05", "80"}
    assert set(frame["participation_rate"]) == {0.0, 1.0}


def test_tabular_adapter_normalizes_pfu_debt_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "pfu_debt"
    source_dir.mkdir()
    pd.DataFrame(
        [
            ["title", None, None, None, None, None, None, None, None],
            [None, None, None, None, None, None, None, None, None],
            [
                "Код регіону",
                "Повна назва боржника",
                "Місце знаходження",
                "код ЄДРПОУ",
                "Підпорядкованість",
                "Код форми власності",
                "Сума боргу на початок року",
                "у т. ч. недоїмка по страхових внесках",
                "Сума боргу станом на звітну дату",
            ],
            [1, 2, 3, 4, 5, 6, 7, 8, 9],
            [5, "Test Firm", "Kyiv", "12345678", "26.", 1, 100.0, 50.0, 125.0],
        ]
    ).to_excel(source_dir / "001_01.04.2019.xlsx", index=False, header=False)

    source = SourceConfig(
        source_id="pfu_debt",
        display_name="PFU debt",
        stage_id=StageId.D3,
        local_path=source_dir,
        normalized_artifact="arrears_panel_monthly.parquet",
        required_columns=["agent_id", "period_id", "arrears_amount"],
        identity_columns=["agent_id", "registration_code"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "registration_code"] == "12345678"
    assert frame.loc[0, "arrears_amount"] == 125.0
    assert frame.loc[0, "period_id"] == "2019-04"


def test_tabular_adapter_normalizes_logistics_mobility_proxy(tmp_path: Path) -> None:
    source_dir = tmp_path / "logistics_mobility_displacement" / "border_crossing_points_public"
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "code": [71200, 71300, 80100],
            "region_name": ["Волинська область", "Волинська область", "м. Київ"],
            "name": ["Ягодин", "Устилуг", "Бориспіль"],
        }
    ).to_excel(source_dir / "001_resource.xlsx", index=False)

    source = SourceConfig(
        source_id="logistics_mobility_displacement",
        display_name="Logistics mobility displacement",
        stage_id=StageId.D3,
        local_path=tmp_path / "logistics_mobility_displacement",
        normalized_artifact="transport_pressure_monthly.parquet",
        required_columns=["cell_id", "period_id", "mobility_pressure"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 2
    assert set(frame["region_code"]) == {"07", "80"}
    assert frame.loc[frame["region_code"] == "07", "mobility_pressure"].item() == 2


def test_tabular_adapter_normalizes_land_cadastre_proxy(tmp_path: Path) -> None:
    source_dir = tmp_path / "land_cadastre"
    source_dir.mkdir()
    pd.DataFrame(
        [
            [
                "Інформація з ведення Державного земельного кадастру на території Дніпропетровської області станом на 27.11.2020",
                None,
                None,
            ],
            ["№ з/п", "Назва адміністративно-територіальних одиниць", "Виконано"],
            [1, "Дніпро", 11],
            [2, "Кам'янське", 7],
        ]
    ).to_excel(source_dir / "001_land_27.11.2020.xlsx", index=False, header=False)

    source = SourceConfig(
        source_id="land_cadastre",
        display_name="Land cadastre",
        stage_id=StageId.D3,
        local_path=source_dir,
        normalized_artifact="land_use_proxy_baseline.parquet",
        required_columns=["cell_id", "period_id", "land_use_proxy"],
    )
    ctx = SourceExecutionContext(BuildRootConfig(root=tmp_path / "build"))
    adapter = TabularSourceAdapter()

    snapshot = adapter.fetch(source, ctx)
    manifest = adapter.normalize(source, snapshot, ctx)
    frame = pd.read_parquet(manifest.normalized_artifact.path)

    assert len(frame) == 1
    assert frame.loc[0, "region_code"] == "12"
    assert frame.loc[0, "period_id"] == "2020-11"
    assert frame.loc[0, "land_use_proxy"] > 0.0
