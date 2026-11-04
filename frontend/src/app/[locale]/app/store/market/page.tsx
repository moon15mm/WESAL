"use client";

import { BadgeCheck, Building2, Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { CategoryFilter, OfferCard, useAddToCart } from "@/components/app/catalog";
import { Pagination, SearchInput, Tabs } from "@/components/ui/data";
import { Card, EmptyState, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useFormat } from "@/lib/format";
import { useList } from "@/lib/list";
import type { BusinessBrief, Offer } from "@/lib/types";

type Supplier = BusinessBrief & { products_count: number; min_order_value: string | null; description: string | null };

export default function Market() {
  const t = useTranslations("catalog");
  const f = useFormat();
  const [tab, setTab] = useState<"products" | "suppliers">("products");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const offers = useList<Offer>(tab === "products" ? "/market/offers" : null, { q, category_id: cat, in_stock: false }, 24);
  const suppliers = useList<Supplier>(tab === "suppliers" ? "/market/suppliers" : null, { q, category_id: cat }, 18);
  const { add, loading } = useAddToCart();
  return (
    <>
      <PageHeader title={t("market_title")} subtitle={t("market_subtitle")} />
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center">
        <Tabs value={tab} onChange={setTab} items={[{ value: "products", label: t("products") }, { value: "suppliers", label: t("suppliers") }]} />
        <div className="flex flex-1 flex-col gap-3 sm:flex-row md:justify-end">
          <SearchInput value={q} onChange={(v) => { setQ(v); offers.reset(); suppliers.reset(); }} placeholder={t("search_placeholder")} className="sm:w-72" />
          <CategoryFilter value={cat} onChange={(v) => { setCat(v); offers.reset(); suppliers.reset(); }} />
        </div>
      </div>
      {tab === "products" ? (
        offers.isLoading ? <SkeletonRows rows={6} /> : offers.data?.items.length ? (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
              {offers.data.items.map((o) => (
                <div key={o.id} className="flex flex-col">
                  <OfferCard offer={o} onAdd={add} adding={loading} />
                  <Link href={`/app/store/products/${o.product.id}`} className="mt-1 text-center text-xs text-teal-600 hover:underline">{t("compare_offers")}</Link>
                </div>
              ))}
            </div>
            <Card padded={false} className="mt-4"><Pagination page={offers.page} pageSize={offers.pageSize} total={offers.data.total} onPage={offers.setPage} /></Card>
          </>
        ) : <Card><EmptyState title={t("no_products")} description={t("no_products_hint")} /></Card>
      ) : suppliers.isLoading ? <SkeletonRows rows={6} /> : suppliers.data?.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {suppliers.data.items.map((s) => (
            <Link key={s.id} href={`/app/store/suppliers/${s.id}`} className="group rounded-lg border border-line bg-white p-5 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]">
              <div className="flex items-start gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-navy-50">{s.logo_url ? <img src={s.logo_url} alt="" className="h-full w-full object-cover" /> : <Building2 className="h-6 w-6 text-navy-300" />}</div>
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 font-semibold text-navy-700">{s.name}{s.verification_status === "verified" && <BadgeCheck className="h-4 w-4 text-teal-500" />}</p>
                  <p className="mt-0.5 text-xs text-muted">{s.city?.name} · {t("products_count", { n: s.products_count })}</p>
                </div>
              </div>
              {s.description && <p className="mt-3 line-clamp-2 text-sm text-muted">{s.description}</p>}
              <div className="mt-4 flex items-center justify-between text-xs">
                <span className="flex items-center gap-1 text-[#a8701f]"><Star className="h-3.5 w-3.5 fill-warning text-warning" />{s.rating_count ? `${s.rating_avg} (${s.rating_count})` : t("no_ratings")}</span>
                {s.min_order_value && <span className="text-muted">{t("min_order")}: {f.money(s.min_order_value)}</span>}
              </div>
            </Link>
          ))}
        </div>
      ) : <Card><EmptyState title={t("no_suppliers")} /></Card>}
    </>
  );
}
