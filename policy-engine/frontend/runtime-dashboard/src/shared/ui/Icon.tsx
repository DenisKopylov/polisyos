import { forwardRef, type SVGAttributes } from "react";
import type { LucideIcon, LucideProps } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

export const iconVariants = cva("shrink-0", {
  variants: {
    size: {
      xs: "size-3",
      sm: "size-4",
      md: "size-5",
      lg: "size-6",
      xl: "size-8",
    },
  },
  defaultVariants: {
    size: "md",
  },
});

export type IconSize = NonNullable<VariantProps<typeof iconVariants>["size"]>;

type IconProps = {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
  label?: string;
} & Omit<LucideProps, "size">;

export const Icon = forwardRef<SVGSVGElement, IconProps>(
  ({ icon: LucideIcon, size = "md", className, label, ...props }, ref) => (
    <LucideIcon
      ref={ref}
      className={cn(iconVariants({ size }), className)}
      aria-hidden={!label}
      aria-label={label}
      {...props}
    />
  ),
);
Icon.displayName = "Icon";

type SpinnerProps = {
  size?: IconSize;
  className?: string;
} & SVGAttributes<SVGSVGElement>;

export function Spinner({ size = "md", className, ...props }: SpinnerProps) {
  return (
    <svg
      className={cn(iconVariants({ size }), "animate-spin", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
      {...props}
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}
