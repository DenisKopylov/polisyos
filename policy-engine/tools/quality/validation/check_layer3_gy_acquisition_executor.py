#!/usr/bin/env python3
"""Recompute and verify GY-N13b acquisition-executor artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric.data_plane import (
    AppendOnlyEvidenceJournal,
    canonical_json_bytes,
)
from polisyos.runtime.quality.acquisition_executor import (
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from tools.quality.validation.layer3_gy_acquisition_executor import (
    DEFAULT_CARRIER_LIVENESS_UPDATE,
    DEFAULT_D6_PRIMARY_METADATA_EVIDENCE,
    DEFAULT_D6_PRIMARY_METADATA_OWNER,
    DEFAULT_D6_ROUTE_SELECTION,
    DEFAULT_METADATA_EXECUTION_EVIDENCE,
    DEFAULT_METADATA_PROBE_OWNER,
    DEFAULT_R1_FORENSIC_RECEIPT,
    DEFAULT_TARGET_AUTHORITY_PROVISION,
    DEFAULT_TARGET_AUTHORITY_REGISTRY,
    DEFAULT_TARGET_HARNESS_RECEIPT,
    bytes_sha256,
    classify_worldbank_indicator_metadata,
    derive_d6_metadata_probe_execution_evidence,
    derive_d6_metadata_probe_owner,
    derive_d6_route_selection,
    derive_live_attempt_id,
    derive_live_target_selection,
    derive_metadata_probe_execution_evidence,
    derive_metadata_probe_owner,
    derive_r1_forensic_receipt,
    derive_target_authority_owners,
    derive_target_family_receipt,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    DEFAULT_ACCEPTANCE_AUTHORITY_OWNER,
    DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS,
    DEFAULT_ACCEPTANCE_INPUT_SELECTION,
    derive_acceptance_authority_owners,
    derive_acceptance_input_selection,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CENSUS_PATH = (
    POLICY_ENGINE_ROOT / "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json"
)
DEFAULT_SUBSTRATE_PATH = (
    POLICY_ENGINE_ROOT
    / "architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json"
)
DEFAULT_CATALOG_OWNER_REF = (
    "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
DEFAULT_L5_OWNER_REF = (
    "repo://production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/"
    "calibration/d2/measurement_registry.json"
)
DEFAULT_LIVE_EXECUTION_EVIDENCE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_live_execution_evidence.json"
)
DEFAULT_RAW_JOURNAL = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)
DEFAULT_CAS_ROOT = Path("architecture/policy_design_case/layer3_gy_acquisition_cas")


def _paid_success_elapsed_seconds(receipt: Any) -> float:
    """Return the longest successful raw-response latency in the paid R1 prefix."""

    candidates = tuple(
        float(attempt.max_elapsed_seconds)
        for attempt in receipt.attempts
        if attempt.raw_body_sha256 is not None
        and attempt.http_status_code is not None
        and 200 <= attempt.http_status_code < 300
    )
    if not candidates:
        raise RuntimeError("acceptance_paid_success_latency_missing")
    return max(candidates)


def main() -> int:
    """Run the requested offline target-owner lifecycle mode."""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-target-owners", action="store_true")
    mode.add_argument("--write-target-owners", action="store_true")
    mode.add_argument("--execute-live", action="store_true")
    mode.add_argument("--check-resumption-owners", action="store_true")
    mode.add_argument("--write-resumption-owners", action="store_true")
    mode.add_argument("--execute-metadata", action="store_true")
    mode.add_argument("--check-metadata-evidence", action="store_true")
    mode.add_argument("--write-metadata-evidence", action="store_true")
    mode.add_argument("--check-d6-route-owners", action="store_true")
    mode.add_argument("--write-d6-route-owners", action="store_true")
    mode.add_argument("--execute-d6-metadata", action="store_true")
    mode.add_argument("--check-d6-metadata-evidence", action="store_true")
    mode.add_argument("--write-d6-metadata-evidence", action="store_true")
    mode.add_argument("--check-acceptance-inputs", action="store_true")
    mode.add_argument("--write-acceptance-inputs", action="store_true")
    mode.add_argument("--check-acceptance-authority", action="store_true")
    mode.add_argument("--write-acceptance-authority", action="store_true")
    parser.add_argument("--catalog-path", type=Path, required=True)
    parser.add_argument("--l5-path", type=Path, required=True)
    parser.add_argument("--census-path", type=Path, default=DEFAULT_CENSUS_PATH)
    parser.add_argument("--substrate-path", type=Path, default=DEFAULT_SUBSTRATE_PATH)
    parser.add_argument("--country-code", default="UKR")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--attempt-count", type=int, default=1)
    parser.add_argument("--attempt-ordinal", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=10)
    args = parser.parse_args()
    if args.attempt_count < 1:
        parser.error("--attempt-count must be at least 1")
    if not 1 <= args.attempt_ordinal <= args.attempt_count:
        parser.error("--attempt-ordinal must be within --attempt-count")
    if args.page_size < 1:
        parser.error("--page-size must be at least 1")

    owners = _recompute_target_owners(
        catalog_path=args.catalog_path,
        l5_path=args.l5_path,
        census_path=args.census_path,
        substrate_path=args.substrate_path,
        attempt_count=args.attempt_count,
    )
    second = _recompute_target_owners(
        catalog_path=args.catalog_path,
        l5_path=args.l5_path,
        census_path=args.census_path,
        substrate_path=args.substrate_path,
        attempt_count=args.attempt_count,
    )
    if owners.payloads() != second.payloads():
        raise RuntimeError("target_owner_derivation_not_byte_stable")

    r1, metadata_owner = _recompute_resumption_owners(
        catalog_path=args.catalog_path,
    )
    second_r1, second_metadata_owner = _recompute_resumption_owners(
        catalog_path=args.catalog_path,
    )
    resumption_payloads = _resumption_owner_payloads(r1, metadata_owner)
    if resumption_payloads != _resumption_owner_payloads(
        second_r1,
        second_metadata_owner,
    ):
        raise RuntimeError("resumption_owner_derivation_not_byte_stable")

    if args.check_acceptance_inputs or args.write_acceptance_inputs:
        paid_success_elapsed = _paid_success_elapsed_seconds(r1)
        acceptance = derive_acceptance_input_selection(
            catalog_path=args.catalog_path,
            census_path=args.census_path,
            r1_paid_success_elapsed_seconds=paid_success_elapsed,
        )
        second_acceptance = derive_acceptance_input_selection(
            catalog_path=args.catalog_path,
            census_path=args.census_path,
            r1_paid_success_elapsed_seconds=paid_success_elapsed,
        )
        payload = canonical_json_bytes(acceptance.model_dump(mode="json"))
        if payload != canonical_json_bytes(second_acceptance.model_dump(mode="json")):
            raise RuntimeError("acceptance_input_selection_not_byte_stable")
        payloads = {DEFAULT_ACCEPTANCE_INPUT_SELECTION: payload}
        if args.write_acceptance_inputs:
            _write_replace_bytes(
                POLICY_ENGINE_ROOT / DEFAULT_ACCEPTANCE_INPUT_SELECTION,
                payload,
            )
            status = "acceptance_inputs_written"
        else:
            _check_payloads(payloads, label="acceptance_input_selection")
            status = "ok"
        print(
            json.dumps(
                {
                    "status": status,
                    "disposition": acceptance.disposition,
                    "all_local_series_group_count": (acceptance.all_local_series_group_count),
                    "local_monetary_denominator_count": (
                        acceptance.local_monetary_denominator_count
                    ),
                    "eligible_local_nominal_count": (acceptance.eligible_local_nominal_count),
                    "inflation_binding_denominator_count": (
                        acceptance.inflation_binding_denominator_count
                    ),
                    "eligible_deflator_count": acceptance.eligible_deflator_count,
                    "selected_nominal_dataset_id": (
                        acceptance.selected_nominal.dataset_id
                        if acceptance.selected_nominal is not None
                        else None
                    ),
                    "selected_deflator_request_dataset_id": (
                        acceptance.selected_deflator.request_dataset_id
                        if acceptance.selected_deflator is not None
                        else None
                    ),
                    "request_years": [
                        acceptance.request_start_year,
                        acceptance.request_end_year,
                    ],
                    "derived_timeout_cap_seconds": (acceptance.derived_timeout_cap_seconds),
                    "byte_stable_passes": 2,
                    "live_network_calls": 0,
                    "artifact_file_sha256": (
                        bytes_sha256(payload) if args.write_acceptance_inputs else None
                    ),
                },
                sort_keys=True,
            )
        )
        return 0

    if args.check_acceptance_authority or args.write_acceptance_authority:
        paid_success_elapsed = _paid_success_elapsed_seconds(r1)
        acceptance = derive_acceptance_input_selection(
            catalog_path=args.catalog_path,
            census_path=args.census_path,
            r1_paid_success_elapsed_seconds=paid_success_elapsed,
        )
        _check_payloads(
            {
                DEFAULT_ACCEPTANCE_INPUT_SELECTION: canonical_json_bytes(
                    acceptance.model_dump(mode="json")
                )
            },
            label="acceptance_input_selection",
        )
        base_owners = _recompute_target_owners(
            catalog_path=args.catalog_path,
            l5_path=args.l5_path,
            census_path=args.census_path,
            substrate_path=args.substrate_path,
            attempt_count=len(r1.attempts),
        )
        acceptance_owners = derive_acceptance_authority_owners(
            acceptance,
            base_owners=base_owners,
            catalog_path=args.catalog_path,
            baseline_owner_ref=DEFAULT_CATALOG_OWNER_REF,
            l5_path=args.l5_path,
            l5_owner_ref=DEFAULT_L5_OWNER_REF,
            fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
        )
        second_acceptance_owners = derive_acceptance_authority_owners(
            acceptance,
            base_owners=base_owners,
            catalog_path=args.catalog_path,
            baseline_owner_ref=DEFAULT_CATALOG_OWNER_REF,
            l5_path=args.l5_path,
            l5_owner_ref=DEFAULT_L5_OWNER_REF,
            fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
        )
        payloads = acceptance_owners.payloads()
        if payloads != second_acceptance_owners.payloads():
            raise RuntimeError("acceptance_authority_derivation_not_byte_stable")
        if args.write_acceptance_authority:
            for relative in (
                DEFAULT_ACCEPTANCE_DEFLATOR_HARNESS,
                DEFAULT_TARGET_AUTHORITY_REGISTRY,
                DEFAULT_TARGET_AUTHORITY_PROVISION,
                DEFAULT_ACCEPTANCE_AUTHORITY_OWNER,
            ):
                _write_replace_bytes(POLICY_ENGINE_ROOT / relative, payloads[relative])
            status = "acceptance_authority_written"
        else:
            _check_payloads(payloads, label="acceptance_authority")
            status = "ok"
        print(
            json.dumps(
                {
                    "status": status,
                    "entry_id": acceptance_owners.entry.entry_id,
                    "attempt_id": acceptance_owners.owner.live_attempt_id,
                    "request_dataset_id": (
                        acceptance.execution_selection.request_dataset_id
                        if acceptance.execution_selection is not None
                        else None
                    ),
                    "registry_entry_count": (acceptance_owners.owner.registry_entry_count),
                    "live_harness_receipt_count": (
                        acceptance_owners.owner.live_harness_receipt_count
                    ),
                    "registry_content_sha256": (acceptance_owners.registry.content_sha256),
                    "provision_id": acceptance_owners.provision.provision_id,
                    "harness_content_sha256": (acceptance_owners.owner.live_harness_content_sha256),
                    "byte_stable_passes": 2,
                    "live_network_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    if any(
        (
            args.write_d6_route_owners,
            args.check_d6_route_owners,
            args.execute_d6_metadata,
            args.check_d6_metadata_evidence,
            args.write_d6_metadata_evidence,
        )
    ):
        d6_selection, d6_metadata_owner = _recompute_d6_route_owners(
            catalog_path=args.catalog_path,
            census_path=args.census_path,
            substrate_path=args.substrate_path,
            r1=r1,
        )
        second_d6_selection, second_d6_metadata_owner = _recompute_d6_route_owners(
            catalog_path=args.catalog_path,
            census_path=args.census_path,
            substrate_path=args.substrate_path,
            r1=r1,
        )
        d6_payloads = _d6_route_owner_payloads(d6_selection, d6_metadata_owner)
        if d6_payloads != _d6_route_owner_payloads(
            second_d6_selection,
            second_d6_metadata_owner,
        ):
            raise RuntimeError("d6_route_owner_derivation_not_byte_stable")
        _check_payloads(resumption_payloads, label="resumption_owner")
        r2_evidence, r2_carrier_update = derive_metadata_probe_execution_evidence(
            owner=metadata_owner,
            r1_receipt=r1,
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            baseline_path=args.catalog_path,
        )
        _check_payloads(
            {
                DEFAULT_METADATA_EXECUTION_EVIDENCE: canonical_json_bytes(
                    r2_evidence.model_dump(mode="json")
                ),
                DEFAULT_CARRIER_LIVENESS_UPDATE: canonical_json_bytes(
                    r2_carrier_update.model_dump(mode="json")
                ),
            },
            label="metadata_evidence",
        )
        if args.execute_d6_metadata:
            _check_payloads(d6_payloads, label="d6_route_owner")
            evidence_path = POLICY_ENGINE_ROOT / DEFAULT_D6_PRIMARY_METADATA_EVIDENCE
            require_new_live_execution_outputs(
                journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
                cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
                evidence_path=evidence_path,
                attempt_id=d6_metadata_owner.authorization.attempt_id,
            )
            _execute_metadata_probe(
                owner=d6_metadata_owner,
                journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
                cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            )
            evidence = derive_d6_metadata_probe_execution_evidence(
                owner=d6_metadata_owner,
                selection=d6_selection,
                journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
                cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
                baseline_path=args.catalog_path,
            )
            _write_replace_bytes(
                evidence_path,
                canonical_json_bytes(evidence.model_dump(mode="json")),
            )
            print(
                json.dumps(
                    {
                        "status": "d6_metadata_evidence_written",
                        "attempt_id": evidence.attempt_id,
                        "call_count": evidence.call_count,
                        "terminal_outcome": evidence.terminal.outcome_code,
                        "metadata_disposition": (
                            evidence.classification.disposition
                            if evidence.classification is not None
                            else "metadata_transport_terminal"
                        ),
                        "metadata_source_id": (
                            evidence.classification.source_id
                            if evidence.classification is not None
                            else None
                        ),
                        "baseline_before_sha256": evidence.baseline_before_sha256,
                        "baseline_after_sha256": evidence.baseline_after_sha256,
                        "evidence_file_sha256": bytes_sha256(evidence_path.read_bytes()),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.check_d6_metadata_evidence or args.write_d6_metadata_evidence:
            _check_payloads(d6_payloads, label="d6_route_owner")
            evidence = derive_d6_metadata_probe_execution_evidence(
                owner=d6_metadata_owner,
                selection=d6_selection,
                journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
                cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
                baseline_path=args.catalog_path,
            )
            second_evidence = derive_d6_metadata_probe_execution_evidence(
                owner=d6_metadata_owner,
                selection=d6_selection,
                journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
                cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
                baseline_path=args.catalog_path,
            )
            payload = canonical_json_bytes(evidence.model_dump(mode="json"))
            if payload != canonical_json_bytes(second_evidence.model_dump(mode="json")):
                raise RuntimeError("d6_metadata_evidence_derivation_not_byte_stable")
            evidence_payloads = {DEFAULT_D6_PRIMARY_METADATA_EVIDENCE: payload}
            if args.write_d6_metadata_evidence:
                _write_replace_bytes(
                    POLICY_ENGINE_ROOT / DEFAULT_D6_PRIMARY_METADATA_EVIDENCE,
                    payload,
                )
                status = "written"
            else:
                _check_payloads(evidence_payloads, label="d6_metadata_evidence")
                status = "ok"
            print(
                json.dumps(
                    {
                        "status": status,
                        "metadata_disposition": (
                            evidence.classification.disposition
                            if evidence.classification is not None
                            else "metadata_transport_terminal"
                        ),
                        "metadata_source_id": (
                            evidence.classification.source_id
                            if evidence.classification is not None
                            else None
                        ),
                        "byte_stable_passes": 2,
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.write_d6_route_owners:
            for relative, payload in d6_payloads.items():
                _write_replace_bytes(POLICY_ENGINE_ROOT / relative, payload)
            status = "written"
        else:
            _check_payloads(d6_payloads, label="d6_route_owner")
            status = "ok"
        print(
            json.dumps(
                {
                    "status": status,
                    "route_disposition": d6_selection.route_disposition,
                    "target_variable": d6_selection.target_variable,
                    "primary_request_dataset_id": (d6_selection.primary.request_dataset_id),
                    "auxiliary_request_dataset_id": (d6_selection.auxiliary.request_dataset_id),
                    "primary_candidate_denominator": (d6_selection.primary_candidate_denominator),
                    "auxiliary_candidate_denominator": (
                        d6_selection.auxiliary_candidate_denominator
                    ),
                    "metadata_attempt_id": (d6_metadata_owner.authorization.attempt_id),
                    "timeout_cap_seconds": (
                        d6_metadata_owner.authorization.budget.timeout_cap_seconds
                    ),
                    "byte_stable_passes": 2,
                    "live_network_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.execute_metadata:
        _check_payloads(resumption_payloads, label="resumption_owner")
        evidence_path = POLICY_ENGINE_ROOT / DEFAULT_METADATA_EXECUTION_EVIDENCE
        update_path = POLICY_ENGINE_ROOT / DEFAULT_CARRIER_LIVENESS_UPDATE
        require_new_live_execution_outputs(
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            evidence_path=evidence_path,
            attempt_id=metadata_owner.authorization.attempt_id,
        )
        if update_path.exists():
            raise RuntimeError(f"live_execution_output_already_exists:{update_path.as_posix()}")
        _execute_metadata_probe(
            owner=metadata_owner,
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
        )
        evidence, carrier_update = derive_metadata_probe_execution_evidence(
            owner=metadata_owner,
            r1_receipt=r1,
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            baseline_path=args.catalog_path,
        )
        _write_replace_bytes(
            evidence_path,
            canonical_json_bytes(evidence.model_dump(mode="json")),
        )
        _write_replace_bytes(
            update_path,
            canonical_json_bytes(carrier_update.model_dump(mode="json")),
        )
        print(
            json.dumps(
                {
                    "status": "metadata_evidence_written",
                    "attempt_id": evidence.attempt_id,
                    "call_count": evidence.call_count,
                    "terminal_outcome": evidence.terminal.outcome_code,
                    "metadata_disposition": (
                        evidence.classification.disposition
                        if evidence.classification is not None
                        else "metadata_transport_terminal"
                    ),
                    "carrier_disposition": carrier_update.carrier_disposition,
                    "timeout_cap_seconds": (
                        metadata_owner.authorization.budget.timeout_cap_seconds
                    ),
                    "evidence_file_sha256": bytes_sha256(evidence_path.read_bytes()),
                    "carrier_update_file_sha256": bytes_sha256(update_path.read_bytes()),
                },
                sort_keys=True,
            )
        )
        return 0

    if args.check_metadata_evidence or args.write_metadata_evidence:
        _check_payloads(resumption_payloads, label="resumption_owner")
        evidence, carrier_update = derive_metadata_probe_execution_evidence(
            owner=metadata_owner,
            r1_receipt=r1,
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            baseline_path=args.catalog_path,
        )
        second_evidence, second_carrier_update = derive_metadata_probe_execution_evidence(
            owner=metadata_owner,
            r1_receipt=r1,
            journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
            cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
            baseline_path=args.catalog_path,
        )
        evidence_payloads = {
            DEFAULT_METADATA_EXECUTION_EVIDENCE: canonical_json_bytes(
                evidence.model_dump(mode="json")
            ),
            DEFAULT_CARRIER_LIVENESS_UPDATE: canonical_json_bytes(
                carrier_update.model_dump(mode="json")
            ),
        }
        if evidence_payloads != {
            DEFAULT_METADATA_EXECUTION_EVIDENCE: canonical_json_bytes(
                second_evidence.model_dump(mode="json")
            ),
            DEFAULT_CARRIER_LIVENESS_UPDATE: canonical_json_bytes(
                second_carrier_update.model_dump(mode="json")
            ),
        }:
            raise RuntimeError("metadata_evidence_derivation_not_byte_stable")
        if args.write_metadata_evidence:
            for relative, payload in evidence_payloads.items():
                _write_replace_bytes(POLICY_ENGINE_ROOT / relative, payload)
            status = "written"
        else:
            _check_payloads(evidence_payloads, label="metadata_evidence")
            status = "ok"
        print(
            json.dumps(
                {
                    "status": status,
                    "metadata_disposition": (
                        evidence.classification.disposition
                        if evidence.classification is not None
                        else "metadata_transport_terminal"
                    ),
                    "carrier_disposition": carrier_update.carrier_disposition,
                    "byte_stable_passes": 2,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.write_resumption_owners:
        for relative, payload in resumption_payloads.items():
            _write_replace_bytes(POLICY_ENGINE_ROOT / relative, payload)
        print(
            json.dumps(
                {
                    "status": "written",
                    "r1_disposition": r1.classification.disposition,
                    "metadata_attempt_id": metadata_owner.authorization.attempt_id,
                    "timeout_cap_seconds": (
                        metadata_owner.authorization.budget.timeout_cap_seconds
                    ),
                    "byte_stable_passes": 2,
                    "live_network_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.check_resumption_owners:
        _check_payloads(resumption_payloads, label="resumption_owner")
        print(
            json.dumps(
                {
                    "status": "ok",
                    "r1_disposition": r1.classification.disposition,
                    "metadata_attempt_id": metadata_owner.authorization.attempt_id,
                    "timeout_cap_seconds": (
                        metadata_owner.authorization.budget.timeout_cap_seconds
                    ),
                    "byte_stable_passes": 2,
                    "live_network_calls": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.execute_live:
        _check_target_owner_payloads(owners)
        if args.start_year is None or args.end_year is None:
            parser.error("--execute-live requires --start-year and --end-year")
        journal_path = POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL
        cas_root = POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT
        evidence_path = POLICY_ENGINE_ROOT / DEFAULT_LIVE_EXECUTION_EVIDENCE
        attempt_id = derive_live_attempt_id(
            owners.selection,
            attempt_ordinal=args.attempt_ordinal,
        )
        require_new_live_execution_outputs(
            journal_path=journal_path,
            cas_root=cas_root,
            evidence_path=evidence_path,
            attempt_id=attempt_id,
        )
        authority = data_forge_read_api.catalog.CanonicalAcquisitionAuthority.from_provision(
            repo_root=POLICY_ENGINE_ROOT,
            baseline_path=args.catalog_path,
            l5_measurement_registry_path=args.l5_path,
        )
        evidence = execute_live_catalog_acquisition(
            authority=authority,
            entry_id=owners.entry.entry_id,
            attempt_id=attempt_id,
            constraints=LiveCatalogExecutionConstraints(
                country_code=args.country_code,
                start_year=args.start_year,
                end_year=args.end_year,
                page_size=args.page_size,
                max_response_bytes=65_536,
                max_decompressed_bytes=65_536,
                timeout_cap_seconds=15.0,
                heartbeat_cap_seconds=3.0,
            ),
            journal_path=journal_path,
            cas_root=cas_root,
        )
        _write_replace_bytes(
            evidence_path,
            canonical_json_bytes(evidence.model_dump(mode="json")),
        )
        print(
            json.dumps(
                {
                    "status": "live_evidence_written",
                    "attempt_id": evidence.authorization.attempt_id,
                    "entry_id": owners.entry.entry_id,
                    "call_count": evidence.call_count,
                    "variable_count": evidence.variable_count,
                    "page_count": evidence.page_count,
                    "raw_body_sha256": evidence.raw_body_sha256,
                    "baseline_before_sha256": evidence.baseline_before_sha256,
                    "baseline_after_sha256": evidence.baseline_after_sha256,
                    "journal_file_sha256": bytes_sha256(journal_path.read_bytes()),
                    "evidence_file_sha256": bytes_sha256(evidence_path.read_bytes()),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.write_target_owners:
        if (POLICY_ENGINE_ROOT / DEFAULT_ACCEPTANCE_AUTHORITY_OWNER).exists():
            raise RuntimeError("historic_target_owner_shrink_forbidden")
        payloads = owners.payloads()
        receipt_paths = sorted(
            (
                relative
                for relative in payloads
                if relative
                not in {
                    DEFAULT_TARGET_AUTHORITY_REGISTRY,
                    DEFAULT_TARGET_AUTHORITY_PROVISION,
                }
            ),
            key=Path.as_posix,
        )
        for relative in (
            *receipt_paths,
            DEFAULT_TARGET_AUTHORITY_REGISTRY,
            DEFAULT_TARGET_AUTHORITY_PROVISION,
        ):
            _write_replace_bytes(POLICY_ENGINE_ROOT / relative, payloads[relative])
        status = "written"
    else:
        _check_target_owner_payloads(owners)
        status = "ok"

    report: dict[str, Any] = {
        "status": status,
        "attempt_ids": [
            derive_live_attempt_id(owners.selection, attempt_ordinal=ordinal)
            for ordinal in range(1, args.attempt_count + 1)
        ],
        "target_variable": owners.selection.target_variable,
        "request_dataset_id": owners.selection.request_dataset_id,
        "entry_id": owners.entry.entry_id,
        "registry_content_sha256": owners.registry.content_sha256,
        "provision_id": owners.provision.provision_id,
        "payload_file_sha256": {
            relative.as_posix(): bytes_sha256(payload)
            for relative, payload in sorted(
                owners.payloads().items(),
                key=lambda item: item[0].as_posix(),
            )
        },
        "byte_stable_passes": 2,
        "live_network_calls": 0,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


def _recompute_target_owners(
    *,
    catalog_path: Path,
    l5_path: Path,
    census_path: Path,
    substrate_path: Path,
    attempt_count: int,
) -> Any:
    if attempt_count < 1:
        raise RuntimeError("target_owner_attempt_count_invalid")
    selection = derive_live_target_selection(
        catalog_path=catalog_path,
        census_path=census_path,
        substrate_path=substrate_path,
    )
    receipts = tuple(
        derive_target_family_receipt(
            selection,
            catalog_path=catalog_path,
            fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
            attempt_ordinal=ordinal,
        )
        for ordinal in range(1, attempt_count + 1)
    )
    return derive_target_authority_owners(
        selection,
        family_receipt=receipts[0],
        additional_family_receipts=tuple(
            (ordinal, receipts[ordinal - 1]) for ordinal in range(2, attempt_count + 1)
        ),
        baseline_path=catalog_path,
        baseline_owner_ref=DEFAULT_CATALOG_OWNER_REF,
        l5_path=l5_path,
        l5_owner_ref=DEFAULT_L5_OWNER_REF,
        receipt_owner_ref=f"repo://{DEFAULT_TARGET_HARNESS_RECEIPT.as_posix()}",
        country_codes=("UKR",),
    )


def _recompute_resumption_owners(*, catalog_path: Path) -> tuple[Any, Any]:
    r1 = derive_r1_forensic_receipt(
        journal_path=POLICY_ENGINE_ROOT / DEFAULT_RAW_JOURNAL,
        cas_root=POLICY_ENGINE_ROOT / DEFAULT_CAS_ROOT,
        request_dataset_id="GC.BAL.CASH.CD",
    )
    metadata_owner = derive_metadata_probe_owner(
        r1_receipt=r1,
        baseline_path=catalog_path,
        fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
    )
    return r1, metadata_owner


def _resumption_owner_payloads(r1: Any, metadata_owner: Any) -> dict[Path, bytes]:
    return {
        DEFAULT_R1_FORENSIC_RECEIPT: canonical_json_bytes(r1.model_dump(mode="json")),
        DEFAULT_METADATA_PROBE_OWNER: canonical_json_bytes(metadata_owner.model_dump(mode="json")),
    }


def _recompute_d6_route_owners(
    *,
    catalog_path: Path,
    census_path: Path,
    substrate_path: Path,
    r1: Any,
) -> tuple[Any, Any]:
    selection = derive_d6_route_selection(
        catalog_path=catalog_path,
        census_path=census_path,
        substrate_path=substrate_path,
        r1_receipt=r1,
        carrier_liveness_path=POLICY_ENGINE_ROOT / DEFAULT_CARRIER_LIVENESS_UPDATE,
    )
    metadata_owner = derive_d6_metadata_probe_owner(
        selection=selection,
        r1_receipt=r1,
        baseline_path=catalog_path,
        fixture_root=POLICY_ENGINE_ROOT / ".tmp/gy-n13b-no-replay-fixtures",
    )
    return selection, metadata_owner


def _d6_route_owner_payloads(selection: Any, metadata_owner: Any) -> dict[Path, bytes]:
    return {
        DEFAULT_D6_ROUTE_SELECTION: canonical_json_bytes(selection.model_dump(mode="json")),
        DEFAULT_D6_PRIMARY_METADATA_OWNER: canonical_json_bytes(
            metadata_owner.model_dump(mode="json")
        ),
    }


def _check_payloads(payloads: dict[Path, bytes], *, label: str) -> None:
    for relative, expected in payloads.items():
        path = POLICY_ENGINE_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"{label}_artifact_missing:{relative}")
        if path.read_bytes() != expected:
            raise RuntimeError(f"{label}_artifact_drift:{relative}")


def _execute_metadata_probe(
    *,
    owner: Any,
    journal_path: Path,
    cas_root: Path,
) -> None:
    """Spend the single authorized metadata call and terminal-close its evidence."""

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
    from polisyos.fabric.connectors.sources.http_base import (
        _install_raw_http_response_observer,
        _remove_raw_http_response_observer,
    )
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.runtime.quality.acquisition_executor import _LiveHTTPExecutionObserver

    profile = SourceProfileRegistry.get_instance().get(owner.authorization.profile_id)
    if profile is None or str(profile.connector_family) != "worldbank":
        raise RuntimeError("metadata_source_profile_unresolved")
    journal = AppendOnlyEvidenceJournal(journal_path)
    request_ref = journal.append_request(
        attempt_id=owner.authorization.attempt_id,
        request=owner.request,
    )
    observer = _LiveHTTPExecutionObserver(
        journal=journal,
        request_ref=request_ref,
        authorization=owner.authorization,
        artifact_store=FileSystemCAS(cas_root, ownership_enforced=False),
        expected_connector_id=owner.authorization.connector_id,
        expected_url=str(owner.request["endpoint_url"]),
        expected_params={str(key): str(value) for key, value in owner.request["params"].items()},
    )
    connector = WorldBankConnector()
    config = replace(
        resolve_connection_config(profile),
        timeout_seconds=max(1, int(owner.authorization.budget.timeout_seconds)),
        max_retries=1,
        max_connections=1,
    )
    captured_error: BaseException | None = None

    async def execute() -> None:
        nonlocal captured_error
        handle: Any | None = None
        try:
            handle = await connector.connect(config)
            _install_raw_http_response_observer(handle, observer)
            await connector.fetch_indicator_metadata_raw(
                handle,
                owner.authorization.request_variable,
            )
        except BaseException as exc:  # noqa: BLE001 - terminal-closed live boundary
            captured_error = exc
        finally:
            if handle is not None:
                _remove_raw_http_response_observer(handle)
                try:
                    await connector.disconnect(handle)
                except BaseException as exc:  # noqa: BLE001 - terminal-closed boundary
                    if captured_error is None:
                        captured_error = exc

    asyncio.run(execute())
    classification = None
    if observer.raw_evidence_ref is not None and observer.raw_body is not None:
        classification = classify_worldbank_indicator_metadata(
            observer.raw_body,
            indicator_id=owner.authorization.request_variable,
        )
        journal.append_classification(
            attempt_id=owner.authorization.attempt_id,
            evidence_ref=observer.raw_evidence_ref,
            classification=classification.model_dump(mode="json"),
        )
    if captured_error is not None:
        failure_code = _metadata_failure_code(captured_error)
    elif classification is None:
        failure_code = "metadata_raw_response_missing"
    elif classification.disposition == "response_shape_unclassified":
        failure_code = "metadata_response_shape_unclassified"
    else:
        failure_code = "metadata_characterization_complete"
    journal.append_failure_terminal(
        attempt_id=owner.authorization.attempt_id,
        request_ref=request_ref,
        raw_evidence_ref=observer.raw_evidence_ref,
        failure_code=failure_code,
    )


def _metadata_failure_code(exc: BaseException) -> str:
    value = getattr(exc, "code", None) or type(exc).__name__
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return f"metadata_{normalized or 'transport_error'}"[:120]


def _write_replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _check_target_owner_payloads(owners: Any) -> None:
    payloads = owners.payloads()
    for relative, expected in payloads.items():
        if relative in {
            DEFAULT_TARGET_AUTHORITY_REGISTRY,
            DEFAULT_TARGET_AUTHORITY_PROVISION,
        }:
            continue
        path = POLICY_ENGINE_ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"target_owner_artifact_missing:{relative}")
        if path.read_bytes() != expected:
            raise RuntimeError(f"target_owner_artifact_drift:{relative}")
    registry_path = POLICY_ENGINE_ROOT / DEFAULT_TARGET_AUTHORITY_REGISTRY
    provision_path = POLICY_ENGINE_ROOT / DEFAULT_TARGET_AUTHORITY_PROVISION
    try:
        registry = data_forge_read_api.catalog.AcquisitionAuthorityRegistry.model_validate_json(
            registry_path.read_bytes()
        )
        provision = data_forge_read_api.catalog.AcquisitionAuthorityProvision.model_validate_json(
            provision_path.read_bytes()
        )
    except (OSError, ValueError) as exc:
        raise RuntimeError("target_owner_canonical_extension_invalid") from exc
    if (
        registry.baseline_content_sha256 != owners.registry.baseline_content_sha256
        or registry.l5_measurement_registry_sha256 != owners.registry.l5_measurement_registry_sha256
        or provision.baseline_content_sha256 != owners.provision.baseline_content_sha256
        or provision.l5_measurement_registry_content_sha256
        != owners.provision.l5_measurement_registry_content_sha256
    ):
        raise RuntimeError("target_owner_canonical_anchor_drift")
    current_entries = {entry.entry_id: entry for entry in registry.entries}
    if any(current_entries.get(entry.entry_id) != entry for entry in owners.registry.entries):
        raise RuntimeError("target_owner_canonical_entry_missing")
    current_receipts = {
        (receipt.entry_id, receipt.attempt_id): receipt
        for receipt in provision.live_harness_receipts
    }
    if any(
        current_receipts.get((receipt.entry_id, receipt.attempt_id)) != receipt
        for receipt in owners.provision.live_harness_receipts
    ):
        raise RuntimeError("target_owner_canonical_harness_missing")


def require_new_live_execution_outputs(
    *,
    journal_path: Path,
    cas_root: Path,
    evidence_path: Path,
    attempt_id: str,
) -> None:
    """Fence a live attempt from overwriting or appending to prior evidence."""

    collisions: list[str] = []
    if evidence_path.exists():
        collisions.append(evidence_path.as_posix())
    if cas_root.exists() and not cas_root.is_dir():
        collisions.append(cas_root.as_posix())
    if journal_path.exists():
        if not journal_path.is_file():
            collisions.append(journal_path.as_posix())
        else:
            try:
                events = [
                    json.loads(line)
                    for line in journal_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except Exception as exc:
                raise RuntimeError("live_execution_journal_unreadable") from exc
            if any(
                isinstance(event, dict) and event.get("attempt_id") == attempt_id
                for event in events
            ):
                collisions.append(f"{journal_path.as_posix()}#{attempt_id}")
    if collisions:
        raise RuntimeError("live_execution_output_already_exists:" + ",".join(collisions))


if __name__ == "__main__":
    raise SystemExit(main())
