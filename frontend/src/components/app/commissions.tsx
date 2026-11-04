"use client";

import { useTranslations } from "next-intl";
import { DataTable, type Column } from "@/components/ui/data";
import { StatusBadge } from "@/components/ui/layout";
import { Button } from "@/components/ui/primitives";
import { useFormat } from "@/lib/format";

export type Commission = {
  id: string; status: string; amount: string; original_amount: string; eligible_amount: string; due_at: string | null; created_at: string; paid_at: string | null;
  order: { id: string; number: string; status: string; total: string; retailer: string } | null; supplier: { name: string } | null;
  representative: { id: string; display_name: string } | null; adjustments: { amount_delta: string; reason: string; note: string | null }[];
  disputes: { id: string; status: string; reason: string; expected_amount: string | null }[];
};

export function CommissionTable({ rows, loading, side, onDispute, selected, onSelect, onResolve }: {
  rows?: Commission[]; loading?: boolean; side: "rep" | "supplier" | "admin"; onDispute?: (c: Commission) => void;
  selected?: Set<string>; onSelect?: (id: string, v: boolean) => void; onResolve?: (c: Commission) => void;
}) {
  const t = useTranslations("commissions");
  const f = useFormat();
  const cols: Column<Commission>[] = [
    ...(onSelect ? [{ key: "sel", header: "", cell: (c: Commission) => <input type="checkbox" className="accent-teal-500" disabled={!["due", "approved"].includes(c.status)} checked={selected?.has(c.id) || false} onChange={(e) => onSelect(c.id, e.target.checked)} onClick={(e) => e.stopPropagation()} aria-label="select" /> }] : []),
    { key: "order", header: t("order"), cell: (c) => <span><span className="ltr font-medium">{c.order?.number}</span><span className="block text-xs text-muted">{c.order?.retailer}</span></span> },
    side === "rep" ? { key: "sup", header: t("company"), cell: (c) => c.supplier?.name } : { key: "rep", header: t("representative"), cell: (c) => c.representative?.display_name },
    { key: "base", header: t("eligible"), numeric: true, hideOnMobile: true, cell: (c) => f.money(c.eligible_amount) },
    { key: "amount", header: t("amount"), numeric: true, cell: (c) => <span className="font-semibold">{f.money(c.amount)}{c.adjustments.length > 0 && <span className="block text-xs text-warning">{t("adjusted_n", { n: c.adjustments.length })}</span>}</span> },
    { key: "status", header: t("status_label"), cell: (c) => <StatusBadge status={c.status} /> },
    { key: "due", header: t("due_at"), hideOnMobile: true, cell: (c) => f.date(c.due_at) },
    { key: "act", header: "", cell: (c) => (
      <span className="flex gap-1">
        {side === "rep" && onDispute && !["cancelled", "disputed"].includes(c.status) && <Button size="sm" variant="ghost" onClick={() => onDispute(c)}>{t("dispute")}</Button>}
        {side === "supplier" && onResolve && c.disputes.some((d) => d.status === "open") && <Button size="sm" variant="outline" onClick={() => onResolve(c)}>{t("resolve")}</Button>}
      </span>
    ) },
  ];
  return <DataTable columns={cols} rows={rows} loading={loading} rowKey={(c) => c.id} />;
}
