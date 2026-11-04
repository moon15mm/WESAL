"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MapPin, Play, Plus, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Pagination, Tabs } from "@/components/ui/data";
import { Card, EmptyState, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Checkbox, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { api, type Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery, useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Visit = { id: string; customer_id: string | null; customer_name: string | null; purpose: string; status: string; scheduled_at: string | null; started_at: string | null; ended_at: string | null; outcome: string | null; notes: string | null };
type Customer = { id: string; name: string };
const PURPOSES = ["introduction", "order_taking", "follow_up", "promotion", "collection", "complaint", "other"];
const OUTCOMES = ["order_created", "interested", "follow_up_needed", "not_interested", "decision_maker_absent", "closed"];

function getLocation(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition((p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }), () => resolve(null), { timeout: 8000 });
  });
}

function VisitsInner() {
  const t = useTranslations("visits");
  const f = useFormat();
  const qc = useQueryClient();
  const sp = useSearchParams();
  const [status, setStatus] = useState("");
  const list = useList<Visit>("/rep/visits", { status });
  const customers = useApiQuery<Page<Customer>>(["rep-customers-all"], "/rep/customers", { page_size: 100 });
  const [create, setCreate] = useState(sp.get("new") === "1");
  const [ending, setEnding] = useState<Visit | null>(null);
  const [form, setForm] = useState({ customer_id: "", purpose: "order_taking", scheduled_at: "", start_now: true });
  const [end, setEnd] = useState({ outcome: "interested", notes: "", next_visit_at: "", share: false });
  const [shareStart, setShareStart] = useState(false);
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: ["/rep/visits"] });

  async function submitCreate() {
    const ok = await run(() => api("/rep/visits", { body: { customer_id: form.customer_id, purpose: form.purpose, start_now: form.start_now, scheduled_at: form.start_now ? null : new Date(form.scheduled_at).toISOString() } }), { success: t("saved") });
    if (ok) { setCreate(false); refresh(); }
  }
  async function start(v: Visit) {
    const loc = shareStart ? await getLocation() : null;
    if (await run(() => api(`/rep/visits/${v.id}/start`, { body: { consent: !!loc, lat: loc?.lat, lng: loc?.lng } }), { success: t("started") })) refresh();
  }
  async function submitEnd() {
    if (!ending) return;
    const loc = end.share ? await getLocation() : null;
    const ok = await run(() => api(`/rep/visits/${ending.id}/end`, { body: { outcome: end.outcome, notes: end.notes || null, next_visit_at: end.next_visit_at ? new Date(end.next_visit_at).toISOString() : null, consent: !!loc, lat: loc?.lat, lng: loc?.lng } }), { success: t("ended") });
    if (ok) { setEnding(null); refresh(); }
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setCreate(true)} data-testid="new-visit">{t("new")}</Button>} />
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={status} onChange={(v) => { setStatus(v); list.reset(); }} items={["", "scheduled", "in_progress", "completed", "missed"].map((s) => ({ value: s, label: s ? t(`status.${s}`) : t("all") }))} />
        <Checkbox checked={shareStart} onChange={(e) => setShareStart(e.target.checked)} label={t("share_location_start")} />
      </div>
      {list.isLoading ? <SkeletonRows /> : list.data?.items.length ? (
        <div className="space-y-3">
          {list.data.items.map((v) => (
            <Card key={v.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="flex items-center gap-2 font-semibold text-navy-700">{v.customer_name || "—"} <StatusBadge status={v.status} /></p>
                <p className="mt-1 text-sm text-muted">{t(`purposes.${v.purpose}`)} · {f.datetime(v.started_at || v.scheduled_at)}{v.outcome && ` · ${t(`outcomes.${v.outcome}`)}`}</p>
                {v.notes && <p className="mt-1 line-clamp-2 text-sm">{v.notes}</p>}
              </div>
              <div className="flex gap-2">
                {v.status === "scheduled" && <Button size="sm" icon={<Play className="h-4 w-4" />} onClick={() => start(v)} loading={loading}>{t("start")}</Button>}
                {v.status === "in_progress" && <Button size="sm" variant="success" icon={<CheckCircle2 className="h-4 w-4" />} onClick={() => setEnding(v)} data-testid="end-visit">{t("end")}</Button>}
                {["scheduled", "in_progress"].includes(v.status) && <Button size="sm" variant="ghost" icon={<X className="h-4 w-4" />} onClick={async () => { if (await run(() => api(`/rep/visits/${v.id}/cancel`, { method: "POST" }))) refresh(); }}>{t("cancel")}</Button>}
              </div>
            </Card>
          ))}
          <Card padded={false}><Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} /></Card>
        </div>
      ) : <Card><EmptyState icon={<MapPin className="h-6 w-6" />} title={t("empty")} description={t("empty_hint")} /></Card>}
      <p className="mt-4 text-xs text-muted">{t("privacy_note")}</p>

      <Modal open={create} onOpenChange={setCreate} title={t("new")} footer={<><Button variant="outline" onClick={() => setCreate(false)}>{t("cancel")}</Button><Button loading={loading} disabled={!form.customer_id} onClick={submitCreate} data-testid="save-visit">{t("save")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("customer")} required hint={t("customer_hint")}>{(id) => <Select id={id} value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}><option value="">—</option>{customers.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
          <Field label={t("purpose")}>{(id) => <Select id={id} value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })}>{PURPOSES.map((p) => <option key={p} value={p}>{t(`purposes.${p}`)}</option>)}</Select>}</Field>
          <Checkbox checked={form.start_now} onChange={(e) => setForm({ ...form, start_now: e.target.checked })} label={t("start_now")} />
          {!form.start_now && <Field label={t("scheduled_at")}>{(id) => <Input id={id} type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} />}</Field>}
        </div>
      </Modal>
      <Modal open={!!ending} onOpenChange={(v) => !v && setEnding(null)} title={t("end")} footer={<><Button variant="outline" onClick={() => setEnding(null)}>{t("cancel")}</Button><Button variant="success" loading={loading} onClick={submitEnd} data-testid="save-end-visit">{t("end")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("outcome")}>{(id) => <Select id={id} value={end.outcome} onChange={(e) => setEnd({ ...end, outcome: e.target.value })}>{OUTCOMES.map((o) => <option key={o} value={o}>{t(`outcomes.${o}`)}</option>)}</Select>}</Field>
          <Field label={t("notes")}>{(id) => <Textarea id={id} value={end.notes} onChange={(e) => setEnd({ ...end, notes: e.target.value })} />}</Field>
          <Field label={t("next_visit")}>{(id) => <Input id={id} type="datetime-local" value={end.next_visit_at} onChange={(e) => setEnd({ ...end, next_visit_at: e.target.value })} />}</Field>
          <Checkbox checked={end.share} onChange={(e) => setEnd({ ...end, share: e.target.checked })} label={t("share_location_end")} />
        </div>
      </Modal>
    </>
  );
}

export default function Visits() {
  return <Suspense><VisitsInner /></Suspense>;
}
