import type { PropsWithChildren, ReactNode } from "react";
import { Component } from "react";
import { useLocation, useMatches } from "react-router-dom";

import { useI18n } from "@/shared/i18n/LocaleProvider";
import { useTelemetry } from "@/shared/telemetry/TelemetryProvider";
import { useLogger } from "@/shared/telemetry/logger";
import { Button } from "@polisyos/atlas-ui";

type ErrorBoundaryProps = PropsWithChildren<{
  fallback:
    | ReactNode
    | ((props: { resetErrorBoundary: () => void }) => ReactNode);
  onError?: (error: unknown) => void;
  onReset?: () => void;
  resetKeys?: unknown[];
}>;

type ErrorBoundaryState = {
  hasError: boolean;
};

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  override componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (
      this.state.hasError &&
      !areResetKeysEqual(prevProps.resetKeys, this.props.resetKeys)
    ) {
      this.setState({ hasError: false });
    }
  }

  override componentDidCatch(error: unknown) {
    console.error(error);
    this.props.onError?.(error);
  }

  resetErrorBoundary = () => {
    this.props.onReset?.();
    this.setState({ hasError: false });
  };

  override render() {
    if (this.state.hasError) {
      if (typeof this.props.fallback === "function") {
        return this.props.fallback({
          resetErrorBoundary: this.resetErrorBoundary,
        });
      }
      return this.props.fallback;
    }
    return this.props.children;
  }
}

function areResetKeysEqual(
  previous: unknown[] | undefined,
  next: unknown[] | undefined,
) {
  if (previous === next) {
    return true;
  }
  if (!previous || !next || previous.length !== next.length) {
    return false;
  }
  return previous.every((value, index) => Object.is(value, next[index]));
}

function ErrorFallback({ title, body }: { title: string; body: string }) {
  return (
    <div className="border-danger/20 bg-danger/5 text-danger rounded-3xl border p-5 text-sm">
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mt-2 max-w-2xl">{body}</p>
    </div>
  );
}

export function PageErrorBoundary({
  children,
  resetKey,
  title,
  body,
}: PropsWithChildren<{
  resetKey?: string;
  title: string;
  body: string;
}>) {
  const { track } = useTelemetry();
  const logger = useLogger();

  return (
    <ErrorBoundary
      fallback={<ErrorFallback title={title} body={body} />}
      onError={(error) => {
        logger.error({
          error,
          event: "ui.error.page",
          message: title,
          tags: {
            boundary: "page",
          },
        });
        track("ui.error.page", {
          message: error instanceof Error ? error.message : "unknown",
          title,
        });
      }}
      resetKeys={resetKey ? [resetKey] : undefined}
    >
      {children}
    </ErrorBoundary>
  );
}

export function PanelErrorBoundary({
  children,
  resetKey,
  title,
  body,
}: PropsWithChildren<{
  resetKey?: string;
  title: string;
  body: string;
}>) {
  const { track } = useTelemetry();
  const logger = useLogger();

  return (
    <ErrorBoundary
      fallback={
        <div className="border-danger/20 bg-danger/5 text-danger rounded-2xl border p-4 text-sm">
          <p className="font-semibold">{title}</p>
          <p className="mt-1">{body}</p>
        </div>
      }
      onError={(error) => {
        logger.error({
          error,
          event: "ui.error.panel",
          message: title,
          tags: {
            boundary: "panel",
          },
        });
        track("ui.error.panel", {
          message: error instanceof Error ? error.message : "unknown",
          title,
        });
      }}
      resetKeys={resetKey ? [resetKey] : undefined}
    >
      {children}
    </ErrorBoundary>
  );
}

type RouteHandleMeta = {
  routeId?: string;
  workspaceKey?: string;
};

function resolveFeatureBoundaryMeta(matches: ReturnType<typeof useMatches>) {
  const currentMatch = matches[matches.length - 1];
  const handle =
    typeof currentMatch?.handle === "object" && currentMatch.handle
      ? (currentMatch.handle as RouteHandleMeta)
      : null;

  return {
    routeId: typeof handle?.routeId === "string" ? handle.routeId : "unknown",
    workspace:
      typeof handle?.workspaceKey === "string"
        ? handle.workspaceKey
        : "unknown",
  };
}

export function FeatureErrorBoundary({
  children,
  feature,
  title,
  body,
  onReset,
  resetKeys,
}: PropsWithChildren<{
  feature: string;
  title: string;
  body: string;
  onReset?: () => void;
  resetKeys?: unknown[];
}>) {
  const location = useLocation();
  const matches = useMatches();
  const { t } = useI18n();
  const { track } = useTelemetry();
  const logger = useLogger({
    tags: {
      feature,
    },
  });
  const routeMeta = resolveFeatureBoundaryMeta(matches);

  return (
    <ErrorBoundary
      fallback={({ resetErrorBoundary }) => (
        <div className="border-danger/20 bg-danger/5 text-danger rounded-2xl border p-4 text-sm">
          <p className="font-semibold">{title}</p>
          <p className="mt-1">{body}</p>
          <div className="mt-3">
            <Button onClick={resetErrorBoundary} size="sm" variant="danger">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      )}
      onError={(error) => {
        logger.error({
          error,
          event: "ui.error.feature",
          message: title,
          tags: {
            feature,
            routeId: routeMeta.routeId,
            workspace: routeMeta.workspace,
          },
        });
        track("ui.error.feature", {
          feature,
          message: error instanceof Error ? error.message : "unknown",
          path: location.pathname,
          routeId: routeMeta.routeId,
          workspace: routeMeta.workspace,
        });
      }}
      onReset={() => {
        logger.info({
          event: "ui.error.feature.reset",
          message: `Reset feature boundary ${feature}`,
        });
        onReset?.();
      }}
      resetKeys={resetKeys}
    >
      {children}
    </ErrorBoundary>
  );
}
