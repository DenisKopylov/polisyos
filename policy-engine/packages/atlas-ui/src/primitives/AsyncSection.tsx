import type { ReactNode } from "react";

export type AsyncSectionQuery = {
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
};

export type AsyncSectionErrorPresentation = {
  error: unknown;
  title?: string;
};

export type AsyncSectionProps = {
  query: AsyncSectionQuery;
  loading?: ReactNode;
  errorTitle?: string;
  renderError: (presentation: AsyncSectionErrorPresentation) => ReactNode;
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
  renderError,
}: AsyncSectionProps) {
  if (query.isLoading) {
    return <>{loading}</>;
  }
  if (query.isError) {
    return <>{renderError({ error: query.error, title: errorTitle })}</>;
  }
  if (empty) {
    return <>{emptyState}</>;
  }
  return <>{children}</>;
}
