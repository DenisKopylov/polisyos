# Сопоставление B и LA: тип связи определяет работу

Новые выводы E02 ниже — инженерная интерпретация двух источников, не дополнительные production-findings.

## REL01 · LA-046 ↔ B12

**Тип:** SAME_OWNER. Actual N7 scenario adapter, text/domain/resolver and acquisition dispatch; source r08 amendment applies.

Пакеты: [REQ-01](bundles/REQ-01.md), [ACQ-01](bundles/ACQ-01.md).

## REL02 · LA-051 ↔ B32

**Тип:** SAME_OWNER. Same S10 helper/times; LA additionally covers fabricated calibration from estimator shape.

Пакеты: [FRC-01](bundles/FRC-01.md), [FRC-02](bundles/FRC-02.md).

## REL03 · LA-015 ↔ B118, B119, B120, B121, B123

**Тип:** EXTRACTION_AND_FIX. One run-state/transition owner, corrected behavior survives native driver cutover.

Пакеты: [CTL-01](bundles/CTL-01.md), [CTL-03](bundles/CTL-03.md), [SRV-01](bundles/SRV-01.md), [SRV-03](bundles/SRV-03.md).

## REL04 · LA-014 ↔ B123, B124

**Тип:** SHARED_ADAPTER. tell must not bypass typed eligibility or source identity via private fields.

Пакеты: [SRV-01](bundles/SRV-01.md), [CTL-03](bundles/CTL-03.md), [CTL-02](bundles/CTL-02.md).

## REL05 · LA-016 ↔ B204, B205, B206, B207, B208, B209

**Тип:** SHARED_HELPERS. Dedicated methods retain shared numerical helpers; metadata migration separate from inference delta.

Пакеты: [CAU-01](bundles/CAU-01.md), [CAU-02](bundles/CAU-02.md), [CAU-05](bundles/CAU-05.md).

## REL06 · LA-031 ↔ B146, B147

**Тип:** EXTRACTION_AND_FIX. Calendar/IO fixes follow actual extracted helper owners; no second patch to obsolete common.

Пакеты: [UDF-01](bundles/UDF-01.md), [OBS-01](bundles/OBS-01.md), [UDF-02](bundles/UDF-02.md), [OBS-02](bundles/OBS-02.md).

## REL07 · LA-057 ↔ B14, B40, B69, B95

**Тип:** SAME_FILE_DIFFERENT_CHANGE. Only TypeVar residue deletion then distinct deadline/context regression commits.

Пакеты: [RUN-01](bundles/RUN-01.md).

## REL08 · LA-007 ↔ B216, B217

**Тип:** NEIGHBOUR_PROTECTED. Delete empty sibling .py, protect real package; correctness of shared ADMG ops independently tested.

Пакеты: [GRF-01](bundles/GRF-01.md).

## REL09 · LA-019 ↔ B216, B217, B214

**Тип:** NEIGHBOUR_PROTECTED. Sibling cleanup does not remove causal/interference packages or attest their algorithms.

Пакеты: [GRF-01](bundles/GRF-01.md), [API-01](bundles/API-01.md), [GRF-03](bundles/GRF-03.md).

## REL10 · LA-024 ↔ B17, B64

**Тип:** SAME_DOMAIN_DIFFERENT_LAYER. Provider exhaustion, transport and LLM cache are distinct; common raw transport only.

Пакеты: [SCL-01](bundles/SCL-01.md), [LLM-01](bundles/LLM-01.md).

## REL11 · LA-025 ↔ B60, B61, B64

**Тип:** UPSTREAM_SNAPSHOT. Version-bound acquired bytes must reach consumers; no common universal cache inferred.

Пакеты: [SCL-03](bundles/SCL-03.md), [STA-02](bundles/STA-02.md), [LLM-01](bundles/LLM-01.md).

## REL12 · LA-052 ↔ B167, B168

**Тип:** ACCEPTANCE_ONLY. Both require honest denominator, but generic calibration and backtest evaluation have different owners.

Пакеты: [PCL-01](bundles/PCL-01.md), [BKT-02](bundles/BKT-02.md).

## REL13 · LA-053 ↔ B174, B175

**Тип:** ALIAS_ONLY. Canonical curve import/test migration must not delete CV/bootstrap or all backtesting.

Пакеты: [PCL-01](bundles/PCL-01.md), [BKT-04](bundles/BKT-04.md).

## REL14 · LA-021 ↔ B94, B150, B152

**Тип:** FORMAT_BOUNDARY. Strict canon profiles vs runtime JSON/Decimal transport; identity preservation joint, mechanisms not indiscriminately merged.

Пакеты: [CAN-01](bundles/CAN-01.md), [WIRE-01](bundles/WIRE-01.md), [CAS-01](bundles/CAS-01.md), [CAS-03](bundles/CAS-03.md).

## REL15 · LA-033 ↔ B70, B74, B75, B76

**Тип:** ALIAS_ONLY. Replay entrypath migration not equivalent to checkpoint identity/inventory repair.

Пакеты: [REP-01](bundles/REP-01.md), [RES-01](bundles/RES-01.md), [RES-04](bundles/RES-04.md).

## REL16 · LA-037 ↔ B42, B43, B49

**Тип:** UPSTREAM_PATH. Current IR slot owner and compiler imports; requires/caching fixes remain separate.

Пакеты: [FRY-01](bundles/FRY-01.md), [CMP-01](bundles/CMP-01.md), [JIT-01](bundles/JIT-01.md).

## REL17 · LA-003 ↔ B185

**Тип:** MODEL_PROFILE. PatchMap/runtime class path relocation must preserve scheduled active/PRNG behavior.

Пакеты: [FRY-03](bundles/FRY-03.md), [CAL-05](bundles/CAL-05.md).

## REL18 · LA-039 ↔ B134, B76, B149

**Тип:** SAME_PRINCIPLE_NOT_SAME_STORE. NPZ/HNSW generation is not in-memory VectorMemoryStore or CAS export; share controls, not ownership.

Пакеты: [EMB-01](bundles/EMB-01.md), [EMB-02](bundles/EMB-02.md), [TRN-02](bundles/TRN-02.md), [RES-04](bundles/RES-04.md), [CAS-02](bundles/CAS-02.md).

## REL19 · LA-041 ↔ B70, B71, B74, B75, B76

**Тип:** SAME_PRINCIPLE_NOT_SAME_CHECKPOINT. Catalog batch state and research checkpoint differ; input/output identity rules bind their own inventory.

Пакеты: [DFI-03](bundles/DFI-03.md), [RES-01](bundles/RES-01.md), [RES-04](bundles/RES-04.md).

## REL20 · LA-054 ↔ B137, B163

**Тип:** ACTIVATION_DISTINCTION. Historical pass/freshness versus measured current readiness analogous, DDM FP owner remains separate.

Пакеты: [DDM-02](bundles/DDM-02.md), [TRN-03](bundles/TRN-03.md), [FUN-03](bundles/FUN-03.md).

## REL21 · LA-055 ↔ B164, B165, B116

**Тип:** ACTIVATION_DISTINCTION. Gate/callback/pointer decisions are not one authority model; preserve DDM R2 and concrete precedence.

Пакеты: [DDM-02](bundles/DDM-02.md), [FUN-03](bundles/FUN-03.md), [FUN-02](bundles/FUN-02.md), [OPT-04](bundles/OPT-04.md).

