"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, api, setApiBusiness, setApiLocale } from "./api";

export type Membership = {
  business_id: string;
  type: "retailer" | "supplier";
  name: string;
  trade_name_ar: string;
  trade_name_en: string | null;
  verification_status: string;
  status: string;
  role: string;
  role_name: string;
  permissions: string[];
  branch_id: string | null;
};

export type Me = {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  locale: string;
  document_locale: string;
  number_system: "latn" | "arab";
  timezone: string;
  currency: string;
  status: string;
  email_verified: boolean;
  phone_verified: boolean;
  mfa_enabled: boolean;
  mfa_verified: boolean;
  mfa_pending: boolean;
  mfa_required_for_admin: boolean;
  platform_roles: string[];
  platform_permissions: string[];
  memberships: Membership[];
  representative: { id: string; kind: string; verification_status: string; display_name: string; is_active: boolean } | null;
};

export type WorkspaceKind = "store" | "supplier" | "rep" | "admin";
export type Workspace = { kind: WorkspaceKind; businessId?: string; label: string; sub?: string };

type Ctx = {
  me: Me | null | undefined;
  loading: boolean;
  workspaces: Workspace[];
  workspace: Workspace | null;
  setWorkspace: (w: Workspace) => void;
  can: (perm: string) => boolean;
  membership: Membership | null;
  refresh: () => Promise<unknown>;
};

const SessionContext = createContext<Ctx | null>(null);
const WS_KEY = "wesal.workspace";

export function workspacesOf(me: Me): Workspace[] {
  const out: Workspace[] = [];
  for (const m of me.memberships) {
    out.push({ kind: m.type === "retailer" ? "store" : "supplier", businessId: m.business_id, label: m.name, sub: m.role_name });
  }
  if (me.representative) out.push({ kind: "rep", label: me.representative.display_name, sub: me.representative.kind });
  if (me.platform_roles.length) out.push({ kind: "admin", label: "WESAL", sub: me.platform_roles[0] });
  return out;
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const locale = useLocale();
  setApiLocale(locale);
  const qc = useQueryClient();
  const meQ = useQuery<Me | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
  const me = meQ.data;
  const workspaces = useMemo(() => (me ? workspacesOf(me) : []), [me]);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    try {
      setSelected(localStorage.getItem(WS_KEY));
    } catch {
      /* storage unavailable */
    }
  }, []);

  const workspace = useMemo(() => {
    if (!workspaces.length) return null;
    return workspaces.find((w) => `${w.kind}:${w.businessId || ""}` === selected) || workspaces[0];
  }, [workspaces, selected]);

  setApiBusiness(workspace?.businessId || null);

  const setWorkspace = useCallback(
    (w: Workspace) => {
      const key = `${w.kind}:${w.businessId || ""}`;
      setSelected(key);
      try {
        localStorage.setItem(WS_KEY, key);
      } catch {
        /* ignore */
      }
      setApiBusiness(w.businessId || null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
    [qc],
  );

  const membership = useMemo(
    () => (workspace?.businessId && me ? me.memberships.find((m) => m.business_id === workspace.businessId) || null : null),
    [workspace, me],
  );
  const can = useCallback(
    (perm: string) => {
      if (!me) return false;
      if (perm.startsWith("admin.")) return me.platform_permissions.includes(perm);
      return !!membership?.permissions.includes(perm);
    },
    [me, membership],
  );

  const value: Ctx = {
    me,
    loading: meQ.isLoading,
    workspaces,
    workspace,
    setWorkspace,
    can,
    membership,
    refresh: () => meQ.refetch(),
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession outside provider");
  return ctx;
}
