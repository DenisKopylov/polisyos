import {
  forwardRef,
  type ButtonHTMLAttributes,
  type MouseEvent,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type ToggleButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "children"
> & {
  icon?: ReactNode;
  label: ReactNode;
  onPressedChange?: (nextPressed: boolean) => void;
  pressed: boolean;
  size?: "md" | "sm";
  tone?: "default" | "rail";
  trailing?: ReactNode;
};

const ToggleButton = forwardRef<HTMLButtonElement, ToggleButtonProps>(
  (
    {
      className,
      icon,
      label,
      onClick,
      onPressedChange,
      pressed,
      size = "md",
      tone = "default",
      trailing,
      type = "button",
      ...props
    },
    ref,
  ) => {
    function handleClick(event: MouseEvent<HTMLButtonElement>) {
      onClick?.(event);
      if (!event.defaultPrevented) {
        onPressedChange?.(!pressed);
      }
    }

    return (
      <button
        {...props}
        ref={ref}
        type={type}
        aria-pressed={pressed}
        data-pressed={pressed ? "true" : "false"}
        className={cn(
          "atlas-toggle-button",
          tone === "rail" && "atlas-toggle-button--rail",
          size === "sm" && "atlas-toggle-button--sm",
          className,
        )}
        onClick={handleClick}
      >
        {icon ? (
          <span className="atlas-toggle-button__icon" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <span className="atlas-toggle-button__label">{label}</span>
        {trailing ? (
          <span className="atlas-toggle-button__trailing">{trailing}</span>
        ) : null}
      </button>
    );
  },
);
ToggleButton.displayName = "ToggleButton";

export { ToggleButton };
