"use client";

import { AlertTriangle, PackageOpen, ShoppingBag, Sparkles, Truck, UsersRound, Wallet } from "lucide-react";
import { useTranslations } from "next-intl";
import { BarList, Donut, TrendChart } from "@/components/ui/charts";
import { Card, CardHeader, EmptyState, PageHeader, Stat, StatusBadge } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import type { Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import type { Order, Offer } from "@/lib/types";

type Report = { kpis: Record<string, string | number>; series: Record<string, unknown>[]; top_products: { name: string; value: string }[]; representatives: { name: string; value: string }[]; statuses: Record<string, number>; channels: Record<string, string> };

export default function SupplierDashboard() {
  const t = useTranslations("supplier");
  const ts = useTranslations("status");
  const f = useFormat();
  const r = useApiQuery<Report>(["sup-report"], "/reports/supplier");
  const newOrders = useApiQuery<Page<Order>>(["sup-new"], "/supplier/orders", { status: "new,supplier_review", page_size: 6 });
  const lowStock = useApiQuery<Page<Offer>>(["sup-low"], "/supplier/products", { availability: "low_stock", page_size: 5 });
  const auths = useApiQuery<{ id: string; status: string; representative: { display_name: string } }[]>(["sup-auths-pending"], "/supplier/authorizations", { status: "sent" });
  const summary = useApiQuery<{ text: string[] }>(["sup-ai-summary"], "/ai/supplier/summary");
  const k = r.data?.kpis || {};
  return (
    <>
      <PageHeader title={t("dashboard_title")} subtitle={t("dashboard_subtitle")} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("kpi_sales")} value={f.money(k.sales)} icon={<Wallet className="h-5 w-5" />} hint={t("last_30")} />
        <Stat label={t("kpi_new_orders")} value={f.number(k.new_orders)} icon={<ShoppingBag className="h-5 w-5" />} tone="warning" />
        <Stat label={t("kpi_in_preparation")} value={f.number(k.in_preparation)} icon={<Truck className="h-5 w-5" />} tone="teal" />
        <Stat label={t("kpi_customers")} value={f.number(k.active_customers)} icon={<UsersRound className="h-5 w-5" />} hint={t("new_n", { n: f.number(k.new_customers) })} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader title={t("sales_trend")} />{r.data?.series.length ? <TrendChart data={r.data.series} /> : <EmptyState title={t("no_sales")} />}</Card>
        <Card>
          <CardHeader title={t("new_orders")} action={<Link href="/app/supplier/orders" className="text-sm text-teal-600">{t("view_all")}</Link>} />
          {newOrders.data?.items.length ? <ul className="space-y-2">{newOrders.data.items.map((o) => <li key={o.id}><Link href={`/app/supplier/orders/${o.id}`} className="flex items-center justify-between gap-2 rounded-md border border-line p-3 text-sm hover:bg-page"><span className="min-w-0"><span className="ltr block font-semibold">{o.number}</span><span className="block truncate text-xs text-muted">{o.retailer.name}</span></span><span className="tabular font-bold">{f.money(o.total)}</span></Link></li>)}</ul> : <p className="py-6 text-center text-sm text-muted">{t("no_new_orders")}</p>}
        </Card>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card><CardHeader title={t("top_products")} />{r.data?.top_products.length ? <BarList data={r.data.top_products.slice(0, 6)} label="name" value="value" /> : <p className="text-sm text-muted">—</p>}</Card>
        <Card><CardHeader title={t("top_reps")} />{r.data?.representatives.length ? <BarList data={r.data.representatives.slice(0, 6)} label="name" value="value" /> : <p className="text-sm text-muted">—</p>}</Card>
        <Card>
          <CardHeader title={t("order_mix")} />
          {r.data && Object.keys(r.data.statuses).length ? <><Donut data={Object.entries(r.data.statuses).map(([name, value]) => ({ name: ts.has(name) ? ts(name) : name, value }))} /><ul className="mt-2 grid grid-cols-2 gap-1 text-xs text-muted">{Object.entries(r.data.statuses).map(([s, n]) => <li key={s}>{ts.has(s) ? ts(s) : s}: {f.number(n)}</li>)}</ul></> : <p className="text-sm text-muted">—</p>}
        </Card>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("alerts")} action={<AlertTriangle className="h-5 w-5 text-warning" />} />
          <ul className="space-y-2 text-sm">
            {lowStock.data?.items.map((o) => <li key={o.id} className="flex justify-between gap-2"><Link href="/app/supplier/products" className="truncate">{o.product.name}</Link><StatusBadge status={o.availability} /></li>)}
            {auths.data?.map((a) => <li key={a.id}><Link href={`/app/supplier/authorizations/${a.id}`} className="flex justify-between gap-2"><span>{t("auth_request_from", { name: a.representative.display_name })}</span><StatusBadge status={a.status} /></Link></li>)}
            {!lowStock.data?.items.length && !auths.data?.length && <li className="text-muted">{t("no_alerts")}</li>}
          </ul>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title={t("ai_summary")} subtitle={t("ai_summary_hint")} action={<Sparkles className="h-5 w-5 text-teal-500" />} />
          {summary.data?.text.length ? <ul className="space-y-2 text-sm">{summary.data.text.map((s, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />{s}</li>)}</ul> : <EmptyState icon={<PackageOpen className="h-6 w-6" />} title={t("no_sales")} />}
        </Card>
      </div>
    </>
  );
}
