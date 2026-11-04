"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Minus, Package, Plus, ShoppingCart } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Badge, StatusBadge } from "@/components/ui/layout";
import { Button, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiAction } from "@/lib/useApiForm";
import { useCategories } from "@/lib/hooks";
import type { Offer } from "@/lib/types";

export function ProductImage({ src, alt, className = "h-28" }: { src: string | null; alt: string; className?: string }) {
  return (
    <div className={`flex items-center justify-center overflow-hidden rounded-md bg-gradient-to-br from-navy-50 to-white ${className}`}>
      {src ? <img src={src} alt={alt} loading="lazy" className="h-full w-full object-contain p-2" /> : <Package className="h-9 w-9 text-navy-200" />}
    </div>
  );
}

export function QtyStepper({ value, onChange, min = 1 }: { value: number; onChange: (v: number) => void; min?: number }) {
  return (
    <div className="inline-flex h-9 items-center rounded-md border border-line bg-white" dir="ltr">
      <button type="button" className="px-2.5 text-muted hover:text-ink disabled:opacity-40" disabled={value <= min} onClick={() => onChange(Math.max(min, value - 1))} aria-label="-"><Minus className="h-3.5 w-3.5" /></button>
      <input value={value} onChange={(e) => onChange(Math.max(min, Number(e.target.value.replace(/\D/g, "")) || min))} className="tabular w-10 bg-transparent text-center text-sm outline-none" inputMode="numeric" />
      <button type="button" className="px-2.5 text-muted hover:text-ink" onClick={() => onChange(value + 1)} aria-label="+"><Plus className="h-3.5 w-3.5" /></button>
    </div>
  );
}

/** Offer card with unit selection and quantity; `onAdd` receives (offer, unit, qty). */
export function OfferCard({ offer, onAdd, adding, showSupplier = true, addLabel }: { offer: Offer; onAdd?: (o: Offer, unit: "piece" | "carton", qty: number) => void; adding?: boolean; showSupplier?: boolean; addLabel?: string }) {
  const t = useTranslations("catalog");
  const f = useFormat();
  const defaultUnit = offer.sell_by_carton ? "carton" : "piece";
  const [unit, setUnit] = useState<"piece" | "carton">(defaultUnit);
  const [qty, setQty] = useState(1);
  const price = offer.price?.[unit];
  const unavailable = ["out_of_stock", "discontinued"].includes(offer.availability);
  return (
    <div className="group flex flex-col rounded-lg border border-line/80 bg-white p-3 transition hover:-translate-y-0.5 hover:shadow-[var(--shadow-card)]" data-testid="offer-card">
      <ProductImage src={offer.product.image_url} alt={offer.product.name} />
      <div className="mt-3 flex-1">
        <p className="line-clamp-2 text-sm font-semibold leading-5 text-ink">{offer.product.name}</p>
        <p className="mt-1 text-xs text-muted">{[offer.product.brand?.name, offer.product.package_size].filter(Boolean).join(" · ")}</p>
        {showSupplier && offer.supplier && <p className="mt-1 truncate text-xs text-teal-700">{offer.supplier.name}</p>}
        <div className="mt-2 flex items-baseline gap-2">
          <span className="tabular text-lg font-bold text-navy-700">{f.money(price?.net ?? offer.unit_price)}</span>
          {price && price.net !== price.list && <span className="tabular text-xs text-muted line-through">{f.money(price.list)}</span>}
          <span className="text-xs text-muted">/ {t(`units.${unit}`)}</span>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {offer.availability !== "in_stock" && <StatusBadge status={offer.availability} />}
          {price?.promotion_id && <Badge tone="teal">{t("offer_badge")}</Badge>}
          {offer.min_order_qty > 1 && <Badge>{t("moq", { n: offer.min_order_qty })}</Badge>}
        </div>
      </div>
      {onAdd && (
        <div className="mt-3 space-y-2">
          {offer.sell_by_piece && offer.sell_by_carton && (
            <Select value={unit} onChange={(e) => setUnit(e.target.value as "piece" | "carton")} className="h-9 text-xs">
              <option value="carton">{t("units.carton")} ({t("pieces", { n: offer.pieces_per_carton })})</option>
              <option value="piece">{t("units.piece")}</option>
            </Select>
          )}
          <div className="flex items-center gap-2">
            <QtyStepper value={qty} onChange={setQty} />
            <Button size="sm" className="h-9 flex-1" disabled={unavailable} loading={adding} onClick={() => onAdd(offer, unit, qty)} icon={<ShoppingCart className="h-4 w-4" />} data-testid="add-offer">
              {addLabel || t("add")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function CategoryFilter({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const t = useTranslations("catalog");
  const cats = useCategories();
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)} className="sm:w-56" aria-label={t("category")}>
      <option value="">{t("all_categories")}</option>
      {cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
    </Select>
  );
}

export function useAddToCart() {
  const t = useTranslations("catalog");
  const qc = useQueryClient();
  const { loading, run } = useApiAction();
  const add = async (o: Offer, unit: "piece" | "carton", quantity: number) => {
    const ok = await run(() => api(`/retailer/carts/${o.supplier_id}/items`, { method: "PUT", body: { offer_id: o.id, unit, quantity } }), { success: t("added") });
    if (ok) qc.invalidateQueries({ queryKey: ["carts"] });
  };
  return { add, loading };
}

