"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { Complaint } from "@/app/[locale]/app/complaints/page";
import { DataTable, Pagination, Tabs, type Column } from "@/components/ui/data";
import { Badge, Card, KV, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Checkbox, Field, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cx, useFormat } from "@/lib/format";
import { useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

export default function AdminComplaints() {
  const t = useTranslations("admin");
  const tc = useTranslations("complaints");
  const f = useFormat();
  const qc = useQueryClient();
  const [status, setStatus] = useState("open");
  const list = useList<Complaint>("/admin/complaints", { status });
  const [open, setOpen] = useState<Complaint | null>(null);
  const [v, setV] = useState({ message: "", internal: false, status: "", resolution: "", order_outcome: "restore" });
  const { loading, run } = useApiAction();
  const cols: Column<Complaint>[] = [
    { key: "n", header: tc("number"), cell: (c) => <span className="ltr font-semibold">{c.number}</span> },
    { key: "s", header: tc("subject"), cell: (c) => c.subject },
    { key: "k", header: tc("kind"), cell: (c) => <Badge tone={c.kind === "order_dispute" ? "danger" : "neutral"}>{tc(`kinds.${c.kind}`)}</Badge> },
    { key: "p", header: t("parties"), hideOnMobile: true, cell: (c) => `${c.raised_by_business?.name || "—"} → ${c.against_business?.name || c.against_representative?.display_name || "—"}` },
    { key: "st", header: tc("status"), cell: (c) => <StatusBadge status={c.status} /> },
    { key: "d", header: tc("date"), hideOnMobile: true, cell: (c) => f.date(c.created_at) },
  ];
  return (
    <>
      <PageHeader title={t("complaints_title")} />
      <div className="mb-4"><Tabs value={status} onChange={(x) => { setStatus(x); list.reset(); }} items={["open", "in_review", "awaiting_response", "resolved", "rejected", "closed", ""].map((s) => ({ value: s, label: s ? tc(`status.${s}`) : t("all") }))} /></div>
      <Card padded={false}><DataTable columns={cols} rows={list.data?.items} loading={list.isLoading} rowKey={(c) => c.id} onRowClick={(c) => { setOpen(c); setV({ message: "", internal: false, status: "", resolution: "", order_outcome: "restore" }); }} />{list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}</Card>
      {open && (
        <Modal open onOpenChange={(x) => !x && setOpen(null)} size="lg" title={open.subject} description={`${open.number} · ${tc(`categories.${open.category}`)}`}
          footer={<><Button variant="outline" onClick={() => setOpen(null)}>{t("close")}</Button><Button loading={loading} onClick={async () => {
            const body = { message: v.message || null, internal: v.internal, status: v.status || null, resolution: v.resolution || null, order_outcome: open.kind === "order_dispute" ? v.order_outcome : null };
            if (await run(() => api(`/admin/complaints/${open.id}`, { body }), { success: t("saved") })) { setOpen(null); qc.invalidateQueries({ queryKey: ["/admin/complaints"] }); }
          }}>{t("save")}</Button></>}>
          <p className="whitespace-pre-line text-sm">{open.description}</p>
          {open.order && <div className="mt-3"><KV items={[[tc("order"), <span key="o" className="ltr">{open.order.number}</span>], [tc("status"), <StatusBadge key="s" status={open.order.status} />]]} /></div>}
          <div className="mt-4 max-h-56 space-y-2 overflow-y-auto">{open.messages.map((m) => <div key={m.id} className={cx("rounded-md p-2 text-sm", m.author_side === "admin" ? "bg-navy-50" : "bg-page")}><p className="text-xs text-muted">{tc(`sides.${m.author_side}`)} · {f.datetime(m.created_at)}</p>{m.body}</div>)}</div>
          <div className="mt-4 space-y-3">
            <Field label={t("message")}>{(id) => <Textarea id={id} value={v.message} onChange={(e) => setV({ ...v, message: e.target.value })} />}</Field>
            <Checkbox checked={v.internal} onChange={(e) => setV({ ...v, internal: e.target.checked })} label={t("internal_note")} />
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("new_status")}>{(id) => <Select id={id} value={v.status} onChange={(e) => setV({ ...v, status: e.target.value })}><option value="">—</option>{["in_review", "awaiting_response", "resolved", "rejected", "closed"].map((s) => <option key={s} value={s}>{tc(`status.${s}`)}</option>)}</Select>}</Field>
              {open.kind === "order_dispute" && <Field label={t("order_outcome")}>{(id) => <Select id={id} value={v.order_outcome} onChange={(e) => setV({ ...v, order_outcome: e.target.value })}>{["restore", "completed", "cancelled"].map((s) => <option key={s} value={s}>{t(`outcomes.${s}`)}</option>)}</Select>}</Field>}
            </div>
            {["resolved", "rejected"].includes(v.status) && <Field label={tc("resolution")}>{(id) => <Textarea id={id} value={v.resolution} onChange={(e) => setV({ ...v, resolution: e.target.value })} />}</Field>}
          </div>
        </Modal>
      )}
    </>
  );
}
