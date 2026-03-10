import type { ReactNode } from "react";

import { ApiErrorAlert } from "@/shared/ui/ApiErrorAlert";

type QueryLike = {
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
};

type AsyncSectionProps = {
  query: QueryLike;
  loading?: ReactNode;
  errorTitle?: string;
  empty?: boolean;
  emptyState?: ReactNode;
  children: ReactNode;
};

export function AsyncSection({
  children,
  empty = false,
  emptyState = null,
  errorTitle,
  loading = null,
  query,
}: AsyncSectionProps) {
  if (query.isLoading) {
    return <>{loading}</>;
  }
  if (query.isError) {
    return <ApiErrorAlert title={errorTitle} error={query.error} />;
  }
  if (empty) {
    return <>{emptyState}</>;
  }
  return <>{children}</>;
}
