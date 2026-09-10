"""Prepare and run separately authorized, immutable candidate extraction campaigns.

This experimental CLI owns source selection and operator admission. Extraction,
checkpoints, retries and candidate artifacts remain owned by reextraction_campaign;
network calls and safe output remain owned by reextraction_transport.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
from contextlib import AsyncExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .reextraction_campaign import (
    CampaignCallContext,
    CampaignCheckpoint,
    CampaignPlan,
    PhaseChatClient,
    _contains_synthetic,
    _digest,
    campaign_owner_projection,
    run_campaign,
    validate_campaign_output_root,
)
from .reextraction_transport import (
    MODELS,
    PROVIDER_BASE_URL,
    SafeJsonWriter,
    SDKExtractionTransport,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from duckdb import DuckDBPyConnection

    from ._graph_staging import GraphCapacityLimits

Selector = Literal["primary", "secondary"]
_HASH = r"^sha256:[0-9a-f]{64}$"
_PREPARATION_SENTINEL = "NO_CREDENTIAL_USED_BY_CAMPAIGN_PREPARATION"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")


class SourceFrame(_StrictModel):
    """Complete source-relative frame, without a second raw corpus copy."""

    schema_version: Literal["policyos.academic.campaign_source_frame.v1"] = (
        "policyos.academic.campaign_source_frame.v1"
    )
    synthetic: bool
    source_path: str
    source_byte_hash: str = Field(pattern=_HASH)
    source_schema_hash: str = Field(pattern=_HASH)
    selector: Selector
    claim_identity_column: Literal["work_id", "openalex_id"] | None
    input_count: int = Field(gt=0)
    input_digest: str = Field(pattern=_HASH)
    identity_digest: str = Field(pattern=_HASH)
    input_bytes: int = Field(gt=0)
    max_observed_work_bytes: int = Field(gt=0)
    identity_reconciliation: Literal["equal_complete_ordered_identity_streams"] = (
        "equal_complete_ordered_identity_streams"
    )
    order: Literal["pinned_snapshot_physical_row_ordinal"] = "pinned_snapshot_physical_row_ordinal"


class ProviderProfile(_StrictModel):
    """The exact bounded SDK configuration, containing no credential."""

    base_url: str = PROVIDER_BASE_URL
    screening_model: str
    extraction_model: str
    timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    max_completion_tokens: int = Field(default=8192, gt=0, le=16384)
    sdk_automatic_retries: Literal[0] = 0


class CampaignRunPlan(_StrictModel):
    """External run authorization plus immutable source, owner and resource bindings."""

    schema_version: Literal["policyos.academic.campaign_run_plan.v1"] = (
        "policyos.academic.campaign_run_plan.v1"
    )
    full_pass_authorized: bool
    authorization_ref: str | None
    authority_status: Literal["candidate_only"] = "candidate_only"
    synthetic: bool
    frame: SourceFrame
    campaign: CampaignPlan
    provider: ProviderProfile
    cli_source_hash: str = Field(pattern=_HASH)
    output_root: str
    credential_prefix: str = Field(min_length=8)
    max_work_bytes: int = Field(gt=0)
    max_context_bytes: int = Field(gt=0)
    min_free_disk_bytes: int = Field(gt=0)
    source_memory_limit_mb: int = Field(default=128, ge=32, le=1024)
    graph_finalization: Literal["not_started_separate_owner_stage"] = (
        "not_started_separate_owner_stage"
    )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    return "sha256:" + digest.hexdigest()


def _cli_hash() -> str:
    return _file_hash(Path(__file__))


def _output_boundary(output: Path, source: Path, synthetic: bool) -> None:
    output = validate_campaign_output_root(output, synthetic=synthetic)
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("campaign_output_crosses_source_database")


def _disk_admission(output: Path, minimum: int) -> None:
    ancestor = output.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < minimum:
        raise ValueError("campaign_free_disk_below_declared_minimum")


@contextmanager
def _source_connection(path: Path, memory_mb: int) -> Iterator[DuckDBPyConnection]:
    import duckdb

    if Path(str(path) + ".wal").exists():
        raise ValueError("campaign_source_has_unbound_wal")
    with duckdb.connect(
        str(path),
        read_only=True,
        config={
            "threads": "1",
            "memory_limit": f"{memory_mb}MB",
        },
    ) as con:
        # Never spill a shadow corpus next to the held read-only database.
        con.execute("SET temp_directory='' ")
        con.execute("BEGIN TRANSACTION")
        yield con


def _schema(
    con: DuckDBPyConnection, selector: Selector, requested: str | None
) -> tuple[list[Any], str | None]:
    works = con.execute("DESCRIBE ac_works").fetchall()
    types = {row[0]: row[1] for row in works}
    if types.get("id") != "VARCHAR" or types.get("abstract") != "VARCHAR" or "rowid" in types:
        raise ValueError("campaign_source_schema_invalid")
    claims = (
        con.execute("DESCRIBE ac_causal_claims_raw").fetchall() if selector == "secondary" else []
    )
    available = [
        row[0] for row in claims if row[0] in {"work_id", "openalex_id"} and row[1] == "VARCHAR"
    ]
    if selector == "primary":
        if requested is not None:
            raise ValueError("campaign_primary_has_no_claim_identity_column")
        key = None
    elif requested is not None:
        if requested not in available:
            raise ValueError("campaign_claim_identity_column_invalid")
        key = requested
    elif len(available) == 1:
        key = available[0]
    else:
        raise ValueError("campaign_claim_identity_column_ambiguous")
    return [works, claims], key


def _selection(key: str | None) -> str:
    # key is derived from the closed SQL identifier set in _schema.
    return (
        "TRUE"
        if key is None
        else (
            f'EXISTS (SELECT 1 FROM ac_causal_claims_raw c WHERE c."{key}"=w.id)'  # noqa: S608 - schema-validated identifier.
        )
    )


def _row_pages(con: DuckDBPyConnection) -> Iterator[tuple[int, int]]:
    """Order only a fixed page of row ordinals, never a sorted raw corpus."""
    cursor = con.cursor()
    after = -1
    try:
        while True:
            rows = cursor.execute(
                "SELECT rowid FROM ac_works WHERE rowid>? ORDER BY rowid LIMIT 64",
                [after],
            ).fetchall()
            if not rows:
                return
            first, after = rows[0][0], rows[-1][0]
            yield first, after
    finally:
        cursor.close()


def _work_rows(
    con: DuckDBPyConnection, key: str | None, bound: int
) -> Iterator[tuple[int, dict[str, Any], int]]:
    cursor = con.cursor()
    try:
        for first, last in _row_pages(con):
            cursor.execute(
                "SELECT w.rowid,octet_length(encode(to_json(w))),"  # noqa: S608 - closed selector SQL; values bound.
                "CASE WHEN octet_length(encode(to_json(w))) <= ? THEN to_json(w) ELSE NULL END "
                "FROM ac_works w WHERE w.rowid BETWEEN ? AND ? "
                "AND abstract IS NOT NULL AND regexp_matches(abstract,'\\S') "
                f"AND {_selection(key)} ORDER BY w.rowid",
                [bound, first, last],
            )
            while row := cursor.fetchone():
                ordinal, size, raw = row
                if raw is None or size > bound:
                    raise ValueError("campaign_source_record_exceeds_bound")
                work = json.loads(raw)
                if not isinstance(work, dict) or not isinstance(work.get("abstract"), str):
                    raise ValueError("campaign_source_record_invalid")
                canonical_size = len(
                    json.dumps(
                        work,
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode()
                )
                if canonical_size > bound:
                    raise ValueError("campaign_source_record_exceeds_bound")
                yield ordinal, work, canonical_size
    finally:
        cursor.close()


def _independent_ids(
    con: DuckDBPyConnection, key: str | None, bound: int
) -> Iterator[tuple[int, str]]:
    cursor = con.cursor()
    membership = (
        "TRUE"
        if key is None
        else (
            f'w.id IN (SELECT DISTINCT "{key}" FROM ac_causal_claims_raw)'  # noqa: S608 - schema-validated identifier.
        )
    )
    try:
        for first, last in _row_pages(con):
            cursor.execute(
                "SELECT w.rowid,w.id,octet_length(encode(abstract)),"  # noqa: S608 - closed selector SQL; values bound.
                "CASE WHEN octet_length(encode(abstract)) <= ? THEN abstract ELSE NULL END,"
                f"{membership} FROM ac_works w WHERE w.rowid BETWEEN ? AND ? ORDER BY w.rowid",
                [bound, first, last],
            )
            while row := cursor.fetchone():
                ordinal, identity, size, abstract, member = row
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError("campaign_source_identity_ambiguous")
                if size is not None and size > bound:
                    raise ValueError("campaign_source_record_exceeds_bound")
                if abstract is not None and abstract.strip() and member:
                    yield ordinal, identity
    finally:
        cursor.close()


def _scan_frame(
    con: DuckDBPyConnection,
    source: Path,
    selector: Selector,
    requested_key: str | None,
    max_work_bytes: int,
) -> SourceFrame:
    schema, key = _schema(con, selector, requested_key)
    ambiguous = con.execute(
        "SELECT id FROM ac_works GROUP BY id HAVING id IS NULL OR length(trim(id))=0 "
        "OR count(*)<>1 LIMIT 1",
    ).fetchone()
    if ambiguous is not None:
        raise ValueError("campaign_source_identity_ambiguous")
    selected_digest = hashlib.sha256()
    identity_digest = hashlib.sha256()
    independent = _independent_ids(con, key, max_work_bytes)
    count = total = maximum = 0
    source_synthetic = False
    try:
        for ordinal, work, size in _work_rows(con, key, max_work_bytes):
            identity = ordinal, work["id"]
            if next(independent, None) != identity:
                raise ValueError("campaign_source_identity_reconciliation_failed")
            selected_digest.update((_digest(work) + "\n").encode())
            identity_digest.update((_digest(identity) + "\n").encode())
            source_synthetic = source_synthetic or _contains_synthetic(work)
            count += 1
            total += size
            maximum = max(maximum, size)
        if next(independent, None) is not None:
            raise ValueError("campaign_source_identity_reconciliation_failed")
    finally:
        independent.close()
    if count == 0:
        raise ValueError("campaign_source_frame_empty")
    return SourceFrame(
        synthetic=source_synthetic,
        source_path=str(source),
        source_byte_hash=_file_hash(source),
        source_schema_hash=_digest(schema),
        selector=selector,
        claim_identity_column=key,
        input_count=count,
        input_digest="sha256:" + selected_digest.hexdigest(),
        identity_digest="sha256:" + identity_digest.hexdigest(),
        input_bytes=total,
        max_observed_work_bytes=maximum,
    )


def _validate_provider(profile: ProviderProfile) -> None:
    if profile.base_url != PROVIDER_BASE_URL:
        raise ValueError("campaign_provider_endpoint_mismatch")
    if profile.screening_model not in MODELS or profile.extraction_model not in MODELS:
        raise ValueError("campaign_provider_model_mismatch")


def prepare_plan(
    *,
    source: Path,
    output_root: Path,
    selector: Selector,
    synthetic: bool,
    campaign_id: str,
    screening_model: str,
    extraction_model: str,
    concurrency: int,
    max_attempts: int,
    max_attempts_per_phase: int,
    credential_prefix: str,
    claim_identity_column: str | None = None,
    max_work_bytes: int = 1_048_576,
    max_context_bytes: int = 2_097_152,
    max_artifact_bytes: int = 8_388_608,
    min_free_disk_bytes: int = 1_073_741_824,
    source_memory_limit_mb: int = 128,
    timeout_seconds: float = 120.0,
    max_completion_tokens: int = 8192,
    retry_unknown: bool = False,
    retry_delay_seconds: float = 0.0,
) -> CampaignRunPlan:
    """Recompute a complete frame and emit an unauthorized plan without credentials."""
    if selector not in {"primary", "secondary"}:
        raise ValueError("campaign_source_selector_invalid")
    source = source.resolve()
    _output_boundary(output_root, source, synthetic)
    _disk_admission(output_root, min_free_disk_bytes)
    provider = ProviderProfile(
        screening_model=screening_model,
        extraction_model=extraction_model,
        timeout_seconds=timeout_seconds,
        max_completion_tokens=max_completion_tokens,
    )
    _validate_provider(provider)
    before = _file_hash(source)
    with _source_connection(source, source_memory_limit_mb) as con:
        frame = _scan_frame(con, source, selector, claim_identity_column, max_work_bytes)
    if frame.synthetic and not synthetic:
        raise ValueError("campaign_synthetic_source_requires_marked_plan")
    if before != frame.source_byte_hash:
        raise ValueError("campaign_source_changed_during_read")
    plan = CampaignPlan(
        campaign_id=campaign_id,
        synthetic=synthetic,
        input_count=frame.input_count,
        input_digest=frame.input_digest,
        provider_profile_hash=_digest(provider.model_dump()),
        screening_model=screening_model,
        extraction_model=extraction_model,
        concurrency=concurrency,
        queue_capacity=2 * concurrency,
        max_attempts=max_attempts,
        max_attempts_per_phase=max_attempts_per_phase,
        retry_unknown=retry_unknown,
        retry_delay_seconds=retry_delay_seconds,
        max_artifact_bytes=max_artifact_bytes,
        owner_source_hash=campaign_owner_projection()["content_hash"],
        execution_epoch="v2",
        fatal_policy="stop_systemic",
    )
    return CampaignRunPlan(
        full_pass_authorized=False,
        authorization_ref=None,
        synthetic=synthetic,
        frame=frame,
        campaign=plan,
        provider=provider,
        cli_source_hash=_cli_hash(),
        output_root=str(output_root.resolve()),
        credential_prefix=credential_prefix,
        max_work_bytes=max_work_bytes,
        max_context_bytes=max_context_bytes,
        min_free_disk_bytes=min_free_disk_bytes,
        source_memory_limit_mb=source_memory_limit_mb,
    )


def _load_credential(prefix: str, environment: Mapping[str, str], dotenv_path: Path | None) -> str:
    values: list[object] = list(environment.values())
    if dotenv_path is not None:
        from dotenv import dotenv_values

        values.extend(dotenv_values(dotenv_path, interpolate=False).values())
    matches = {
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip().startswith(prefix)
    }
    if not matches:
        raise ValueError("campaign_credential_absent")
    if len(matches) != 1:
        raise ValueError("campaign_credential_ambiguous")
    return next(iter(matches))


class _LimitedClient:
    def __init__(self, bound: PhaseChatClient, maximum: int) -> None:
        self.bound = bound
        self.maximum = maximum
        self.synthetic = bound.synthetic

    async def chat(
        self, *, model: str, temperature: float, prompt: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if len(prompt.encode()) > self.maximum:
            raise ValueError("campaign_context_exceeds_bound")
        return await self.bound.chat(model=model, temperature=temperature, prompt=prompt)


def _admit_plan(plan: CampaignRunPlan) -> CampaignRunPlan:
    """Recompute the single live execution/recovery intake before side effects."""
    if (
        plan.full_pass_authorized is not True
        or not plan.authorization_ref
        or not plan.authorization_ref.strip()
    ):
        raise ValueError("campaign_full_pass_not_authorized")
    # Re-enter strict intake even for an object created with model_copy in a caller.
    plan = CampaignRunPlan.model_validate_json(plan.model_dump_json())
    _validate_provider(plan.provider)
    if plan.cli_source_hash != _cli_hash():
        raise ValueError("campaign_cli_source_mismatch")
    if plan.campaign.owner_source_hash != campaign_owner_projection()["content_hash"]:
        raise ValueError("campaign_owner_source_mismatch")
    if (
        plan.campaign.execution_epoch != "v2"
        or plan.campaign.fatal_policy != "stop_systemic"
        or plan.synthetic is not plan.campaign.synthetic
        or (plan.frame.synthetic and not plan.synthetic)
        or plan.campaign.input_count != plan.frame.input_count
        or plan.campaign.input_digest != plan.frame.input_digest
        or plan.campaign.provider_profile_hash != _digest(plan.provider.model_dump())
        or plan.campaign.screening_model != plan.provider.screening_model
        or plan.campaign.extraction_model != plan.provider.extraction_model
    ):
        raise ValueError("campaign_run_plan_binding_mismatch")
    return plan


def _invocation_plan(plan: CampaignRunPlan, writer: SafeJsonWriter, *, create: bool) -> None:
    path = Path(plan.output_root) / "invocation_plan.json"
    if path.exists():
        with path.open("rb") as stream:
            saved = stream.read(1_048_577)
        if len(saved) > 1_048_576 or saved.decode() != writer.encode(plan.model_dump(mode="json")):
            raise ValueError("campaign_invocation_plan_mismatch")
    elif create:
        writer(path, plan.model_dump(mode="json"))
    else:
        raise ValueError("campaign_invocation_plan_missing")


def recover_plan(
    plan: CampaignRunPlan,
    stop_ref: dict[str, str],
    *,
    acknowledgment_ref: str,
    reason: str,
    dotenv_path: Path | None = None,
) -> dict[str, str]:
    """Delegate explicit append-only operator recovery to the same campaign owner."""
    plan = _admit_plan(plan)
    source = Path(plan.frame.source_path).resolve()
    output = Path(plan.output_root).resolve()
    _output_boundary(output, source, plan.synthetic)
    credential = _load_credential(plan.credential_prefix, os.environ, dotenv_path)
    writer = SafeJsonWriter(credential)
    writer.check_payload(plan.model_dump(mode="json"))
    _invocation_plan(plan, writer, create=False)
    with CampaignCheckpoint(output, plan.campaign, writer) as checkpoint:
        checkpoint.validate_complete_frame()
        return checkpoint.recover_fatal_stop(
            stop_ref,
            acknowledgment_ref=acknowledgment_ref,
            reason=reason,
        )


def finalize_plan(
    plan: CampaignRunPlan, *, capacity_limits: GraphCapacityLimits | None = None
) -> dict[str, Any]:
    """Build and resolve a candidate graph from the exact historical invocation.

    This operation neither resumes execution nor requires current execution-source
    identity. The graph owner separately binds its current implementation while
    the checkpoint owner verifies the original campaign's complete evidence.
    """
    plan = CampaignRunPlan.model_validate_json(plan.model_dump_json())
    output = Path(plan.output_root).resolve()
    _output_boundary(output, Path(plan.frame.source_path).resolve(), plan.synthetic)
    writer = SafeJsonWriter(_PREPARATION_SENTINEL)
    _invocation_plan(plan, writer, create=False)
    # No graph owner or derivative output is reached without the exact input envelope.
    from .pipeline import (
        finalize_extraction_campaign_graph,
        resolve_extraction_campaign_graph,
    )

    ref = finalize_extraction_campaign_graph(
        plan.campaign, output, capacity_limits=capacity_limits, safe_write_json=writer
    )
    packet = resolve_extraction_campaign_graph(plan.campaign, output, ref)
    return {
        "synthetic": packet["synthetic"],
        "authority_status": "candidate_only",
        "graph_finalization": packet["artifact_kind"],
        "input_mode": packet["input_mode"],
        "graph_ref": {"path": ref.path, "sha256": ref.sha256},
    }


async def run_plan(plan: CampaignRunPlan, *, dotenv_path: Path | None = None) -> dict[str, Any]:
    """Verify source and authorization, then delegate durable execution and resume."""
    plan = _admit_plan(plan)
    source = Path(plan.frame.source_path).resolve()
    output = Path(plan.output_root).resolve()
    _output_boundary(output, source, plan.synthetic)
    _disk_admission(output, plan.min_free_disk_bytes)
    if _file_hash(source) != plan.frame.source_byte_hash:
        raise ValueError("campaign_source_snapshot_mismatch")
    with _source_connection(source, plan.source_memory_limit_mb) as con:
        current = _scan_frame(
            con, source, plan.frame.selector, plan.frame.claim_identity_column, plan.max_work_bytes
        )
        if current != plan.frame:
            raise ValueError("campaign_source_frame_mismatch")
        credential = _load_credential(plan.credential_prefix, os.environ, dotenv_path)
        writer = SafeJsonWriter(credential)
        writer.check_payload(plan.model_dump(mode="json"))
        _invocation_plan(plan, writer, create=True)
        async with AsyncExitStack() as stack:
            transports = {}
            for model in sorted({plan.provider.screening_model, plan.provider.extraction_model}):
                transports[model] = await stack.enter_async_context(
                    SDKExtractionTransport(
                        api_key=credential,
                        base_url=plan.provider.base_url,
                        model_id=model,
                        output_root=output,
                        timeout_seconds=plan.provider.timeout_seconds,
                        max_completion_tokens=plan.provider.max_completion_tokens,
                    )
                )

            def factory(context: CampaignCallContext) -> _LimitedClient:
                writer.check_payload(context.__dict__)
                if len(writer.encode(context.__dict__).encode()) > plan.max_context_bytes:
                    raise ValueError("campaign_context_exceeds_bound")
                return _LimitedClient(
                    transports[context.model_id].bind(context), plan.max_context_bytes
                )

            report = await run_campaign(
                plan.campaign,
                works=(
                    work
                    for _, work, _ in _work_rows(
                        con,
                        current.claim_identity_column,
                        plan.max_work_bytes,
                    )
                ),
                output_root=output,
                client_factory=factory,
                safe_write_json=writer,
            )
            writer.check_payload(report)
            return report


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.exit(2, '{"status":"blocked","error_kind":"campaign_cli_arguments_invalid"}\n')


def main(argv: list[str] | None = None) -> int:
    """Run the experimental operator CLI, printing only secret-safe output."""
    parser = _SafeArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Read-only frame preparation; no provider calls")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--plan-output", type=Path, required=True)
    prepare.add_argument("--selector", choices=["primary", "secondary"], default="primary")
    prepare.add_argument("--claim-identity-column", choices=["work_id", "openalex_id"])
    prepare.add_argument("--campaign-id", required=True)
    prepare.add_argument("--screening-model", choices=sorted(MODELS), required=True)
    prepare.add_argument("--extraction-model", choices=sorted(MODELS), required=True)
    prepare.add_argument("--credential-prefix", required=True)
    prepare.add_argument("--synthetic", action="store_true")
    for name, default in (
        ("concurrency", 32),
        ("max-attempts-per-phase", 2),
        ("max-work-bytes", 1048576),
        ("max-context-bytes", 2097152),
        ("max-artifact-bytes", 8388608),
        ("min-free-disk-bytes", 1073741824),
        ("source-memory-limit-mb", 128),
        ("max-completion-tokens", 8192),
    ):
        prepare.add_argument("--" + name, type=int, default=default)
    prepare.add_argument("--max-attempts", type=int, required=True)
    prepare.add_argument("--timeout-seconds", type=float, default=120.0)
    prepare.add_argument("--retry-delay-seconds", type=float, default=0.0)
    prepare.add_argument("--retry-unknown", action="store_true")
    run = commands.add_parser("run", help="Run only a separately authorized plan")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--dotenv", type=Path)
    recover = commands.add_parser(
        "recover", help="Append an exact-stop operator recovery; no calls"
    )
    recover.add_argument("--plan", type=Path, required=True)
    recover.add_argument("--stop-path", required=True)
    recover.add_argument("--stop-sha256", required=True)
    recover.add_argument("--acknowledgment-ref", required=True)
    recover.add_argument("--reason", required=True)
    recover.add_argument("--dotenv", type=Path)
    finalize = commands.add_parser(
        "finalize", help="Build a candidate graph from complete historical outputs; no calls"
    )
    finalize.add_argument("--plan", type=Path, required=True)
    finalize.add_argument("--capacity-limits", type=Path)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        if command == "prepare":
            path = args.pop("plan_output").resolve()
            _output_boundary(path, args["source"].resolve(), args["synthetic"])
            plan = prepare_plan(**args)
            writer = SafeJsonWriter(_PREPARATION_SENTINEL)
            writer(path, plan.model_dump(mode="json"))
            result = {
                "status": "prepared",
                "full_pass_authorized": False,
                "synthetic": plan.synthetic,
                "authority_status": "candidate_only",
                "input_count": plan.frame.input_count,
                "input_digest": plan.frame.input_digest,
            }
        else:
            with args["plan"].open("rb") as stream:
                raw = stream.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ValueError("campaign_plan_exceeds_bound")
            plan = CampaignRunPlan.model_validate_json(raw)
            if command == "finalize":
                limits = None
                if args["capacity_limits"] is not None:
                    from ._graph_staging import GraphCapacityLimits

                    with args["capacity_limits"].open("rb") as stream:
                        limits_raw = stream.read(65_537)
                    if len(limits_raw) > 65_536:
                        raise ValueError("campaign_graph_limits_exceed_bound")
                    limits = GraphCapacityLimits(**json.loads(limits_raw))
                result = finalize_plan(plan, capacity_limits=limits)
            elif command == "recover":
                ref = recover_plan(
                    plan,
                    {"path": args["stop_path"], "sha256": args["stop_sha256"]},
                    acknowledgment_ref=args["acknowledgment_ref"],
                    reason=args["reason"],
                    dotenv_path=args["dotenv"],
                )
                result = {
                    "synthetic": plan.synthetic,
                    "authority_status": "candidate_only",
                    "recovery_ref": ref,
                }
            else:
                result = asyncio.run(run_plan(plan, dotenv_path=args["dotenv"]))
        sys.stdout.write(SafeJsonWriter(_PREPARATION_SENTINEL).encode(result))
        return 0
    except Exception:
        # Never print provider bodies, malformed input, credential names or values.
        sys.stderr.write('{"status":"blocked","error_kind":"campaign_cli_refused"}\n')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
