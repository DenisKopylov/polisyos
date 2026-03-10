import {
  createContext,
  type PropsWithChildren,
  useContext,
  useMemo,
  useSyncExternalStore,
} from "react";

import {
  clearAuthSession,
  readAuthSessionState,
  refreshAuthSession,
  setAuthAccessToken,
  subscribeAuthSession,
  type AuthSessionState,
} from "@/app/auth/authSession";

type AuthSessionContextValue = AuthSessionState & {
  clearSession: (reason?: string) => void;
  refreshSession: () => Promise<string | null>;
  setAccessToken: (accessToken: string | null) => void;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

export function AuthSessionProvider({ children }: PropsWithChildren) {
  const state = useSyncExternalStore(
    subscribeAuthSession,
    readAuthSessionState,
    readAuthSessionState,
  );

  const value = useMemo<AuthSessionContextValue>(
    () => ({
      ...state,
      clearSession: clearAuthSession,
      refreshSession: () => refreshAuthSession({ reason: "manual" }),
      setAccessToken: setAuthAccessToken,
    }),
    [state],
  );

  return (
    <AuthSessionContext.Provider value={value}>
      {children}
    </AuthSessionContext.Provider>
  );
}

export function useAuthSession() {
  const context = useContext(AuthSessionContext);
  if (!context) {
    throw new Error("useAuthSession must be used within an AuthSessionProvider");
  }
  return context;
}
