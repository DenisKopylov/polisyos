import type { ReactNode } from "react";
import { Suspense } from "react";
import { QueryErrorResetBoundary } from "@tanstack/react-query";

import { FeatureErrorBoundary } from "@/shared/components/ErrorBoundary";

type FeatureAsyncBoundaryProps = {
  feature: string;
  title: string;
  body: string;
  loading: ReactNode;
  resetKeys?: unknown[];
  children: ReactNode;
};

export function FeatureAsyncBoundary({
  children,
  feature,
  title,
  body,
  loading,
  resetKeys,
}: FeatureAsyncBoundaryProps) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <FeatureErrorBoundary
          feature={feature}
          title={title}
          body={body}
          onReset={reset}
          resetKeys={resetKeys}
        >
          <Suspense fallback={loading}>{children}</Suspense>
        </FeatureErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  );
}
