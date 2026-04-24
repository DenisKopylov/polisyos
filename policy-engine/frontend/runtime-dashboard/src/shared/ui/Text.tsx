import {
  createElement,
  type ComponentPropsWithoutRef,
  type ElementType,
  type ReactNode,
} from "react";

import { useI18n } from "@/i18n/LocaleProvider";
import {
  applyTypographyToReactNode,
  type LocaleTypographyOptions,
} from "@/i18n/typography/typography";
import { cn } from "@/lib/utils";

type TextProps<T extends ElementType = "p"> = {
  as?: T;
  children: ReactNode;
  className?: string;
  lang?: string;
  mono?: boolean;
  typography?: boolean | LocaleTypographyOptions;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className" | "lang">;

function resolveTypographyOptions(
  typography?: boolean | LocaleTypographyOptions,
): LocaleTypographyOptions {
  if (typography === false) {
    return { enabled: false };
  }

  if (typography === true || typography === undefined) {
    return {};
  }

  return typography;
}

export function Text<T extends ElementType = "p">({
  as,
  children,
  className,
  lang,
  mono = false,
  typography,
  ...props
}: TextProps<T>) {
  const { locale } = useI18n();
  const Component = (as ?? "p") as ElementType;

  return createElement(
    Component,
    {
      ...props,
      className: cn(mono && "mono font-mono", className),
      lang: lang ?? locale,
    },
    applyTypographyToReactNode(
      children,
      locale,
      resolveTypographyOptions(typography),
    ),
  );
}
