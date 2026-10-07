from dataclasses import replace
from collections import Counter
import numpy as np
from test_output_anomaly_count import observed_dispatch, _NativeOutput
from polisyos.foundry.methods.base import SlotSpec, SlotType, Unit

class _TwoSlots(_NativeOutput):
    signature = replace(_NativeOutput.signature, name="independent_two_slots", output_slots=frozenset({SlotSpec("result",SlotType.SCALAR,Unit("signal","1")), SlotSpec("second",SlotType.SCALAR,Unit("signal","1"))}))

class _EmptyVector(_NativeOutput):
    signature = replace(_NativeOutput.signature, name="independent_empty_vector", output_slots=frozenset({SlotSpec("result", SlotType.VECTOR, Unit("signal","1"),shape=(None,))}))

def test_two_declared_slots_and_identical_sidecar_are_three_observations(observed_dispatch):
    bad = np.array([np.nan, np.inf])
    result, flags, seen, counts = observed_dispatch({"report": bad, "second":bad, "diagnostic_draw":bad}, _TwoSlots)
    assert result.slot_outputs["result"] is result.slot_outputs["second"] is bad
    assert {(f.key, f.reason) for f in flags} == {(key,reason) for key in ("result","second","diagnostic_draw") for reason in ("nan_detected","inf_detected")}
    assert len(flags) == len(seen) == 6
    assert counts == Counter({"nan_detected":3,"inf_detected":3})

def test_declared_empty_vector_alias_is_red_once_and_sidecar_stays_red(observed_dispatch):
    empty = np.empty(0)
    result, flags, seen, counts = observed_dispatch({"report":empty,"diagnostic_draw":empty}, _EmptyVector)
    assert result.slot_outputs["result"] is empty
    assert {(f.key, f.reason) for f in flags} == {("result","empty_array"),("diagnostic_draw","empty_array")}
    assert len(flags) == len(seen) == 2
    assert counts == Counter({"empty_array":2})
