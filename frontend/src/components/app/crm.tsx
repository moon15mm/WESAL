"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Phone, Plus, StickyNote } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Pagination, SearchInput, Tabs, type Column } from "@/components/ui/data";
import { Badge, Card, CardHeader, KV, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCities } from "@/lib/hooks";
import { useList } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

export type Customer = {
  id: string; name: string; contact_name: string | null; phone: string | null; email: string | null; retailer_id: string | null; registered: boolean;
  city: { name: string } | null; district: string | null; status: string; source: string; tags: string[]; assigned_representative_id: string | null;
  last_order_at: string | null; last_visit_at: string | null; next_follow_up_at: string | null; orders_count: number; total_sales: string; created_at: string;
  contacts?: { id: string; name: string; role: string | null; phone: string | null }[];
  notes?: { id: string; body: string; author: string | null; created_at: string }[];
  visits?: { id: string; status: string; purpose: string; outcome: string | null; started_at: string | null; ended_at: string | null; notes: string | null }[];
  orders?: { id: string; number: string; status: string; total: string; created_at: string }[];
  favorite_products?: { product_id: string; name: string; quantity: number }[];
  opportunities?: { id: string; title: string; stage: string; estimated_value: string | null }[];
  acquisition?: { source: string; acquired_at: string; representative_id: string | null; changes: { old_source: string; new_source: string; reason: string; created_at: string }[] };
};

type Side = "rep" | "supplier";
const BASE = { rep: "/rep/customers", supplier: "/supplier/customers" };
const ROUTE = { rep: "/app/rep/customers", supplier: "/app/supplier/customers" };

export function CustomerList({ side }: { side: Side }) {
  const t = useTranslations("crm");
  const f = useFormat();
  const router = useRouter();
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [due, setDue] = useState(false);
  const list = useList<Customer>(BASE[side], { q, status, due_follow_up: due || undefined });
  const [adding, setAdding] = useState(false);
  const canManage = side === "rep" || can("supplier.customers.manage");
  const cols: Column<Customer>[] = [
    { key: "name", header: t("name"), cell: (c) => <span className="font-medium text-navy-700">{c.name}{!c.registered && <Badge className="ms-2">{t("lead")}</Badge>}</span> },
    { key: "city", header: t("area"), cell: (c) => [c.city?.name, c.district].filter(Boolean).join(" · ") || "—" },
    { key: "status", header: t("status"), cell: (c) => <StatusBadge status={c.status} /> },
    { key: "orders", header: t("orders"), numeric: true, hideOnMobile: true, cell: (c) => f.number(c.orders_count) },
    { key: "sales", header: t("sales"), numeric: true, cell: (c) => f.money(c.total_sales) },
    { key: "last", header: t("last_order"), hideOnMobile: true, cell: (c) => f.date(c.last_order_at) },
    { key: "follow", header: t("follow_up"), hideOnMobile: true, cell: (c) => f.date(c.next_follow_up_at) },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t(`subtitle_${side}`)} actions={canManage && <Button icon={<Plus className="h-4 w-4" />} onClick={() => setAdding(true)}>{t("add")}</Button>} />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs value={due ? "due" : status} onChange={(v) => { if (v === "due") { setDue(true); setStatus(""); } else { setDue(false); setStatus(v); } list.reset(); }}
          items={[{ value: "", label: t("all") }, { value: "active", label: t("status_active") }, { value: "prospect", label: t("status_prospect") }, { value: "lead", label: t("status_lead") }, { value: "due", label: t("due_follow_up") }]} />
        <SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} className="lg:w-64" />
      </div>
      <Card padded={false}>
        <DataTable columns={cols} rows={list.data?.items} loading={list.isLoading} rowKey={(c) => c.id} onRowClick={(c) => router.push(`${ROUTE[side]}/${c.id}`)} />
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
      </Card>
      {adding && <AddCustomer side={side} onClose={() => setAdding(false)} />}
    </>
  );
}

