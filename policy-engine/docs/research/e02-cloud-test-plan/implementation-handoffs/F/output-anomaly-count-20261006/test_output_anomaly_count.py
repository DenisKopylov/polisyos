"""Native dispatch and real OTel counts for one normalized output fact."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
from typing import Any, ClassVar
import warnings

import numpy as np
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import (
    ComplexityClass, ComputeBackend, FidelityLevel, MethodMetadata,
    MethodSignature, SlotSpec, SlotType, Unit,
)
from polisyos.foundry.methods.lifecycle import observability
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.selection.history import SelectionHistoryStore


class _NativeOutput:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name='anomaly_count',namespace='tests.monitor',version='1.0.0',
        input_slots=frozenset(),output_slots=frozenset({SlotSpec('result',SlotType.SCALAR,Unit('signal','1'))}),
        parameters=(),fidelity=FidelityLevel.LOW,complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,supports_jit=False,supports_vmap=False,supports_grad=False)
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description='Native anomaly-count test producer')

    @staticmethod
    def pure_step(state: Any,params: Any) -> Any:
        return state


class _CopiedProjection(_NativeOutput):
    signature=replace(_NativeOutput.signature,name='copied_projection')

    @staticmethod
    def dematerialize_output(output: Any) -> Any:
        return {'result':np.asarray(output['report']).copy()}


@pytest.fixture
def observed_dispatch(monkeypatch):
    reader=InMemoryMetricReader()
    provider=MeterProvider(metric_readers=[reader])
    counter=provider.get_meter('independent-anomaly-counter').create_counter('foundry.method.anomaly_detected')
    was_active = observability.is_instrumentation_active()
    assert observability.activate_foundry_instrumentation() is True
    assert observability._OTEL_AVAILABLE is True
    monkeypatch.setattr(observability,'_method_errors_counter',counter)
    from polisyos.foundry.methods.backends import dispatch as dispatcher
    emit=dispatcher._emit_anomaly_metric
    emitted=[]

    def observed(fqn,flags):
        emitted.append((fqn,tuple(flags)))
        emit(fqn,flags)

    monkeypatch.setattr(dispatcher,'_emit_anomaly_metric',observed)
    MethodRegistry.reset_instance()

    def run(raw,method=_NativeOutput):
        registry=MethodRegistry.get_instance()
        registry.register(method,override=True)
        actual=registry.get(method.signature.fqn)
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter('always')
            result=MethodDispatcher(runtime_history=SelectionHistoryStore()).dispatch(
                method_class=actual,signature=actual.signature,state=raw,params={},seed=17)
        assert len(emitted)==1
        flags=emitted[0][1]
        data=reader.get_metrics_data()
        counts=Counter()
        for resource in data.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    if metric.name=='foundry.method.anomaly_detected':
                        for point in metric.data.data_points:
                            assert point.attributes['method.fqn']==method.signature.fqn
                            counts[point.attributes['anomaly.reason']]+=point.value
        print(json.dumps(dict(flags=[dict(key=f.key,reason=f.reason,severity=f.severity) for f in flags],
            warnings=[str(w.message) for w in seen],actual_otel_counter=dict(counts),
            method_fqn=actual.signature.fqn),sort_keys=True))
        return result,flags,seen,counts

    yield run
    MethodRegistry.reset_instance()
    provider.shutdown()
    if not was_active:
        observability.deactivate_foundry_instrumentation()


@pytest.mark.parametrize('source',['report','result','bare'])
@pytest.mark.parametrize('bad',[float('nan'),float('inf'),float('-inf'),np.array([np.nan,np.inf])],
    ids=['nan','inf','negative_inf','nan_inf_vector'])
def test_one_canonical_warning_and_metric_for_consumed_source(observed_dispatch,source,bad):
    raw=bad if source=='bare' else {source:bad}
    result,flags,seen,counts=observed_dispatch(raw)
    assert result.slot_outputs['result'] is bad
    reasons={'nan_detected','inf_detected'} if isinstance(bad,np.ndarray) else {
        'nan_detected' if np.isnan(bad) else 'inf_detected'}
    assert {(f.key,f.reason,f.severity) for f in flags}=={('result',reason,'error') for reason in reasons}
    assert len(flags)==len(seen)==len(reasons)
    assert counts==Counter({reason:1 for reason in reasons})


@pytest.mark.parametrize('same_object',[False,True])
@pytest.mark.parametrize('bad',[float('nan'),float('inf'),np.array([np.nan,np.inf])],
    ids=['nan','inf','nan_inf_vector'])
def test_distinct_sidecar_keeps_its_own_anomalies_even_for_same_object(observed_dispatch,same_object,bad):
    sidecar=bad if same_object else (bad.copy() if isinstance(bad,np.ndarray) else float(str(bad)))
    result,flags,seen,counts=observed_dispatch({'report':bad,'diagnostic_draw':sidecar})
    assert result.slot_outputs['result'] is bad
    reasons={'nan_detected','inf_detected'} if isinstance(bad,np.ndarray) else {
        'nan_detected' if np.isnan(bad) else 'inf_detected'}
    expected={(key,reason,'error') for key in ('result','diagnostic_draw') for reason in reasons}
    assert {(f.key,f.reason,f.severity) for f in flags}==expected
    assert len(flags)==len(seen)==2*len(reasons)
    assert counts==Counter({reason:2 for reason in reasons})


def test_existing_canonical_key_has_priority_over_unused_alias(observed_dispatch):
    canonical=np.array([2.,5.])
    unused=np.array([np.nan,np.inf])
    result,flags,seen,counts=observed_dispatch({'result':canonical,'report':unused})
    assert result.slot_outputs['result'] is canonical
    assert {(f.key,f.reason) for f in flags}=={('report','nan_detected'),('report','inf_detected')}
    assert len(flags)==len(seen)==2
    assert counts==Counter({'nan_detected':1,'inf_detected':1})


def test_custom_copy_projection_has_no_invented_source_correspondence(observed_dispatch):
    raw=np.array([np.nan,np.inf])
    result,flags,seen,counts=observed_dispatch({'report':raw},_CopiedProjection)
    assert result.slot_outputs['result'] is not raw
    assert {(f.key,f.reason) for f in flags}=={
        (key,reason) for key in ('result','report') for reason in ('nan_detected','inf_detected')}
    assert len(flags)==len(seen)==4
    assert counts==Counter({'nan_detected':2,'inf_detected':2})
