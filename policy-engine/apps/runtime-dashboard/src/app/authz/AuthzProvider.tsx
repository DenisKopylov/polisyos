import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
} from "react";

import { useAuthMe } from "@/api/hooks/useAuthMe";
import {
  type PermissionKey,
  WORKSPACE_PERMISSIONS,
} from "@/app/authz/permissions";
import type { WorkspaceKey } from "@/app/workspaces";

type AuthzContextValue = {
  can: (permission: PermissionKey) => boolean;
  decision: AuthzDecision;
  hasRole: (role: string) => boolean;
  isWorkspaceAllowed: (workspaceKey: WorkspaceKey) => boolean;
  permissions: Set<string>;
  roles: Set<string>;
  status: "error" | "loading" | "ready";
  user: ReturnType<typeof useAuthMe>["data"];
};

const verifiedAuthzDecisionBrand: unique symbol = Symbol(
  "verified-authz-decision",
);

type UnknownAuthzDecision = Readonly<{
  kind: "unknown";
}>;

export type VerifiedAuthzDecision = Readonly<{
  [verifiedAuthzDecisionBrand]: true;
  can: (permission: PermissionKey) => boolean;
  isWorkspaceAllowed: (workspaceKey: WorkspaceKey) => boolean;
  kind: "verified";
}>;

export type AuthzDecision = UnknownAuthzDecision | VerifiedAuthzDecision;

const UNKNOWN_AUTHZ_DECISION: UnknownAuthzDecision = Object.freeze({
  kind: "unknown",
});

function issueVerifiedAuthzDecision(
  can: VerifiedAuthzDecision["can"],
  isWorkspaceAllowed: VerifiedAuthzDecision["isWorkspaceAllowed"],
): VerifiedAuthzDecision {
  return Object.freeze({
    [verifiedAuthzDecisionBrand]: true as const,
    can,
    isWorkspaceAllowed,
    kind: "verified",
  });
}

const AuthzContext = createContext<AuthzContextValue | null>(null);

export function AuthzProvider({ children }: PropsWithChildren) {
  const authMeQuery = useAuthMe();
  const identityReady =
    authMeQuery.isSuccess && !authMeQuery.isFetching && !!authMeQuery.data;
  const identityStatus: AuthzContextValue["status"] = authMeQuery.isError
    ? "error"
    : identityReady
      ? "ready"
      : "loading";
  const user = identityReady ? authMeQuery.data : undefined;
  const permissions = useMemo(
    () => new Set(user?.permissions ?? []),
    [user?.permissions],
  );
  const roles = useMemo(() => new Set(user?.roles ?? []), [user?.roles]);

  const value = useMemo<AuthzContextValue>(() => {
    const can: AuthzContextValue["can"] = (permission) =>
      permissions.has(permission);
    const isWorkspaceAllowed: AuthzContextValue["isWorkspaceAllowed"] = (
      workspaceKey,
    ) => {
      if (identityStatus !== "ready") {
        return false;
      }
      const permission = WORKSPACE_PERMISSIONS[workspaceKey];
      return permission ? permissions.has(permission) : true;
    };
    return {
      can,
      decision:
        identityStatus === "ready"
          ? issueVerifiedAuthzDecision(can, isWorkspaceAllowed)
          : UNKNOWN_AUTHZ_DECISION,
      hasRole: (role) => roles.has(role),
      isWorkspaceAllowed,
      permissions,
      roles,
      status: identityStatus,
      user,
    };
  }, [identityStatus, permissions, roles, user]);

  return (
    <AuthzContext.Provider value={value}>{children}</AuthzContext.Provider>
  );
}

export function useAuthz() {
  const context = useContext(AuthzContext);
  if (!context) {
    throw new Error("useAuthz must be used within an AuthzProvider");
  }
  return context;
}

export function useMaybeAuthz() {
  return useContext(AuthzContext);
}

export function useAuthzDecision(): AuthzDecision {
  return useContext(AuthzContext)?.decision ?? UNKNOWN_AUTHZ_DECISION;
}

export function usePermission(permission: PermissionKey) {
  const { can } = useAuthz();
  return can(permission);
}

export function useReviewCollaborationEnabled() {
  const authz = useAuthz();
  return (
    authz.status === "ready" &&
    authz.user?.feature_overrides?.enableReviewCollaboration === true
  );
}
