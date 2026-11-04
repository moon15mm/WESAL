"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileUp, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Alert, Card, CardHeader, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Button, Field, Input, Select, Switch, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Profile = Record<string, unknown> & { type: string; verification_status: string; rejection_reason: string | null; my_permissions: string[]; logo_url: string | null };
type Doc = { id: string; doc_type: string; number: string | null; status: string; file_url: string; review_notes: string | null };
const FIELDS_COMMON = ["trade_name_ar", "trade_name_en", "legal_name", "cr_number", "vat_number", "activity", "email", "phone", "website"];

export default function BusinessPage() {
  const t = useTranslations("business");
  const qc = useQueryClient();
  const { refresh } = useSession();
  const cities = useCities();
  const p = useApiQuery<Profile>(["biz-profile"], "/business/profile");
  const docs = useApiQuery<Doc[]>(["biz-docs"], "/business/documents");
  const [v, setV] = useState<Record<string, unknown> | null>(null);
  const [docType, setDocType] = useState("commercial_registration");
  const [docNo, setDocNo] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const { loading, fields, run } = useApiAction();
  useEffect(() => { if (p.data) setV({ ...p.data }); }, [p.data]);
  if (!v || !p.data) return <SkeletonRows />;
  const can = p.data.my_permissions.some((x) => x.endsWith(".business.manage"));
  const supplier = p.data.type === "supplier";
  const str = (k: string) => (v[k] === null || v[k] === undefined ? "" : String(v[k]));
  async function save() {
    const keys = [...FIELDS_COMMON, "description", supplier ? "min_order_value" : "store_type", ...(supplier ? ["supply_terms", "payment_terms", "default_lead_time_days"] : ["discoverable"])];
    const body: Record<string, unknown> = {};
    for (const k of keys) body[k] = v![k] === "" ? null : v![k];
    body.city_id = v!.city ? (v!.city as { id: number }).id : v!.city_id || null;
    if (body.default_lead_time_days !== null && body.default_lead_time_days !== undefined) body.default_lead_time_days = Number(body.default_lead_time_days);
    if (await run(() => api("/business/profile", { method: "PATCH", body }), { success: t("saved") })) { qc.invalidateQueries({ queryKey: ["biz-profile"] }); refresh(); }
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t(supplier ? "subtitle_supplier" : "subtitle_store")} actions={<StatusBadge status={p.data.verification_status} />} />
      {p.data.verification_status === "rejected" && <div className="mb-4"><Alert tone="danger" title={t("rejected")}>{p.data.rejection_reason}</Alert></div>}
      {p.data.verification_status === "unverified" && <div className="mb-4"><Alert tone="warning" title={t("unverified_title")}>{t(supplier ? "unverified_supplier" : "unverified_store")}</Alert></div>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS_COMMON.map((k) => <Field key={k} label={t(`fields.${k}`)} error={fields[k] && t("invalid")}>{(id) => <Input id={id} value={str(k)} disabled={!can} dir={["cr_number", "vat_number", "email", "phone", "website", "trade_name_en"].includes(k) ? "ltr" : undefined} onChange={(e) => setV({ ...v, [k]: e.target.value })} />}</Field>)}
            <Field label={t("fields.city")}>{(id) => <Select id={id} disabled={!can} value={String((v.city as { id: number } | null)?.id || v.city_id || "")} onChange={(e) => setV({ ...v, city: { id: Number(e.target.value) } })}><option value="">—</option>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
            {supplier ? <>
              <Field label={t("fields.min_order_value")}>{(id) => <Input id={id} type="number" disabled={!can} value={str("min_order_value")} onChange={(e) => setV({ ...v, min_order_value: e.target.value })} />}</Field>
              <Field label={t("fields.default_lead_time_days")}>{(id) => <Input id={id} type="number" disabled={!can} value={str("default_lead_time_days")} onChange={(e) => setV({ ...v, default_lead_time_days: e.target.value })} />}</Field>
              <Field label={t("fields.supply_terms")} className="sm:col-span-2">{(id) => <Textarea id={id} disabled={!can} value={str("supply_terms")} onChange={(e) => setV({ ...v, supply_terms: e.target.value })} />}</Field>
              <Field label={t("fields.payment_terms")} className="sm:col-span-2">{(id) => <Textarea id={id} disabled={!can} value={str("payment_terms")} onChange={(e) => setV({ ...v, payment_terms: e.target.value })} />}</Field>
            </> : <>
              <Field label={t("fields.store_type")}>{(id) => <Select id={id} disabled={!can} value={str("store_type")} onChange={(e) => setV({ ...v, store_type: e.target.value })}>{["grocery", "minimarket", "supermarket", "hypermarket", "pharmacy", "other"].map((s) => <option key={s} value={s}>{t(`store_types.${s}`)}</option>)}</Select>}</Field>
              <div className="flex items-end"><Switch checked={!!v.discoverable} disabled={!can} onChange={(x) => setV({ ...v, discoverable: x })} label={t("fields.discoverable")} /></div>
            </>}
            <Field label={t("fields.description")} className="sm:col-span-2">{(id) => <Textarea id={id} disabled={!can} value={str("description")} onChange={(e) => setV({ ...v, description: e.target.value })} />}</Field>
          </div>
          {can && <div className="mt-5 flex justify-end"><Button loading={loading} onClick={save}>{t("save")}</Button></div>}
        </Card>
        <Card>
          <CardHeader title={t("verification")} subtitle={t("verification_hint")} action={<ShieldCheck className="h-5 w-5 text-teal-500" />} />
          <ul className="mb-4 space-y-2 text-sm">{docs.data?.map((d) => <li key={d.id} className="flex items-center justify-between gap-2"><a href={d.file_url} target="_blank" className="truncate text-teal-700 underline">{t(`doc_types.${d.doc_type}`)}{d.number && ` · ${d.number}`}</a><StatusBadge status={d.status} /></li>)}</ul>
          {can && (
            <div className="space-y-2">
              <Select value={docType} onChange={(e) => setDocType(e.target.value)}>{["commercial_registration", "vat_certificate", "municipal_license", "national_address", "other"].map((d) => <option key={d} value={d}>{t(`doc_types.${d}`)}</option>)}</Select>
              <Input placeholder={t("doc_number")} value={docNo} onChange={(e) => setDocNo(e.target.value)} dir="ltr" />
              <Input type="file" accept="application/pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <Button variant="outline" className="w-full" icon={<FileUp className="h-4 w-4" />} disabled={!file} loading={loading} onClick={async () => {
                const fd = new FormData(); fd.set("doc_type", docType); if (docNo) fd.set("number", docNo); fd.set("file", file!);
                if (await run(() => api("/business/documents", { form: fd }), { success: t("uploaded") })) { setFile(null); qc.invalidateQueries({ queryKey: ["biz-docs"] }); }
              }}>{t("upload")}</Button>
              {["unverified", "rejected"].includes(p.data.verification_status) && <Button className="w-full" loading={loading} onClick={async () => { if (await run(() => api("/business/verification/submit", { method: "POST" }), { success: t("submitted") })) { qc.invalidateQueries({ queryKey: ["biz-profile"] }); refresh(); } }} data-testid="submit-verification">{t("submit")}</Button>}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
