"use client";

import { ClipboardCheck, PackageCheck, ShoppingBag, Sparkles, TrendingUp, Wallet } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card, CardHeader, EmptyState, PageHeader, Stat, StatusBadge } from "@/components/ui/layout";
import { BarList, TrendChart } from "@/components/ui/charts";
import { Link } from "@/i18n/navigation";
import type { Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import type { Order } from "@/lib/types";

type Report = { kpis: Record<string, string | number>; series: Record<string, unknown>[]; suppliers: { supplier_id: string; name: string; value: string; orders: number }[]; top_products: { name: string; value: string; pieces: number }[] };
type Forecast = { items: { product_id: string; name: string; predicted_next: string; days_until: number; urgency: string; suggested_pieces: number }[] };
type Ad = { id: string; title: string; body: string | null; link_url: string | null };

export default function StoreDashboard() {
  const t = useTranslations("store");
  const f = useFormat();
  const { me } = useSession();
  const report = useApiQuery<Report>(["store-report"], "/reports/retailer");
  const pending = useApiQuery<Page<Order>>(["store-pending"], "/retailer/orders", { status: "pending_retailer_approval,quoted,awaiting_retailer_approval", page_size: 5 });
  const current = useApiQuery<Page<Order>>(["store-current"], "/retailer/orders", { status: "new,supplier_review,approved,preparing,ready,out_for_delivery,delivered", page_size: 6 });
  const forecast = useApiQuery<Forecast>(["store-forecast"], "/ai/reorder-forecast");
  const ads = useApiQuery<Ad[]>(["ads", "retailer_dashboard"], "/ads", { placement: "retailer_dashboard" });
  const k = report.data?.kpis || {};
  return (
    <>
      <PageHeader title={t("welcome", { name: me?.full_name.split(" ")[0] || "" })} subtitle={t("dashboard_subtitle")}
        actions={<Link href="/app/store/market" className="inline-flex h-10 items-center gap-2 rounded-md bg-teal-500 px-4 text-sm font-semibold text-white hover:bg-teal-600"><ShoppingBag className="h-4 w-4" />{t("start_order")}</Link>} />
      {ads.data?.map((a) => (
        <a key={a.id} href={a.link_url || "#"} className="mb-6 block rounded-xl bg-gradient-to-r from-navy-700 to-teal-600 p-5 text-white shadow-md">
          <p className="font-semibold">{a.title}</p>{a.body && <p className="mt-1 text-sm text-white/85">{a.body}</p>}
        </a>
      ))}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t("kpi_purchases")} value={f.money(k.purchases)} icon={<Wallet className="h-5 w-5" />} hint={t("last_30")} />
        <Stat label={t("kpi_orders")} value={f.number(k.orders)} icon={<ShoppingBag className="h-5 w-5" />} tone="teal" />
        <Stat label={t("kpi_pending")} value={f.number(k.pending_approvals)} icon={<ClipboardCheck className="h-5 w-5" />} tone="warning" />
        <Stat label={t("kpi_completed")} value={f.number(k.completed)} icon={<PackageCheck className="h-5 w-5" />} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={t("spend_trend")} subtitle={t("last_30")} action={<TrendingUp className="h-5 w-5 text-teal-500" />} />
          {report.data?.series.length ? <TrendChart data={report.data.series} /> : <EmptyState title={t("no_orders_yet")} description={t("no_orders_hint")} />}
        </Card>
        <Card>
          <CardHeader title={t("needs_your_action")} action={<Link href="/app/store/approvals" className="text-sm text-teal-600">{t("view_all")}</Link>} />
          {pending.data?.items.length ? (
            <ul className="space-y-3">
              {pending.data.items.map((o) => (
                <li key={o.id}>
                  <Link href={`/app/store/orders/${o.id}`} className="block rounded-md border border-warning/30 bg-warning/5 p-3 transition hover:bg-warning/10">
                    <div className="flex items-center justify-between gap-2"><span className="ltr text-sm font-semibold">{o.number}</span><span className="tabular text-sm font-bold">{f.money(o.total)}</span></div>
                    <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted"><span className="truncate">{o.supplier.name}{o.representative && ` · ${o.representative.display_name}`}</span><StatusBadge status={o.status} /></div>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="py-6 text-center text-sm text-muted">{t("nothing_pending")}</p>}
        </Card>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader title={t("current_orders")} />
          {current.data?.items.length ? (
            <ul className="divide-y divide-line">
              {current.data.items.map((o) => (
                <li key={o.id}><Link href={`/app/store/orders/${o.id}`} className="flex items-center justify-between gap-3 py-2.5 text-sm"><span className="min-w-0"><span className="ltr block font-medium">{o.number}</span><span className="block truncate text-xs text-muted">{o.supplier.name}</span></span><StatusBadge status={o.status} /></Link></li>
              ))}
            </ul>
          ) : <p className="py-6 text-center text-sm text-muted">{t("no_current")}</p>}
        </Card>
        <Card>
          <CardHeader title={t("top_suppliers")} />
          {report.data?.suppliers.length ? <BarList data={report.data.suppliers.slice(0, 5)} label="name" value="value" /> : <p className="py-6 text-center text-sm text-muted">—</p>}
        </Card>
        <Card>
          <CardHeader title={t("reorder_suggestions")} action={<Sparkles className="h-5 w-5 text-teal-500" />} />
          {forecast.data?.items.length ? (
            <ul className="space-y-2.5">
              {forecast.data.items.slice(0, 5).map((i) => (
                <li key={i.product_id} className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate">{i.name}</span>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${i.urgency === "due" ? "bg-danger/10 text-danger" : i.urgency === "soon" ? "bg-warning/10 text-[#a8701f]" : "bg-navy-50 text-navy-500"}`}>{t(`urgency.${i.urgency}`)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="py-6 text-center text-sm text-muted">{t("forecast_empty")}</p>}
          <Link href="/app/store/reorder" className="mt-4 inline-block text-sm font-medium text-teal-600">{t("open_assistant")} →</Link>
        </Card>
      </div>
    </>
  );
}
