"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { DataTable, Tabs, type Column } from "@/components/ui/data";
import { Badge, Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useApiAction } from "@/lib/useApiForm";

type Task = { id: string; representative_id: string; title: string; due_at: string | null; priority: string; status: string };
type TargetRow = { id: string; representative_id: string; period_start: string; period_end: string; sales_target: string; sales_actual: string; visits_target: number; visits_actual: number };
type Rep = { id: string; display_name: string };

export default function SupplierTasks() {
  const t = useTranslations("tasks");
  const f = useFormat();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"tasks" | "targets">("tasks");
  const reps = useApiQuery<Rep[]>(["sup-reps"], "/supplier/reps");
  const tasks = useApiQuery<Task[]>(["sup-tasks"], "/supplier/tasks");
  const targets = useApiQuery<TargetRow[]>(["sup-targets"], "/supplier/targets");
  const [task, setTask] = useState<null | { representative_id: string; title: string; description: string; due_at: string; priority: string }>(null);
  const [target, setTarget] = useState<null | { representative_id: string; period_start: string; period_end: string; sales_target: string; visits_target: string; new_customers_target: string }>(null);
  const { loading, run } = useApiAction();
  const name = (id: string) => reps.data?.find((r) => r.id === id)?.display_name || "—";
  const cols: Column<Task>[] = [
    { key: "t", header: t("task"), cell: (x) => <span className="font-medium">{x.title}</span> },
    { key: "r", header: t("representative"), cell: (x) => name(x.representative_id) },
    { key: "p", header: t("priority_label"), cell: (x) => <Badge tone={["high", "urgent"].includes(x.priority) ? "danger" : "neutral"}>{t(`priority.${x.priority}`)}</Badge> },
    { key: "d", header: t("due"), cell: (x) => f.date(x.due_at) },
    { key: "s", header: t("status"), cell: (x) => <StatusBadge status={x.status === "done" ? "completed" : x.status} /> },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("supplier_subtitle")} actions={<Button icon={<Plus className="h-4 w-4" />} onClick={() => tab === "tasks" ? setTask({ representative_id: "", title: "", description: "", due_at: "", priority: "normal" }) : setTarget({ representative_id: "", period_start: new Date().toISOString().slice(0, 8) + "01", period_end: "", sales_target: "", visits_target: "0", new_customers_target: "0" })}>{tab === "tasks" ? t("new_task") : t("new_target")}</Button>} />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} items={[{ value: "tasks", label: t("tasks") }, { value: "targets", label: t("targets") }]} /></div>
      {tab === "tasks" ? <Card padded={false}><DataTable columns={cols} rows={tasks.data} loading={tasks.isLoading} rowKey={(x) => x.id} /></Card> : (
        <Card padded={false}><DataTable rows={targets.data} loading={targets.isLoading} rowKey={(x) => x.id} columns={[
          { key: "r", header: t("representative"), cell: (x) => name(x.representative_id) },
          { key: "p", header: t("period"), cell: (x) => `${f.date(x.period_start)} → ${f.date(x.period_end)}` },
          { key: "s", header: t("sales"), numeric: true, cell: (x) => `${f.money(x.sales_actual)} / ${f.money(x.sales_target)}` },
          { key: "v", header: t("visits"), numeric: true, cell: (x) => `${f.number(x.visits_actual)} / ${f.number(x.visits_target)}` },
        ]} /></Card>
      )}
      {task && (
        <Modal open onOpenChange={(v) => !v && setTask(null)} title={t("new_task")} footer={<><Button variant="outline" onClick={() => setTask(null)}>{t("cancel")}</Button><Button loading={loading} disabled={!task.representative_id || !task.title} onClick={async () => {
          if (await run(() => api("/supplier/tasks", { body: { ...task, description: task.description || null, due_at: task.due_at ? new Date(task.due_at).toISOString() : null } }), { success: t("saved") })) { setTask(null); qc.invalidateQueries({ queryKey: ["sup-tasks"] }); }
        }}>{t("save")}</Button></>}>
          <div className="space-y-3">
            <Field label={t("representative")}>{(id) => <Select id={id} value={task.representative_id} onChange={(e) => setTask({ ...task, representative_id: e.target.value })}><option value="">—</option>{reps.data?.map((r) => <option key={r.id} value={r.id}>{r.display_name}</option>)}</Select>}</Field>
            <Field label={t("task")}>{(id) => <Input id={id} value={task.title} onChange={(e) => setTask({ ...task, title: e.target.value })} />}</Field>
            <Field label={t("description")}>{(id) => <Textarea id={id} value={task.description} onChange={(e) => setTask({ ...task, description: e.target.value })} />}</Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("due")}>{(id) => <Input id={id} type="datetime-local" value={task.due_at} onChange={(e) => setTask({ ...task, due_at: e.target.value })} />}</Field>
              <Field label={t("priority_label")}>{(id) => <Select id={id} value={task.priority} onChange={(e) => setTask({ ...task, priority: e.target.value })}>{["low", "normal", "high", "urgent"].map((p) => <option key={p} value={p}>{t(`priority.${p}`)}</option>)}</Select>}</Field>
            </div>
          </div>
        </Modal>
      )}
      {target && (
        <Modal open onOpenChange={(v) => !v && setTarget(null)} title={t("new_target")} footer={<><Button variant="outline" onClick={() => setTarget(null)}>{t("cancel")}</Button><Button loading={loading} disabled={!target.representative_id || !target.period_end} onClick={async () => {
          if (await run(() => api("/supplier/targets", { body: { ...target, sales_target: target.sales_target || "0", visits_target: Number(target.visits_target), new_customers_target: Number(target.new_customers_target) } }), { success: t("saved") })) { setTarget(null); qc.invalidateQueries({ queryKey: ["sup-targets"] }); }
        }}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("representative")} className="sm:col-span-2">{(id) => <Select id={id} value={target.representative_id} onChange={(e) => setTarget({ ...target, representative_id: e.target.value })}><option value="">—</option>{reps.data?.map((r) => <option key={r.id} value={r.id}>{r.display_name}</option>)}</Select>}</Field>
            <Field label={t("from")}>{(id) => <Input id={id} type="date" value={target.period_start} onChange={(e) => setTarget({ ...target, period_start: e.target.value })} />}</Field>
            <Field label={t("to")}>{(id) => <Input id={id} type="date" value={target.period_end} onChange={(e) => setTarget({ ...target, period_end: e.target.value })} />}</Field>
            <Field label={t("sales")}>{(id) => <Input id={id} type="number" value={target.sales_target} onChange={(e) => setTarget({ ...target, sales_target: e.target.value })} />}</Field>
            <Field label={t("visits")}>{(id) => <Input id={id} type="number" value={target.visits_target} onChange={(e) => setTarget({ ...target, visits_target: e.target.value })} />}</Field>
            <Field label={t("new_customers")}>{(id) => <Input id={id} type="number" value={target.new_customers_target} onChange={(e) => setTarget({ ...target, new_customers_target: e.target.value })} />}</Field>
          </div>
        </Modal>
      )}
    </>
  );
}
