"""Resolve a run-bound S2 case record from one strict terminal Core trace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core import artifacts, canon
from polisyos.pdc import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    DesignRecordV0,
    RunBoundDesignRecordBinding,
    SearchLedger,
)
from polisyos.runtime.http.services.adapters.core_run import (
    TerminalCoreRunSource,
    load_terminal_core_run_source,
)
from polisyos.runtime.http.services.run_paper_contracts import RunPaperSourceError

if TYPE_CHECKING:
    from pathlib import Path

_BINDING_KIND = "policyos.pdc.run_bound_design_record_binding"
_BINDING_SCHEMA_VERSION = "policyos.pdc.run_bound_design_record_binding.v1"
_DESIGN_RECORD_KIND = "policyos.layer2_s2.design_record_v0"
_SEARCH_LEDGER_KIND = "policyos.layer2_s2.search_ledger"
_JSON_MEDIA_TYPE = "application/json"
_PDC_PRODUCER = artifacts.ProducerInfo(
    component="polisyos.pdc.layer2_design_search",
    version="policyos.layer2.s2.design_search.v1",
)


@dataclass(frozen=True)
class ResolvedRunBoundDesignRecord:
    """One fully verified terminal manifest, binding, record, and ledger chain."""

    terminal_source: TerminalCoreRunSource
    binding_ref: artifacts.ArtifactRef
    binding: RunBoundDesignRecordBinding
    design_record: DesignRecordV0
    search_ledger: SearchLedger


class RunBoundDesignRecordResolver:
    """Resolve an S2 case strictly through the terminal trace's manifest outputs."""

    def __init__(self, store: artifacts.ArtifactStore, core_runs_root: Path) -> None:
        self._store = store
        self._core_runs_root = core_runs_root

    def resolve(self, run_id: str) -> ResolvedRunBoundDesignRecord:
        """Return the one content- and owner-bound S2 record for ``run_id``."""

        try:
            source = load_terminal_core_run_source(
                store=self._store,
                core_runs_root=self._core_runs_root,
                run_id=run_id,
            )
            return self._resolve_source(source)
        except RunPaperSourceError:
            raise
        except Exception as exc:
            raise RunPaperSourceError(str(exc)) from exc

    def _resolve_source(self, source: TerminalCoreRunSource) -> ResolvedRunBoundDesignRecord:
        binding_refs = [
            ref for ref in source.manifest.outputs if ref.kind == _BINDING_KIND
        ]
        if len(binding_refs) != 1:
            raise RunPaperSourceError(
                "terminal run manifest must name exactly one run-bound DesignRecord binding"
            )
        binding_ref = binding_refs[0]
        binding_sidecar = self._verify_role(
            binding_ref,
            kind=_BINDING_KIND,
            schema_name=_BINDING_KIND,
            schema_version=_BINDING_SCHEMA_VERSION,
            producer=_PDC_PRODUCER,
            role="binding",
        )
        binding = RunBoundDesignRecordBinding.model_validate(
            self._load_payload(binding_ref, role="binding")
        )
        if binding_sidecar.producer != binding.producer or binding.producer != _PDC_PRODUCER:
            raise RunPaperSourceError("binding producer provenance mismatch")
        if (
            binding.run_id != source.run_id
            or binding.tenant_id != source.tenant_id
            or binding.cell_id != source.cell_id
        ):
            raise RunPaperSourceError("binding owner identity does not match terminal trace")
        if source.tenant_id is None:
            raise RunPaperSourceError("terminal S2 run is not tenant-bound")
        self._require_exact_manifest_output(
            source,
            binding.design_record_ref,
            role="DesignRecord",
        )
        self._require_exact_manifest_output(
            source,
            binding.search_ledger_ref,
            role="SearchLedger",
        )
        self._verify_role(
            binding.design_record_ref,
            kind=_DESIGN_RECORD_KIND,
            schema_name=binding.design_record_schema_name,
            schema_version=binding.design_record_schema_version,
            producer=binding.producer,
            role="DesignRecord",
        )
        design_record = DesignRecordV0.model_validate(
            self._load_payload(binding.design_record_ref, role="DesignRecord")
        )
        self._verify_role(
            binding.search_ledger_ref,
            kind=_SEARCH_LEDGER_KIND,
            schema_name=_SEARCH_LEDGER_KIND,
            schema_version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
            producer=binding.producer,
            role="SearchLedger",
        )
        search_ledger = SearchLedger.model_validate(
            self._load_payload(binding.search_ledger_ref, role="SearchLedger")
        )
        if design_record.record_id != binding.design_record_record_id:
            raise RunPaperSourceError("DesignRecord record identity does not match binding")
        if design_record.schema_version != binding.design_record_schema_version:
            raise RunPaperSourceError("DesignRecord schema identity does not match binding")
        if search_ledger.case_id != binding.case_id:
            raise RunPaperSourceError("SearchLedger case identity does not match binding")
        if search_ledger.ledger_id != binding.search_ledger_id:
            raise RunPaperSourceError("SearchLedger identity does not match binding")
        return ResolvedRunBoundDesignRecord(
            terminal_source=source,
            binding_ref=binding_ref,
            binding=binding,
            design_record=design_record,
            search_ledger=search_ledger,
        )

    def _verify_role(
        self,
        artifact_ref: artifacts.ArtifactRef,
        *,
        kind: str,
        schema_name: str,
        schema_version: str,
        producer: artifacts.ProducerInfo,
        role: str,
    ) -> artifacts.ArtifactManifest:
        if artifact_ref.kind != kind or artifact_ref.media_type != _JSON_MEDIA_TYPE:
            raise RunPaperSourceError(f"{role} reference metadata mismatch")
        verification = self._store.verify(artifact_ref.artifact_id)
        if not verification.ok:
            raise RunPaperSourceError(f"{role} failed CAS verification")
        sidecar = self._store.get_manifest(artifact_ref.artifact_id)
        if sidecar.kind != kind or sidecar.media_type != _JSON_MEDIA_TYPE:
            raise RunPaperSourceError(f"{role} sidecar identity mismatch")
        if (
            sidecar.artifact_schema is None
            or sidecar.artifact_schema.name != schema_name
            or sidecar.artifact_schema.version != schema_version
        ):
            raise RunPaperSourceError(f"{role} sidecar schema mismatch")
        if sidecar.producer != producer:
            raise RunPaperSourceError(f"{role} sidecar producer mismatch")
        return sidecar

    def _load_payload(self, artifact_ref: artifacts.ArtifactRef, *, role: str) -> object:
        try:
            payload_bytes = self._store.get_bytes(artifact_ref.artifact_id)
            if canon.content_hash(payload_bytes, prefix=True) != str(artifact_ref.artifact_id):
                raise ValueError("resolved bytes do not match their content address")
            return canon.from_canonical_bytes(payload_bytes)
        except Exception as exc:
            raise RunPaperSourceError(f"{role} bytes are invalid") from exc

    @staticmethod
    def _require_exact_manifest_output(
        source: TerminalCoreRunSource,
        artifact_ref: artifacts.ArtifactRef,
        *,
        role: str,
    ) -> None:
        if source.manifest.outputs.count(artifact_ref) != 1:
            raise RunPaperSourceError(
                f"terminal run manifest does not name exactly one bound {role} output"
            )


__all__ = ["ResolvedRunBoundDesignRecord", "RunBoundDesignRecordResolver"]
