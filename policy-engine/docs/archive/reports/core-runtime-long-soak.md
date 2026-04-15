# Core Runtime Long Soak

- Generated at: `2026-04-15T15:15:02.740591+00:00`
- Sample every: `16` iterations
- Failures: `0`

| Scenario | Status | Iterations | Avg ms/iter | Peak KiB | Plateau |
|---|---|---:|---:|---:|---|
| `run_index_incremental_refresh` | `pass` | 192 | 9.788 | 198.06 | pass |
| `timeline_build_loops` | `pass` | 192 | 9.356 | 467.23 | pass |
| `async_cas_round_trip` | `pass` | 192 | 10.373 | 681.29 | pass |
| `async_checkpoint_restore` | `pass` | 192 | 14.090 | 281.68 | pass |
| `async_cursor_store_stream_progress` | `pass` | 192 | 14.549 | 522.72 | pass |

## Run index incremental refresh

- Status: `pass`
- Iterations: `192`
- Duration seconds: `1.8792`
- Avg ms/iter: `9.788`
- Current memory KiB: `33.75`
- Peak memory KiB: `198.06`
- Plateau: `pass` (head max `24.54` KiB, tail max `33.39` KiB, allowance `1024.0` KiB)
- Details: `{"listed_runs": 1}`

### Memory Samples

| Iteration | Current KiB | Peak KiB |
|---|---:|---:|
| 16 | 14.68 | 164.73 |
| 32 | 17.12 | 180.99 |
| 48 | 19.21 | 183.79 |
| 64 | 20.90 | 185.48 |
| 80 | 22.59 | 187.17 |
| 96 | 24.54 | 188.72 |
| 112 | 26.11 | 190.80 |
| 128 | 27.62 | 192.26 |
| 144 | 29.43 | 194.12 |
| 160 | 31.12 | 195.24 |
| 176 | 32.46 | 197.09 |
| 192 | 33.39 | 198.06 |

## Timeline query/build loops

- Status: `pass`
- Iterations: `192`
- Duration seconds: `1.7964`
- Avg ms/iter: `9.356`
- Current memory KiB: `326.27`
- Peak memory KiB: `467.23`
- Plateau: `pass` (head max `167.15` KiB, tail max `325.92` KiB, allowance `1024.0` KiB)
- Details: `{"timeline_events": 5}`

### Memory Samples

| Iteration | Current KiB | Peak KiB |
|---|---:|---:|
| 16 | 28.80 | 166.13 |
| 32 | 56.88 | 197.23 |
| 48 | 85.25 | 225.53 |
| 64 | 113.21 | 254.01 |
| 80 | 139.95 | 280.86 |
| 96 | 167.15 | 308.08 |
| 112 | 194.04 | 335.03 |
| 128 | 220.44 | 361.52 |
| 144 | 246.81 | 387.95 |
| 160 | 273.02 | 414.23 |
| 176 | 300.08 | 440.57 |
| 192 | 325.92 | 467.23 |

## Async CAS repeated round trips

- Status: `pass`
- Iterations: `192`
- Duration seconds: `1.9916`
- Avg ms/iter: `10.373`
- Current memory KiB: `68.0`
- Peak memory KiB: `681.29`
- Plateau: `pass` (head max `56.57` KiB, tail max `79.67` KiB, allowance `1024.0` KiB)
- Details: `{"concurrency": 4, "payload_bytes": 6226}`

### Memory Samples

| Iteration | Current KiB | Peak KiB |
|---|---:|---:|
| 16 | 35.30 | 505.00 |
| 32 | 39.86 | 637.94 |
| 48 | 44.15 | 653.93 |
| 64 | 47.81 | 662.05 |
| 80 | 51.38 | 662.05 |
| 96 | 56.57 | 662.05 |
| 112 | 60.22 | 674.07 |
| 128 | 63.81 | 674.07 |
| 144 | 67.33 | 674.07 |
| 160 | 70.48 | 674.07 |
| 176 | 76.71 | 674.07 |
| 192 | 79.67 | 681.29 |

## Async checkpoint restore cycles

- Status: `pass`
- Iterations: `192`
- Duration seconds: `2.7053`
- Avg ms/iter: `14.09`
- Current memory KiB: `65.51`
- Peak memory KiB: `281.68`
- Plateau: `pass` (head max `62.83` KiB, tail max `76.87` KiB, allowance `1024.0` KiB)
- Details: `{"completed_nodes": 192, "last_sequence": 191}`

### Memory Samples

| Iteration | Current KiB | Peak KiB |
|---|---:|---:|
| 16 | 38.62 | 218.69 |
| 32 | 45.81 | 239.22 |
| 48 | 51.93 | 246.02 |
| 64 | 55.67 | 251.38 |
| 80 | 60.15 | 256.51 |
| 96 | 62.83 | 261.43 |
| 112 | 64.68 | 264.05 |
| 128 | 66.93 | 267.17 |
| 144 | 68.97 | 271.62 |
| 160 | 71.72 | 275.14 |
| 176 | 73.14 | 277.73 |
| 192 | 76.87 | 281.68 |

## Async cursor-store stream progress

- Status: `pass`
- Iterations: `192`
- Duration seconds: `2.7934`
- Avg ms/iter: `14.549`
- Current memory KiB: `94.8`
- Peak memory KiB: `522.72`
- Plateau: `pass` (head max `63.87` KiB, tail max `104.46` KiB, allowance `1024.0` KiB)
- Details: `{"last_offset": 191}`

### Memory Samples

| Iteration | Current KiB | Peak KiB |
|---|---:|---:|
| 16 | 23.49 | 436.38 |
| 32 | 31.87 | 450.06 |
| 48 | 40.55 | 458.80 |
| 64 | 47.47 | 465.67 |
| 80 | 54.15 | 472.35 |
| 96 | 63.87 | 482.13 |
| 112 | 69.53 | 487.79 |
| 128 | 75.58 | 493.78 |
| 144 | 81.70 | 499.90 |
| 160 | 87.35 | 505.61 |
| 176 | 99.27 | 517.53 |
| 192 | 104.46 | 522.72 |
