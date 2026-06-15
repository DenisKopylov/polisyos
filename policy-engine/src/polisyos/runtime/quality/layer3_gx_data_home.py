"""Persisted Layer 3 GX pinned-route demand data home.

The data home stores demand-side request, concept, scope, and demand-pull rows
before runtime literals are removed. It may describe what the pinned route asks
for, but it cannot assert that corpus rows, source contracts, or measurements
exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable

LAYER3_GX_DATA_HOME_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gx_data_home.v1"
LAYER3_GX_DATA_HOME_RULE_VERSION = "policyos.layer3.gx.data_home.v1"
LAYER3_GX_CONCEPT_ALIAS_GRAPH_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gx_concept_alias_graph.v1"
)
LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION = "policyos.layer3.gx.concept_alias_graph.v1"
POLICY_DESIGN_CASE_DIR = Path("architecture/policy_design_case")
ACADEMIC_SKG_DB_PATH = (
    Path("production_data/policyos_academic_runtime_slim_20260411T112032Z")
    / "academic/graph/scholar_knowledge.duckdb"
)
PINNED_REQUEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_pinned_request.json"
CONCEPT_ALIAS_SEED_ROWS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_concept_alias_seed_rows.json"
CONCEPT_ALIAS_GRAPH_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_concept_alias_graph.json"
SCOPE_SEED_ROWS_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_scope_seed_rows.json"
DEMAND_PULL_REQUEST_PATH = POLICY_DESIGN_CASE_DIR / "layer3_gx_demand_pull_request.json"
TASK_0A_ARTIFACT_PATHS: tuple[Path, ...] = (
    PINNED_REQUEST_PATH,
    CONCEPT_ALIAS_SEED_ROWS_PATH,
    SCOPE_SEED_ROWS_PATH,
    DEMAND_PULL_REQUEST_PATH,
)
TASK_7_ARTIFACT_PATHS: tuple[Path, ...] = (CONCEPT_ALIAS_GRAPH_PATH,)
L1_DCAT_REF = (
    "duckdb://production_data/datasets_full_phase3full_20260327_183054/"
    "dataset_catalog.duckdb#ds_metric_bindings"
)
REQUIRED_SCOPE_KEYS: frozenset[str] = frozenset(
    {
        "entity_type",
        "population",
        "geography",
        "modality",
        "source_family_alias",
        "validity_limit",
    }
)
REQUIRED_CONSUMER_PATH: frozenset[str] = frozenset({"G1", "G2", "G4", "G5"})


class _GXDataHomeModel(BaseModel):
    """Strict base model for GX data-home contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Layer3GXRequestedConstruct(_GXDataHomeModel):
    """One requested construct row from the pinned external request."""

    construct_ref: str = Field(min_length=1)
    role: str = Field(min_length=1)
    g1_request_shape: str = Field(min_length=1)
    g2_variable_ref: str = Field(min_length=1)
    broad_query_terms: tuple[str, ...] = Field(default=())


class Layer3GXPinnedRequest(_GXDataHomeModel):
    """Persisted pinned-route request seed."""

    schema_version: str = "policyos.policy_design_case.layer3_gx_pinned_request.v1"
    rule_version: str = LAYER3_GX_DATA_HOME_RULE_VERSION
    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    request_ref: str = Field(min_length=1)
    producer_ref: str = Field(min_length=1)
    producer_type: Literal["external_request"] = "external_request"
    producer_root_refs: tuple[str, ...] = Field(default=())
    authority_purpose: str = Field(min_length=1)
    expected_consumer_path: tuple[str, ...] = Field(default=())
    requested_constructs: tuple[Layer3GXRequestedConstruct, ...] = Field(default=())
    g1_requests: tuple[dict[str, Any], ...] = Field(default=())
    g2_request: dict[str, Any] = Field(default_factory=dict)
    g4_promotion_requests: tuple[dict[str, Any], ...] = Field(default=())
    may_not_use_for: tuple[str, ...] = Field(default=())


class Layer3GXConceptAliasRow(_GXDataHomeModel):
    """Unverified concept alias seed row."""

    row_id: str = Field(min_length=1)
    concept_ref: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(default=())
    resolution_status: Literal["unverified"] = "unverified"
    asserts_corpus_supply: bool = False
    corpus_row_refs: tuple[str, ...] = Field(default=())


