import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ForwardedRef,
  ReactNode,
} from "react";
import { forwardRef } from "react";
import { Link, type LinkProps } from "react-router-dom";

import { cn } from "@/lib/utils";

export type ButtonVariant = "primary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

type CommonButtonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  fullWidth?: boolean;
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

const sizeClassName: Record<ButtonSize, string> = {
  sm: "px-3 py-2 text-xs",
  md: "px-4 py-3 text-sm",
  lg: "px-5 py-3.5 text-sm",
};

const variantClassName: Record<ButtonVariant, string> = {
  primary:
    "bg-[linear-gradient(135deg,var(--button-primary-start),var(--button-primary-end))] text-[var(--button-primary-text)] shadow-[0_16px_28px_rgba(28,139,130,0.22)]",
  ghost: "border border-line bg-white/70 text-text hover:bg-white/90",
  danger: "border border-danger/20 bg-danger/10 text-danger hover:bg-danger/15",
};

function buttonClassName({
  variant,
  size,
  className,
  fullWidth,
}: Pick<CommonButtonProps, "variant" | "size" | "className" | "fullWidth">) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)] font-extrabold transition disabled:cursor-not-allowed disabled:opacity-50",
    sizeClassName[size ?? "md"],
    variantClassName[variant ?? "ghost"],
    fullWidth ? "w-full" : "",
    className,
  );
}

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
  } = props;

  const resolvedClassName = buttonClassName({
    variant,
    size,
    className,
    fullWidth,
  });

  if ("to" in props && props.to !== undefined) {
    const {
      children: _children,
      className: _className,
      fullWidth: _fullWidth,
      leading: _leading,
      size: _size,
      trailing: _trailing,
      variant: _variant,
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
      children: _children,
      className: _className,
      fullWidth: _fullWidth,
      href,
      leading: _leading,
      size: _size,
      trailing: _trailing,
      variant: _variant,
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
    children: _children,
    className: _className,
    fullWidth: _fullWidth,
    leading: _leading,
    size: _size,
    trailing: _trailing,
    variant: _variant,
    ...buttonProps
  } = props as NativeButtonProps;
  return (
    <button
      ref={ref as ForwardedRef<HTMLButtonElement>}
      className={resolvedClassName}
      {...buttonProps}
    >
      <ButtonInner leading={leading} trailing={trailing}>
        {children}
      </ButtonInner>
    </button>
  );
}

export const Button = forwardRef(ButtonComponent);

Button.displayName = "Button";
