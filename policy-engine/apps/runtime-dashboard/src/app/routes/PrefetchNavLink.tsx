import type { FocusEvent, MouseEvent, TouchEvent } from "react";
import { NavLink, type NavLinkProps } from "react-router-dom";

import { type PrefetchMode, useRoutePrefetch } from "@/app/routes/PrefetchLink";

type PrefetchNavLinkProps = Omit<
  NavLinkProps,
  "onFocus" | "onMouseEnter" | "onTouchStart"
> & {
  onFocus?: NavLinkProps["onFocus"];
  onMouseEnter?: NavLinkProps["onMouseEnter"];
  onTouchStart?: NavLinkProps["onTouchStart"];
  prefetch?: PrefetchMode;
};

export function PrefetchNavLink({
  onFocus,
  onMouseEnter,
  onTouchStart,
  prefetch = "intent",
  to,
  ...props
}: PrefetchNavLinkProps) {
  const routePrefetch = useRoutePrefetch(to, prefetch);

  return (
    <NavLink
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
