import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useLiveAnnouncer } from "@/app/providers/LiveAnnouncerProvider";
import { Button } from "@/shared/ui";

export type ToastTone = "error" | "info" | "success" | "warning";

export type ToastInput = {
  title: string;
  description?: string;
  durationMs?: number;
  tone?: ToastTone;
};

type ToastRecord = ToastInput & {
  id: string;
};

type ToastContextValue = {
  dismissToast: (id: string) => void;
  pushToast: (toast: ToastInput) => string;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const toneClassName: Record<ToastTone, string> = {
  error: "border-danger/30 bg-danger/10 text-danger",
  info: "border-line bg-panel text-text",
  success:
    "border-[color-mix(in_srgb,var(--color-status-approved)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-status-approved)_12%,transparent)] text-[var(--color-status-approved)]",
  warning:
    "border-[color-mix(in_srgb,var(--color-status-pending)_35%,transparent)] bg-[color-mix(in_srgb,var(--color-status-pending)_12%,transparent)] text-[var(--color-status-pending)]",
};

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const { announce } = useLiveAnnouncer();

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: ToastInput) => {
      const nextToast: ToastRecord = {
        durationMs: 4_500,
        tone: "info",
        ...toast,
        id: `toast-${Date.now()}-${Math.round(Math.random() * 10_000)}`,
      };
      setToasts((current) => [...current, nextToast]);
      announce(
        toast.description ? `${toast.title}. ${toast.description}` : toast.title,
        toast.tone === "error" ? "assertive" : "polite",
      );
      return nextToast.id;
    },
    [announce],
  );

  useEffect(() => {
    if (toasts.length === 0) {
      return;
    }
    const timers = toasts.map((toast) =>
      window.setTimeout(() => dismissToast(toast.id), toast.durationMs),
    );
    return () => {
      for (const timer of timers) {
        window.clearTimeout(timer);
      }
    };
  }, [dismissToast, toasts]);

  const value = useMemo<ToastContextValue>(
    () => ({
      dismissToast,
      pushToast,
    }),
    [dismissToast, pushToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-label="Notifications"
        className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-3"
      >
        {toasts.map((toast) => (
          <section
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className={`pointer-events-auto rounded-[var(--radius-card)] border px-4 py-3 shadow-panel ${toneClassName[toast.tone ?? "info"]}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{toast.title}</p>
                {toast.description ? (
                  <p className="mt-1 text-sm opacity-90">{toast.description}</p>
                ) : null}
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => dismissToast(toast.id)}
              >
                Close
              </Button>
            </div>
          </section>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
