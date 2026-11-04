"use client";

import { useQueryClient } from "@tanstack/react-query";
import { MapPin, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Badge, Card, EmptyState, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Branch = { id: string; name: string; code: string | null; city: { name: string } | null; city_id: number | null; district: string | null; address_line: string | null; phone: string | null; lat: number | null; lng: number | null; is_active: boolean; is_primary: boolean };

export default function Branches() {
  const t = useTranslations("branches");
  const qc = useQueryClient();
  const { can } = useSession();
  const cities = useCities();
  const q = useApiQuery<Branch[]>(["branches"], "/retailer/branches");
  const [edit, setEdit] = useState<Partial<Branch> | null>(null);
  const { loading, run } = useApiAction();
  const manage = can("retailer.branches.manage");

  async function save() {
    if (!edit) return;
    const body = { name: edit.name, code: edit.code || null, city_id: edit.city_id ? Number(edit.city_id) : null, district: edit.district || null, address_line: edit.address_line || null, phone: edit.phone || null, lat: edit.lat ? Number(edit.lat) : null, lng: edit.lng ? Number(edit.lng) : null, ...(edit.id ? { is_active: edit.is_active } : {}) };
    const ok = await run(() => (edit.id ? api(`/retailer/branches/${edit.id}`, { method: "PATCH", body }) : api("/retailer/branches", { body })), { success: t("saved") });
    if (ok) { setEdit(null); qc.invalidateQueries({ queryKey: ["branches"] }); }
  }
  function locate() {
    navigator.geolocation?.getCurrentPosition((p) => setEdit((e) => ({ ...e, lat: Number(p.coords.latitude.toFixed(5)), lng: Number(p.coords.longitude.toFixed(5)) })));
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={manage && <Button icon={<Plus className="h-4 w-4" />} onClick={() => setEdit({ is_active: true })}>{t("add")}</Button>} />
      {q.isLoading ? <SkeletonRows /> : q.data?.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {q.data.map((b) => (
            <Card key={b.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-navy-700">{b.name}</p>
                <div className="flex gap-1">{b.is_primary && <Badge tone="teal">{t("primary")}</Badge>}{!b.is_active && <Badge>{t("inactive")}</Badge>}</div>
              </div>
              <p className="mt-2 flex items-start gap-1.5 text-sm text-muted"><MapPin className="mt-0.5 h-4 w-4 shrink-0" />{[b.city?.name, b.district, b.address_line].filter(Boolean).join(" · ") || "—"}</p>
              {b.phone && <p className="ltr mt-1 text-sm text-muted">{b.phone}</p>}
              {manage && <Button variant="outline" size="sm" className="mt-4 self-start" onClick={() => setEdit(b)}>{t("edit")}</Button>}
            </Card>
          ))}
        </div>
      ) : <Card><EmptyState title={t("empty")} /></Card>}
      {edit && (
        <Modal open onOpenChange={(v) => !v && setEdit(null)} title={edit.id ? t("edit") : t("add")}
          footer={<><Button variant="outline" onClick={() => setEdit(null)}>{t("cancel")}</Button><Button loading={loading} onClick={save} disabled={!edit.name}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("name")} required>{(id) => <Input id={id} value={edit.name || ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />}</Field>
            <Field label={t("code")}>{(id) => <Input id={id} value={edit.code || ""} onChange={(e) => setEdit({ ...edit, code: e.target.value })} />}</Field>
            <Field label={t("city")}>{(id) => <Select id={id} value={edit.city_id || ""} onChange={(e) => setEdit({ ...edit, city_id: Number(e.target.value) })}><option value="">—</option>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
            <Field label={t("district")}>{(id) => <Input id={id} value={edit.district || ""} onChange={(e) => setEdit({ ...edit, district: e.target.value })} />}</Field>
            <Field label={t("address")} className="sm:col-span-2">{(id) => <Input id={id} value={edit.address_line || ""} onChange={(e) => setEdit({ ...edit, address_line: e.target.value })} />}</Field>
            <Field label={t("phone")}>{(id) => <Input id={id} dir="ltr" value={edit.phone || ""} onChange={(e) => setEdit({ ...edit, phone: e.target.value })} />}</Field>
            <Field label={t("location")} hint={t("location_hint")}>{() => <div className="flex gap-2"><Input dir="ltr" placeholder="lat" value={edit.lat ?? ""} onChange={(e) => setEdit({ ...edit, lat: Number(e.target.value) })} /><Input dir="ltr" placeholder="lng" value={edit.lng ?? ""} onChange={(e) => setEdit({ ...edit, lng: Number(e.target.value) })} /><Button variant="outline" onClick={locate}><MapPin className="h-4 w-4" /></Button></div>}</Field>
            {edit.id && !edit.is_primary && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!edit.is_active} onChange={(e) => setEdit({ ...edit, is_active: e.target.checked })} />{t("active")}</label>}
          </div>
        </Modal>
      )}
    </>
  );
}
