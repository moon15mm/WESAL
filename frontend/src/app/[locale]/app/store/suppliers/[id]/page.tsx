"use client";

import { BadgeCheck, Building2, Clock, Phone, Star, Truck } from "lucide-react";
import { useTranslations } from "next-intl";
import { use, useState } from "react";
import { CategoryFilter, OfferCard, useAddToCart } from "@/components/app/catalog";
import { Pagination, SearchInput } from "@/components/ui/data";
import { Card, CardHeader, EmptyState, KV, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useFormat } from "@/lib/format";
import { useApiQuery, useList } from "@/lib/list";
import type { BusinessBrief, Offer } from "@/lib/types";

type SupplierDetail = BusinessBrief & { description: string | null; min_order_value: string | null; supply_terms: string | null; payment_terms: string | null; phone: string | null; default_lead_time_days: number | null;
  coverage: { city: { name: string }; delivery_fee: string; lead_time_days: number; district: string | null }[]; categories: { id: number; name: string; count: number }[] };

export default function SupplierPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("catalog");
  const f = useFormat();
  const s = useApiQuery<SupplierDetail>(["supplier", id], `/market/suppliers/${id}`);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const offers = useList<Offer>(`/market/offers`, { supplier_id: id, q, category_id: cat }, 24);
  const { add, loading } = useAddToCart();
  if (!s.data) return <SkeletonRows />;
  const d = s.data;
  return (
    <>
      <PageHeader back={<Link href="/app/store/market" className="mb-2 inline-block text-sm text-teal-600">← {t("market_title")}</Link>}
        title={<span className="flex items-center gap-2">{d.name}{d.verification_status === "verified" && <BadgeCheck className="h-5 w-5 text-teal-500" />}</span>}
        subtitle={d.description || undefined} />
      <div className="grid gap-6 lg:grid-cols-4">
        <div className="space-y-4 lg:col-span-1">
          <Card>
            <div className="mb-4 flex h-16 w-16 items-center justify-center overflow-hidden rounded-xl bg-navy-50">{d.logo_url ? <img src={d.logo_url} alt="" /> : <Building2 className="h-8 w-8 text-navy-300" />}</div>
            <KV className="sm:grid-cols-1" items={[
              [t("rating"), <span key="r" className="flex items-center gap-1"><Star className="h-4 w-4 fill-warning text-warning" />{d.rating_count ? `${d.rating_avg} (${d.rating_count})` : t("no_ratings")}</span>],
              [t("min_order"), d.min_order_value ? f.money(d.min_order_value) : "—"],
              [t("lead_time"), d.default_lead_time_days !== null ? <span key="l" className="flex items-center gap-1"><Clock className="h-4 w-4" />{t("days", { n: d.default_lead_time_days })}</span> : "—"],
              [t("phone"), d.phone && <span key="p" className="ltr flex items-center gap-1"><Phone className="h-4 w-4" />{d.phone}</span>],
              [t("supply_terms"), d.supply_terms],
              [t("payment_terms"), d.payment_terms],
            ]} />
          </Card>
          <Card>
            <CardHeader title={t("coverage")} action={<Truck className="h-5 w-5 text-teal-500" />} />
            <ul className="space-y-2 text-sm">{d.coverage.map((c, i) => <li key={i} className="flex justify-between gap-2"><span>{c.city.name}{c.district && ` · ${c.district}`}</span><span className="tabular text-muted">{Number(c.delivery_fee) ? f.money(c.delivery_fee) : t("free_delivery")}</span></li>)}</ul>
          </Card>
        </div>
        <div className="lg:col-span-3">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <SearchInput value={q} onChange={(v) => { setQ(v); offers.reset(); }} className="flex-1" />
            <CategoryFilter value={cat} onChange={(v) => { setCat(v); offers.reset(); }} />
          </div>
          {offers.data?.items.length ? (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">{offers.data.items.map((o) => <OfferCard key={o.id} offer={o} onAdd={add} adding={loading} showSupplier={false} />)}</div>
              <Card padded={false} className="mt-4"><Pagination page={offers.page} pageSize={offers.pageSize} total={offers.data.total} onPage={offers.setPage} /></Card>
            </>
          ) : <Card><EmptyState title={t("no_products")} /></Card>}
        </div>
      </div>
    </>
  );
}
