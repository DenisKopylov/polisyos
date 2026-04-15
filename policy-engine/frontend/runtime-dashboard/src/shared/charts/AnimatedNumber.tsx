import { useEffect, useRef, useState } from "react";
import { animate, useReducedMotion } from "motion/react";

import { cn, formatNumber } from "@/lib/utils";

type AnimatedNumberProps = {
  value: number;
  formatOptions?: Intl.NumberFormatOptions;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
};

export function AnimatedNumber({
  value,
  formatOptions,
  duration = 0.6,
  prefix = "",
  suffix = "",
  className,
}: AnimatedNumberProps) {
  const prefersReduced = useReducedMotion();
  const nodeRef = useRef<HTMLSpanElement>(null);
  const prevValue = useRef(0);
  const [display, setDisplay] = useState(() =>
    formatNumber(value, formatOptions),
  );

  useEffect(() => {
    if (prefersReduced || !nodeRef.current) {
      setDisplay(formatNumber(value, formatOptions));
      prevValue.current = value;
      return;
    }

    const from = prevValue.current;
    prevValue.current = value;

    const controls = animate(from, value, {
      duration,
      ease: [0.2, 0, 0, 1],
      onUpdate(v) {
        setDisplay(formatNumber(v, formatOptions));
      },
    });

    return () => controls.stop();
  }, [value, duration, formatOptions, prefersReduced]);

  return (
    <span
      ref={nodeRef}
      className={cn("tabular-nums", className)}
      aria-live="polite"
      aria-atomic="true"
    >
      {prefix}
      {display}
      {suffix}
    </span>
  );
}
