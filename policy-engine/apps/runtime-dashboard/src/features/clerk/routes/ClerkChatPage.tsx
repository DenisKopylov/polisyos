import { useLayoutEffect, useState } from "react";

import { useAuthz } from "@/app/authz/AuthzProvider";

import { ChatContainer } from "../components/ChatContainer";
import { hydrateChatStoreForIdentity } from "../state/useChatStore";

type IdentitySnapshot = Readonly<{
  tenantId: string;
  userId: string;
}>;

function settledIdentity(
  authz: ReturnType<typeof useAuthz>,
): IdentitySnapshot | null {
  try {
    if (authz.status !== "ready") return null;
    const identity = authz.user;
    const tenantId = identity?.tenant_id;
    const userId = identity?.user_id;
    if (
      typeof tenantId !== "string" ||
      tenantId.trim().length === 0 ||
      typeof userId !== "string" ||
      userId.trim().length === 0
    ) {
      return null;
    }
    return Object.freeze({ tenantId, userId });
  } catch {
    return null;
  }
}

function IdentityBoundChat({
  binding,
  tenantId,
  userId,
}: {
  binding: string;
  tenantId: string | null;
  userId: string | null;
}) {
  const [hydratedBinding, setHydratedBinding] = useState<string | null>(null);

  useLayoutEffect(() => {
    const scope =
      tenantId === null || userId === null
        ? null
        : Object.freeze({ tenantId, userId });
    hydrateChatStoreForIdentity(scope);
    setHydratedBinding(binding);
  }, [binding, tenantId, userId]);

  if (tenantId === null || userId === null || hydratedBinding !== binding) {
    return null;
  }
  return <ChatContainer />;
}

export default function ClerkChatPage() {
  const identity = settledIdentity(useAuthz());
  const binding = JSON.stringify(
    identity ? ["scoped", identity.tenantId, identity.userId] : ["unscoped"],
  );

  return (
    <IdentityBoundChat
      key={binding}
      binding={binding}
      tenantId={identity?.tenantId ?? null}
      userId={identity?.userId ?? null}
    />
  );
}
