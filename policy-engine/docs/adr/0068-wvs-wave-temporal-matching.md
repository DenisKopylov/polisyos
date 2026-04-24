# ADR-0068: WVS wave-based temporal matching find_closest_in_wave(max_distance=3)

## Status

Proposed

## Date

2026-02-28

## Context

The World Values Survey publishes data in discrete waves (e.g., Wave 6:
2010-2014, Wave 7: 2017-2022) rather than annual releases. When the scientist
workflow requests WVS data for a specific policy year, a temporal matching
strategy is needed to select the most appropriate survey wave. Exact year
matching is usually impossible because waves span multi-year fieldwork periods
and not all countries are surveyed in every wave. A closest-wave strategy with a
bounded maximum distance prevents silently using data that is too temporally
distant to be relevant.

## Decision

1. Implement `find_closest_in_wave(target_year, max_distance=3)` in the WVS
   connector that returns the wave whose midpoint year is closest to the
   target.
2. If the absolute distance between the target year and the closest wave
   midpoint exceeds `max_distance` years, the function raises a
   `TemporalMismatchError` instead of returning stale data.
3. The `max_distance` parameter defaults to 3 years and is overridable in the
   batch pipeline configuration.
4. When multiple waves are equidistant, the more recent wave is preferred.

## Consequences

### Positive

- Bounded temporal matching prevents the silent use of survey data that is
  too old to reflect current societal values, improving analysis validity.

- The `max_distance` parameter provides a tunable knob for domains where
  temporal sensitivity varies (e.g., fast-changing vs. stable indicators).

### Negative

- A strict distance bound may cause data unavailability errors for countries
  or years with sparse WVS coverage, requiring fallback strategies.

- Wave midpoint calculation is an approximation; countries surveyed at the
  start vs. end of a wave may have different effective temporal distances.
