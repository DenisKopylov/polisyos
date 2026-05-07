import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type NetworkStatusSnapshot = {
  effectiveType: string | null;
  online: boolean;
  saveData: boolean;
  visibilityState: DocumentVisibilityState | "unknown";
};

type NetworkStatusContextValue = NetworkStatusSnapshot & {
  constrained: boolean;
};

const NetworkStatusContext = createContext<NetworkStatusContextValue | null>(
  null,
);

export function readNetworkStatusSnapshot(): NetworkStatusSnapshot {
  const connection =
    typeof navigator === "undefined"
      ? null
      : ((
          navigator as Navigator & {
            connection?: { effectiveType?: string; saveData?: boolean };
            mozConnection?: { effectiveType?: string; saveData?: boolean };
            webkitConnection?: { effectiveType?: string; saveData?: boolean };
          }
        ).connection ??
        (
          navigator as Navigator & {
            mozConnection?: { effectiveType?: string; saveData?: boolean };
          }
        ).mozConnection ??
        (
          navigator as Navigator & {
            webkitConnection?: { effectiveType?: string; saveData?: boolean };
          }
        ).webkitConnection ??
        null);

  return {
    effectiveType: connection?.effectiveType ?? null,
    online: typeof navigator === "undefined" ? true : navigator.onLine,
    saveData: connection?.saveData === true,
    visibilityState:
      typeof document === "undefined" ? "unknown" : document.visibilityState,
  };
}

export function isConstrainedNetwork(snapshot: NetworkStatusSnapshot) {
  return (
    !snapshot.online ||
    snapshot.saveData ||
    snapshot.effectiveType === "slow-2g" ||
    snapshot.effectiveType === "2g"
  );
}

export function shouldSkipViewportPrefetch(snapshot: NetworkStatusSnapshot) {
  return (
    isConstrainedNetwork(snapshot) || snapshot.visibilityState !== "visible"
  );
}

export function NetworkStatusProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<NetworkStatusSnapshot>(() =>
    readNetworkStatusSnapshot(),
  );

  useEffect(() => {
    const updateSnapshot = () => {
      setSnapshot(readNetworkStatusSnapshot());
    };

    const connection =
      (
        navigator as Navigator & {
          connection?: EventTarget;
          mozConnection?: EventTarget;
          webkitConnection?: EventTarget;
        }
      ).connection ??
      (navigator as Navigator & { mozConnection?: EventTarget })
        .mozConnection ??
      (navigator as Navigator & { webkitConnection?: EventTarget })
        .webkitConnection ??
      null;

    window.addEventListener("online", updateSnapshot);
    window.addEventListener("offline", updateSnapshot);
    document.addEventListener("visibilitychange", updateSnapshot);
    connection?.addEventListener?.("change", updateSnapshot);

    return () => {
      window.removeEventListener("online", updateSnapshot);
      window.removeEventListener("offline", updateSnapshot);
      document.removeEventListener("visibilitychange", updateSnapshot);
      connection?.removeEventListener?.("change", updateSnapshot);
    };
  }, []);

  const value = useMemo<NetworkStatusContextValue>(
    () => ({
      ...snapshot,
      constrained: isConstrainedNetwork(snapshot),
    }),
    [snapshot],
  );

  return (
    <NetworkStatusContext.Provider value={value}>
      {children}
    </NetworkStatusContext.Provider>
  );
}

export function useNetworkStatus() {
  const context = useContext(NetworkStatusContext);
  if (!context) {
    throw new Error(
      "useNetworkStatus must be used within a NetworkStatusProvider",
    );
  }
  return context;
}

export function useMaybeNetworkStatus() {
  return useContext(NetworkStatusContext);
}
