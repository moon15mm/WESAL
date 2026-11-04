"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { CommissionTable, type Commission } from "@/components/app/commissions";
import { Pagination, Tabs } from "@/components/ui/data";
import { Card, PageHeader, Stat } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

export default function RepCommissions() {
  const t = useTranslations("commissions");
  const f = useFormat();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const list = useList<Commission>("/rep/commissions", { status });
  const summary = (list.data?.summary || {}) as Record<string, { count: number; amount: string }>;
  const [dispute, setDispute] = useState<Commission | null>(null);
  const [v, setV] = useState({ reason: "", expected_amount: "" });
  const { loading, run } = useApiAction();
  const sum = (ks: string[]) => ks.reduce((a, k) => a + Number(summary[k]?.amount || 0), 0);
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("rep_subtitle")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("expected")} value={f.money(sum(["estimated", "pending"]))} />
        <Stat label={t("due")} value={f.money(sum(["due", "approved"]))} tone="teal" />
        <Stat label={t("paid")} value={f.money(sum(["paid", "adjusted"]))} />
        <Stat label={t("disputed")} value={f.money(sum(["disputed"]))} tone="warning" />
      </div>
      <div className="my-4"><Tabs value={status} onChange={(x) => { setStatus(x); list.reset(); }} items={["", "estimated", "pending", "due", "approved", "paid", "disputed", "cancelled"].map((s) => ({ value: s, label: s ? t(`status.${s}`) : t("all") }))} /></div>
      <Card padded={false}>
        <CommissionTable rows={list.data?.items} loading={list.isLoading} side="rep" onDispute={(c) => setDispute(c)} />
        {list.data && <Pagination page={list.page} pageSize={list.pageSize} total={list.data.total} onPage={list.setPage} />}
      </Card>
      <Modal open={!!dispute} onOpenChange={(x) => !x && setDispute(null)} title={t("dispute")} description={t("dispute_hint")}
        footer={<><Button variant="outline" onClick={() => setDispute(null)}>{t("cancel")}</Button><Button variant="danger" loading={loading} disabled={v.reason.length < 10} onClick={async () => {
          if (await run(() => api(`/rep/commissions/${dispute!.id}/dispute`, { body: { reason: v.reason, expected_amount: v.expected_amount || null } }), { success: t("dispute_sent") })) { setDispute(null); qc.invalidateQueries({ queryKey: ["/rep/commissions"] }); }
        }}>{t("send")}</Button></>}>
        <div className="space-y-3">
          <Field label={t("reason")} required>{(id) => <Textarea id={id} value={v.reason} onChange={(e) => setV({ ...v, reason: e.target.value })} />}</Field>
          <Field label={t("expected_amount")}>{(id) => <Input id={id} type="number" step="0.01" value={v.expected_amount} onChange={(e) => setV({ ...v, expected_amount: e.target.value })} />}</Field>
        </div>
      </Modal>
    </>
  );
}
