"""Cut the real owner predicate in memory while retaining all receipt markers."""
import sys
import pytest
from polisyos.fabric.retrieval import custody
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore

MODE = sys.argv[1]
BASE = "tests/unit/fabric/test_retrieval_fetch_custody.py::"
if MODE == "contract":
    from polisyos.fabric.connectors.contracts import ContractValidatingProxy
    ContractValidatingProxy.validate_result_against_contract = classmethod(
        lambda cls, result, contract: []
    )
    selected = ["test_current_registry_validates_full_result_without_fetch_or_mutation"]
elif MODE == "source":
    custody._require_source_agreement = lambda *args, **kwargs: None
    selected = ["test_real_connector_readback_refuses_complete_counterfeit_chain",
                "test_real_connector_recomputes_full_current_source_and_preserves_raw_capture"]
elif MODE == "catalog":
    actual = DatasetCatalogStore._fetch_target_candidates
    def marked_candidates(self, metric_id, targets):
        return actual(self, "metric.test", targets)
    def no_target_lookup(request, candidates):
        _,target=next(item for values in candidates.values() for item in values)
        return None,target.model_copy(update={
            "connector_id":request.connector_id,"request_dataset_id":request.request_dataset_id,
            "profile_id":request.profile_id or ""})
    DatasetCatalogStore._fetch_target_candidates=marked_candidates
    DatasetCatalogStore._select_fetch_target=staticmethod(no_target_lookup)
    selected = ["test_unknown_catalog_tuple_refuses_real_fetch",
                "test_fallback_cannot_reuse_primary_catalog_markers",
                "test_bulk_catalog_owner_preserves_full_order_and_refuses_novel_tuple",
                "test_persisted_fetch_carries_complete_payload_and_actual_catalog"]
elif MODE == "bulk_source":
    actual=DatasetCatalogStore._fetch_source_identities
    cached={}
    def markers_only(self):
        if self not in cached:cached[self]=actual(self)
        return cached[self]
    DatasetCatalogStore._fetch_source_identities=markers_only
    selected=["test_bulk_catalog_owner_returns_nothing_on_mid_read_source_change",
              "test_bulk_catalog_owner_preserves_full_order_and_refuses_novel_tuple"]
else:
    raise ValueError(MODE)
print("REMOVED_PROPERTY", MODE, "markers and real positive control retained", flush=True)
raise SystemExit(pytest.main([*(BASE + name for name in selected), "-q", "-rA"]))
