"use client";

import { useTranslations } from "next-intl";
import { DataTable } from "@/components/ui/data";
import { Badge, Card, CardHeader, PageHeader, StatusBadge } from "@/components/ui/layout";
import { useLocale } from "next-intl";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

type Plan = { id: string; code: string; audience: string; name: Record<string, string>; price_monthly: string; price_yearly: string; limits: Record<string, number | null>; features: string[]; is_active: boolean };
type Sub = { id: string; plan: string; status: string; business_id: string | null; representative_id: string | null; period_start: string; period_end: string | null };

export default function Subscriptions() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const f = useFormat();
  const plans = useApiQuery<Plan[]>(["plans"], "/admin/plans");
  const subs = useApiQuery<Sub[]>(["subs"], "/admin/subscriptions");
  return (
    <>
      <PageHeader title={t("subscriptions_title")} subtitle={t("subscriptions_subtitle")} />
      <div className="grid gap-4 md:grid-cols-3">{plans.data?.map((p) => (
        <Card key={p.id}>
          <div className="flex items-center justify-between"><p className="font-semibold text-navy-700">{p.name[locale] || p.name.en}</p><Badge tone="teal">{t(`audiences.${p.audience}`)}</Badge></div>
          <p className="tabular mt-3 text-2xl font-bold">{f.money(p.price_monthly)}<span className="text-sm font-normal text-muted"> / {t("month")}</span></p>
          <p className="mt-2 text-xs text-muted">{Object.entries(p.limits).map(([k, v]) => `${k}: ${v ?? "∞"}`).join(" · ")}</p>
        </Card>
      ))}</div>
      <Card padded={false} className="mt-6">
        <div className="p-5 pb-0"><CardHeader title={t("subscriptions")} /></div>
        <DataTable rows={subs.data} loading={subs.isLoading} rowKey={(s) => s.id} columns={[
          { key: "p", header: t("plan"), cell: (s) => s.plan }, { key: "s", header: t("status"), cell: (s) => <StatusBadge status={s.status} /> },
          { key: "f", header: t("from"), cell: (s) => f.date(s.period_start) }, { key: "t", header: t("to"), cell: (s) => f.date(s.period_end) },
        ]} />
      </Card>
      <p className="mt-4 text-xs text-muted">{t("billing_note")}</p>
    </>
  );
}
