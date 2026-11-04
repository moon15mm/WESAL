"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, type Column } from "@/components/ui/data";
import { Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

export type Complaint = { id: string; number: string; kind: string; category: string; status: string; priority: string; subject: string; description: string; my_side: string | null;
  order: { id: string; number: string; status: string } | null; raised_by_business: { name: string } | null; against_business: { name: string } | null; against_representative: { display_name: string } | null;
  resolution: string | null; created_at: string; messages: { id: string; author_side: string; body: string; created_at: string }[] };

export default function Complaints() {
  const t = useTranslations("complaints");
  const f = useFormat();
  const qc = useQueryClient();
  const router = useRouter();
  const { workspace } = useSession();
  const q = useApiQuery<Complaint[]>(["complaints"], "/complaints");
  const [open, setOpen] = useState(false);
  const [v, setV] = useState({ category: "other", subject: "", description: "" });
  const { loading, run } = useApiAction();
  const cols: Column<Complaint>[] = [
    { key: "n", header: t("number"), cell: (c) => <span className="ltr font-semibold">{c.number}</span> },
    { key: "s", header: t("subject"), cell: (c) => c.subject },
    { key: "k", header: t("kind"), hideOnMobile: true, cell: (c) => t(`kinds.${c.kind}`) },
    { key: "side", header: t("side"), hideOnMobile: true, cell: (c) => (c.my_side ? t(`sides.${c.my_side}`) : "—") },
    { key: "st", header: t("status"), cell: (c) => <StatusBadge status={c.status} /> },
    { key: "d", header: t("date"), hideOnMobile: true, cell: (c) => f.date(c.created_at) },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => setOpen(true)}>{t("new")}</Button>} />
      <Card padded={false}><DataTable columns={cols} rows={q.data} loading={q.isLoading} rowKey={(c) => c.id} onRowClick={(c) => router.push(`/app/complaints/${c.id}`)} /></Card>
      <Modal open={open} onOpenChange={setOpen} title={t("new")} description={t("new_hint")} footer={<><Button variant="outline" onClick={() => setOpen(false)}>{t("cancel")}</Button><Button loading={loading} disabled={v.subject.length < 3 || v.description.length < 10} onClick={async () => {
        if (await run(() => api("/complaints", { body: { kind: "complaint", ...v, business_id: workspace?.businessId || null } }), { success: t("sent") })) { setOpen(false); qc.invalidateQueries({ queryKey: ["complaints"] }); }
      }}>{t("send")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("category")}>{(id) => <Select id={id} value={v.category} onChange={(e) => setV({ ...v, category: e.target.value })}>{["delivery", "product_quality", "pricing", "representative_conduct", "payment", "account", "other"].map((c) => <option key={c} value={c}>{t(`categories.${c}`)}</option>)}</Select>}</Field>
          <Field label={t("subject")}>{(id) => <Input id={id} value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value })} />}</Field>
          <Field label={t("description")}>{(id) => <Textarea id={id} rows={5} value={v.description} onChange={(e) => setV({ ...v, description: e.target.value })} />}</Field>
        </div>
      </Modal>
    </>
  );
}
