"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, ClipboardCheck, Download, FileUp, MessageSquareWarning, PackageCheck, Pencil, Receipt, RotateCcw,
  Star, Truck, Undo2, XCircle,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Card, CardHeader, KV, PageHeader, StatusBadge, Alert, Badge } from "@/components/ui/layout";
import { DataTable, Pagination, SearchInput, Tabs, type Column } from "@/components/ui/data";
import { ConfirmDialog, Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api, download } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";
import type { Order, OrderItem } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

export type Side = "store" | "supplier" | "rep" | "admin";
const BASE: Record<Side, string> = { store: "/retailer/orders", supplier: "/supplier/orders", rep: "/rep/orders", admin: "/admin/orders" };
const ROUTE: Record<Side, string> = { store: "/app/store/orders", supplier: "/app/supplier/orders", rep: "/app/rep/orders", admin: "/app/admin/orders" };

const STATUS_TABS: Record<Side, { value: string; key: string }[]> = {
  store: [
    { value: "", key: "all" }, { value: "pending_retailer_approval,quoted,awaiting_retailer_approval", key: "needs_action" },
    { value: "new,supplier_review", key: "open" }, { value: "approved,preparing,ready,out_for_delivery", key: "in_progress" },
    { value: "delivered,completed", key: "done" }, { value: "rejected,cancelled", key: "closed" },
  ],
  supplier: [
    { value: "", key: "all" }, { value: "new,supplier_review", key: "new" }, { value: "quoted,awaiting_retailer_approval", key: "waiting_store" },
    { value: "approved,preparing,ready", key: "fulfillment" }, { value: "out_for_delivery", key: "on_the_way" },
    { value: "delivered,completed,partially_returned", key: "done" }, { value: "disputed", key: "disputed" },
  ],
  rep: [
    { value: "", key: "all" }, { value: "draft", key: "drafts" }, { value: "pending_retailer_approval", key: "waiting_store" },
    { value: "new,supplier_review,quoted,approved,preparing,ready,out_for_delivery", key: "in_progress" },
    { value: "delivered,completed", key: "done" }, { value: "rejected,cancelled", key: "closed" },
  ],
  admin: [{ value: "", key: "all" }, { value: "disputed", key: "disputed" }, { value: "new,supplier_review", key: "open" }, { value: "completed", key: "done" }],
};

export function OrderList({ side, title, initialStatus = "", subtitle, actions }: { side: Side; title: string; initialStatus?: string; subtitle?: string; actions?: React.ReactNode }) {
  const t = useTranslations("orders");
  const f = useFormat();
  const router = useRouter();
  const [status, setStatus] = useState(initialStatus);
  const [q, setQ] = useState("");
  const list = useList<Order>(BASE[side], { status, q });
  const columns: Column<Order>[] = [
    { key: "number", header: t("number"), cell: (o) => <span className="ltr font-semibold text-navy-700">{o.number}</span> },
    {
      key: "party", header: side === "supplier" ? t("store") : t("supplier"),
      cell: (o) => <span className="truncate">{side === "supplier" ? o.retailer.name : o.supplier.name}{side === "admin" && ` ← ${o.retailer.name}`}</span>,
    },
    { key: "channel", header: t("channel"), hideOnMobile: true, cell: (o) => <Badge tone={o.channel === "representative" ? "teal" : "neutral"}>{t(`channel_${o.channel}`)}</Badge> },
    { key: "status", header: t("status"), cell: (o) => <StatusBadge status={o.status} /> },
    { key: "total", header: t("total"), numeric: true, cell: (o) => f.money(o.total) },
    { key: "date", header: t("date"), hideOnMobile: true, cell: (o) => <span className="text-muted">{f.date(o.created_at)}</span> },
  ];
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} actions={actions} />
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs value={status} onChange={(v) => { setStatus(v); list.reset(); }} items={STATUS_TABS[side].map((s) => ({ value: s.value, label: t(`tabs.${s.key}`) }))} />
        <SearchInput value={q} onChange={(v) => { setQ(v); list.reset(); }} placeholder={t("search_number")} className="lg:w-64" />
      </div>
      <Card padded={false}>
        <DataTable columns={columns} rows={list.data?.items} loading={list.isLoading} rowKey={(o) => o.id} onRowClick={(o) => router.push(`${ROUTE[side]}/${o.id}`)} />
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
      </Card>
    </>
  );
}

