"use client";

import { CalendarClock, ClipboardCheck, Lightbulb, MapPin, Route, Wallet } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card, CardHeader, EmptyState, PageHeader, Stat, StatusBadge } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import type { Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";

type Visit = { id: string; customer_name: string | null; purpose: string; status: string; scheduled_at: string | null };
type Perf = { current: Record<string, number | string>; previous: Record<string, number | string>; insights: { code: string; value: unknown }[] };
type Opp = { customers: { customer_id: string; name: string; score: number; reasons: string[] }[]; new_stores: { retailer_id: string; name: string; district: string | null }[] };
type Task = { id: string; title: string; due_at: string | null; priority: string; status: string };
type Auth = { id: string; status: string; supplier: { name: string }; end_date: string | null };

export default function RepDashboard() {
  const t = useTranslations("rep");
  const f = useFormat();
  const { me } = useSession();
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59).toISOString();
  const visits = useApiQuery<Page<Visit>>(["rep-visits-today"], "/rep/visits", { date_from: start, date_to: end, page_size: 10 });
  const perf = useApiQuery<Perf>(["rep-perf"], "/ai/rep/performance");
  const opps = useApiQuery<Opp>(["rep-opps"], "/ai/rep/opportunities");
  const comm = useApiQuery<Page<unknown> & { summary: Record<string, { amount: string }> }>(["rep-comm"], "/rep/commissions", { page_size: 1 });
  const tasks = useApiQuery<Task[]>(["rep-tasks"], "/rep/tasks", { status: "open" });
  const auths = useApiQuery<Auth[]>(["rep-auths"], "/rep/authorizations");
  const pending = useApiQuery<Page<unknown>>(["rep-pending"], "/rep/orders", { status: "pending_retailer_approval", page_size: 1 });
  const c = perf.data?.current || {};
  const s = comm.data?.summary || {};
  const owed = ["estimated", "pending", "due", "approved"].reduce((a, k) => a + Number(s[k]?.amount || 0), 0);
  return (
    <>
      <PageHeader title={t("hello", { name: me?.full_name.split(" ")[0] || "" })} subtitle={t("dashboard_subtitle")}
        actions={<><Link href="/app/rep/visits?new=1" className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-semibold"><MapPin className="h-4 w-4" />{t("start_visit")}</Link><Link href="/app/rep/orders/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-teal-500 px-4 text-sm font-semibold text-white">{t("new_order")}</Link></>} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("kpi_sales")} value={f.money(c.sales)} icon={<Wallet className="h-5 w-5" />} hint={t("last_30")} />
        <Stat label={t("kpi_visits")} value={f.number(c.visits)} icon={<Route className="h-5 w-5" />} tone="teal" />
        <Stat label={t("kpi_pending_store")} value={f.number(pending.data?.total)} icon={<ClipboardCheck className="h-5 w-5" />} tone="warning" />
        <Stat label={t("kpi_commissions")} value={f.money(owed)} icon={<Wallet className="h-5 w-5" />} hint={t("not_paid_yet")} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("today_visits")} action={<CalendarClock className="h-5 w-5 text-teal-500" />} />
          {visits.data?.items.length ? (
            <ul className="space-y-2">{visits.data.items.map((v) => <li key={v.id}><Link href="/app/rep/visits" className="flex items-center justify-between gap-2 rounded-md border border-line p-3 text-sm"><span><span className="block font-medium">{v.customer_name || "—"}</span><span className="text-xs text-muted">{f.datetime(v.scheduled_at)} · {t(`purposes.${v.purpose}`)}</span></span><StatusBadge status={v.status} /></Link></li>)}</ul>
          ) : <EmptyState title={t("no_visits_today")} />}
        </Card>
        <Card>
          <CardHeader title={t("opportunities")} action={<Lightbulb className="h-5 w-5 text-warning" />} />
          {opps.data && (opps.data.customers.length || opps.data.new_stores.length) ? (
            <ul className="space-y-2 text-sm">
              {opps.data.customers.slice(0, 5).map((o) => <li key={o.customer_id}><Link href={`/app/rep/customers/${o.customer_id}`} className="block rounded-md bg-page p-2.5"><span className="font-medium">{o.name}</span><span className="mt-0.5 block text-xs text-muted">{o.reasons.map((r) => t(`reasons.${r}`)).join(" · ")}</span></Link></li>)}
              {opps.data.new_stores.slice(0, 3).map((s) => <li key={s.retailer_id}><Link href="/app/rep/discover" className="block rounded-md bg-teal-50 p-2.5"><span className="font-medium">{s.name}</span><span className="mt-0.5 block text-xs text-teal-700">{t("reasons.new_store_in_your_area")}{s.district && ` · ${s.district}`}</span></Link></li>)}
            </ul>
          ) : <EmptyState title={t("no_opportunities")} />}
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title={t("insights")} />
            {perf.data?.insights.length ? <ul className="space-y-2 text-sm">{perf.data.insights.map((i, k) => <li key={k} className="rounded-md bg-navy-50 p-2.5">{t(`insight.${i.code}`, { value: String(i.value) })}</li>)}</ul> : <p className="text-sm text-muted">{t("no_insights")}</p>}
            <p className="mt-3 text-xs text-muted">{t("conversion")}: {f.percent(c.conversion)}</p>
          </Card>
          <Card>
            <CardHeader title={t("tasks")} action={<Link href="/app/rep/tasks" className="text-sm text-teal-600">{t("view_all")}</Link>} />
            {tasks.data?.length ? <ul className="space-y-2 text-sm">{tasks.data.slice(0, 4).map((x) => <li key={x.id} className="flex justify-between gap-2"><span>{x.title}</span><span className="text-xs text-muted">{f.date(x.due_at)}</span></li>)}</ul> : <p className="text-sm text-muted">{t("no_tasks")}</p>}
          </Card>
          <Card>
            <CardHeader title={t("authorizations")} />
            <ul className="space-y-2 text-sm">{auths.data?.slice(0, 4).map((a) => <li key={a.id}><Link href={`/app/rep/authorizations/${a.id}`} className="flex items-center justify-between gap-2"><span className="truncate">{a.supplier.name}</span><StatusBadge status={a.status} /></Link></li>)}</ul>
            {!auths.data?.length && <Link href="/app/rep/companies" className="text-sm font-medium text-teal-600">{t("find_companies")} →</Link>}
          </Card>
        </div>
      </div>
    </>
  );
}
