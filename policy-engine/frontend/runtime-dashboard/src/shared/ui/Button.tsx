import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ForwardedRef,
  ReactNode,
} from "react";
import { forwardRef } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)] font-extrabold leading-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-[linear-gradient(135deg,var(--button-primary-start),var(--button-primary-end))] text-[var(--button-primary-text)] shadow-[0_16px_28px_rgba(28,139,130,0.22)] hover:brightness-110",
        ghost:
          "border border-line bg-[var(--ghost-bg)] text-text hover:bg-[var(--ghost-bg-hover)]",
        danger:
          "border border-danger/20 bg-danger/10 text-danger hover:bg-danger/15",
        outline:
          "border border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground border border-border hover:bg-secondary/80",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-[var(--control-height-sm)] px-[var(--control-px-sm)] text-[length:var(--control-text-sm)]",
        md: "h-[var(--control-height-md)] px-[var(--control-px-md)] text-[length:var(--control-text-md)]",
        lg: "h-[var(--control-height-lg)] px-[var(--control-px-lg)] text-[length:var(--control-text-lg)]",
        icon: "size-[var(--control-height-icon)]",
      },
    },
    defaultVariants: {
      variant: "ghost",
      size: "md",
    },
  },
);

export type ButtonVariant = NonNullable<
  VariantProps<typeof buttonVariants>["variant"]
>;
export type ButtonSize = NonNullable<
  VariantProps<typeof buttonVariants>["size"]
>;

type CommonButtonProps = VariantProps<typeof buttonVariants> & {
  className?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  fullWidth?: boolean;
  asChild?: boolean;
  children: ReactNode;
};

type NativeButtonProps = CommonButtonProps &
  ButtonHTMLAttributes<HTMLButtonElement> & { to?: never; href?: never };

type RouterButtonProps = CommonButtonProps &
  Omit<LinkProps, "className" | "children"> & {
    to: LinkProps["to"];
    href?: never;
  };

type AnchorButtonProps = CommonButtonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "children"> & {
    href: string;
    to?: never;
  };

export type ButtonProps =
  | NativeButtonProps
  | RouterButtonProps
  | AnchorButtonProps;

function ButtonInner({
  children,
  leading,
  trailing,
}: Pick<CommonButtonProps, "children" | "leading" | "trailing">) {
  return (
    <>
      {leading}
      <span>{children}</span>
      {trailing}
    </>
  );
}

function ButtonComponent(
  props: ButtonProps,
  ref: ForwardedRef<HTMLAnchorElement | HTMLButtonElement>,
) {
  const {
    children,
    className,
    fullWidth,
    leading,
    size = "md",
    trailing,
    variant = "ghost",
    asChild,
  } = props;

  const resolvedClassName = cn(
    buttonVariants({ variant, size }),
    fullWidth && "w-full",
    className,
  );

  if ("to" in props && props.to !== undefined) {
    const {
      children: _c,
      className: _cl,
      fullWidth: _fw,
      leading: _l,
      size: _s,
      trailing: _t,
      variant: _v,
      asChild: _a,
      to,
      ...linkProps
    } = props as RouterButtonProps;
    return (
      <Link
        ref={ref as ForwardedRef<HTMLAnchorElement>}
        to={to}
        className={resolvedClassName}
        {...linkProps}
      >
        <ButtonInner leading={leading} trailing={trailing}>
          {children}
        </ButtonInner>
      </Link>
    );
  }

  if ("href" in props && props.href !== undefined) {
    const {
      children: _c,
      className: _cl,
      fullWidth: _fw,
      href,
      leading: _l,
      size: _s,
      trailing: _t,
      variant: _v,
      asChild: _a,
      ...anchorProps
    } = props as AnchorButtonProps;
    return (
      <a
        ref={ref as ForwardedRef<HTMLAnchorElement>}
        href={href}
        className={resolvedClassName}
        {...anchorProps}
      >
        <ButtonInner leading={leading} trailing={trailing}>
          {children}
        </ButtonInner>
      </a>
    );
  }

  const {
    children: _c,
    className: _cl,
    fullWidth: _fw,
    leading: _l,
    size: _s,
    trailing: _t,
    variant: _v,
    asChild: _a,
    ...buttonProps
  } = props as NativeButtonProps;

  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      ref={ref as ForwardedRef<HTMLButtonElement>}
      className={resolvedClassName}
      {...buttonProps}
    >
      {asChild ? (
        children
      ) : (
        <ButtonInner leading={leading} trailing={trailing}>
          {children}
        </ButtonInner>
      )}
    </Comp>
  );
}

export const Button = forwardRef(ButtonComponent);

Button.displayName = "Button";
