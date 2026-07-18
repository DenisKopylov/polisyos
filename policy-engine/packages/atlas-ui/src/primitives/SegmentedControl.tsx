import { type InputHTMLAttributes, type ReactNode, useId } from "react";

import { cn } from "../lib/cn";

export type SegmentedOption<T extends string> = {
  description?: ReactNode;
  disabled?: boolean;
  icon?: ReactNode;
  label: ReactNode;
  testId?: string;
  value: T;
};

type SegmentedControlProps<T extends string> = {
  ariaLabel?: string;
  ariaLabelledBy?: string;
  className?: string;
  layout?: "grid" | "wrap";
  name?: string;
  onValueChange: (value: T) => void;
  options: readonly SegmentedOption<T>[];
  optionClassName?: string;
  size?: "md" | "sm";
  tone?: "default" | "rail";
  value: T;
} & Omit<
  InputHTMLAttributes<HTMLInputElement>,
  | "aria-label"
  | "aria-labelledby"
  | "checked"
  | "className"
  | "defaultChecked"
  | "name"
  | "onChange"
  | "size"
  | "type"
  | "value"
>;

export function SegmentedControl<T extends string>({
  ariaLabel,
  ariaLabelledBy,
  className,
  disabled,
  layout = "grid",
  name,
  onValueChange,
  options,
  optionClassName,
  size = "md",
  tone = "default",
  value,
  ...inputProps
}: SegmentedControlProps<T>) {
  const fallbackName = useId();
  const groupName = name ?? fallbackName;

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      aria-labelledby={ariaLabelledBy}
      className={cn(
        "atlas-segmented",
        layout === "wrap" && "atlas-segmented--wrap",
        tone === "rail" && "atlas-segmented--rail",
        size === "sm" && "atlas-segmented--sm",
        className,
      )}
    >
      {options.map((option) => {
        const optionId = `${groupName}-${option.value}`;
        const checked = value === option.value;
        const optionDisabled = disabled || option.disabled;

        return (
          <label
            key={option.value}
            htmlFor={optionId}
            className={cn(
              "atlas-segmented__option",
              optionDisabled && "atlas-segmented__option--disabled",
              optionClassName,
            )}
            data-selected={checked ? "true" : "false"}
            data-disabled={optionDisabled ? "true" : "false"}
            data-testid={option.testId}
          >
            <input
              {...inputProps}
              id={optionId}
              type="radio"
              name={groupName}
              value={option.value}
              checked={checked}
              disabled={optionDisabled}
              onChange={() => onValueChange(option.value)}
              className="sr-only"
            />
            {option.icon ? (
              <span className="atlas-segmented__icon" aria-hidden="true">
                {option.icon}
              </span>
            ) : null}
            <span className="atlas-segmented__body">
              <span className="atlas-segmented__label">{option.label}</span>
              {option.description ? (
                <span className="atlas-segmented__description">
                  {option.description}
                </span>
              ) : null}
            </span>
          </label>
        );
      })}
    </div>
  );
}
