import { useCallback, useState } from "react";
import { Check, Copy, Globe, Lock, Link2 } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { useI18n } from "@/shared/i18n/LocaleProvider";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
} from "@/shared/ui/primitives";

import type { ShareConfig } from "../types";

type ShareDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Current URL or identifier to share. */
  shareUrl: string;
  /** Called when the user confirms sharing. */
  onShare?: (config: ShareConfig) => void;
  className?: string;
};

export function ShareDialog({
  open,
  onOpenChange,
  shareUrl,
  onShare,
  className,
}: ShareDialogProps) {
  const { t } = useI18n();
  const [access, setAccess] = useState<ShareConfig["access"]>("link");
  const [linkPermission, setLinkPermission] =
    useState<ShareConfig["linkPermission"]>("view");
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the input text
    }
  }, [shareUrl]);

  const handleShare = useCallback(() => {
    onShare?.({
      access,
      linkPermission,
      allowedUserIds: [],
    });
    onOpenChange(false);
  }, [access, linkPermission, onShare, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("sm:max-w-md", className)}>
        <DialogHeader>
          <DialogTitle>{t("collaboration.share.title")}</DialogTitle>
          <DialogDescription>
            {t("collaboration.share.description")}
          </DialogDescription>
        </DialogHeader>

        {/* Link input */}
        <div className="flex items-center gap-2">
          <div className="border-line bg-surface relative flex flex-1 items-center rounded-xl border">
            <Link2 className="text-muted absolute left-3 h-4 w-4" />
            <Input
              readOnly
              value={shareUrl}
              className="border-0 pl-9 text-sm focus-visible:ring-0"
            />
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
        </div>

        {/* Access mode */}
        <div className="space-y-3">
          <p className="text-sm font-medium">
            {t("collaboration.share.access")}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className={cn(
                "border-line flex flex-1 items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors",
                access === "link"
                  ? "border-accent bg-accent/5 text-accent"
                  : "hover:bg-surface",
              )}
              onClick={() => setAccess("link")}
            >
              <Globe className="h-4 w-4" />
              {t("collaboration.share.anyoneWithLink")}
            </button>
            <button
              type="button"
              className={cn(
                "border-line flex flex-1 items-center gap-2 rounded-xl border px-3 py-2 text-sm transition-colors",
                access === "restricted"
                  ? "border-accent bg-accent/5 text-accent"
                  : "hover:bg-surface",
              )}
              onClick={() => setAccess("restricted")}
            >
              <Lock className="h-4 w-4" />
              {t("collaboration.share.restricted")}
            </button>
          </div>
        </div>

        {/* Permission level for link access */}
        {access === "link" && (
          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("collaboration.share.permission")}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                className={cn(
                  "border-line rounded-xl border px-3 py-1.5 text-sm",
                  linkPermission === "view"
                    ? "border-accent bg-accent/5 text-accent"
                    : "hover:bg-surface",
                )}
                onClick={() => setLinkPermission("view")}
              >
                {t("collaboration.share.canView")}
              </button>
              <button
                type="button"
                className={cn(
                  "border-line rounded-xl border px-3 py-1.5 text-sm",
                  linkPermission === "edit"
                    ? "border-accent bg-accent/5 text-accent"
                    : "hover:bg-surface",
                )}
                onClick={() => setLinkPermission("edit")}
              >
                {t("collaboration.share.canEdit")}
              </button>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
          >
            {t("common.cancel")}
          </Button>
          <Button type="button" variant="primary" onClick={handleShare}>
            {t("collaboration.share.shareButton")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
