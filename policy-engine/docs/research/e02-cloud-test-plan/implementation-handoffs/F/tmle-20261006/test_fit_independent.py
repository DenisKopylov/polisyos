"""Independent native adversarial witnesses; never modifies the candidate tree."""
from dataclasses import replace

import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.special import expit

from polisyos.foundry.methods.catalog.causal import tmle_core as c


def inputs():
    r = np.random.default_rng(9918)
    x = r.normal(size=(240, 2))
    t = r.binomial(1, .5, 240).astype(float)
    y = r.binomial(1, .2 + .4*t).astype(float)
    return x, t, y


P = dict(propensity_backend="logistic", outcome_backend="linear", calibration_mode="none",
         outcome_scaling="raw", n_repeats=2, crossfit_folds=3, random_seed=93,
         coverage_guard="off", ci_mode="wald", __shared_nuisance_key="review")


@pytest.fixture(autouse=True)
def cache(monkeypatch):
    monkeypatch.setattr(c, "_SHARED_NUISANCE_CACHE", {})
    monkeypatch.setattr(c, "_SHARED_NUISANCE_CACHE_ORDER", [])


def test_reader_entire_base_chain_header_and_write_isolation():
    x,t,y = inputs()
    contract = c.ATENuisanceContract.from_params(P)
    issued = c.fit_crossfit_nuisance_bundle(x,t,y,contract,P)
    originals = {n:getattr(issued,n).copy() for n in ("propensity","mu1","mu0","trim_mask")}
    for name, original in originals.items():
        array = getattr(issued,name)
        chain=[]
        while isinstance(array,np.ndarray):
            chain.append(array)
            with pytest.raises(ValueError): array.setflags(write=True)
            array=array.base
        assert isinstance(array,bytes), "immutable bytes must be the ultimate base"
        for header in chain:
            header.shape=(1,header.size)
            header.dtype=np.uint8
        fresh=c.fit_crossfit_nuisance_bundle(x,t,y,contract,P)
        np.testing.assert_array_equal(getattr(fresh,name),original)
        assert getattr(fresh,name).dtype==original.dtype
        assert getattr(fresh,name).shape==original.shape
    issued.split_manifest[0]["folds"][0]["test_indices"].clear()
    fresh=c.fit_crossfit_nuisance_bundle(x,t,y,contract,P)
    assert len(fresh.split_manifest[0]["folds"][0]["test_indices"])>0


def test_cache_identity_binds_row_order_and_actual_current_contract():
    x,t,y=inputs(); contract=c.ATENuisanceContract.from_params(P)
    first=c.fit_crossfit_nuisance_bundle(x,t,y,contract,P)
    permutation=np.random.default_rng(83).permutation(len(y))
    changed=c.fit_crossfit_nuisance_bundle(x[permutation],t[permutation],y[permutation],contract,P)
    assert first.fit_identity != changed.fit_identity
    view=replace(contract, overlap_diagnostic_policy="fresh-review-policy", min_effective_sample_size=999)
    current=c.fit_crossfit_nuisance_bundle(x,t,y,view,P)
    assert current.fit_identity==first.fit_identity and current.contract is view
    assert current.diagnostics()["min_effective_sample_size"]==999
    assert all(r["split_policy"]=="fresh-review-policy" for r in current.selection_manifest)


def test_precomputed_identity_string_without_issued_core_is_refused():
    x,t,y=inputs(); contract=c.ATENuisanceContract.from_params(P)
    bundle=c.fit_crossfit_nuisance_bundle(x,t,y,contract,P)
    bundle.mu1=np.full(len(y),1000.)
    accepted=c.fit_crossfit_nuisance_bundle(x,t,y,contract,{**P,"__shared_nuisance_bundle":bundle})
    assert np.max(accepted.mu1)<2
    c._SHARED_NUISANCE_CACHE.clear()
    with pytest.raises(ValueError,match="controlled cache"):
        c.fit_crossfit_nuisance_bundle(x,t,y,contract,{**P,"__shared_nuisance_bundle":bundle})


def test_logistic_score_matches_independent_brent_root():
    r=np.random.default_rng(499)
    offset=r.normal(0,2,713); clever=r.uniform(-4,4,713)
    y=r.binomial(1,expit(offset+.27*clever))
    def score(e): return np.mean(clever*(y-expit(offset+e*clever)))
    expected=brentq(score,-30,30,xtol=1e-14)
    actual=c._logistic_fluctuation_epsilon(offset,clever,y)
    assert actual==pytest.approx(expected,abs=1e-10)
    assert abs(score(actual))<1e-11
    assert np.all(np.isfinite(c._expit(np.array([-1e4,0,1e4]))))


@pytest.mark.parametrize("mode",["positivity","trimmed","unsupported","nonconvergence"])
def test_limitation_honesty_under_actual_native_target(mode,monkeypatch):
    x,t,y=inputs(); params={**P,"targeting_step_limit":5.}
    contract=c.ATENuisanceContract.from_params(params)
    bundle=c.fit_crossfit_nuisance_bundle(x,t,y,contract,params)
    if mode=="positivity": bundle.propensity=np.full(len(y),contract.propensity_clipping)
    if mode=="trimmed":
        bundle.trim_mask=np.arange(len(y))%2==0
        params["weak_overlap_mode"]="trimmed_dr"
    if mode=="unsupported": params["inference_profile"]="clustered"
    if mode=="nonconvergence":
        bundle.mu1=np.full(len(y),.01); bundle.mu0=np.full(len(y),.99)
        params.update(max_targeting_iter=1,targeting_step_limit=1e-12)
    monkeypatch.setattr(c,"fit_crossfit_nuisance_bundle",lambda *args:bundle)
    fit,actual=c.fit_tmle_ate(x,t,y,params)
    output=c.result_payload(fit,actual)
    assert fit.inference_limitations
    assert fit.ci_lower is None and fit.ci_upper is None
    assert output["status"]=="limited" and output["gate_eligible"] is False
    assert output["assumption_basis"]=="consumer_asserted"


def test_repeated_native_target_retains_full_heldout_lineage_and_eif_oracle():
    x,t,y=inputs(); fit,bundle=c.fit_tmle_ate(x,t,y,P)
    assert len(bundle.split_manifest)==2
    for repeat in bundle.split_manifest:
        indices=[i for fold in repeat["folds"] for i in fold["test_indices"]]
        assert sorted(indices)==list(range(len(y)))
    assert fit.standard_error==pytest.approx(np.std(fit.eif_values,ddof=1)/np.sqrt(len(y)))
    assert abs(fit.targeting_summary["targeting_score"])<1e-8
    payload=c.result_payload(fit,bundle)
    assert payload["status"]=="candidate" and payload["gate_eligible"] is False
