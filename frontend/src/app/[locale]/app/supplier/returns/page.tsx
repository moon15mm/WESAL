"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Tabs, type Column } from "@/components/ui/data";
import { Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { ConfirmDialog, Modal } from "@/components/ui/overlay";
import { Button, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Ret = { id: string; number: string; order_number: string | null; status: string; reason: string; description: string | null; total_value: string; created_at: string; evidence: string[]; items: { id: string; name: string | null; quantity: number; approved_quantity: number | null }[] };

export default function SupplierReturns() {
  const t = useTranslations("returns");
  const f = useFormat();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const q = useApiQuery<Ret[]>(["sup-returns", status], "/supplier/returns", { status: status || undefined });
  const [open, setOpen] = useState<Ret | null>(null);
  const [reject, setReject] = useState(false);
  const [settle, setSettle] = useState("");
  const { loading, run } = useApiAction();
  const refresh = () => { qc.invalidateQueries({ queryKey: ["sup-returns"] }); setOpen(null); };
  const act = async (path: string, body: unknown) => { if (await run(() => api(`/supplier/returns/${open!.id}/${path}`, { body }), { success: t("saved") })) refresh(); };
  const cols: Column<Ret>[] = [
    { key: "n", header: t("number"), cell: (r) => <span className="ltr font-semibold">{r.number}</span> },
    { key: "o", header: t("order"), cell: (r) => <span className="ltr">{r.order_number}</span> },
    { key: "r", header: t("reason"), cell: (r) => t(`reasons.${r.reason}`) },
    { key: "s", header: t("status_label"), cell: (r) => <StatusBadge status={r.status} /> },
    { key: "v", header: t("value"), numeric: true, cell: (r) => f.money(r.total_value) },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("supplier_subtitle")} />
      <div className="mb-4"><Tabs value={status} onChange={setStatus} items={["", "requested", "approved", "received", "settled", "rejected"].map((s) => ({ value: s, label: s ? t(`status.${s}`) : t("all") }))} /></div>
      <Card padded={false}><DataTable columns={cols} rows={q.data} loading={q.isLoading} rowKey={(r) => r.id} onRowClick={setOpen} /></Card>
      {open && (
        <Modal open onOpenChange={(v) => !v && setOpen(null)} size="lg" title={`${t("return")} ${open.number}`} description={open.description || undefined}
          footer={<>
            {open.status === "requested" && <><Button variant="ghost" className="text-danger" onClick={() => setReject(true)}>{t("reject")}</Button><Button variant="success" loading={loading} onClick={() => act("decide", { decision: "approve" })}>{t("approve")}</Button></>}
            {open.status === "approved" && <Button loading={loading} onClick={() => act("receive", {})}>{t("mark_received")}</Button>}
            {open.status === "received" && <Button loading={loading} disabled={settle.length < 3} onClick={() => act("settle", { settlement_note: settle })}>{t("mark_settled")}</Button>}
          </>}>
          <ul className="space-y-2 text-sm">{open.items.map((i) => <li key={i.id} className="flex justify-between"><span>{i.name}</span><span className="tabular">{f.number(i.approved_quantity ?? i.quantity)}</span></li>)}</ul>
          {open.evidence.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{open.evidence.map((u) => <a key={u} href={u} target="_blank"><img src={u} alt="" className="h-20 w-20 rounded-md object-cover ring-1 ring-line" /></a>)}</div>}
          {open.status === "received" && <div className="mt-4"><p className="mb-1 text-sm font-medium">{t("settlement_note")}</p><Textarea value={settle} onChange={(e) => setSettle(e.target.value)} placeholder={t("settlement_hint")} /></div>}
          <p className="mt-4 text-xs text-muted">{t("offline_note")}</p>
        </Modal>
      )}
      <ConfirmDialog open={reject} onOpenChange={setReject} title={t("reject")} requireReason tone="danger" loading={loading} onConfirm={async (notes) => { setReject(false); await act("decide", { decision: "reject", notes }); }} />
    </>
  );
}
