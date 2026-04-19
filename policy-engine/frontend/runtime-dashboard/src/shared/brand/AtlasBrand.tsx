import { cn } from "@/lib/utils";

export type AtlasBrandMarkSize = 16 | 24 | 32 | 48;
export type AtlasBrandVariant = "lockup" | "mark";

type AtlasBrandAssetOptions = {
  inverted?: boolean;
  size?: number;
};

export function resolveAtlasLogoMarkAsset({
  inverted = false,
  size = 32,
}: AtlasBrandAssetOptions = {}) {
  if (size <= 16) {
    return "/atlas/favicon.svg";
  }
  return inverted ? "/atlas/logo-mark-inverse.svg" : "/atlas/logo-mark.svg";
}

export function resolveAtlasWordmarkAsset({
  inverted = false,
}: AtlasBrandAssetOptions = {}) {
  return inverted ? "/atlas/logo-atlas-inverse.svg" : "/atlas/logo-atlas.svg";
}

export function getAtlasLogoMarkBucket(size: number): AtlasBrandMarkSize {
  if (size <= 16) {
    return 16;
  }
  if (size <= 24) {
    return 24;
  }
  if (size <= 32) {
    return 32;
  }
  return 48;
}

export function AtlasBrand({
  alt,
  className,
  inverted = false,
  size = 32,
  variant = "lockup",
}: {
  alt?: string;
  className?: string;
  inverted?: boolean;
  size?: number;
  variant?: AtlasBrandVariant;
}) {
  if (variant === "mark") {
    const bucket = getAtlasLogoMarkBucket(size);

    return (
      <img
        alt={alt ?? "Atlas logo mark"}
        className={cn("atlas-brand__mark", className)}
        data-brand-bucket={bucket}
        data-testid={`atlas-logo-mark-${bucket}`}
        height={size}
        src={resolveAtlasLogoMarkAsset({ inverted, size: bucket })}
        width={size}
      />
    );
  }

  return (
    <img
      alt={alt ?? "PolisyOS Atlas wordmark"}
      className={cn("atlas-brand__lockup-image", className)}
      data-testid="atlas-logo-lockup"
      height={Math.round(size * 0.2333)}
      src={resolveAtlasWordmarkAsset({ inverted })}
      width={size}
    />
  );
}
