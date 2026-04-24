import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { resolveAtlasLogoMarkAsset } from "@/shared/brand/AtlasBrand";
import { JANUS_ASSETS } from "@/shared/brand/JanusGlyph";

export const PUBLIC_BRAND_PATH_PREFIXES = ["/login", "/welcome"] as const;
export const PUBLIC_FAVICON_HREF = resolveAtlasLogoMarkAsset({ size: 16 });
export const PRODUCT_FAVICON_HREF = JANUS_ASSETS.favicon;

export function resolveBrandSurface(pathname: string): "public" | "product" {
  for (const prefix of PUBLIC_BRAND_PATH_PREFIXES) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      return "public";
    }
  }
  return "product";
}

export function resolveFaviconHref(pathname: string): string {
  return resolveBrandSurface(pathname) === "public"
    ? PUBLIC_FAVICON_HREF
    : PRODUCT_FAVICON_HREF;
}

export function syncFavicon(href: string) {
  if (typeof document === "undefined") {
    return;
  }

  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    link.type = "image/svg+xml";
    document.head.appendChild(link);
  }
  link.id = "app-favicon";
  link.href = href;
}

export function RouteIconProvider({
  surface = "auto",
}: {
  surface?: "auto" | "public" | "product";
}) {
  const location = useLocation();

  useEffect(() => {
    const href =
      surface === "auto"
        ? resolveFaviconHref(location.pathname)
        : surface === "public"
          ? PUBLIC_FAVICON_HREF
          : PRODUCT_FAVICON_HREF;
    syncFavicon(href);
  }, [location.pathname, surface]);

  return null;
}
