import { useEffect } from "react";
import {
  type DefaultError,
  type QueryKey,
  type UseQueryOptions,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { hasOwnerAsOf } from "@/api/cacheDiscipline";

type OwnerAsOfData = Readonly<{ packet: Readonly<{ as_of: unknown }> }>;

export type GovernedQueryPolicy =
  | Readonly<{ kind: "owner_as_of" }>
  | Readonly<{ kind: "never_cache_authority" }>
  | Readonly<{ kind: "operational" }>;

type QueryOptions<TData, TQueryKey extends QueryKey> = UseQueryOptions<
  TData,
  DefaultError,
  TData,
  TQueryKey
>;

type OwnerAsOfQueryOptions<TData extends OwnerAsOfData, TQueryKey extends QueryKey> =
  Omit<QueryOptions<TData, TQueryKey>, "initialData" | "placeholderData"> &
    Readonly<{ initialData?: never; placeholderData?: never }>;

type NeverCacheQueryOptions<TData, TQueryKey extends QueryKey> = Omit<
  QueryOptions<TData, TQueryKey>,
  "gcTime" | "initialData" | "placeholderData" | "staleTime"
> &
  Readonly<{
    gcTime?: never;
    initialData?: never;
    placeholderData?: never;
    staleTime?: never;
  }>;

const governedQueryOptionsBrand: unique symbol = Symbol("governed-query-options");

type IssuedBase<
  TData,
  TQueryKey extends QueryKey = QueryKey,
> = QueryOptions<TData, TQueryKey> &
  Readonly<{
    policy: GovernedQueryPolicy;
    readonly [governedQueryOptionsBrand]: true;
  }>;

type OwnerAsOfIssuedOptions<TData, TQueryKey extends QueryKey> = Readonly<
  Omit<IssuedBase<TData, TQueryKey>, "initialData" | "placeholderData" | "policy"> & {
    initialData?: never;
    placeholderData?: never;
    policy: Readonly<{ kind: "owner_as_of" }>;
  }
>;

type NeverCacheIssuedOptions<TData, TQueryKey extends QueryKey> = Readonly<
  Omit<
    IssuedBase<TData, TQueryKey>,
    "gcTime" | "initialData" | "placeholderData" | "policy" | "staleTime"
  > & {
    gcTime: 0;
    initialData?: never;
    placeholderData?: never;
    policy: Readonly<{ kind: "never_cache_authority" }>;
    staleTime: 0;
  }
>;

type OperationalIssuedOptions<TData, TQueryKey extends QueryKey> = Readonly<
  Omit<IssuedBase<TData, TQueryKey>, "policy"> & {
    policy: Readonly<{ kind: "operational" }>;
  }
>;

export type GovernedQueryOptions<TData, TQueryKey extends QueryKey = QueryKey> =
  | OwnerAsOfIssuedOptions<TData, TQueryKey>
  | NeverCacheIssuedOptions<TData, TQueryKey>
  | OperationalIssuedOptions<TData, TQueryKey>;

function issueGovernedOptions(options: Record<PropertyKey, unknown>): unknown {
  Object.defineProperty(options, governedQueryOptionsBrand, {
    enumerable: false,
    value: true,
  });
  return Object.freeze(options);
}

function hasOwnerPacketAsOf(data: unknown): boolean {
  if (typeof data !== "object" || data === null) {
    return false;
  }
  const packet = (data as Readonly<{ packet?: unknown }>).packet;
  return (
    typeof packet === "object" &&
    packet !== null &&
    hasOwnerAsOf((packet as Readonly<{ as_of?: unknown }>).as_of)
  );
}

function assertNoRetainedAuthorityFields(options: QueryOptions<unknown, QueryKey>) {
  if (options.gcTime === Infinity || options.staleTime === Infinity) {
    throw new TypeError("governed query policy forbids infinite retention");
  }
  if (options.initialData !== undefined) {
    throw new TypeError("governed query policy forbids initialData");
  }
  if (options.placeholderData !== undefined) {
    throw new TypeError("governed query policy forbids placeholderData");
  }
}

/** Prepare owner-bound, never-cache, or operational options for the governed hook. */
export function governedQueryOptions<
  TData extends OwnerAsOfData,
  TQueryKey extends QueryKey,
>(
  options: OwnerAsOfQueryOptions<TData, TQueryKey>,
  policy: Readonly<{ kind: "owner_as_of" }>,
): OwnerAsOfIssuedOptions<TData, TQueryKey>;
export function governedQueryOptions<TData, TQueryKey extends QueryKey>(
  options: NeverCacheQueryOptions<TData, TQueryKey>,
  policy: Readonly<{ kind: "never_cache_authority" }>,
): NeverCacheIssuedOptions<TData, TQueryKey>;
export function governedQueryOptions<TData, TQueryKey extends QueryKey>(
  options: QueryOptions<TData, TQueryKey>,
  policy: Readonly<{ kind: "operational" }>,
): OperationalIssuedOptions<TData, TQueryKey>;
export function governedQueryOptions(
  options: unknown,
  policy: GovernedQueryPolicy,
): unknown {
  const supplied = options as QueryOptions<unknown, QueryKey>;
  const queryFn = supplied.queryFn;
  if (typeof queryFn !== "function") {
    throw new TypeError("governed query policy requires queryFn");
  }
  if (policy.kind !== "operational") {
    assertNoRetainedAuthorityFields(supplied);
  }

  return issueGovernedOptions({
    ...supplied,
    [governedQueryOptionsBrand]: true,
    ...(policy.kind === "never_cache_authority"
      ? {
          gcTime: 0,
          initialData: undefined,
          placeholderData: undefined,
          staleTime: 0,
        }
      : {}),
    policy,
    queryFn: async (...args: Parameters<typeof queryFn>) => {
      const data = await queryFn(...args);
      if (policy.kind === "owner_as_of" && !hasOwnerPacketAsOf(data)) {
        throw new TypeError("governed query response lacks a valid packet as_of");
      }
      return data;
    },
  });
}

/** Execute branded governed options and erase never-cache authority data on loss. */
export function useGovernedQuery<TData, TQueryKey extends QueryKey>(
  options: GovernedQueryOptions<TData, TQueryKey>,
) {
  if (!options[governedQueryOptionsBrand]) {
    throw new TypeError("governed query options are unissued");
  }
  const queryClient = useQueryClient();
  const query = useQuery(options);

  useEffect(() => {
    if (
      options.policy.kind === "never_cache_authority" &&
      (query.isPaused || query.isRefetchError)
    ) {
      queryClient.removeQueries({ exact: true, queryKey: options.queryKey });
    }
  }, [options.policy.kind, options.queryKey, query.isPaused, query.isRefetchError, queryClient]);

  return query;
}
