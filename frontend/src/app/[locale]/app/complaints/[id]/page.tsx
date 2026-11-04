"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { use, useState } from "react";
import { Card, CardHeader, KV, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Button, Textarea } from "@/components/ui/primitives";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { cx, useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";
import type { Complaint } from "../page";

export default function ComplaintPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("complaints");
  const f = useFormat();
  const qc = useQueryClient();
  const q = useApiQuery<Complaint>(["complaint", id], `/complaints/${id}`);
  const [msg, setMsg] = useState("");
  const { loading, run } = useApiAction();
  if (!q.data) return <SkeletonRows />;
  const c = q.data;
  return (
    <>
      <PageHeader back={<Link href="/app/complaints" className="mb-2 inline-block text-sm text-teal-600">← {t("title")}</Link>} title={<span className="flex items-center gap-2">{c.subject}<StatusBadge status={c.status} /></span>} subtitle={`${c.number} · ${t(`kinds.${c.kind}`)}`} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <p className="whitespace-pre-line text-sm leading-7">{c.description}</p>
          <div className="mt-6 space-y-3">
            {c.messages.map((m) => (
              <div key={m.id} className={cx("max-w-[85%] rounded-lg p-3 text-sm", m.author_side === c.my_side ? "ms-auto bg-teal-50" : m.author_side === "admin" ? "bg-navy-50" : "bg-page")}>
                <p className="mb-1 text-xs font-medium text-muted">{t(`sides.${m.author_side}`)} · {f.datetime(m.created_at)}</p>
                <p className="whitespace-pre-line">{m.body}</p>
              </div>
            ))}
          </div>
          {!["closed", "rejected"].includes(c.status) && (
            <div className="mt-4 flex gap-2"><Textarea rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t("reply_placeholder")} /><Button loading={loading} disabled={!msg.trim()} onClick={async () => { if (await run(() => api(`/complaints/${id}/messages`, { body: { body: msg } }))) { setMsg(""); qc.invalidateQueries({ queryKey: ["complaint", id] }); } }}>{t("reply")}</Button></div>
          )}
        </Card>
        <Card>
          <CardHeader title={t("details")} />
          <KV className="sm:grid-cols-1" items={[[t("category"), t(`categories.${c.category}`)], [t("order"), c.order && <span key="o" className="ltr">{c.order.number}</span>], [t("against"), c.against_business?.name || c.against_representative?.display_name], [t("date"), f.datetime(c.created_at)], [t("resolution"), c.resolution]]} />
        </Card>
      </div>
    </>
  );
}