// ------------------------------------------------------------------ detail
export function OrderDetail({ side, id }: { side: Side; id: string }) {
  const t = useTranslations("orders");
  const f = useFormat();
  const locale = useLocale();
  const qc = useQueryClient();
  const key = ["order", side, id];
  const { data: o, isLoading } = useQuery({ queryKey: key, queryFn: () => api<Order>(`${BASE[side]}/${id}`) });
  const [modal, setModal] = useState<string | null>(null);
  const { loading, run } = useApiAction();
  const refresh = () => qc.invalidateQueries({ queryKey: key });

  if (isLoading || !o) return <div className="space-y-4"><div className="skeleton h-10 w-60" /><div className="skeleton h-64" /></div>;
  const a = new Set(o.actions);
  const base = `${BASE[side]}/${o.id}`;
  const act = async (path: string, body: unknown = {}, success?: string) => {
    const ok = await run(() => api(`${base}/${path}`, { body }), { success: success || t("saved") });
    if (ok) { setModal(null); await refresh(); }
  };
  const decision = (path: string) => act(path, { version: o.pending_approval?.version ?? o.version, snapshot_hash: o.pending_approval?.snapshot_hash });

  const primary: React.ReactNode[] = [];
  if (a.has("approve")) primary.push(<Button key="ap" variant="success" icon={<CheckCircle2 className="h-4 w-4" />} loading={loading} onClick={() => decision("approve")} data-testid="approve-order">{t("approve")}</Button>);
  if (a.has("accept_offer")) primary.push(<Button key="ao" variant="success" icon={<CheckCircle2 className="h-4 w-4" />} loading={loading} onClick={() => decision("accept-offer")} data-testid="accept-offer">{t("accept_offer")}</Button>);
  if (a.has("approve_change")) primary.push(<Button key="ac" variant="success" loading={loading} onClick={() => decision("approve-change")}>{t("approve_change")}</Button>);
  if (a.has("submit")) primary.push(<Button key="sb" loading={loading} onClick={() => act("submit")} data-testid="submit-order">{t("submit")}</Button>);
  if (a.has("accept")) primary.push(<Button key="acc" variant="success" icon={<CheckCircle2 className="h-4 w-4" />} loading={loading} onClick={() => act("accept", {})} data-testid="supplier-accept">{t("accept")}</Button>);
  if (a.has("offer") || a.has("revise_offer")) primary.push(<Button key="of" variant="outline" icon={<Pencil className="h-4 w-4" />} onClick={() => setModal("offer")} data-testid="supplier-offer">{t(a.has("offer") ? "make_offer" : "revise_offer")}</Button>);
  if (a.has("start_review")) primary.push(<Button key="sr" variant="outline" onClick={() => act("start-review")}>{t("start_review")}</Button>);
  if (a.has("prepare")) primary.push(<Button key="pr" icon={<PackageCheck className="h-4 w-4" />} loading={loading} onClick={() => act("prepare")} data-testid="prepare">{t("prepare")}</Button>);
  if (a.has("ready")) primary.push(<Button key="rd" loading={loading} onClick={() => act("ready")} data-testid="ready">{t("mark_ready")}</Button>);
  if (a.has("dispatch")) primary.push(<Button key="dp" icon={<Truck className="h-4 w-4" />} onClick={() => setModal("dispatch")} data-testid="dispatch">{t("dispatch")}</Button>);
  if (a.has("deliver")) primary.push(<Button key="dl" variant="success" onClick={() => setModal("deliver")} data-testid="deliver">{t("mark_delivered")}</Button>);
  if (a.has("confirm_delivery")) primary.push(<Button key="cd" variant="success" icon={<ClipboardCheck className="h-4 w-4" />} onClick={() => setModal("confirm")} data-testid="confirm-delivery">{t("confirm_receipt")}</Button>);

  const secondary: { key: string; label: string; onClick: () => void; danger?: boolean; icon?: React.ReactNode }[] = [];
  if (a.has("request_changes")) secondary.push({ key: "rc", label: t("request_changes"), onClick: () => setModal("request_changes") });
  if (a.has("reject")) secondary.push({ key: "rj", label: t("reject"), danger: true, onClick: () => setModal("reject"), icon: <XCircle className="h-4 w-4" /> });
  if (a.has("reject_offer")) secondary.push({ key: "ro", label: t("reject_offer"), danger: true, onClick: () => setModal("reject-offer") });
  if (a.has("reject_change")) secondary.push({ key: "rch", label: t("reject_change"), danger: true, onClick: () => setModal("reject-change") });
  if (a.has("modify")) secondary.push({ key: "md", label: t("modify"), onClick: () => setModal("modify") });
  if (a.has("cancel")) secondary.push({ key: "cn", label: t("cancel_order"), danger: true, onClick: () => setModal("cancel") });
  if (a.has("withdraw")) secondary.push({ key: "wd", label: t("withdraw"), danger: true, onClick: () => setModal("withdraw") });
  if (a.has("record_collection")) secondary.push({ key: "col", label: t("record_collection"), onClick: () => setModal("collection"), icon: <Receipt className="h-4 w-4" /> });
  if (a.has("upload_invoice")) secondary.push({ key: "inv", label: t("upload_invoice"), onClick: () => setModal("invoice"), icon: <FileUp className="h-4 w-4" /> });
  if (a.has("request_return")) secondary.push({ key: "ret", label: t("request_return"), onClick: () => setModal("return"), icon: <Undo2 className="h-4 w-4" /> });
  if (a.has("dispute")) secondary.push({ key: "dis", label: t("open_dispute"), onClick: () => setModal("dispute"), icon: <MessageSquareWarning className="h-4 w-4" /> });
  if (a.has("rate")) secondary.push({ key: "rate", label: t("rate"), onClick: () => setModal("rate"), icon: <Star className="h-4 w-4" /> });
  if (a.has("reorder")) secondary.push({ key: "reo", label: t("reorder"), onClick: async () => { if (await run(() => api(`${base}/reorder`, { method: "POST" }), { success: t("added_to_cart") })) await qc.invalidateQueries({ queryKey: ["carts"] }); }, icon: <RotateCcw className="h-4 w-4" /> });

  const reasonModal = (name: string, path: string, title: string, tone: "danger" | "primary" = "danger") => (
    <ConfirmDialog open={modal === name} onOpenChange={(v) => setModal(v ? name : null)} title={title} requireReason tone={tone} loading={loading}
      onConfirm={(reason) => act(path, { reason })} />
  );

  return (
    <>
      <PageHeader
        back={<Link href={ROUTE[side]} className="mb-2 inline-block text-sm text-teal-600">← {t("back")}</Link>}
        title={<span className="flex flex-wrap items-center gap-3"><span className="ltr">{o.number}</span><StatusBadge status={o.status} /></span>}
        subtitle={`${t("created")} ${f.datetime(o.created_at)} · ${t(`channel_${o.channel}`)}${o.representative ? ` · ${o.representative.display_name}` : ""}`}
        actions={
          <Button variant="outline" icon={<Download className="h-4 w-4" />} onClick={() => download(`/orders/${o.id}/document.pdf`, { locale }, `${o.number}.pdf`)}>{t("pdf")}</Button>
        }
      />
      {o.status_reason && <div className="mb-4"><Alert tone="info" title={t("status_note")}>{o.status_reason}</Alert></div>}
      {o.pending_approval && side === "store" && (
        <div className="mb-4">
          <Alert tone="warning" title={t(`approval_kind.${o.pending_approval.kind}`)}>{t("approval_explain", { version: o.pending_approval.version })}</Alert>
        </div>
      )}
      {(primary.length > 0 || secondary.length > 0) && (
        <Card className="mb-6 flex flex-wrap items-center gap-2">
          {primary}
          {secondary.map((s) => (
            <Button key={s.key} variant={s.danger ? "ghost" : "outline"} className={s.danger ? "text-danger hover:bg-danger/5" : ""} onClick={s.onClick} icon={s.icon}>{s.label}</Button>
          ))}
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card padded={false}>
            <div className="p-5 pb-0"><CardHeader title={t("items")} subtitle={t("items_count", { count: o.items?.length || 0 })} /></div>
            <ItemsTable items={o.items || []} />
            <Totals o={o} />
          </Card>
          {o.delivery && (
            <Card>
              <CardHeader title={t("delivery")} action={<StatusBadge status={o.delivery.status} ns="delivery_status" />} />
              <KV items={[
                [t("scheduled_date"), f.date(o.delivery.scheduled_date || o.expected_delivery_date)],
                [t("dispatched_at"), f.datetime(o.delivery.dispatched_at)],
                [t("driver"), o.delivery.driver_name],
                [t("vehicle"), o.delivery.vehicle_plate && <span className="ltr">{o.delivery.vehicle_plate}</span>],
                [t("delivered_at"), f.datetime(o.delivery.delivered_at)],
                [t("proof"), o.delivery.proof_url ? <a href={o.delivery.proof_url} target="_blank" className="text-teal-600 underline">{t("view")}</a> : null],
              ]} />
              {o.confirmations?.map((c, i) => (
                <div key={i} className="mt-4 rounded-md bg-page p-3 text-sm">
                  <p className="font-medium text-navy-700">{t("receipt_confirmed")} · {f.datetime(c.created_at)} {c.receiver_name && `· ${c.receiver_name}`}</p>
                  {c.has_shortage && <p className="mt-1 text-[#8a5c19]">{t("shortage_recorded")}</p>}
                </div>
              ))}
            </Card>
          )}
          <Timeline o={o} />
        </div>
        <div className="space-y-6">
          <Card>
            <CardHeader title={t("parties")} />
            <KV className="sm:grid-cols-1" items={[
              [t("supplier"), o.supplier.name],
              [t("store"), o.retailer.name],
              [t("branch"), o.branch ? `${o.branch.name}${o.branch.district ? ` · ${o.branch.district}` : ""}` : null],
              [t("representative"), o.representative?.display_name],
              [t("expected_delivery"), f.date(o.expected_delivery_date)],
              [t("notes"), o.notes],
              [t("supplier_notes"), o.supplier_notes],
            ]} />
          </Card>
          <Card>
            <CardHeader title={t("payment")} subtitle={t("payment_note")} />
            <KV className="sm:grid-cols-1" items={[
              [t("payment_status"), <StatusBadge key="ps" status={o.payment_status} />],
              [t("paid_amount"), f.money(o.paid_amount)],
              [t("invoice"), o.invoice_url ? <a href={o.invoice_url} target="_blank" className="text-teal-600 underline">{o.invoice_number}</a> : t("invoice_pending")],
            ]} />
            {o.collections && o.collections.length > 0 && (
              <ul className="mt-4 space-y-2 text-sm">
                {o.collections.map((c, i) => <li key={i} className="flex justify-between"><span className="text-muted">{f.date(c.collected_at)} · {t(`methods.${c.method}`)}</span><span className="tabular font-medium">{f.money(c.amount)}</span></li>)}
              </ul>
            )}
          </Card>
          {o.commission && (
            <Card>
              <CardHeader title={t("commission")} />
              <div className="flex items-center justify-between"><span className="tabular text-xl font-bold text-navy-700">{f.money(o.commission.amount)}</span><StatusBadge status={o.commission.status} /></div>
            </Card>
          )}
          {o.returns && o.returns.length > 0 && (
            <Card>
              <CardHeader title={t("returns")} />
              <ul className="space-y-2 text-sm">{o.returns.map((r) => <li key={r.id} className="flex items-center justify-between"><span className="ltr">{r.number}</span><StatusBadge status={r.status} /></li>)}</ul>
            </Card>
          )}
          {o.approvals && o.approvals.length > 0 && (
            <Card>
              <CardHeader title={t("approvals_log")} />
              <ul className="space-y-3 text-sm">
                {o.approvals.map((ap) => (
                  <li key={ap.id} className="rounded-md border border-line p-3">
                    <div className="flex items-center justify-between"><span>{t(`approval_kind.${ap.kind}`)} · v{ap.version}</span><StatusBadge status={ap.decision} ns="decision" /></div>
                    <p className="mt-1 text-xs text-muted">{t("requested")} {f.datetime(ap.requested_at)}{ap.opened_at && ` · ${t("opened")} ${f.datetime(ap.opened_at)}`}{ap.decided_at && ` · ${t("decided")} ${f.datetime(ap.decided_at)}`}</p>
                    <p className="ltr mt-1 truncate font-mono text-[10px] text-muted/80">#{ap.snapshot_hash.slice(0, 16)}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      {reasonModal("reject", side === "supplier" ? "reject" : "reject", t("reject"))}
      {reasonModal("request_changes", "request-changes", t("request_changes"), "primary")}
      {reasonModal("reject-offer", "reject-offer", t("reject_offer"))}
      {reasonModal("reject-change", "reject-change", t("reject_change"))}
      {reasonModal("cancel", "cancel", t("cancel_order"))}
      {reasonModal("withdraw", "withdraw", t("withdraw"))}
      {(modal === "offer" || modal === "modify") && <OfferModal o={o} mode={modal} onClose={() => setModal(null)} onSubmit={(body) => act(modal === "offer" ? "offer" : "modify", body)} loading={loading} />}
      {modal === "dispatch" && <DispatchModal onClose={() => setModal(null)} onSubmit={(b) => act("dispatch", b)} loading={loading} />}
      {modal === "deliver" && <DeliverModal base={base} onClose={() => setModal(null)} onDone={async () => { setModal(null); await refresh(); }} />}
      {modal === "confirm" && <ConfirmReceiptModal o={o} onClose={() => setModal(null)} onSubmit={(b) => act("confirm-delivery", b, t("receipt_confirmed"))} loading={loading} />}
      {modal === "collection" && <CollectionModal base={base} o={o} onClose={() => setModal(null)} onDone={async () => { setModal(null); await refresh(); }} />}
      {modal === "invoice" && <InvoiceModal base={base} onClose={() => setModal(null)} onDone={async () => { setModal(null); await refresh(); }} />}
      {modal === "return" && <ReturnModal o={o} onClose={() => setModal(null)} onDone={async () => { setModal(null); await refresh(); }} />}
      {modal === "rate" && <RateModal o={o} onClose={() => setModal(null)} />}
      {modal === "dispute" && <DisputeModal o={o} onClose={() => setModal(null)} onDone={async () => { setModal(null); await refresh(); }} />}
    </>
  );
}

function ItemsTable({ items }: { items: OrderItem[] }) {
  const t = useTranslations("orders");
  const f = useFormat();
  const cols: Column<OrderItem>[] = [
    { key: "name", header: t("product"), cell: (i) => <span><span className="font-medium text-ink">{i.name}</span>{i.sku && <span className="ltr ms-2 text-xs text-muted">{i.sku}</span>}</span> },
    { key: "unit", header: t("unit"), cell: (i) => `${t(`units.${i.unit}`)}${i.unit === "carton" ? ` ×${i.pieces_per_unit}` : ""}` },
    { key: "qty", header: t("quantity"), numeric: true, cell: (i) => <span>{f.number(i.quantity)}{i.delivered_qty !== null && i.delivered_qty !== i.quantity && <span className="ms-1 text-xs text-warning">({f.number(i.delivered_qty)})</span>}</span> },
    { key: "price", header: t("unit_price"), numeric: true, cell: (i) => <span>{f.money(i.unit_price)}{i.list_unit_price !== i.unit_price && <span className="ms-1 text-xs text-muted line-through">{f.money(i.list_unit_price)}</span>}</span> },
    { key: "disc", header: t("discount"), numeric: true, hideOnMobile: true, cell: (i) => (Number(i.discount) ? f.money(i.discount) : "—") },
    { key: "total", header: t("line_total"), numeric: true, cell: (i) => <span className="font-semibold">{f.money(i.line_total)}</span> },
  ];
  return <DataTable columns={cols} rows={items} rowKey={(i) => i.id} />;
}

function Totals({ o }: { o: Order }) {
  const t = useTranslations("orders");
  const f = useFormat();
  const rows: [string, string][] = [[t("subtotal"), o.subtotal], [t("discount"), `-${o.discount_total}`], [t("delivery_fee"), o.delivery_fee], [`${t("vat")} (${Math.round(Number(o.vat_rate) * 100)}%)`, o.vat_total]];
  return (
    <div className="border-t border-line bg-page/60 p-5">
      <dl className="ms-auto max-w-xs space-y-1.5 text-sm">
        {rows.map(([k, v]) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="tabular">{f.money(v)}</dd></div>)}
        <div className="flex justify-between border-t border-line pt-2 text-base font-bold text-navy-700"><dt>{t("total")}</dt><dd className="tabular" data-testid="order-total">{f.money(o.total)}</dd></div>
      </dl>
    </div>
  );
}

function Timeline({ o }: { o: Order }) {
  const t = useTranslations("orders");
  const f = useFormat();
  if (!o.history?.length) return null;
  return (
    <Card>
      <CardHeader title={t("timeline")} />
      <ol className="relative space-y-5 border-s border-line ps-5">
        {o.history.map((h, i) => (
          <li key={i} className="relative">
            <span className="absolute -start-[27px] top-1 h-3 w-3 rounded-full border-2 border-white bg-teal-500 ring-1 ring-teal-200" />
            <div className="flex flex-wrap items-center gap-2"><StatusBadge status={h.to} /><span className="text-xs text-muted">{f.datetime(h.at)}</span>{h.actor_role && <span className="text-xs text-muted">· {t(`roles.${h.actor_role}`)}</span>}</div>
            {h.reason && <p className="mt-1 text-sm text-ink">{h.reason}</p>}
          </li>
        ))}
      </ol>
    </Card>
  );
}

// ------------------------------------------------------------------ modals
function OfferModal({ o, mode, onClose, onSubmit, loading }: { o: Order; mode: "offer" | "modify"; onClose: () => void; onSubmit: (b: unknown) => void; loading: boolean }) {
  const t = useTranslations("orders");
  const f = useFormat();
  const [lines, setLines] = useState(() => (o.items || []).map((i) => ({ order_item_id: i.id, name: i.name, quantity: i.quantity, unit_price: i.unit_price, discount: i.discount })));
  const [fee, setFee] = useState(o.delivery_fee);
  const [notes, setNotes] = useState("");
  const [date, setDate] = useState("");
  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 0) - Number(l.discount || 0), 0) + Number(fee || 0);
  const set = (i: number, k: string, v: string) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  return (
    <Modal open onOpenChange={(v) => !v && onClose()} size="xl" title={t(mode === "offer" ? "make_offer" : "modify")} description={t(mode === "offer" ? "offer_help" : "modify_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} onClick={() => onSubmit({ items: lines.map(({ name: _n, ...l }) => ({ ...l, quantity: Number(l.quantity) })), delivery_fee: fee, notes: notes || null, expected_delivery_date: date || null })} data-testid="send-offer">{t(mode === "offer" ? "send_offer" : "send_change")}</Button></>}>
      <div className="space-y-3">
        {lines.map((l, i) => (
          <div key={l.order_item_id} className="grid grid-cols-2 gap-2 rounded-md border border-line p-3 sm:grid-cols-[1fr_90px_110px_110px] sm:items-center">
            <p className="col-span-2 text-sm font-medium sm:col-span-1">{l.name}</p>
            <Input aria-label={t("quantity")} type="number" min={0} value={l.quantity} onChange={(e) => set(i, "quantity", e.target.value)} />
            <Input aria-label={t("unit_price")} type="number" min={0} step="0.01" value={l.unit_price} onChange={(e) => set(i, "unit_price", e.target.value)} />
            <Input aria-label={t("discount")} type="number" min={0} step="0.01" value={l.discount} onChange={(e) => set(i, "discount", e.target.value)} />
          </div>
        ))}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("delivery_fee")}>{(id) => <Input id={id} type="number" min={0} step="0.01" value={fee} onChange={(e) => setFee(e.target.value)} />}</Field>
          <Field label={t("expected_delivery")}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} />}</Field>
        </div>
        <Field label={t("notes")}>{(id) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
        <p className="text-end text-sm text-muted">{t("estimated_total")}: <span className="tabular font-bold text-navy-700">{f.money(total)}</span> <span className="text-xs">({t("vat_added")})</span></p>
      </div>
    </Modal>
  );
}

function DispatchModal({ onClose, onSubmit, loading }: { onClose: () => void; onSubmit: (b: unknown) => void; loading: boolean }) {
  const t = useTranslations("orders");
  const [v, setV] = useState({ driver_name: "", driver_phone: "", vehicle_plate: "", scheduled_date: "", notes: "" });
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("dispatch")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} onClick={() => onSubmit(Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x || null])))} data-testid="confirm-dispatch">{t("dispatch")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("driver")}>{(id) => <Input id={id} value={v.driver_name} onChange={(e) => setV({ ...v, driver_name: e.target.value })} />}</Field>
        <Field label={t("driver_phone")}>{(id) => <Input id={id} dir="ltr" value={v.driver_phone} onChange={(e) => setV({ ...v, driver_phone: e.target.value })} />}</Field>
        <Field label={t("vehicle")}>{(id) => <Input id={id} dir="ltr" value={v.vehicle_plate} onChange={(e) => setV({ ...v, vehicle_plate: e.target.value })} />}</Field>
        <Field label={t("scheduled_date")}>{(id) => <Input id={id} type="date" value={v.scheduled_date} onChange={(e) => setV({ ...v, scheduled_date: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
}

function DeliverModal({ base, onClose, onDone }: { base: string; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("mark_delivered")} description={t("deliver_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button variant="success" loading={loading} data-testid="confirm-deliver" onClick={async () => {
        const fd = new FormData();
        if (notes) fd.set("notes", notes);
        if (file) fd.set("proof", file);
        if (await run(() => api(`${base}/deliver`, { form: fd }), { success: t("saved") })) onDone();
      }}>{t("mark_delivered")}</Button></>}>
      <Field label={t("proof")}>{(id) => <Input id={id} type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />}</Field>
      <div className="mt-3"><Field label={t("notes")}>{(id) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field></div>
    </Modal>
  );
}

function ConfirmReceiptModal({ o, onClose, onSubmit, loading }: { o: Order; onClose: () => void; onSubmit: (b: unknown) => void; loading: boolean }) {
  const t = useTranslations("orders");
  const [rows, setRows] = useState(() => (o.items || []).map((i) => ({ order_item_id: i.id, name: i.name, ordered: i.quantity, received_qty: i.quantity, damaged_qty: 0 })));
  const [receiver, setReceiver] = useState("");
  const [notes, setNotes] = useState("");
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} size="lg" title={t("confirm_receipt")} description={t("confirm_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button variant="success" loading={loading} data-testid="submit-receipt"
        onClick={() => onSubmit({ items: rows.map(({ name: _n, ordered: _o, ...r }) => ({ ...r, received_qty: Number(r.received_qty), damaged_qty: Number(r.damaged_qty) })), receiver_name: receiver || null, notes: notes || null })}>{t("confirm_receipt")}</Button></>}>
      <div className="space-y-2">
        {rows.map((r, i) => (
          <div key={r.order_item_id} className="grid grid-cols-2 items-center gap-2 rounded-md border border-line p-3 sm:grid-cols-[1fr_110px_110px]">
            <p className="col-span-2 text-sm font-medium sm:col-span-1">{r.name} <span className="text-muted">× {r.ordered}</span></p>
            <Field label={t("received")}>{(id) => <Input id={id} type="number" min={0} max={r.ordered} value={r.received_qty} onChange={(e) => setRows((x) => x.map((y, j) => (j === i ? { ...y, received_qty: Number(e.target.value) } : y)))} />}</Field>
            <Field label={t("damaged")}>{(id) => <Input id={id} type="number" min={0} value={r.damaged_qty} onChange={(e) => setRows((x) => x.map((y, j) => (j === i ? { ...y, damaged_qty: Number(e.target.value) } : y)))} />}</Field>
          </div>
        ))}
        <Field label={t("receiver")}>{(id) => <Input id={id} value={receiver} onChange={(e) => setReceiver(e.target.value)} />}</Field>
        <Field label={t("notes")}>{(id) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}

function CollectionModal({ base, o, onClose, onDone }: { base: string; o: Order; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [amount, setAmount] = useState(String((Number(o.total) - Number(o.paid_amount)).toFixed(2)));
  const [method, setMethod] = useState("bank_transfer");
  const [reference, setReference] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("record_collection")} description={t("collection_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} onClick={async () => {
        const fd = new FormData();
        fd.set("amount", amount); fd.set("method", method);
        if (reference) fd.set("reference", reference);
        if (file) fd.set("proof", file);
        if (await run(() => api(`${base}/collections`, { form: fd }), { success: t("saved") })) onDone();
      }}>{t("save")}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("amount")}>{(id) => <Input id={id} type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />}</Field>
        <Field label={t("method")}>{(id) => <Select id={id} value={method} onChange={(e) => setMethod(e.target.value)}>{["bank_transfer", "cash", "cheque", "pos", "other"].map((m) => <option key={m} value={m}>{t(`methods.${m}`)}</option>)}</Select>}</Field>
        <Field label={t("reference")}>{(id) => <Input id={id} value={reference} onChange={(e) => setReference(e.target.value)} />}</Field>
        <Field label={t("proof")}>{(id) => <Input id={id} type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />}</Field>
      </div>
    </Modal>
  );
}

function InvoiceModal({ base, onClose, onDone }: { base: string; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [num, setNum] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("upload_invoice")} description={t("invoice_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} disabled={!num || !file} onClick={async () => {
        const fd = new FormData(); fd.set("invoice_number", num); fd.set("file", file!);
        if (await run(() => api(`${base}/invoice`, { form: fd }), { success: t("saved") })) onDone();
      }}>{t("save")}</Button></>}>
      <div className="space-y-3">
        <Field label={t("invoice_number")}>{(id) => <Input id={id} value={num} onChange={(e) => setNum(e.target.value)} dir="ltr" />}</Field>
        <Field label={t("file")}>{(id) => <Input id={id} type="file" accept="application/pdf,image/*" onChange={(e) => setFile(e.target.files?.[0] || null)} />}</Field>
      </div>
    </Modal>
  );
}

function ReturnModal({ o, onClose, onDone }: { o: Order; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [qty, setQty] = useState<Record<string, number>>({});
  const [reason, setReason] = useState("damaged");
  const [desc, setDesc] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const lines = Object.entries(qty).filter(([, q]) => q > 0).map(([order_item_id, quantity]) => ({ order_item_id, quantity }));
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} size="lg" title={t("request_return")} description={t("return_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} disabled={!lines.length} onClick={async () => {
        const fd = new FormData(); fd.set("reason", reason); fd.set("items", JSON.stringify(lines)); if (desc) fd.set("description", desc);
        Array.from(files || []).slice(0, 5).forEach((f) => fd.append("evidence", f));
        if (await run(() => api(`/retailer/orders/${o.id}/returns`, { form: fd }), { success: t("return_sent") })) onDone();
      }}>{t("send")}</Button></>}>
      <div className="space-y-2">
        {(o.items || []).map((i) => {
          const max = (i.delivered_qty ?? i.quantity) - i.returned_qty;
          return (
            <div key={i.id} className="flex items-center justify-between gap-3 rounded-md border border-line p-3 text-sm">
              <span>{i.name} <span className="text-muted">({t("max")} {max})</span></span>
              <Input className="w-24" type="number" min={0} max={max} value={qty[i.id] || 0} onChange={(e) => setQty({ ...qty, [i.id]: Math.min(max, Number(e.target.value)) })} />
            </div>
          );
        })}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("return_reason")}>{(id) => <Select id={id} value={reason} onChange={(e) => setReason(e.target.value)}>{["damaged", "expired", "wrong_item", "quality", "excess", "other"].map((r) => <option key={r} value={r}>{t(`return_reasons.${r}`)}</option>)}</Select>}</Field>
          <Field label={t("evidence")}>{(id) => <Input id={id} type="file" multiple accept="image/*,application/pdf" onChange={(e) => setFiles(e.target.files)} />}</Field>
        </div>
        <Field label={t("description")}>{(id) => <Textarea id={id} value={desc} onChange={(e) => setDesc(e.target.value)} />}</Field>
      </div>
    </Modal>
  );
}