class Layer3GXConceptAliasSeedRows(_GXDataHomeModel):
    """Persisted alias seed rows for the pinned constructs."""

    schema_version: str = "policyos.policy_design_case.layer3_gx_concept_alias_seed_rows.v1"
    rule_version: str = LAYER3_GX_DATA_HOME_RULE_VERSION
    producer_ref: str = Field(min_length=1)
    producer_type: Literal["external_request"] = "external_request"
    alias_rows: tuple[Layer3GXConceptAliasRow, ...] = Field(default=())


class Layer3GXConceptAliasGraphRow(_GXDataHomeModel):
    """Data-owned concept alias graph row for query expansion."""

    row_id: str = Field(min_length=1)
    concept_ref: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(default=())
    metric_ids: tuple[str, ...] = Field(default=())
    variable_names: tuple[str, ...] = Field(default=())
    source_layer_refs: tuple[str, ...] = Field(default=())
    jurisdiction_constraints: tuple[str, ...] = Field(default=())
    validity_limits: tuple[str, ...] = Field(default=())
    producer_owner: str = Field(min_length=1)
    producer_type: Literal["external_request", "measurement", "derivation"]
    verification_status: Literal["unverified", "measured", "invalid"] = "unverified"
    resolved_corpus_row_refs: tuple[str, ...] = Field(default=())
    rule_version: str = LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION


