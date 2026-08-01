import { useQuery, type UseQueryOptions } from "@tanstack/react-query";

import {
  temporalScopeKey,
  type TemporalScope,
} from "@/shared/lib/domain/temporal";
import { useMaybeTemporalCursor } from "@/shared/ui/temporal/TemporalRuntimeBridge";

type TemporalQueryOptions<TData, TError> = Omit<
  UseQueryOptions<TData, TError>,
  "queryKey"
> & {
  queryKey: readonly unknown[];
  temporalScope?: TemporalScope | null;
};

export function useTemporalQuery<TData, TError = Error>({
  queryKey,
  temporalScope,
  ...options
}: TemporalQueryOptions<TData, TError>) {
  const cursor = useMaybeTemporalCursor();
  const scope = temporalScope ?? cursor?.committedScope ?? null;
  return useQuery({
    ...options,
    queryKey: [...queryKey, { temporal: temporalScopeKey(scope) }],
  });
}
