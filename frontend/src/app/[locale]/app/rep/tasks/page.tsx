"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Target } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge, Card, CardHeader, EmptyState, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

type Task = { id: string; title: string; description: string | null; due_at: string | null; priority: string; status: string };
type TargetRow = { id: string; period_start: string; period_end: string; sales_target: string; sales_actual: string; visits_target: number; visits_actual: number; new_customers_target: number; new_customers_actual: number };

function Progress({ label, actual, target, money }: { label: string; actual: number; target: number; money?: boolean }) {
  const f = useFormat();
  const pct = target ? Math.min(100, Math.round((actual / target) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm"><span>{label}</span><span className="tabular text-muted">{money ? f.money(actual) : f.number(actual)} / {money ? f.money(target) : f.number(target)}</span></div>
      <div className="h-2 rounded-full bg-navy-50"><div className="h-full rounded-full bg-teal-500" style={{ width: `${pct}%` }} /></div>
    </div>
  );
}

export default function RepTasks() {
  const t = useTranslations("tasks");
  const f = useFormat();
  const qc = useQueryClient();
  const tasks = useApiQuery<Task[]>(["rep-tasks-all"], "/rep/tasks");
  const targets = useApiQuery<TargetRow[]>(["rep-targets"], "/rep/targets");
  const done = async (id: string) => { await api(`/rep/tasks/${id}`, { method: "PATCH", body: { status: "done" } }); qc.invalidateQueries({ queryKey: ["rep-tasks-all"] }); };
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("rep_subtitle")} />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          {tasks.isLoading ? <SkeletonRows /> : tasks.data?.length ? tasks.data.map((x) => (
            <Card key={x.id} className="flex items-start justify-between gap-3">
              <div><p className="flex items-center gap-2 font-semibold text-navy-700">{x.title}<Badge tone={x.priority === "urgent" || x.priority === "high" ? "danger" : "neutral"}>{t(`priority.${x.priority}`)}</Badge></p>{x.description && <p className="mt-1 text-sm text-muted">{x.description}</p>}<p className="mt-1 text-xs text-muted">{t("due")}: {f.date(x.due_at)}</p></div>
              {x.status === "done" ? <StatusBadge status="completed" /> : <Button size="sm" variant="outline" icon={<CheckCircle2 className="h-4 w-4" />} onClick={() => done(x.id)}>{t("mark_done")}</Button>}
            </Card>
          )) : <Card><EmptyState title={t("empty")} /></Card>}
        </div>
        <Card>
          <CardHeader title={t("targets")} action={<Target className="h-5 w-5 text-teal-500" />} />
          {targets.data?.length ? targets.data.map((g) => (
            <div key={g.id} className="mb-5 space-y-3 last:mb-0">
              <p className="text-xs text-muted">{f.date(g.period_start)} → {f.date(g.period_end)}</p>
              <Progress label={t("sales")} actual={Number(g.sales_actual)} target={Number(g.sales_target)} money />
              <Progress label={t("visits")} actual={g.visits_actual} target={g.visits_target} />
              <Progress label={t("new_customers")} actual={g.new_customers_actual} target={g.new_customers_target} />
            </div>
          )) : <p className="text-sm text-muted">{t("no_targets")}</p>}
        </Card>
      </div>
    </>
  );
}