class Layer3GXConceptAliasGraph(_GXDataHomeModel):
    """Loaded concept alias graph and degradation status."""

    schema_version: str = LAYER3_GX_CONCEPT_ALIAS_GRAPH_SCHEMA_VERSION
    rule_version: str = LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION
    status: Literal["ready", "missing", "typed_blocker"] = "ready"
    producer_ref: str = Field(min_length=1)
    producer_type: Literal["external_request", "measurement", "derivation"]
    graph_rows: tuple[Layer3GXConceptAliasGraphRow, ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GXScopeSeedRow(_GXDataHomeModel):
    """One demand-side scope seed row."""

    scope_key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    authority_role: Literal["demand_scope"] = "demand_scope"
    validity_status: Literal["unverified"] = "unverified"


class Layer3GXScopeSeedRows(_GXDataHomeModel):
    """Persisted scope seed rows for the pinned request."""

    schema_version: str = "policyos.policy_design_case.layer3_gx_scope_seed_rows.v1"
    rule_version: str = LAYER3_GX_DATA_HOME_RULE_VERSION
    producer_ref: str = Field(min_length=1)
    producer_type: Literal["external_request"] = "external_request"
    scope_rows: tuple[Layer3GXScopeSeedRow, ...] = Field(default=())


class Layer3GXDemandPullRequest(_GXDataHomeModel):
    """Persisted demand-pull request for G5/G6/G7 consumers."""

    schema_version: str = "policyos.policy_design_case.layer3_gx_demand_pull_request.v1"
    rule_version: str = LAYER3_GX_DATA_HOME_RULE_VERSION
    request_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    producer_ref: str = Field(min_length=1)
    producer_type: Literal["external_request"] = "external_request"
    source: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    accountable_principal_ref: str | None = None
    request_source_ref: str | None = None
    replay_key: str = Field(min_length=1)
    consumer_path: tuple[str, ...] = Field(default=())
    demand_refs: tuple[str, ...] = Field(default=())
    attempted_grounding_path_refs: tuple[str, ...] = Field(default=())


class Layer3GXDataHome(_GXDataHomeModel):
    """Loaded and validated GX data-home view."""

    schema_version: str = LAYER3_GX_DATA_HOME_SCHEMA_VERSION
    rule_version: str = LAYER3_GX_DATA_HOME_RULE_VERSION
    status: Literal["ready", "typed_blocker"]
    pinned_request: Layer3GXPinnedRequest | None = None
    concept_alias_rows: tuple[Layer3GXConceptAliasRow, ...] = Field(default=())
    scope_rows: tuple[Layer3GXScopeSeedRow, ...] = Field(default=())
    demand_pull_request: Layer3GXDemandPullRequest | None = None
    expected_consumer_path: tuple[str, ...] = Field(default=())
    producer_records: tuple[dict[str, Any], ...] = Field(default=())
    issue_codes: tuple[str, ...] = Field(default=())


class Layer3GXDataHomeBlockedError(RuntimeError):
    """Raised when a consumer requires the GX data home but it is blocked."""

    def __init__(self, data_home: Layer3GXDataHome) -> None:
        super().__init__(
            "Layer 3 GX data home is typed_blocker: " + ", ".join(data_home.issue_codes)
        )
        self.data_home = data_home


def build_layer3_gx_data_home_artifacts(
    repo_root: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Read Task 0A artifacts and derive the Task 7 concept alias graph."""

    root = _repo_root() if repo_root is None else Path(repo_root)
    return {
        "layer3_gx_pinned_request": _read_data_home_payload(root, PINNED_REQUEST_PATH),
        "layer3_gx_concept_alias_seed_rows": _read_data_home_payload(
            root,
            CONCEPT_ALIAS_SEED_ROWS_PATH,
        ),
        "layer3_gx_concept_alias_graph": build_layer3_gx_concept_alias_graph_artifact(
            root,
        ),
        "layer3_gx_scope_seed_rows": _read_data_home_payload(root, SCOPE_SEED_ROWS_PATH),
        "layer3_gx_demand_pull_request": _read_data_home_payload(
            root,
            DEMAND_PULL_REQUEST_PATH,
        ),
    }


def read_layer3_gx_pinned_case_id(repo_root: Path | None = None) -> str:
    """Read the pinned case id from the persisted GX request artifact."""

    root = _repo_root() if repo_root is None else Path(repo_root)
    payload = _read_data_home_payload(root, PINNED_REQUEST_PATH)
    return _required_text(payload, "case_id", PINNED_REQUEST_PATH)


def read_layer3_gx_construct_bundle_id(repo_root: Path | None = None) -> str:
    """Read the construct bundle id from the persisted GX G1 request rows."""

    root = _repo_root() if repo_root is None else Path(repo_root)
    payload = _read_data_home_payload(root, PINNED_REQUEST_PATH)
    requests = payload.get("g1_requests")
    if not isinstance(requests, (list, tuple)) or not requests:
        raise ValueError(f"{PINNED_REQUEST_PATH.as_posix()} has no g1_requests rows")
    first = requests[0]
    if not isinstance(first, dict):
        raise ValueError(f"{PINNED_REQUEST_PATH.as_posix()} has invalid g1_requests rows")
    return _required_text(first, "construct_bundle_id", PINNED_REQUEST_PATH)


def load_layer3_gx_data_home(repo_root: Path) -> Layer3GXDataHome:
    """Load and validate the persisted Task 0A data home."""

    root = Path(repo_root)
    issues: list[str] = []
    pinned = _load_model(root / PINNED_REQUEST_PATH, Layer3GXPinnedRequest, issues)
    aliases = _load_model(
        root / CONCEPT_ALIAS_SEED_ROWS_PATH,
        Layer3GXConceptAliasSeedRows,
        issues,
    )
    scope = _load_model(root / SCOPE_SEED_ROWS_PATH, Layer3GXScopeSeedRows, issues)
    demand = _load_model(root / DEMAND_PULL_REQUEST_PATH, Layer3GXDemandPullRequest, issues)

    alias_rows = aliases.alias_rows if aliases is not None else ()
    scope_rows = scope.scope_rows if scope is not None else ()
    requested_constructs = pinned.requested_constructs if pinned is not None else ()
    alias_by_construct = {row.concept_ref: row for row in alias_rows}
    for construct in requested_constructs:
        row = alias_by_construct.get(construct.construct_ref)
        if row is None:
            issues.append("layer3_gx_pinned_construct_alias_missing")
            continue
        if row.resolution_status != "unverified":
            issues.append("layer3_gx_alias_row_not_unverified")
        if row.asserts_corpus_supply or row.corpus_row_refs:
            issues.append("layer3_gx_alias_supply_fact_forbidden")
    scope_keys = {row.scope_key for row in scope_rows}
    if REQUIRED_SCOPE_KEYS - scope_keys:
        issues.append("layer3_gx_scope_seed_row_missing")
    expected_path = pinned.expected_consumer_path if pinned is not None else ()
    if REQUIRED_CONSUMER_PATH - set(expected_path):
        issues.append("layer3_gx_expected_consumer_path_incomplete")
    if demand is not None and not (demand.accountable_principal_ref or demand.request_source_ref):
        issues.append("layer3_gx_demand_pull_request_source_missing")
    producer_records = _producer_records(pinned, aliases, scope, demand)
    required_refs: tuple[str, ...] = ()
    if pinned is not None:
        required_refs = (
            f"external-request://layer3-gx/pinned-request/{pinned.case_id}",
            f"external-request://layer3-gx/scope/{pinned.case_id}",
            f"external-request://layer3-gx/demand-pull/{pinned.case_id}",
        )
    for required_ref in required_refs:
        producer = next(
            (record for record in producer_records if record.get("producer_ref") == required_ref),
            None,
        )
        if producer is None or producer.get("producer_type") != "external_request":
            issues.append("layer3_gx_external_request_root_missing")
    normalized_issues = tuple(dict.fromkeys(issues))
    return Layer3GXDataHome(
        status="typed_blocker" if normalized_issues else "ready",
        pinned_request=pinned,
        concept_alias_rows=alias_rows,
        scope_rows=scope_rows,
        demand_pull_request=demand,
        expected_consumer_path=expected_path,
        producer_records=tuple(producer_records),
        issue_codes=normalized_issues,
    )


def build_layer3_gx_concept_alias_graph_artifact(
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build the Task 7 concept alias graph from data-home seed rows."""

    root = _repo_root() if repo_root is None else Path(repo_root)
    data_home = load_layer3_gx_data_home(root)
    alias_payload = _read_data_home_payload(root, CONCEPT_ALIAS_SEED_ROWS_PATH)
    alias_producer_ref = _required_text(
        alias_payload,
        "producer_ref",
        CONCEPT_ALIAS_SEED_ROWS_PATH,
    )
    alias_producer_type = _required_text(
        alias_payload,
        "producer_type",
        CONCEPT_ALIAS_SEED_ROWS_PATH,
    )
    construct_by_ref = {
        row.construct_ref: row
        for row in (
            data_home.pinned_request.requested_constructs
            if data_home.pinned_request is not None
            else ()
        )
    }
    scope_values = {row.scope_key: row.value for row in data_home.scope_rows}
    skg_measurements = _skg_concept_alias_measurements(root, construct_by_ref)
    graph_rows: list[dict[str, Any]] = []
    for alias_row in data_home.concept_alias_rows:
        requested = construct_by_ref.get(alias_row.concept_ref)
        measurement = skg_measurements.get(alias_row.concept_ref)
        if measurement is not None:
            graph_rows.append(
                {
                    "row_id": f"gx-concept-alias:{alias_row.concept_ref}",
                    "concept_ref": alias_row.concept_ref,
                    "aliases": _dedupe_strs((*alias_row.aliases, *measurement["aliases"])),
                    "metric_ids": _dedupe_strs(
                        (_concept_metric_id(alias_row.concept_ref), *measurement["metric_ids"])
                    ),
                    "variable_names": _dedupe_strs(measurement["variable_names"]),
                    "source_layer_refs": _dedupe_strs(
                        (*measurement["source_layer_refs"], L1_DCAT_REF)
                    ),
                    "jurisdiction_constraints": _dedupe_strs(
                        (
                            *measurement["jurisdiction_constraints"],
                            *_non_empty_list(scope_values.get("geography")),
                        )
                    ),
                    "validity_limits": _dedupe_strs(
                        (
                            "measurement_canonicalized_alias_only",
                            *measurement["validity_limits"],
                            *_non_empty_list(scope_values.get("validity_limit")),
                        )
                    ),
                    "producer_owner": measurement["producer_owner"][0],
                    "producer_type": "measurement",
                    "verification_status": "measured",
                    "resolved_corpus_row_refs": _dedupe_strs(
                        measurement["resolved_corpus_row_refs"]
                    ),
                    "rule_version": LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION,
                }
            )
            continue
        variable_names = (requested.g2_variable_ref,) if requested is not None else ()
        graph_rows.append(
            {
                "row_id": f"gx-concept-alias:{alias_row.concept_ref}",
                "concept_ref": alias_row.concept_ref,
                "aliases": list(alias_row.aliases),
                "metric_ids": [_concept_metric_id(alias_row.concept_ref)],
                "variable_names": list(variable_names),
                "source_layer_refs": [L1_DCAT_REF],
                "jurisdiction_constraints": _non_empty_list(scope_values.get("geography")),
                "validity_limits": _non_empty_list(scope_values.get("validity_limit")),
                "producer_owner": alias_producer_ref,
                "producer_type": alias_producer_type,
                "verification_status": alias_row.resolution_status,
                "resolved_corpus_row_refs": list(alias_row.corpus_row_refs),
                "rule_version": LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION,
            }
        )
    artifact = {
        "schema_version": LAYER3_GX_CONCEPT_ALIAS_GRAPH_SCHEMA_VERSION,
        "rule_version": LAYER3_GX_CONCEPT_ALIAS_GRAPH_RULE_VERSION,
        "producer_ref": (
            "derivation://layer3-gx/concept-alias-graph/"
            f"{data_home.pinned_request.case_id if data_home.pinned_request else 'unknown'}"
        ),
        "producer_type": "derivation",
        "graph_rows": graph_rows,
    }
    return Layer3GXConceptAliasGraph.model_validate(artifact).model_dump(mode="json")


def load_layer3_gx_concept_alias_graph(repo_root: Path) -> Layer3GXConceptAliasGraph:
    """Load the Task 7 concept alias graph with explicit degraded states."""

    root = Path(repo_root)
    path = root / CONCEPT_ALIAS_GRAPH_PATH
    if not path.exists():
        return Layer3GXConceptAliasGraph(
            status="missing",
            producer_ref="missing://layer3-gx/concept-alias-graph",
            producer_type="derivation",
            issue_codes=("layer3_gx_concept_alias_graph_missing",),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        graph = Layer3GXConceptAliasGraph.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        return Layer3GXConceptAliasGraph(
            status="typed_blocker",
            producer_ref="invalid://layer3-gx/concept-alias-graph",
            producer_type="derivation",
            issue_codes=("layer3_gx_concept_alias_graph_invalid",),
        )
    issues: list[str] = list(graph.issue_codes)
    if not graph.graph_rows:
        issues.append("layer3_gx_concept_alias_graph_empty")
    seen: set[str] = set()
    for row in graph.graph_rows:
        if row.concept_ref in seen:
            issues.append("layer3_gx_concept_alias_graph_duplicate_concept")
        seen.add(row.concept_ref)
        if row.verification_status == "measured":
            if row.producer_type != "measurement" or not row.resolved_corpus_row_refs:
                issues.append("layer3_gx_concept_alias_measured_resolution_missing")
        elif row.resolved_corpus_row_refs:
            issues.append("layer3_gx_concept_alias_unverified_resolution_refs")
    normalized_issues = tuple(dict.fromkeys(issues))
    return graph.model_copy(
        update={
            "status": "typed_blocker" if normalized_issues else "ready",
            "issue_codes": normalized_issues,
        }
    )


def build_g1_request_dicts_from_data_home(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Build G1 request dictionaries from the persisted GX data home."""

    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return ()
    rows: list[dict[str, Any]] = []
    for row in data_home.pinned_request.g1_requests:
        payload = {"case_id": data_home.pinned_request.case_id}
        payload.update(row)
        rows.append(payload)
    return tuple(rows)


def build_g2_request_dict_from_data_home(repo_root: Path) -> dict[str, Any]:
    """Build the G2 request dictionary from the persisted GX data home."""

    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        raise Layer3GXDataHomeBlockedError(data_home)
    payload = {"case_id": data_home.pinned_request.case_id}
    payload.update(data_home.pinned_request.g2_request)
    return payload


def build_g4_promotion_request_dicts_from_data_home(
    repo_root: Path,
) -> tuple[dict[str, Any], ...]:
    """Build G4 promotion request dictionaries from the persisted GX data home."""

    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.pinned_request is None:
        return ()
    rows: list[dict[str, Any]] = []
    for row in data_home.pinned_request.g4_promotion_requests:
        payload = {"case_id": data_home.pinned_request.case_id}
        payload.update(row)
        rows.append(payload)
    return tuple(rows)


def build_g5_demand_pull_dict_from_data_home(repo_root: Path) -> dict[str, Any]:
    """Build a G5 demand-pull dictionary from the persisted GX data home."""

    data_home = load_layer3_gx_data_home(repo_root)
    if data_home.status != "ready" or data_home.demand_pull_request is None:
        return {
            "status": "fail",
            "authority_purpose": "demand_pull_input_only",
            "may_not_use_for": (
                "conversion_authority",
                "production_authority",
                "closeout_authority",
                "useful_design_credit",
            ),
            "issue_codes": data_home.issue_codes,
            "producer_ref": None,
            "producer_type": None,
            "source": None,
            "timestamp": None,
            "request_source_ref": None,
            "replay_key": None,
            "consumer_path": (),
            "demand_pull_refs": (),
            "s12_demand_act_refs": (),
            "accountable_principal_refs": (),
            "attempted_grounding_path_refs": (),
        }
    demand = data_home.demand_pull_request
    principal_refs = (
        (demand.accountable_principal_ref,)
        if demand.accountable_principal_ref
        else ()
    )
    return {
        "status": "pass",
        "authority_purpose": "demand_pull_input_only",
        "may_not_use_for": (
            "conversion_authority",
            "production_authority",
            "closeout_authority",
            "useful_design_credit",
        ),
        "issue_codes": (),
        "producer_ref": demand.producer_ref,
        "producer_type": demand.producer_type,
        "source": demand.source,
        "timestamp": demand.timestamp,
        "request_source_ref": demand.request_source_ref,
        "replay_key": demand.replay_key,
        "consumer_path": tuple(demand.consumer_path),
        "demand_pull_refs": tuple(demand.demand_refs),
        "s12_demand_act_refs": tuple(demand.demand_refs),
        "accountable_principal_refs": principal_refs,
        "attempted_grounding_path_refs": tuple(demand.attempted_grounding_path_refs),
    }


def _load_model[DataHomeModel: _GXDataHomeModel](
    path: Path,
    model: type[DataHomeModel],
    issues: list[str],
) -> DataHomeModel | None:
    if not path.exists():
        issues.append("layer3_gx_data_home_artifact_missing")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        issues.append("layer3_gx_data_home_artifact_invalid")
        return None


def _skg_concept_alias_measurements(
    root: Path,
    construct_by_ref: dict[str, Layer3GXRequestedConstruct],
) -> dict[str, dict[str, tuple[str, ...]]]:
    db_path = Path(root) / ACADEMIC_SKG_DB_PATH
    if not db_path.exists():
        return {}
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.Error:
        return {}
    try:
        if not _duckdb_table_exists(con, "ac_skg_variables"):
            return {}
        variable_columns = _duckdb_columns(con, "ac_skg_variables")
        context_columns = _duckdb_columns(con, "ac_skg_context_attributes")
        measurements: dict[str, dict[str, tuple[str, ...]]] = {}
        for concept_ref, requested in construct_by_ref.items():
            candidates = _dedupe_strs(
                (
                    concept_ref,
                    requested.g2_variable_ref,
                    _concept_metric_id(concept_ref),
                    *requested.broad_query_terms,
                )
            )
            variable_rows = _skg_variable_rows(con, variable_columns, candidates)
            if not variable_rows:
                continue
            variable_names = _dedupe_strs(
                str(row.get("approved_canonical_name") or row.get("canonical_name") or "")
                for row in variable_rows
            )
            aliases = _dedupe_strs(
                value
                for row in variable_rows
                for value in (
                    row.get("normalized_name"),
                    row.get("display_name"),
                    row.get("canonical_name"),
                )
                if value
            )
            source_layer_refs = (_duckdb_ref(ACADEMIC_SKG_DB_PATH, "ac_skg_variables"),)
            context_refs: tuple[str, ...] = ()
            jurisdiction_constraints: tuple[str, ...] = ()
            if _duckdb_table_exists(con, "ac_skg_context_attributes"):
                context = _skg_context_attribute_rows(con, context_columns, variable_names)
                context_refs = _dedupe_strs(
                    _duckdb_ref(
                        ACADEMIC_SKG_DB_PATH,
                        "ac_skg_context_attributes",
                        str(row.get("attr_id") or ""),
                    )
                    for row in context
                    if row.get("attr_id")
                )
                jurisdiction_constraints = _dedupe_strs(
                    str(row.get("country_code") or "") for row in context
                )
                if context_refs:
                    source_layer_refs = (
                        *source_layer_refs,
                        _duckdb_ref(
                            ACADEMIC_SKG_DB_PATH,
                            "ac_skg_context_attributes",
                        ),
                    )
            variable_refs = tuple(
                _duckdb_ref(ACADEMIC_SKG_DB_PATH, "ac_skg_variables", variable)
                for variable in variable_names
            )
            measurements[concept_ref] = {
                "aliases": aliases,
                "metric_ids": (_concept_metric_id(concept_ref),),
                "variable_names": variable_names,
                "source_layer_refs": _dedupe_strs(source_layer_refs),
                "jurisdiction_constraints": jurisdiction_constraints,
                "validity_limits": ("measurement_root_alias_not_source_contract",),
                "producer_owner": (
                    "polisyos.data_forge.domains.academic.knowledge.SKGQuery",
                ),
                "resolved_corpus_row_refs": _dedupe_strs((*variable_refs, *context_refs)),
            }
        return measurements
    except duckdb.Error:
        return {}
    finally:
        con.close()


def _skg_variable_rows(
    con: duckdb.DuckDBPyConnection,
    columns: set[str],
    candidates: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not candidates:
        return []
    lookup_columns = [
        column
        for column in ("canonical_name", "approved_canonical_name", "normalized_name")
        if column in columns
    ]
    if not lookup_columns:
        return []
    select_columns = [
        column
        for column in (
            "canonical_name",
            "normalized_name",
            "display_name",
            "approved_canonical_name",
            "mention_count",
        )
        if column in columns
    ]
    if not select_columns:
        return []
    placeholders = ", ".join(["?"] * len(candidates))
    filters = " OR ".join(f"{column} IN ({placeholders})" for column in lookup_columns)
    params: list[str] = []
    for _column in lookup_columns:
        params.extend(candidates)
    order = (
        " ORDER BY mention_count DESC, canonical_name ASC"
        if "mention_count" in columns and "canonical_name" in columns
        else ""
    )
    query = (
        f"SELECT {', '.join(select_columns)} FROM ac_skg_variables "  # noqa: S608
        f"WHERE {filters}{order}"
    )
    rows = con.execute(query, params).fetchall()
    return [dict(zip(select_columns, row, strict=False)) for row in rows]


def _skg_context_attribute_rows(
    con: duckdb.DuckDBPyConnection,
    columns: set[str],
    variable_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not variable_names or "canonical_name" not in columns or "attr_id" not in columns:
        return []
    select_columns = [
        column
        for column in (
            "attr_id",
            "canonical_name",
            "country_code",
            "time_period",
            "measurement_method",
            "confidence",
        )
        if column in columns
    ]
    placeholders = ", ".join(["?"] * len(variable_names))
    query = (
        f"SELECT {', '.join(select_columns)} FROM ac_skg_context_attributes "  # noqa: S608
        f"WHERE canonical_name IN ({placeholders}) ORDER BY attr_id ASC"
    )
    rows = con.execute(query, list(variable_names)).fetchall()
    return [dict(zip(select_columns, row, strict=False)) for row in rows]


def _duckdb_table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()
    return bool(row and row[0])


def _duckdb_columns(con: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    if not _duckdb_table_exists(con, table):
        return set()
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _duckdb_ref(path: Path, table: str, fragment: str | None = None) -> str:
    ref = f"duckdb://{path.as_posix()}#{table}"
    if fragment:
        ref = f"{ref}/{fragment}"
    return ref


def _read_data_home_payload(root: Path, path: Path) -> dict[str, Any]:
    payload = json.loads((Path(root) / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.as_posix()} must contain a JSON object")
    return payload


def _required_text(payload: dict[str, Any], field: str, path: Path) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path.as_posix()} missing required text field {field}")
    return value


def _concept_metric_id(concept_ref: str) -> str:
    return (
        str(concept_ref)
        .removeprefix("construct:")
        .removeprefix("policy.")
        .replace(
            ".",
            "_",
        )
    )


def _non_empty_list(value: str | None) -> list[str]:
    return [value] if value else []


def _dedupe_strs(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(value).strip() for value in values if str(value or "").strip())
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _producer_records(
    *payloads: _GXDataHomeModel | None,
) -> list[dict[str, str | tuple[str, ...]]]:
    records: list[dict[str, str | tuple[str, ...]]] = []
    for payload in payloads:
        if payload is None:
            continue
        producer_ref = getattr(payload, "producer_ref", None)
        producer_type = getattr(payload, "producer_type", None)
        if not producer_ref or not producer_type:
            continue
        records.append(
            {
                "producer_ref": producer_ref,
                "producer_type": producer_type,
                "root_refs": tuple(getattr(payload, "producer_root_refs", ()) or ()),
            }
        )
    return records
