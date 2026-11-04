"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Percent, Plus, Tags } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Tabs } from "@/components/ui/data";
import { Badge, Card, CardHeader, EmptyState, PageHeader } from "@/components/ui/layout";
import { Modal } from "@/components/ui/overlay";
import { Button, Field, Input, Select } from "@/components/ui/primitives";
import { api, type Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCategories, useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";
import type { Offer } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

type PriceList = { id: string; name: string; type: string; priority: number; valid_from: string | null; valid_to: string | null; is_active: boolean; customer_business_ids: string[]; city_ids: number[]; items: { offer_id: string; unit_price: string; carton_price: string | null }[] };
type Promo = { id: string; name: string; kind: string; value: string; min_qty: number; offer_id: string | null; category_id: number | null; starts_at: string; ends_at: string; is_active: boolean };
type Cust = { id: string; name: string; retailer_id: string | null };

const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export default function Pricing() {
  const t = useTranslations("pricing");
  const f = useFormat();
  const qc = useQueryClient();
  const cats = useCategories();
  const cities = useCities();
  const [tab, setTab] = useState<"promotions" | "lists">("promotions");
  const lists = useApiQuery<PriceList[]>(["price-lists"], "/supplier/price-lists");
  const promos = useApiQuery<Promo[]>(["promos"], "/supplier/promotions");
  const offers = useApiQuery<Page<Offer>>(["sup-offers-all"], "/supplier/products", { page_size: 100 });
  const customers = useApiQuery<Page<Cust>>(["sup-cust-all"], "/supplier/customers", { page_size: 100 });
  const { loading, run } = useApiAction();
  const [promo, setPromo] = useState<null | { id?: string; name: string; kind: string; value: string; min_qty: string; offer_id: string; category_id: string; starts_at: string; ends_at: string; is_active: boolean }>(null);
  const [pl, setPl] = useState<null | { id?: string; name: string; type: string; priority: string; customer: string[]; cities: number[]; items: Record<string, string> }>(null);
  const offerName = (id: string | null) => offers.data?.items.find((o) => o.id === id)?.product.name;

  async function savePromo() {
    const p = promo!;
    const body = { name: p.name, kind: p.kind, value: p.value, min_qty: Number(p.min_qty), offer_id: p.offer_id || null, category_id: p.category_id ? Number(p.category_id) : null, starts_at: new Date(p.starts_at).toISOString(), ends_at: new Date(p.ends_at).toISOString(), is_active: p.is_active };
    if (await run(() => (p.id ? api(`/supplier/promotions/${p.id}`, { method: "PUT", body }) : api("/supplier/promotions", { body })), { success: t("saved") })) { setPromo(null); qc.invalidateQueries({ queryKey: ["promos"] }); }
  }
  async function savePl() {
    const p = pl!;
    const body = { name: p.name, type: p.type, priority: Number(p.priority), customer_business_ids: p.customer, city_ids: p.cities, is_active: true,
      items: Object.entries(p.items).filter(([, v]) => v).map(([offer_id, unit_price]) => ({ offer_id, unit_price })) };
    if (await run(() => (p.id ? api(`/supplier/price-lists/${p.id}`, { method: "PUT", body }) : api("/supplier/price-lists", { body })), { success: t("saved") })) { setPl(null); qc.invalidateQueries({ queryKey: ["price-lists"] }); }
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={tab === "promotions"
        ? <Button icon={<Plus className="h-4 w-4" />} onClick={() => setPromo({ name: "", kind: "percent", value: "10", min_qty: "1", offer_id: "", category_id: "", starts_at: local(new Date()), ends_at: local(new Date(Date.now() + 7 * 864e5)), is_active: true })}>{t("new_promo")}</Button>
        : <Button icon={<Plus className="h-4 w-4" />} onClick={() => setPl({ name: "", type: "customer", priority: "100", customer: [], cities: [], items: {} })}>{t("new_list")}</Button>} />
      <div className="mb-4"><Tabs value={tab} onChange={setTab} items={[{ value: "promotions", label: t("promotions") }, { value: "lists", label: t("price_lists") }]} /></div>
      {tab === "promotions" ? (
        promos.data?.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {promos.data.map((p) => (
              <Card key={p.id} className="cursor-pointer hover:shadow-[var(--shadow-pop)]" onClick={() => setPromo({ ...p, value: p.value, min_qty: String(p.min_qty), offer_id: p.offer_id || "", category_id: p.category_id ? String(p.category_id) : "", starts_at: local(new Date(p.starts_at)), ends_at: local(new Date(p.ends_at)) })}>
                <div className="flex items-start justify-between"><p className="font-semibold text-navy-700">{p.name}</p><Badge tone={p.is_active && new Date(p.ends_at) > new Date() ? "success" : "neutral"}>{p.is_active && new Date(p.ends_at) > new Date() ? t("running") : t("inactive")}</Badge></div>
                <p className="tabular mt-2 text-2xl font-bold text-teal-600">{p.kind === "fixed" ? f.money(p.value) : `${f.number(p.value)}%`}</p>
                <p className="mt-1 text-sm text-muted">{offerName(p.offer_id) || cats.data?.find((c) => c.id === p.category_id)?.name || t("all_products")}{p.min_qty > 1 && ` · ${t("min_qty", { n: p.min_qty })}`}</p>
                <p className="mt-2 text-xs text-muted">{f.date(p.starts_at)} → {f.date(p.ends_at)}</p>
              </Card>
            ))}
          </div>
        ) : <Card><EmptyState icon={<Percent className="h-6 w-6" />} title={t("no_promos")} /></Card>
      ) : lists.data?.length ? (
        <div className="space-y-3">{lists.data.map((l) => (
          <Card key={l.id} className="flex cursor-pointer items-center justify-between" onClick={() => setPl({ id: l.id, name: l.name, type: l.type, priority: String(l.priority), customer: l.customer_business_ids, cities: l.city_ids, items: Object.fromEntries(l.items.map((i) => [i.offer_id, i.unit_price])) })}>
            <div><p className="font-semibold text-navy-700">{l.name}</p><p className="text-sm text-muted">{t(`types.${l.type}`)} · {t("items_n", { n: l.items.length })}</p></div>
            <Badge tone="teal">{t("priority")} {l.priority}</Badge>
          </Card>
        ))}</div>
      ) : <Card><EmptyState icon={<Tags className="h-6 w-6" />} title={t("no_lists")} description={t("lists_hint")} /></Card>}

      {promo && (
        <Modal open onOpenChange={(v) => !v && setPromo(null)} title={promo.id ? t("edit_promo") : t("new_promo")}
          footer={<><Button variant="outline" onClick={() => setPromo(null)}>{t("cancel")}</Button><Button loading={loading} onClick={savePromo} disabled={!promo.name}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("name")} className="sm:col-span-2">{(id) => <Input id={id} value={promo.name} onChange={(e) => setPromo({ ...promo, name: e.target.value })} />}</Field>
            <Field label={t("kind")}>{(id) => <Select id={id} value={promo.kind} onChange={(e) => setPromo({ ...promo, kind: e.target.value })}>{["percent", "fixed", "quantity_tier"].map((k) => <option key={k} value={k}>{t(`kinds.${k}`)}</option>)}</Select>}</Field>
            <Field label={t("value")}>{(id) => <Input id={id} type="number" step="0.01" value={promo.value} onChange={(e) => setPromo({ ...promo, value: e.target.value })} />}</Field>
            <Field label={t("product")}>{(id) => <Select id={id} value={promo.offer_id} onChange={(e) => setPromo({ ...promo, offer_id: e.target.value })}><option value="">{t("all_products")}</option>{offers.data?.items.map((o) => <option key={o.id} value={o.id}>{o.product.name}</option>)}</Select>}</Field>
            <Field label={t("category")}>{(id) => <Select id={id} value={promo.category_id} onChange={(e) => setPromo({ ...promo, category_id: e.target.value })}><option value="">—</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>}</Field>
            <Field label={t("min_pieces")}>{(id) => <Input id={id} type="number" min={1} value={promo.min_qty} onChange={(e) => setPromo({ ...promo, min_qty: e.target.value })} />}</Field>
            <div />
            <Field label={t("starts")}>{(id) => <Input id={id} type="datetime-local" value={promo.starts_at} onChange={(e) => setPromo({ ...promo, starts_at: e.target.value })} />}</Field>
            <Field label={t("ends")}>{(id) => <Input id={id} type="datetime-local" value={promo.ends_at} onChange={(e) => setPromo({ ...promo, ends_at: e.target.value })} />}</Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={promo.is_active} onChange={(e) => setPromo({ ...promo, is_active: e.target.checked })} />{t("active")}</label>
          </div>
        </Modal>
      )}
      {pl && (
        <Modal open onOpenChange={(v) => !v && setPl(null)} size="lg" title={pl.id ? t("edit_list") : t("new_list")}
          footer={<><Button variant="outline" onClick={() => setPl(null)}>{t("cancel")}</Button><Button loading={loading} onClick={savePl} disabled={!pl.name}>{t("save")}</Button></>}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("name")}>{(id) => <Input id={id} value={pl.name} onChange={(e) => setPl({ ...pl, name: e.target.value })} />}</Field>
            <Field label={t("type")}>{(id) => <Select id={id} value={pl.type} onChange={(e) => setPl({ ...pl, type: e.target.value })}>{["customer", "region", "default"].map((k) => <option key={k} value={k}>{t(`types.${k}`)}</option>)}</Select>}</Field>
            <Field label={t("priority")}>{(id) => <Input id={id} type="number" value={pl.priority} onChange={(e) => setPl({ ...pl, priority: e.target.value })} />}</Field>
          </div>
          {pl.type === "customer" && <div className="mt-3"><p className="mb-2 text-sm font-medium">{t("customers")}</p><div className="flex flex-wrap gap-2">{customers.data?.items.filter((c) => c.retailer_id).map((c) => <button key={c.id} type="button" onClick={() => setPl({ ...pl, customer: pl.customer.includes(c.retailer_id!) ? pl.customer.filter((x) => x !== c.retailer_id) : [...pl.customer, c.retailer_id!] })} className={`rounded-full px-3 py-1 text-xs ring-1 ${pl.customer.includes(c.retailer_id!) ? "bg-navy-700 text-white" : "ring-line"}`}>{c.name}</button>)}</div></div>}
          {pl.type === "region" && <div className="mt-3"><p className="mb-2 text-sm font-medium">{t("cities")}</p><div className="flex flex-wrap gap-2">{cities.data?.map((c) => <button key={c.id} type="button" onClick={() => setPl({ ...pl, cities: pl.cities.includes(c.id) ? pl.cities.filter((x) => x !== c.id) : [...pl.cities, c.id] })} className={`rounded-full px-3 py-1 text-xs ring-1 ${pl.cities.includes(c.id) ? "bg-navy-700 text-white" : "ring-line"}`}>{c.name}</button>)}</div></div>}
          <CardHeader className="mt-5" title={t("prices")} subtitle={t("prices_hint")} />
          <div className="max-h-72 space-y-2 overflow-y-auto">{offers.data?.items.map((o) => (
            <div key={o.id} className="flex items-center justify-between gap-3 text-sm"><span className="truncate">{o.product.name} <span className="text-muted">({f.money(o.unit_price)})</span></span><Input className="w-28" type="number" step="0.01" placeholder="—" value={pl.items[o.id] || ""} onChange={(e) => setPl({ ...pl, items: { ...pl.items, [o.id]: e.target.value } })} /></div>
          ))}</div>
        </Modal>
      )}
    </>
  );
}
