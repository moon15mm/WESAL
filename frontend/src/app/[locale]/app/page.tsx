"use client";

import { useEffect } from "react";
import { HOME } from "@/components/app/nav";
import { useRouter } from "@/i18n/navigation";
import { useSession } from "@/lib/session";

export default function AppHome() {
  const { workspace } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (workspace) router.replace(HOME[workspace.kind]);
  }, [workspace, router]);
  return null;
}
