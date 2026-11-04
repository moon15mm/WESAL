"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Plus, Sparkles, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Badge, Card, CardHeader, PageHeader } from "@/components/ui/layout";
import { Button, Input, Select } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useFormat } from "@/lib/format";
import { useCities } from "@/lib/hooks";
import { useApiQuery } from "@/lib/list";
import { useSession } from "@/lib/session";
import { useApiAction } from "@/lib/useApiForm";

type Area = { city_id: number; district: string | null; delivery_fee: string; min_order_value: string | null; lead_time_days: number };
type Gap = { items: { city_id: number; city: string; stores: number; suppliers: number; representatives: number; you_cover: boolean; opportunity: boolean }[] };

export default function Coverage() {
  const t = useTranslations("coverage");
  const f = useFormat();
  const qc = useQueryClient();
  const { can } = useSession();
  const cities = useCities();
  const q = useApiQuery<Area[]>(["coverage"], "/supplier/coverage");
  const gaps = useApiQuery<Gap>(["gaps"], "/ai/supplier/coverage-gaps");
  const [rows, setRows] = useState<Area[]>([]);
  const { loading, run } = useApiAction();
  useEffect(() => { if (q.data) setRows(q.data.map((a) => ({ ...a }))); }, [q.data]);
  const set = (i: number, k: keyof Area, v: unknown) => setRows((r) => r.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  const manage = can("supplier.coverage.manage");
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={manage && <Button loading={loading} onClick={async () => {
        if (await run(() => api("/supplier/coverage", { method: "PUT", body: rows.map((r) => ({ ...r, district: r.district || null, min_order_value: r.min_order_value || null, lead_time_days: Number(r.lead_time_days) })) }), { success: t("saved") })) qc.invalidateQueries({ queryKey: ["coverage"] });
      }}>{t("save")}</Button>} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-2 gap-2 rounded-md border border-line p-2 sm:grid-cols-[1.3fr_1fr_100px_110px_80px_auto] sm:items-center">
                <Select value={r.city_id} onChange={(e) => set(i, "city_id", Number(e.target.value))}>{cities.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
                <Input placeholder={t("district_all")} value={r.district || ""} onChange={(e) => set(i, "district", e.target.value)} />
                <Input type="number" step="0.01" aria-label={t("fee")} placeholder={t("fee")} value={r.delivery_fee} onChange={(e) => set(i, "delivery_fee", e.target.value)} />
                <Input type="number" step="0.01" aria-label={t("min_order")} placeholder={t("min_order")} value={r.min_order_value || ""} onChange={(e) => set(i, "min_order_value", e.target.value)} />
                <Input type="number" min={0} aria-label={t("lead_days")} value={r.lead_time_days} onChange={(e) => set(i, "lead_time_days", Number(e.target.value))} />
                <button className="p-2 text-muted hover:text-danger" onClick={() => setRows(rows.filter((_, j) => j !== i))} aria-label="remove"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
            {manage && <Button variant="ghost" icon={<Plus className="h-4 w-4" />} onClick={() => setRows([...rows, { city_id: cities.data?.[0]?.id || 1, district: null, delivery_fee: "0", min_order_value: null, lead_time_days: 1 }])}>{t("add")}</Button>}
          </div>
          <p className="mt-3 text-xs text-muted">{t("columns_hint")}</p>
        </Card>
        <Card>
          <CardHeader title={t("gaps")} subtitle={t("gaps_hint")} action={<Sparkles className="h-5 w-5 text-teal-500" />} />
          <ul className="space-y-2 text-sm">{gaps.data?.items.filter((g) => g.opportunity).slice(0, 10).map((g) => (
            <li key={g.city_id} className="flex items-center justify-between gap-2 rounded-md bg-page p-2.5"><span><span className="font-medium">{g.city}</span><span className="block text-xs text-muted">{t("gap_line", { stores: f.number(g.stores), suppliers: f.number(g.suppliers), reps: f.number(g.representatives) })}</span></span>{!g.you_cover && <Badge tone="teal">{t("not_covered")}</Badge>}</li>
          ))}</ul>
        </Card>
      </div>
    </>
  );
}
