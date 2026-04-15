import type { ReactNode } from "react";
import { Suspense } from "react";
import { useLocation } from "react-router-dom";

import { useCapabilities } from "@/api/hooks/useCapabilities";
import { useMaybeAuthz } from "@/app/authz/AuthzProvider";
import { useFeatureFlags } from "@/app/providers/FeatureFlagProvider";
import {
  WORKSPACES,
  type WorkspaceKey,
  type WorkspaceLayout,
} from "@/app/workspaces";
import { useI18n } from "@/i18n/LocaleProvider";
import { isCapabilityEnabled } from "@/lib/capabilities";
import { PageErrorBoundary } from "@/shared/components/ErrorBoundary";
import { Card, EmptyState, PageSkeleton } from "@/shared/ui";

type WorkspaceBoundaryProps = {
  workspaceKey: WorkspaceKey;
  children: ReactNode;
};

const workspaceLayoutClassName: Record<WorkspaceLayout, string> = {
  overview: "workspace-frame workspace-frame--overview",
  form: "workspace-frame workspace-frame--form",
  "master-detail": "workspace-frame workspace-frame--master-detail",
  "full-width": "workspace-frame workspace-frame--full-width",
  chat: "workspace-frame workspace-frame--chat",
};

function WorkspaceContentFrame({
  children,
  layout,
}: {
  children: ReactNode;
  layout: WorkspaceLayout;
}) {
  return (
    <div
      className={workspaceLayoutClassName[layout]}
      data-workspace-layout={layout}
    >
      {children}
    </div>
  );
}

export function WorkspaceBoundary({
  children,
  workspaceKey,
}: WorkspaceBoundaryProps) {
  const location = useLocation();
  const { t } = useI18n();
  const capabilitiesQuery = useCapabilities();
  const authz = useMaybeAuthz();
  const { flags } = useFeatureFlags();

  const workspace = WORKSPACES[workspaceKey];
  const workspaceEnabled = workspace.featureFlag
    ? flags[workspace.featureFlag]
    : true;
  const workspaceAllowed = authz
    ? authz.isWorkspaceAllowed(workspaceKey)
    : true;
  const missingCapabilities = workspace.requiredCapabilities.filter(
    (capability) => !isCapabilityEnabled(capabilitiesQuery.data, capability),
  );

  if (!workspaceEnabled) {
    return (
      <Card>
        <EmptyState
          title={t("common.unavailable")}
          body={t("shell.header.workspaceDisabled")}
        />
      </Card>
    );
  }

  if (!workspaceAllowed) {
    return (
      <Card>
        <EmptyState
          title={t("common.unavailable")}
          body={t("shell.header.workspaceAccessDenied")}
        />
      </Card>
    );
  }

  if (!capabilitiesQuery.isLoading && missingCapabilities.length > 0) {
    return (
      <Card>
        <EmptyState
          title={t("common.unavailable")}
          body={`Required runtime capabilities are disabled: ${missingCapabilities.join(", ")}`}
        />
      </Card>
    );
  }

  return (
    <PageErrorBoundary
      resetKey={location.pathname}
      title={t("common.pageErrorTitle")}
      body={t("common.pageErrorBody")}
    >
      <Suspense
        fallback={
          <WorkspaceContentFrame layout={workspace.layout}>
            <PageSkeleton />
          </WorkspaceContentFrame>
        }
      >
        <WorkspaceContentFrame layout={workspace.layout}>
          {children}
        </WorkspaceContentFrame>
      </Suspense>
    </PageErrorBoundary>
  );
}
