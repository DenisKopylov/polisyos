import { QueryClient } from "@tanstack/react-query";

import { queryRetryDelay, shouldRetryQueryError } from "@/api/queryRetryPolicy";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: shouldRetryQueryError,
      retryDelay: queryRetryDelay,
    },
  },
});
