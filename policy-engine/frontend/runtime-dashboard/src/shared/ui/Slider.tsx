import { forwardRef } from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/lib/utils";

type SliderProps = React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
  /** Optional CSS gradient for the track (used for sensitivity zones). */
  trackGradient?: string;
};

const Slider = forwardRef<
  React.ComponentRef<typeof SliderPrimitive.Root>,
  SliderProps
>(({ className, trackGradient, ...props }, ref) => (
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
      <SliderPrimitive.Range className="bg-[var(--chart-primary)] absolute h-full" />
    </SliderPrimitive.Track>
    {(props.value ?? props.defaultValue ?? [0]).map((_, i) => (
      <SliderPrimitive.Thumb
        key={i}
        className="border-border bg-surface focus-visible:ring-ring block size-5 rounded-full border-2 shadow-sm transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
      />
    ))}
  </SliderPrimitive.Root>
));

Slider.displayName = "Slider";

export { Slider };
