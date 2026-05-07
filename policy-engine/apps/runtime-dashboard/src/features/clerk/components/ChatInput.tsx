import {
  type KeyboardEvent,
  type SyntheticEvent,
  useRef,
  useState,
} from "react";

import { Button } from "@/shared/ui";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import { CLERK_DEFAULT_DOMAIN_HINTS } from "../domain/clerkDefaults";

type ChatInputProps = {
  onSubmit: (question: string, domainHint?: string) => void;
  disabled?: boolean;
};

export function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [domainHint, setDomainHint] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submitQuestion = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSubmit(trimmed, domainHint || undefined);
    setValue("");
    textareaRef.current?.focus();
  };

  const handleSubmit = (event: SyntheticEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitQuestion();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitQuestion();
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-b-[var(--radius-panel)] border-t border-[var(--line)] bg-[var(--panel)] px-5 py-4"
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("clerk.chatPlaceholder")}
        disabled={disabled}
        rows={3}
        className="w-full resize-none rounded-[var(--radius-card)] border border-[var(--line)] bg-[var(--surface)] px-4 py-3 text-[16px] leading-relaxed text-[var(--ink)] transition-[border-color,box-shadow] duration-[var(--motion-fast)] placeholder:text-[var(--slate)] focus:border-[var(--teal)] focus:ring-2 focus:ring-[var(--focus-ring)] focus:outline-none"
      />
      <div className="flex items-center justify-between gap-3">
        <select
          value={domainHint}
          onChange={(e) => setDomainHint(e.target.value)}
          className="rounded-[var(--radius-pill)] border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--slate)] focus:border-[var(--teal)] focus:outline-none"
        >
          <option value="">{t("clerk.chatDomainAuto")}</option>
          {CLERK_DEFAULT_DOMAIN_HINTS.map((hint) => (
            <option key={hint} value={hint}>
              {hint.charAt(0).toUpperCase() + hint.slice(1).replace("_", " ")}
            </option>
          ))}
        </select>
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={disabled || !value.trim()}
        >
          {disabled ? t("clerk.chatStreaming") : t("clerk.chatSubmit")}
        </Button>
      </div>
    </form>
  );
}
