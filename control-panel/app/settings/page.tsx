"use client";

import { authClient } from "@/lib/auth-client";
import { isAdmin } from "@/lib/api";
import { HitlToggles } from "@/components/settings/hitl-toggles";
import { BrandConstantsView } from "@/components/settings/brand-constants";
import { IntegrationsStatus } from "@/components/settings/integrations-status";

export default function SettingsPage() {
  const { data: session } = authClient.useSession();
  const role = (session?.user as unknown as { role?: string } | undefined)?.role;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-sans text-2xl font-semibold">Settings</h1>

      <HitlToggles role={role} />
      <BrandConstantsView role={role} />
      <IntegrationsStatus />
    </div>
  );
}
