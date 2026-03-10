import type { FocusEvent, MouseEvent, TouchEvent } from "react";

import { type PrefetchMode, useRoutePrefetch } from "@/app/routes/PrefetchLink";
import { type ButtonProps, Button } from "@/shared/ui";

type RouterButtonProps = Extract<ButtonProps, { to: unknown }>;

type PrefetchButtonProps = Omit<
  RouterButtonProps,
  "onFocus" | "onMouseEnter" | "onTouchStart"
> & {
  onFocus?: RouterButtonProps["onFocus"];
  onMouseEnter?: RouterButtonProps["onMouseEnter"];
  onTouchStart?: RouterButtonProps["onTouchStart"];
  prefetch?: PrefetchMode;
};

export function PrefetchButton({
  onFocus,
  onMouseEnter,
  onTouchStart,
  prefetch = "intent",
  to,
  ...props
}: PrefetchButtonProps) {
  const routePrefetch = useRoutePrefetch(to, prefetch);

  return (
    <Button
      {...props}
      to={to}
      onFocus={(event: FocusEvent<HTMLAnchorElement>) => {
        routePrefetch.onFocus(event);
        onFocus?.(event);
      }}
      onMouseEnter={(event: MouseEvent<HTMLAnchorElement>) => {
        routePrefetch.onMouseEnter(event);
        onMouseEnter?.(event);
      }}
      onTouchStart={(event: TouchEvent<HTMLAnchorElement>) => {
        routePrefetch.onTouchStart(event);
        onTouchStart?.(event);
      }}
    />
  );
}
