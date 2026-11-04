"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Tabs } from "@/components/ui/data";
import { Card, EmptyState, PageHeader } from "@/components/ui/layout";
import { ConfirmDialog } from "@/components/ui/overlay";
import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type R = { id: string; target_type: string; overall: number; comment: string | null; status: string; created_at: string };

export default function AdminRatings() {
  const t = useTranslations("admin");
  const f = useFormat();
  const qc = useQueryClient();
  const [status, setStatus] = useState("flagged");
  const q = useApiQuery<R[]>(["admin-ratings", status], "/admin/ratings", { status });
  const [act, setAct] = useState<{ r: R; s: string } | null>(null);
  const { loading, run } = useApiAction();
  return (
    <>
      <PageHeader title={t("ratings_title")} subtitle={t("ratings_subtitle")} />
      <div className="mb-4"><Tabs value={status} onChange={setStatus} items={["flagged", "published", "hidden"].map((s) => ({ value: s, label: t(`rstatus.${s}`) }))} /></div>
      {q.data?.length ? <div className="space-y-3">{q.data.map((r) => (
        <Card key={r.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><p className="flex items-center gap-1 text-sm" dir="ltr">{Array.from({ length: 5 }).map((_, i) => <Star key={i} className={`h-4 w-4 ${i < r.overall ? "fill-warning text-warning" : "text-line"}`} />)}</p><p className="mt-1 text-sm">{r.comment || "—"}</p><p className="text-xs text-muted">{t(`rtargets.${r.target_type}`)} · {f.date(r.created_at)}</p></div>
          <div className="flex gap-2">{r.status !== "published" && <Button size="sm" variant="outline" onClick={() => setAct({ r, s: "published" })}>{t("publish")}</Button>}{r.status !== "hidden" && <Button size="sm" variant="ghost" className="text-danger" onClick={() => setAct({ r, s: "hidden" })}>{t("hide")}</Button>}</div>
        </Card>
      ))}</div> : <Card><EmptyState title={t("no_data")} /></Card>}
      <ConfirmDialog open={!!act} onOpenChange={(v) => !v && setAct(null)} title={t("moderate")} requireReason loading={loading} onConfirm={async (reason) => { if (await run(() => api(`/admin/ratings/${act!.r.id}?status=${act!.s}`, { body: { reason } }))) { setAct(null); qc.invalidateQueries({ queryKey: ["admin-ratings"] }); } }} />
    </>
  );
}
