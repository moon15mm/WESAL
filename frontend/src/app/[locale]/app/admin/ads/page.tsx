"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Card, EmptyState, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Ad = { id?: string; placement: string; title: Record<string, string>; body: Record<string, string>; link_url: string | null; starts_at: string; ends_at: string; status: string; impressions?: number };

export default function Ads() {
  const t = useTranslations("admin");
  const f = useFormat();
  const qc = useQueryClient();
  const ads = useApiQuery<Ad[]>(["ads-admin"], "/admin/ads");
  const [edit, setEdit] = useState<Ad | null>(null);
  const { loading, run } = useApiAction();
  return (
    <>
      <PageHeader title={t("ads_title")} actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setEdit({ placement: "retailer_dashboard", title: { ar: "", en: "" }, body: { ar: "", en: "" }, link_url: "", starts_at: new Date().toISOString().slice(0, 16), ends_at: new Date(Date.now() + 14 * 864e5).toISOString().slice(0, 16), status: "draft" })}>{t("new_ad")}</Button>} />
      {ads.data?.length ? <div className="grid gap-4 md:grid-cols-2">{ads.data.map((a) => (
        <Card key={a.id} className="cursor-pointer" onClick={() => setEdit({ ...a, starts_at: a.starts_at.slice(0, 16), ends_at: a.ends_at.slice(0, 16) })}>
          <div className="flex justify-between"><p className="font-semibold">{a.title.ar || a.title.en}</p><StatusBadge status={a.status} /></div>
          <p className="mt-1 text-xs text-muted">{t(`placements.${a.placement}`)} · {f.date(a.starts_at)} → {f.date(a.ends_at)} · {t("impressions_n", { n: a.impressions || 0 })}</p>
        </Card>
      ))}</div> : <Card><EmptyState title={t("no_ads")} /></Card>}
      {edit && (
        <Modal open onOpenChange={(v) => !v && setEdit(null)} size="lg" title={t("new_ad")} footer={<><Button variant="outline" onClick={() => setEdit(null)}>{t("cancel")}</Button><Button loading={loading} onClick={async () => {
          const body = { placement: edit.placement, title: edit.title, body: edit.body, link_url: edit.link_url || null, starts_at: new Date(edit.starts_at).toISOString(), ends_at: new Date(edit.ends_at).toISOString(), status: edit.status };
          if (await run(() => (edit.id ? api(`/admin/ads/${edit.id}`, { method: "PUT", body }) : api("/admin/ads", { body })), { success: t("saved") })) { setEdit(null); qc.invalidateQueries({ queryKey: ["ads-admin"] }); }
        }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("placement")}>{(id) => <Select id={id} value={edit.placement} onChange={(e) => setEdit({ ...edit, placement: e.target.value })}>{["retailer_dashboard", "marketplace_top", "rep_dashboard", "supplier_dashboard"].map((p) => <option key={p} value={p}>{t(`placements.${p}`)}</option>)}</Select>}</Field>
            <Field label={t("status")}>{(id) => <Select id={id} value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>{["draft", "active", "paused", "ended"].map((s) => <option key={s} value={s}>{t(`adstatus.${s}`)}</option>)}</Select>}</Field>
            {(["ar", "en"] as const).map((l) => <Field key={l} label={`${t("ad_title")} (${l})`}>{(id) => <Input id={id} value={edit.title[l] || ""} onChange={(e) => setEdit({ ...edit, title: { ...edit.title, [l]: e.target.value } })} />}</Field>)}
            {(["ar", "en"] as const).map((l) => <Field key={l} label={`${t("ad_body")} (${l})`}>{(id) => <Input id={id} value={edit.body[l] || ""} onChange={(e) => setEdit({ ...edit, body: { ...edit.body, [l]: e.target.value } })} />}</Field>)}
            <Field label={t("link")} className="sm:col-span-2">{(id) => <Input id={id} dir="ltr" value={edit.link_url || ""} onChange={(e) => setEdit({ ...edit, link_url: e.target.value })} placeholder="/ar/app/store/market" />}</Field>
            <Field label={t("from")}>{(id) => <Input id={id} type="datetime-local" value={edit.starts_at} onChange={(e) => setEdit({ ...edit, starts_at: e.target.value })} />}</Field>
            <Field label={t("to")}>{(id) => <Input id={id} type="datetime-local" value={edit.ends_at} onChange={(e) => setEdit({ ...edit, ends_at: e.target.value })} />}</Field>
          </div>
        </Modal>
      )}
    </>
  );
}
