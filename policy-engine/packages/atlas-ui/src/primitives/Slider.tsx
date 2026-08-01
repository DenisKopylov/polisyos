import { forwardRef } from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "../lib/cn";

type SliderProps = React.ComponentPropsWithoutRef<
  typeof SliderPrimitive.Root
> & {
  /** Optional CSS gradient for the track (used for sensitivity zones). */
  trackGradient?: string;
  /** Accessible name overrides for generated thumbs. */
  thumbLabels?: string[];
};

const Slider = forwardRef<
  React.ComponentRef<typeof SliderPrimitive.Root>,
  SliderProps
>(({ className, trackGradient, thumbLabels, ...props }, ref) => {
  const thumbCount = (props.value ?? props.defaultValue ?? [0]).length;
  const rootLabel = props["aria-label"];
  const rootLabelledBy = props["aria-labelledby"];

  return (
    <SliderPrimitive.Root
      ref={ref}
      className={cn(
        "relative flex w-full touch-none items-center select-none",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track
        className="bg-line relative h-2 w-full grow overflow-hidden rounded-full"
        style={trackGradient ? { background: trackGradient } : undefined}
      >
        <SliderPrimitive.Range className="absolute h-full bg-[var(--chart-primary)]" />
      </SliderPrimitive.Track>
      {Array.from({ length: thumbCount }).map((_, index) => (
        <SliderPrimitive.Thumb
          key={index}
          aria-label={
            thumbLabels?.[index] ??
            (thumbCount === 1 && typeof rootLabel === "string"
              ? rootLabel
              : undefined)
          }
          aria-labelledby={thumbLabels?.[index] ? undefined : rootLabelledBy}
          className="border-border bg-surface focus-visible:ring-ring block size-5 rounded-full border-2 shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
        />
      ))}
    </SliderPrimitive.Root>
  );
});

Slider.displayName = "Slider";

export { Slider };
