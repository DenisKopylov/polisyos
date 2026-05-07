import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
} from "react";

import { FALLBACK_AUTH_ME, useAuthMe } from "@/api/hooks/useAuthMe";
import {
  type PermissionKey,
  WORKSPACE_PERMISSIONS,
} from "@/app/authz/permissions";
import type { WorkspaceKey } from "@/app/workspaces";

type AuthzContextValue = {
  can: (permission: PermissionKey) => boolean;
  hasRole: (role: string) => boolean;
  isWorkspaceAllowed: (workspaceKey: WorkspaceKey) => boolean;
  permissions: Set<string>;
  roles: Set<string>;
  status: "error" | "loading" | "ready";
  user: ReturnType<typeof useAuthMe>["data"];
};

const AuthzContext = createContext<AuthzContextValue | null>(null);

export function AuthzProvider({ children }: PropsWithChildren) {
  const authMeQuery = useAuthMe();
  const user = authMeQuery.data ?? FALLBACK_AUTH_ME;
  const permissions = useMemo(
    () => new Set(user.permissions ?? []),
    [user.permissions],
  );
  const roles = useMemo(() => new Set(user.roles ?? []), [user.roles]);

  const value = useMemo<AuthzContextValue>(
    () => ({
      can: (permission) => permissions.has(permission),
      hasRole: (role) => roles.has(role),
      isWorkspaceAllowed: (workspaceKey) => {
        const permission = WORKSPACE_PERMISSIONS[workspaceKey];
        return permission ? permissions.has(permission) : true;
      },
      permissions,
      roles,
      status: authMeQuery.isError
        ? "error"
        : authMeQuery.isLoading
          ? "loading"
          : "ready",
      user,
    }),
    [authMeQuery.isError, authMeQuery.isLoading, permissions, roles, user],
  );

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

export function usePermission(permission: PermissionKey) {
  const { can } = useAuthz();
  return can(permission);
}

export function useReviewCollaborationEnabled() {
  const authz = useAuthz();
  return authz.user?.feature_overrides?.enableReviewCollaboration === true;
}
