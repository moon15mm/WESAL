"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ShoppingCart, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { ProductImage, QtyStepper } from "@/components/app/catalog";
import { Alert, Card, CardHeader, EmptyState, PageHeader, SkeletonRows, StatusBadge } from "@/components/ui/layout";
import { Button, Field, Select, Textarea } from "@/components/ui/primitives";
import { Link, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { BusinessBrief } from "@/lib/types";
import { useApiAction } from "@/lib/useApiForm";

type CartLine = { offer_id: string; name: string; image_url: string | null; unit: "piece" | "carton"; quantity: number; pieces_per_unit: number; unit_price: string; discount: string; line_total: string; availability: string; min_order_qty: number };
type Cart = { id: string; supplier: BusinessBrief; items: CartLine[]; subtotal: string; discount_total: string; net: string; min_order_value: string | null };
type Branch = { id: string; name: string; is_active: boolean };

export default function CartPage() {
  const t = useTranslations("cart");
  const f = useFormat();
  const qc = useQueryClient();
  const router = useRouter();
  const { workspace } = useSession();
  const carts = useQuery({ queryKey: ["carts", workspace?.businessId], queryFn: () => api<Cart[]>("/retailer/carts") });
  const branches = useQuery({ queryKey: ["branches", workspace?.businessId], queryFn: () => api<Branch[]>("/retailer/branches") });
  const { loading, run } = useApiAction();
  const [branch, setBranch] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const refresh = () => qc.invalidateQueries({ queryKey: ["carts"] });
  const setQty = async (c: Cart, l: CartLine, quantity: number) => {
    await run(() => api(`/retailer/carts/${c.supplier.id}/items`, { method: "PUT", body: { offer_id: l.offer_id, unit: l.unit, quantity } }), { silent: false });
    refresh();
  };
  if (carts.isLoading) return <SkeletonRows />;
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      {!carts.data?.length ? (
        <Card><EmptyState icon={<ShoppingCart className="h-6 w-6" />} title={t("empty")} description={t("empty_hint")} action={<Link href="/app/store/market" className="rounded-md bg-navy-700 px-4 py-2 text-sm font-semibold text-white">{t("browse")}</Link>} /></Card>
      ) : (
        <div className="space-y-6">
          {carts.data.map((c) => {
            const below = c.min_order_value && Number(c.net) < Number(c.min_order_value);
            return (
              <Card key={c.id} padded={false} data-testid="cart">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
                  <div><p className="text-xs text-muted">{t("supplier")}</p><p className="font-semibold text-navy-700">{c.supplier.name}</p></div>
                  <Button variant="ghost" className="text-danger" icon={<Trash2 className="h-4 w-4" />} onClick={async () => { await run(() => api(`/retailer/carts/${c.supplier.id}`, { method: "DELETE" })); refresh(); }}>{t("clear")}</Button>
                </div>
                <ul className="divide-y divide-line">
                  {c.items.map((l) => (
                    <li key={`${l.offer_id}-${l.unit}`} className="flex flex-wrap items-center gap-4 p-4">
                      <ProductImage src={l.image_url} alt={l.name} className="h-14 w-14" />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-ink">{l.name}</p>
                        <p className="text-xs text-muted">{t(`units.${l.unit}`)}{l.unit === "carton" && ` ×${l.pieces_per_unit}`} · {f.money(l.unit_price)}</p>
                        {l.availability !== "in_stock" && <StatusBadge status={l.availability} />}
                      </div>
                      <QtyStepper value={l.quantity} onChange={(v) => setQty(c, l, v)} />
                      <div className="w-24 text-end">
                        <p className="tabular font-semibold">{f.money(l.line_total)}</p>
                        {Number(l.discount) > 0 && <p className="tabular text-xs text-success">-{f.money(l.discount)}</p>}
                      </div>
                      <button className="rounded p-1.5 text-muted hover:bg-danger/5 hover:text-danger" onClick={() => setQty(c, l, 0)} aria-label={t("remove")}><Trash2 className="h-4 w-4" /></button>
                    </li>
                  ))}
                </ul>
                <div className="grid gap-4 border-t border-line bg-page/50 p-5 md:grid-cols-2">
                  <div className="space-y-3">
                    <Field label={t("branch")}>{(id) => <Select id={id} value={branch[c.id] || ""} onChange={(e) => setBranch({ ...branch, [c.id]: e.target.value })}><option value="">{t("main_branch")}</option>{branches.data?.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select>}</Field>
                    <Field label={t("notes")}>{(id) => <Textarea id={id} rows={2} value={notes[c.id] || ""} onChange={(e) => setNotes({ ...notes, [c.id]: e.target.value })} />}</Field>
                  </div>
                  <div className="flex flex-col justify-between gap-3">
                    <dl className="space-y-1 text-sm">
                      <div className="flex justify-between"><dt className="text-muted">{t("subtotal")}</dt><dd className="tabular">{f.money(c.subtotal)}</dd></div>
                      <div className="flex justify-between"><dt className="text-muted">{t("discount")}</dt><dd className="tabular text-success">-{f.money(c.discount_total)}</dd></div>
                      <div className="flex justify-between text-base font-bold text-navy-700"><dt>{t("net")}</dt><dd className="tabular">{f.money(c.net)}</dd></div>
                      <p className="text-xs text-muted">{t("vat_delivery_note")}</p>
                    </dl>
                    {below && <Alert tone="warning">{t("below_minimum", { min: f.money(c.min_order_value) })}</Alert>}
                    <Button size="lg" disabled={!!below} loading={loading} data-testid="checkout" onClick={async () => {
                      const o = await run(() => api<{ id: string }>(`/retailer/carts/${c.supplier.id}/checkout`, { body: { branch_id: branch[c.id] || null, notes: notes[c.id] || null } }), { success: t("sent") });
                      if (o) { refresh(); router.push(`/app/store/orders/${o.id}`); }
                    }}>{t("send_order")}</Button>
                  </div>
                </div>
              </Card>
            );
          })}
          <CardHeader title="" subtitle={t("direct_payment_note")} />
        </div>
      )}
    </>
  );
}
