import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { Button } from "@/shared/ui";

export type ConfirmDialogOptions = {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "primary";
};

type PendingDialogState = ConfirmDialogOptions & {
  resolve: (value: boolean) => void;
};

type AlertDialogContextValue = {
  confirm: (options: ConfirmDialogOptions) => Promise<boolean>;
};

const AlertDialogContext = createContext<AlertDialogContextValue | null>(null);

function AlertDialogSurface({
  onCancel,
  onConfirm,
  pending,
}: {
  onCancel: () => void;
  onConfirm: () => void;
  pending: PendingDialogState;
}) {
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const focusable = [cancelRef.current, confirmRef.current].filter(
        Boolean,
      ) as HTMLElement[];
      const currentIndex = focusable.findIndex(
        (element) => element === document.activeElement,
      );
      if (focusable.length === 0) {
        return;
      }
      if (event.shiftKey && currentIndex <= 0) {
        event.preventDefault();
        focusable[focusable.length - 1]?.focus();
      } else if (!event.shiftKey && currentIndex === focusable.length - 1) {
        event.preventDefault();
        focusable[0]?.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onCancel]);

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/35 p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={pending.description ? descriptionId : undefined}
        className="border-line bg-panel shadow-panel w-full max-w-lg rounded-[var(--radius-panel)] border p-6"
      >
        <h2 id={titleId} className="text-xl font-semibold">
          {pending.title}
        </h2>
        {pending.description ? (
          <p id={descriptionId} className="text-muted mt-2 text-sm">
            {pending.description}
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button
            ref={cancelRef}
            type="button"
            variant="ghost"
            onClick={onCancel}
          >
            {pending.cancelLabel ?? "Cancel"}
          </Button>
          <Button
            ref={confirmRef}
            type="button"
            variant={pending.tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
          >
            {pending.confirmLabel ?? "Confirm"}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

export function AlertDialogProvider({ children }: PropsWithChildren) {
  const [pending, setPending] = useState<PendingDialogState | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const confirm = useCallback((options: ConfirmDialogOptions) => {
    triggerRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    return new Promise<boolean>((resolve) => {
      setPending({
        ...options,
        resolve,
      });
    });
  }, []);

  const resolvePending = useCallback((value: boolean) => {
    setPending((current) => {
      current?.resolve(value);
      return null;
    });
    triggerRef.current?.focus();
  }, []);

  const value = useMemo<AlertDialogContextValue>(
    () => ({
      confirm,
    }),
    [confirm],
  );

  return (
    <AlertDialogContext.Provider value={value}>
      {children}
      {pending ? (
        <AlertDialogSurface
          pending={pending}
          onCancel={() => resolvePending(false)}
          onConfirm={() => resolvePending(true)}
        />
      ) : null}
    </AlertDialogContext.Provider>
  );
}

export function useAlertDialog() {
  const context = useContext(AlertDialogContext);
  if (!context) {
    throw new Error("useAlertDialog must be used within AlertDialogProvider");
  }
  return context;
}
