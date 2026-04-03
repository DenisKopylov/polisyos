> **Archived:** This document reflects plans as of 2026-03-18.
> See [current docs](../../explanation/index.md) for up-to-date information.

# Local SOTA Evidence Pack

Этот профиль собирает честный локальный пакет real-data бенчмарков для MacBook Air M2 без агрессивной тепловой нагрузки.

## Что входит

`air-m2` профиль тянет:
- `ACIC`: официальный `causallib` sample layout (`x.csv` + `zymu_1..10.csv`)
- `LBIDD`: официальный IBM sample pack, но только маленький `scaling` subset с лучшим `snr`
- `RealCause`: upstream `twins`, `lalonde_cps`, `lalonde_psid` sample-файлы

## Почему именно этот набор

Он дает лучший локальный signal/compute ratio:
- реальные semi-synthetic корпуса для estimation
- сильные symbolic / transport / missing / reproducibility контуры
- lightweight discovery sanity checks (`Sachs`, `Tuebingen`)
- end-to-end capability demos

Это хороший локальный evidence pack для claims уровня:
- система сильна как symbolic causal engine
- estimation pipeline работает на реальных benchmark-корпусах
- выводы воспроизводимы и аудируемы

## Что не стоит обещать только по этому пакету

Этот профиль не равен full publication-grade SOTA claim:
- нет полного ACIC/LBIDD корпуса
- нет тяжелого external comparator stack (`econml`, `y0`, `dowhy`, `BART`)
- нет cloud-scale discovery run

Для максимально сильного research claim нужен отдельный `acceptance` прогон с полными датасетами и reference comparators.

## Команды

Подготовить данные:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
python3 benchmarks/prepare_real_benchmark_data.py --profile air-m2
```

Прогнать локальный evidence profile:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
bash benchmarks/run_local_sota_profile.sh --profile air-m2
```

Расширенный профиль:

```bash
cd /Users/deniskopylov/polisyos/policy-engine
bash benchmarks/run_local_sota_profile.sh --profile extended
```

## Где лежат результаты

- benchmark JSON: `benchmarks/_reports/`
- local summary: `benchmarks/_reports/local_sota_<profile>/local_sota_summary.json`
- data manifest: `data/raw/benchmarks/local_real/manifest.json`

## Источники

- ACIC sample: [IBM causallib](https://github.com/IBM/causallib/tree/master/causallib/datasets/data/acic_challenge_2016)
- LBIDD sample: [IBM Causal Inference Benchmarking Framework](https://github.com/IBM-HRL-MLHLS/IBM-Causal-Inference-Benchmarking-Framework/tree/master/data/LBIDD)
- RealCause datasets: [realcause](https://github.com/bradyneal/realcause/tree/master/realcause_datasets)
