"use client";

import { Sparkles, Truck } from "lucide-react";
import { useTranslations } from "next-intl";
import { use } from "react";
import { OfferCard, ProductImage, useAddToCart } from "@/components/app/catalog";
import { Card, CardHeader, KV, PageHeader, SkeletonRows } from "@/components/ui/layout";
import { Link } from "@/i18n/navigation";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import type { Offer, Product } from "@/lib/types";

export default function ProductCompare({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const t = useTranslations("catalog");
  const f = useFormat();
  const d = useApiQuery<{ product: Product; offers: Offer[] }>(["product", id], `/market/products/${id}`);
  const alts = useApiQuery<{ items: { offer_id: string; product_id: string; name: string; unit_price: string; same_package_size: boolean }[] }>(["alts", id], `/ai/alternatives/${id}`);
  const { add, loading } = useAddToCart();
  if (!d.data) return <SkeletonRows />;
  const p = d.data.product;
  return (
    <>
      <PageHeader back={<Link href="/app/store/market" className="mb-2 inline-block text-sm text-teal-600">← {t("market_title")}</Link>} title={p.name} subtitle={[p.brand?.name, p.package_size, p.category.name].filter(Boolean).join(" · ")} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card>
          <ProductImage src={p.image_url} alt={p.name} className="h-56" />
          <div className="mt-4"><KV className="sm:grid-cols-1" items={[[t("barcode"), p.barcode && <span key="b" className="ltr">{p.barcode}</span>], [t("manufacturer"), p.manufacturer], [t("pieces_per_carton"), f.number(p.pieces_per_carton)], [t("description"), p.description]]} /></div>
        </Card>
        <div className="lg:col-span-2">
          <Card className="mb-6">
            <CardHeader title={t("offers_compare", { n: d.data.offers.length })} subtitle={t("offers_compare_hint")} />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {d.data.offers.map((o) => (
                <div key={o.id}>
                  <OfferCard offer={o} onAdd={add} adding={loading} />
                  {o.delivers_to_you !== undefined && <p className={`mt-1 flex items-center gap-1 text-xs ${o.delivers_to_you ? "text-success" : "text-danger"}`}><Truck className="h-3.5 w-3.5" />{o.delivers_to_you ? t("delivers_to_you") : t("not_your_area")}</p>}
                </div>
              ))}
            </div>
          </Card>
          {alts.data?.items.length ? (
            <Card>
              <CardHeader title={t("alternatives")} action={<Sparkles className="h-5 w-5 text-teal-500" />} />
              <ul className="divide-y divide-line">{alts.data.items.map((a) => <li key={a.offer_id}><Link href={`/app/store/products/${a.product_id}`} className="flex justify-between gap-3 py-2 text-sm"><span>{a.name}</span><span className="tabular text-muted">{f.money(a.unit_price)}</span></Link></li>)}</ul>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