export function AddCustomer({ side, onClose, preset }: { side: Side; onClose: () => void; preset?: { retailer_id?: string; name?: string } }) {
  const t = useTranslations("crm");
  const qc = useQueryClient();
  const cities = useCities();
  const { loading, run } = useApiAction();
  const [v, setV] = useState({ name: preset?.name || "", contact_name: "", phone: "", city_id: "", district: "", next_follow_up_at: "" });
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("add")} description={t("add_hint")}
      footer={<><Button variant="outline" onClick={onClose}>{t("cancel")}</Button><Button loading={loading} disabled={!preset?.retailer_id && v.name.length < 2} onClick={async () => {
        const body = { retailer_id: preset?.retailer_id || null, name: v.name || null, contact_name: v.contact_name || null, phone: v.phone || null, city_id: v.city_id ? Number(v.city_id) : null, district: v.district || null, next_follow_up_at: v.next_follow_up_at ? new Date(v.next_follow_up_at).toISOString() : null };
        if (await run(() => api(BASE[side], { body }), { success: t("saved") })) { qc.invalidateQueries({ queryKey: [BASE[side]] }); onClose(); }
      }}>{t("save")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("name")} className="sm:col-span-2">{(id) => <Input id={id} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />}</Field>
        <Field label={t("contact_name")}>{(id) => <Input id={id} value={v.contact_name} onChange={(e) => setV({ ...v, contact_name: e.target.value })} />}</Field>
        <Field label={t("phone")}>{(id) => <Input id={id} dir="ltr" value={v.phone} onChange={(e) => setV({ ...v, phone: e.target.value })} />}</Field>
        <Field label={t("city")}>{(id) => <Select id={id} value={v.city_id} onChange={(e) => setV({ ...v, city_id: e.target.value })}><option value="">—</option>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
        <Field label={t("district")}>{(id) => <Input id={id} value={v.district} onChange={(e) => setV({ ...v, district: e.target.value })} />}</Field>
        <Field label={t("follow_up")} className="sm:col-span-2">{(id) => <Input id={id} type="datetime-local" value={v.next_follow_up_at} onChange={(e) => setV({ ...v, next_follow_up_at: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
}

export function CustomerDetail({ side, id }: { side: Side; id: string }) {
  const t = useTranslations("crm");
  const f = useFormat();
  const qc = useQueryClient();
  const { can } = useSession();
  const key = ["customer", side, id];
  const { data: c } = useQuery({ queryKey: key, queryFn: () => api<Customer>(`${BASE[side]}/${id}`) });
  const [note, setNote] = useState("");
  const [sourceOpen, setSourceOpen] = useState(false);
  const [src, setSrc] = useState({ source: "rep_visit", reason: "" });
  const { loading, run } = useApiAction();
  if (!c) return <SkeletonRows />;
  const refresh = () => qc.invalidateQueries({ queryKey: key });
  const orderRoute = side === "rep" ? "/app/rep/orders" : "/app/supplier/orders";
  return (
    <>
      <PageHeader back={<Link href={ROUTE[side]} className="mb-2 inline-block text-sm text-teal-600">← {t("title")}</Link>}
        title={<span className="flex items-center gap-2">{c.name}<StatusBadge status={c.status} /></span>}
        subtitle={[c.city?.name, c.district].filter(Boolean).join(" · ")}
        actions={side === "rep" && c.retailer_id && <Link href={`/app/rep/orders/new?retailer=${c.retailer_id}`} className="inline-flex h-10 items-center rounded-md bg-teal-500 px-4 text-sm font-semibold text-white">{t("new_order")}</Link>} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6">
          <Card>
            <KV className="sm:grid-cols-1" items={[
              [t("contact_name"), c.contact_name], [t("phone"), c.phone && <a key="p" href={`tel:${c.phone}`} className="ltr inline-flex items-center gap-1 text-teal-600"><Phone className="h-4 w-4" />{c.phone}</a>],
              [t("source"), t(`sources.${c.source}`)], [t("orders"), f.number(c.orders_count)], [t("sales"), f.money(c.total_sales)],
              [t("last_order"), f.date(c.last_order_at)], [t("last_visit"), f.date(c.last_visit_at)], [t("follow_up"), f.datetime(c.next_follow_up_at)],
            ]} />
          </Card>
          {c.acquisition && (
            <Card>
              <CardHeader title={t("acquisition")} action={can("supplier.customers.source_change") && <Button size="sm" variant="outline" onClick={() => setSourceOpen(true)}>{t("change_source")}</Button>} />
              <p className="text-sm">{t(`sources.${c.acquisition.source}`)} · {f.date(c.acquisition.acquired_at)}</p>
              {c.acquisition.changes.map((x, i) => <p key={i} className="mt-2 rounded bg-page p-2 text-xs text-muted">{t(`sources.${x.old_source}`)} → {t(`sources.${x.new_source}`)} · {x.reason}</p>)}
            </Card>
          )}
          {c.favorite_products && c.favorite_products.length > 0 && (
            <Card><CardHeader title={t("favorites")} /><ul className="space-y-1.5 text-sm">{c.favorite_products.map((p) => <li key={p.product_id} className="flex justify-between"><span>{p.name}</span><span className="tabular text-muted">{f.number(p.quantity)}</span></li>)}</ul></Card>
          )}
        </div>
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title={t("notes")} action={<StickyNote className="h-5 w-5 text-warning" />} />
            <div className="flex gap-2"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("note_placeholder")} /><Button loading={loading} disabled={!note.trim()} onClick={async () => { if (await run(() => api(`${BASE[side]}/${id}/notes`, { body: { body: note } }))) { setNote(""); refresh(); } }}>{t("add_note")}</Button></div>
            <ul className="mt-4 space-y-3">{c.notes?.map((n) => <li key={n.id} className="rounded-md bg-page p-3 text-sm"><p>{n.body}</p><p className="mt-1 text-xs text-muted">{n.author} · {f.datetime(n.created_at)}</p></li>)}</ul>
          </Card>
          <Card padded={false}>
            <div className="p-5 pb-2"><CardHeader title={t("orders")} /></div>
            <DataTable rows={c.orders} rowKey={(o) => o.id} columns={[
              { key: "n", header: t("number"), cell: (o) => <Link href={`${orderRoute}/${o.id}`} className="ltr font-medium text-teal-700">{o.number}</Link> },
              { key: "s", header: t("status"), cell: (o) => <StatusBadge status={o.status} /> },
              { key: "t", header: t("total"), numeric: true, cell: (o) => f.money(o.total) },
              { key: "d", header: t("date"), cell: (o) => f.date(o.created_at) },
            ]} />
          </Card>
          <Card>
            <CardHeader title={t("visits")} />
            <ul className="space-y-2 text-sm">{c.visits?.map((v) => <li key={v.id} className="flex items-center justify-between gap-2 border-b border-line pb-2 last:border-0"><span>{f.datetime(v.ended_at || v.started_at)} · {v.outcome || v.purpose}</span><StatusBadge status={v.status} /></li>)}</ul>
            {!c.visits?.length && <p className="text-sm text-muted">—</p>}
          </Card>
        </div>
      </div>
      <Modal open={sourceOpen} onOpenChange={setSourceOpen} title={t("change_source")} description={t("change_source_hint")}
        footer={<><Button variant="outline" onClick={() => setSourceOpen(false)}>{t("cancel")}</Button><Button loading={loading} disabled={src.reason.length < 10} onClick={async () => { if (await run(() => api(`/supplier/customers/${id}/source`, { body: src }), { success: t("saved") })) { setSourceOpen(false); refresh(); } }}>{t("save")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("source")}>{(fid) => <Select id={fid} value={src.source} onChange={(e) => setSrc({ ...src, source: e.target.value })}>{["rep_visit", "rep_invite", "direct_signup", "marketplace", "supplier_import", "referral"].map((s) => <option key={s} value={s}>{t(`sources.${s}`)}</option>)}</Select>}</Field>
          <Field label={t("reason")} required hint={t("reason_hint")}>{(fid) => <Textarea id={fid} value={src.reason} onChange={(e) => setSrc({ ...src, reason: e.target.value })} />}</Field>
        </div>
      </Modal>
    </>
  );
}
