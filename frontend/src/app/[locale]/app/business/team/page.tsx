"use client";

import { useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, type Column } from "@/components/ui/data";
import { Badge, Card, CardHeader, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Member = { id: string; full_name: string; email: string | null; phone: string | null; role_id: string; role: string; role_name: string; status: string; user_status: string; branch_id: string | null; title: string | null };
type Roles = { roles: { id: string; code: string; name: string; is_system: boolean; permissions: string[] }[]; available_permissions: string[] };

export default function Team() {
  const t = useTranslations("team");
  const qc = useQueryClient();
  const { workspace } = useSession();
  const members = useApiQuery<Member[]>(["team"], "/business/team");
  const roles = useApiQuery<Roles>(["roles"], "/business/roles");
  const branches = useApiQuery<{ id: string; name: string }[]>(["branches"], workspace?.kind === "store" ? "/retailer/branches" : null);
  const [invite, setInvite] = useState<null | { full_name: string; email: string; phone: string; role_id: string; branch_id: string }>(null);
  const [role, setRole] = useState<null | { code: string; name_ar: string; name_en: string; permissions: string[] }>(null);
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: ["team"] });
  const update = async (m: Member, body: Record<string, unknown>) => { if (await run(() => api(`/business/team/${m.id}`, { method: "PATCH", body }), { success: t("saved") })) refresh(); };
  const cols: Column<Member>[] = [
    { key: "n", header: t("name"), cell: (m) => <span><span className="font-medium">{m.full_name}</span><span className="ltr block text-xs text-muted">{m.email || m.phone}</span></span> },
    { key: "r", header: t("role"), cell: (m) => <Select className="h-8 w-44 text-xs" value={m.role_id} onChange={(e) => update(m, { role_id: e.target.value })}>{roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select> },
    { key: "s", header: t("status"), cell: (m) => <span className="flex gap-1"><StatusBadge status={m.status} />{m.user_status === "pending" && <Badge tone="warning">{t("invited")}</Badge>}</span> },
    { key: "a", header: "", cell: (m) => m.status === "active" ? <Button size="sm" variant="ghost" className="text-danger" onClick={() => update(m, { status: "disabled" })}>{t("disable")}</Button> : <Button size="sm" variant="ghost" onClick={() => update(m, { status: "active" })}>{t("enable")}</Button> },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={<>
        <Button variant="outline" onClick={() => setRole({ code: "", name_ar: "", name_en: "", permissions: [] })}>{t("custom_role")}</Button>
        <Button icon={<UserPlus className="h-4 w-4" />} onClick={() => setInvite({ full_name: "", email: "", phone: "", role_id: "", branch_id: "" })}>{t("invite")}</Button>
      </>} />
      <Card padded={false}><DataTable columns={cols} rows={members.data} loading={members.isLoading} rowKey={(m) => m.id} /></Card>
      <Card className="mt-6">
        <CardHeader title={t("roles")} subtitle={t("roles_hint")} />
        <div className="grid gap-3 md:grid-cols-2">{roles.data?.roles.map((r) => <div key={r.id} className="rounded-md border border-line p-3"><p className="font-medium">{r.name} {!r.is_system && <Badge tone="teal">{t("custom")}</Badge>}</p><p className="mt-1 text-xs text-muted">{r.permissions.map((p) => t(`perms.${p.split(".").slice(1).join("_")}`)).join(" · ")}</p></div>)}</div>
      </Card>
      {invite && (
        <Modal open onOpenChange={(v) => !v && setInvite(null)} title={t("invite")} description={t("invite_hint")} footer={<><Button variant="outline" onClick={() => setInvite(null)}>{t("cancel")}</Button><Button loading={loading} disabled={!invite.full_name || !invite.role_id || (!invite.email && !invite.phone)} onClick={async () => {
          if (await run(() => api("/business/team", { body: { ...invite, email: invite.email || null, phone: invite.phone || null, branch_id: invite.branch_id || null } }), { success: t("invited_ok") })) { setInvite(null); refresh(); }
        }}>{t("send_invite")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("name")} className="sm:col-span-2">{(id) => <Input id={id} value={invite.full_name} onChange={(e) => setInvite({ ...invite, full_name: e.target.value })} />}</Field>
            <Field label={t("email")}>{(id) => <Input id={id} type="email" dir="ltr" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} />}</Field>
            <Field label={t("phone")}>{(id) => <Input id={id} dir="ltr" value={invite.phone} onChange={(e) => setInvite({ ...invite, phone: e.target.value })} />}</Field>
            <Field label={t("role")}>{(id) => <Select id={id} value={invite.role_id} onChange={(e) => setInvite({ ...invite, role_id: e.target.value })}><option value="">—</option>{roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</Select>}</Field>
            {branches.data && <Field label={t("branch")} hint={t("branch_hint")}>{(id) => <Select id={id} value={invite.branch_id} onChange={(e) => setInvite({ ...invite, branch_id: e.target.value })}><option value="">{t("all_branches")}</option>{branches.data.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select>}</Field>}
          </div>
        </Modal>
      )}
      {role && (
        <Modal open onOpenChange={(v) => !v && setRole(null)} size="lg" title={t("custom_role")} footer={<><Button variant="outline" onClick={() => setRole(null)}>{t("cancel")}</Button><Button loading={loading} disabled={!/^[a-z][a-z0-9_]{2,40}$/.test(role.code) || !role.name_ar || !role.name_en || !role.permissions.length} onClick={async () => {
          if (await run(() => api("/business/roles", { body: role }), { success: t("saved") })) { setRole(null); qc.invalidateQueries({ queryKey: ["roles"] }); }
        }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("role_code")} hint="a-z, 0-9, _">{(id) => <Input id={id} dir="ltr" value={role.code} onChange={(e) => setRole({ ...role, code: e.target.value })} />}</Field>
            <Field label={t("name_ar")}>{(id) => <Input id={id} value={role.name_ar} onChange={(e) => setRole({ ...role, name_ar: e.target.value })} />}</Field>
            <Field label={t("name_en")}>{(id) => <Input id={id} dir="ltr" value={role.name_en} onChange={(e) => setRole({ ...role, name_en: e.target.value })} />}</Field>
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">{roles.data?.available_permissions.map((p) => <label key={p} className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-teal-500" checked={role.permissions.includes(p)} onChange={(e) => setRole({ ...role, permissions: e.target.checked ? [...role.permissions, p] : role.permissions.filter((x) => x !== p) })} />{t(`perms.${p.split(".").slice(1).join("_")}`)}</label>)}</div>
        </Modal>
      )}
    </>
  );
}
