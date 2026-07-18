import {
  createContext,
  createElement,
  type ComponentPropsWithoutRef,
  type ElementType,
  type PropsWithChildren,
  type ReactNode,
  useContext,
} from "react";

import { cn } from "../lib/cn";

export type TextTypographyOptions = {
  enabled?: boolean;
  nonBreakingSpaces?: boolean;
  quoteMarks?: boolean;
};

export type TextPresentation = {
  locale: string;
  transform: (
    node: ReactNode,
    locale: string,
    options: TextTypographyOptions,
  ) => ReactNode;
};

const defaultPresentation: TextPresentation = {
  locale: "en",
  transform: (node) => node,
};
const TextPresentationContext =
  createContext<TextPresentation>(defaultPresentation);

export type TextPresentationProviderProps = PropsWithChildren<TextPresentation>;

export function TextPresentationProvider({
  children,
  locale,
  transform,
}: TextPresentationProviderProps) {
  return (
    <TextPresentationContext.Provider value={{ locale, transform }}>
      {children}
    </TextPresentationContext.Provider>
  );
}

export type TextProps<T extends ElementType = "p"> = {
  as?: T;
  children: ReactNode;
  className?: string;
  lang?: string;
  mono?: boolean;
  typography?: boolean | TextTypographyOptions;
} & Omit<ComponentPropsWithoutRef<T>, "as" | "children" | "className" | "lang">;

function resolveTypographyOptions(
  typography?: boolean | TextTypographyOptions,
): TextTypographyOptions {
  if (typography === false) return { enabled: false };
  if (typography === true || typography === undefined) return {};
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
  const { locale, transform } = useContext(TextPresentationContext);
  const Component = as ?? "p";
  const typographyOptions = resolveTypographyOptions(typography);
  const renderedChildren =
    typographyOptions.enabled === false
      ? children
      : transform(children, locale, typographyOptions);
  return createElement(
    Component,
    {
      ...props,
      className: cn(mono && "mono font-mono", className),
      lang: lang ?? locale,
    },
    renderedChildren,
  );
}