function Stars({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" dir="ltr">
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" onClick={() => onChange(n)} aria-label={String(n)}>
          <Star className={`h-6 w-6 ${n <= value ? "fill-warning text-warning" : "text-line"}`} />
        </button>
      ))}
    </div>
  );
}

function RateModal({ o, onClose }: { o: Order; onClose: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [target, setTarget] = useState<"supplier" | "representative">("supplier");
  const [v, setV] = useState({ overall: 5, product_quality: 5, delivery_commitment: 5, communication: 5, comment: "" });
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("rate")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button loading={loading} onClick={async () => {
        if (await run(() => api(`/retailer/orders/${o.id}/ratings`, { body: { target, ...v, comment: v.comment || null } }), { success: t("thanks_rating") })) onClose();
      }}>{t("send")}</Button></>}>
      <div className="space-y-4">
        {o.representative && <Tabs value={target} onChange={setTarget} items={[{ value: "supplier", label: t("supplier") }, { value: "representative", label: t("representative") }]} />}
        {(["overall", "product_quality", "delivery_commitment", "communication"] as const).map((k) => (
          <div key={k} className="flex items-center justify-between"><span className="text-sm">{t(`rating.${k}`)}</span><Stars value={v[k]} onChange={(n) => setV({ ...v, [k]: n })} /></div>
        ))}
        <Field label={t("comment")}>{(id) => <Textarea id={id} value={v.comment} onChange={(e) => setV({ ...v, comment: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
}

function DisputeModal({ o, onClose, onDone }: { o: Order; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("orders");
  const { loading, run } = useApiAction();
  const [v, setV] = useState({ category: "delivery", subject: "", description: "" });
  return (
    <Modal open onOpenChange={(x) => !x && onClose()} title={t("open_dispute")} description={t("dispute_help")}
      footer={<><Button variant="outline" onClick={onClose}>{t("close")}</Button><Button variant="danger" loading={loading} disabled={v.subject.length < 3 || v.description.length < 10} onClick={async () => {
        if (await run(() => api("/complaints", { body: { kind: "order_dispute", order_id: o.id, ...v } }), { success: t("dispute_opened") })) onDone();
      }}>{t("send")}</Button></>}>
      <div className="space-y-3">
        <Field label={t("category")}>{(id) => <Select id={id} value={v.category} onChange={(e) => setV({ ...v, category: e.target.value })}>{["delivery", "product_quality", "pricing", "payment", "other"].map((c) => <option key={c} value={c}>{t(`complaint_categories.${c}`)}</option>)}</Select>}</Field>
        <Field label={t("subject")}>{(id) => <Input id={id} value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} />}</Field>
        <Field label={t("description")}>{(id) => <Textarea id={id} rows={4} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />}</Field>
      </div>
    </Modal>
  );
}
