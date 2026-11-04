"use client";

import { Send, Sparkles, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { OfferCard, QtyStepper } from "@/components/app/catalog";
import { SearchInput } from "@/components/ui/data";
import { Alert, Card, CardHeader, EmptyState, PageHeader } from "@/components/ui/layout";
import { Button, Field, Select, Textarea } from "@/components/ui/primitives";
import { useRouter } from "@/i18n/navigation";
import { api, type Page } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";
import type { Offer } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

type Customer = { id: string; name: string; retailer_id: string | null };
type Line = { offer: Offer; unit: "piece" | "carton"; quantity: number };
type Cat = Page<Offer> & { authorizations: { id: string; supplier_id: string; supplier: { name: string } }[] };

function Builder() {
  const t = useTranslations("rep_order");
  const f = useFormat();
  const router = useRouter();
  const sp = useSearchParams();
  const [retailer, setRetailer] = useState(sp.get("retailer") || "");
  const [supplier, setSupplier] = useState("");
  const [q, setQ] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [notes, setNotes] = useState("");
  const [nl, setNl] = useState("");
  const { loading, run } = useApiAction();
  const customers = useApiQuery<Page<Customer>>(["rep-customers-registered"], "/rep/customers", { page_size: 100 });
  const cat = useApiQuery<Cat>(["rep-cat", supplier, retailer, q], "/rep/catalog", { supplier_id: supplier || undefined, retailer_id: retailer || undefined, q, page_size: 24 });
  const registered = customers.data?.items.filter((c) => c.retailer_id) || [];
  const total = useMemo(() => lines.reduce((s, l) => s + Number(l.offer.price?.[l.unit].net || 0) * l.quantity, 0), [lines]);

  const add = (offer: Offer, unit: "piece" | "carton", quantity: number) => {
    if (!supplier) setSupplier(offer.supplier_id);
    if (supplier && offer.supplier_id !== supplier) return;
    setLines((ls) => {
      const i = ls.findIndex((l) => l.offer.id === offer.id && l.unit === unit);
      if (i >= 0) return ls.map((l, j) => (j === i ? { ...l, quantity: l.quantity + quantity } : l));
      return [...ls, { offer, unit, quantity }];
    });
  };
  async function parse() {
    const res = await run(() => api<{ lines: { quantity: number; unit: "piece" | "carton"; match: { offer_id: string } | null; needs_review: boolean }[] }>("/ai/rep/parse-order", { body: { text: nl, supplier_id: supplier || null } }));
    if (!res || !cat.data) return;
    for (const l of res.lines) {
      const offer = cat.data.items.find((o) => o.id === l.match?.offer_id);
      if (offer) add(offer, l.unit, l.quantity);
    }
  }
  async function submit(send: boolean) {
    const o = await run(() => api<{ id: string }>("/rep/orders", { body: { retailer_id: retailer, supplier_id: supplier, notes: notes || null, submit: send, items: lines.map((l) => ({ offer_id: l.offer.id, unit: l.unit, quantity: l.quantity })) } }), { success: send ? t("sent_to_store") : t("saved_draft") });
    if (o) router.push(`/app/rep/orders/${o.id}`);
  }
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <Card className="grid gap-3 sm:grid-cols-2">
            <Field label={t("store")} required hint={t("store_hint")}>{(id) => <Select id={id} value={retailer} onChange={(e) => setRetailer(e.target.value)} data-testid="rep-order-store"><option value="">—</option>{registered.map((c) => <option key={c.id} value={c.retailer_id!}>{c.name}</option>)}</Select>}</Field>
            <Field label={t("company")} required>{(id) => <Select id={id} value={supplier} onChange={(e) => { setSupplier(e.target.value); setLines([]); }} data-testid="rep-order-supplier"><option value="">—</option>{cat.data?.authorizations.map((a) => <option key={a.id} value={a.supplier_id}>{a.supplier.name}</option>)}</Select>}</Field>
          </Card>
          <Card>
            <CardHeader title={t("quick_entry")} subtitle={t("quick_entry_hint")} action={<Sparkles className="h-5 w-5 text-teal-500" />} />
            <div className="flex gap-2"><Textarea rows={2} value={nl} onChange={(e) => setNl(e.target.value)} placeholder={t("quick_placeholder")} /><Button variant="outline" onClick={parse} loading={loading} disabled={!nl.trim() || !supplier}>{t("analyze")}</Button></div>
          </Card>
          <SearchInput value={q} onChange={setQ} />
          {cat.data?.items.length ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3">{cat.data.items.filter((o) => !supplier || o.supplier_id === supplier).map((o) => <OfferCard key={o.id} offer={o} onAdd={add} addLabel={t("add")} />)}</div>
          ) : <Card><EmptyState title={t("no_products")} description={t("no_products_hint")} /></Card>}
        </div>
        <div className="lg:col-span-2">
          <Card className="sticky top-20">
            <CardHeader title={t("summary")} subtitle={t("lines", { n: lines.length })} />
            {lines.length ? (
              <ul className="space-y-3">
                {lines.map((l, i) => (
                  <li key={`${l.offer.id}-${l.unit}`} className="flex items-center gap-2 text-sm">
                    <div className="min-w-0 flex-1"><p className="truncate font-medium">{l.offer.product.name}</p><p className="text-xs text-muted">{t(`units.${l.unit}`)} · {f.money(l.offer.price?.[l.unit].net)}</p></div>
                    <QtyStepper value={l.quantity} onChange={(v) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, quantity: v } : x)))} />
                    <button onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))} className="p-1 text-muted hover:text-danger" aria-label="remove"><Trash2 className="h-4 w-4" /></button>
                  </li>
                ))}
              </ul>
            ) : <p className="py-6 text-center text-sm text-muted">{t("empty")}</p>}
            <div className="mt-4 border-t border-line pt-4">
              <div className="flex justify-between font-bold text-navy-700"><span>{t("estimated")}</span><span className="tabular">{f.money(total)}</span></div>
              <p className="mt-1 text-xs text-muted">{t("price_note")}</p>
            </div>
            <div className="mt-3"><Field label={t("notes")}>{(id) => <Textarea id={id} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field></div>
            <div className="mt-4 grid gap-2">
              <Button size="lg" icon={<Send className="h-4 w-4" />} loading={loading} disabled={!retailer || !supplier || !lines.length} onClick={() => submit(true)} data-testid="send-to-store">{t("send")}</Button>
              <Button variant="outline" disabled={!retailer || !supplier || !lines.length} onClick={() => submit(false)}>{t("save_draft")}</Button>
            </div>
            <div className="mt-4"><Alert tone="info">{t("approval_note")}</Alert></div>
          </Card>
        </div>
      </div>
    </>
  );
}

export default function NewRepOrder() {
  return <Suspense><Builder /></Suspense>;
}
