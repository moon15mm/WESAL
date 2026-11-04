"use client";

import { Building2, CircleDollarSign, Gauge, MessageSquareWarning, ShieldCheck, ShoppingBag, Store, Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { BarList, Donut, TrendChart } from "@/components/ui/charts";
import { Tabs } from "@/components/ui/data";
import { Card, CardHeader, EmptyState, PageHeader, SkeletonRows, Stat } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

type Dash = { kpis: Record<string, number | string>; series: Record<string, unknown>[]; statuses: Record<string, number>; regions: { region: string; orders: number; value: string }[] };

export default function AdminDashboard() {
  const t = useTranslations("admin");
  const ts = useTranslations("status");
  const f = useFormat();
  const [days, setDays] = useState("30");
  const d = useApiQuery<Dash>(["admin-dash", days], "/admin/dashboard", { days });
  if (!d.data) return <SkeletonRows rows={8} />;
  const k = d.data.kpis;
  return (
    <>
      <PageHeader title={t("dashboard_title")} subtitle={t("dashboard_subtitle")} actions={<Tabs value={days} onChange={setDays} items={["7", "30", "90", "365"].map((x) => ({ value: x, label: t("days_n", { n: x }) }))} />} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("kpi.gmv")} value={f.money(k.gmv)} icon={<CircleDollarSign className="h-5 w-5" />} />
        <Stat label={t("kpi.orders")} value={f.number(k.orders)} icon={<ShoppingBag className="h-5 w-5" />} tone="teal" hint={t("completed_n", { n: f.number(k.completed) })} />
        <Stat label={t("kpi.aov")} value={f.money(k.avg_order_value)} icon={<Gauge className="h-5 w-5" />} hint={`${t("kpi.conversion")}: ${f.percent(k.conversion_rate)}`} />
        <Stat label={t("kpi.mrr")} value={f.money(k.platform_mrr)} icon={<CircleDollarSign className="h-5 w-5" />} hint={t("mrr_hint")} />
        <Stat label={t("kpi.users")} value={f.number(k.users)} icon={<Users className="h-5 w-5" />} hint={t("new_n", { n: f.number(k.new_users) })} />
        <Stat label={t("kpi.suppliers")} value={`${f.number(k.active_suppliers)} / ${f.number(k.verified_suppliers)}`} icon={<Building2 className="h-5 w-5" />} hint={t("active_verified")} />
        <Stat label={t("kpi.stores")} value={`${f.number(k.active_stores)} / ${f.number(k.stores)}`} icon={<Store className="h-5 w-5" />} hint={t("active_total")} />
        <Stat label={t("kpi.reps")} value={`${f.number(k.active_representatives)} / ${f.number(k.representatives)}`} icon={<Users className="h-5 w-5" />} hint={t("active_total")} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader title={t("gmv_trend")} />{d.data.series.length ? <TrendChart data={d.data.series} /> : <EmptyState title={t("no_data")} />}</Card>
        <div className="space-y-4">
          <Link href="/app/admin/verification"><Stat label={t("kpi.pending_verifications")} value={f.number(k.pending_verifications)} icon={<ShieldCheck className="h-5 w-5" />} tone="warning" /></Link>
          <Link href="/app/admin/complaints"><Stat label={t("kpi.open_disputes")} value={`${f.number(k.open_disputes)} · ${f.number(k.open_complaints)}`} icon={<MessageSquareWarning className="h-5 w-5" />} tone="danger" hint={t("disputes_complaints")} /></Link>
        </div>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card><CardHeader title={t("regions")} />{d.data.regions.length ? <BarList data={d.data.regions} label="region" value="value" /> : <p className="text-sm text-muted">—</p>}</Card>
        <Card><CardHeader title={t("order_statuses")} />{Object.keys(d.data.statuses).length ? <Donut data={Object.entries(d.data.statuses).map(([s, v]) => ({ name: ts.has(s) ? ts(s) : s, value: v }))} /> : <p className="text-sm text-muted">—</p>}</Card>
      </div>
    </>
  );
}
