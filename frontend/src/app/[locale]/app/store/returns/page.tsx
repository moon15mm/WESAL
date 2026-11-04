"use client";

import { useTranslations } from "next-intl";
import { DataTable, type Column } from "@/components/ui/data";
import { Card, PageHeader, StatusBadge } from "@/components/ui/layout";
import { useRouter } from "@/i18n/navigation";
import { useFormat } from "@/lib/format";
import { useApiQuery } from "@/lib/list";

export type ReturnRow = { id: string; number: string; order_id: string; order_number: string | null; status: string; reason: string; total_value: string; created_at: string; items: { name: string | null; quantity: number; approved_quantity: number | null }[] };

export default function StoreReturns() {
  const t = useTranslations("returns");
  const f = useFormat();
  const router = useRouter();
  const q = useApiQuery<ReturnRow[]>(["store-returns"], "/retailer/returns");
  const cols: Column<ReturnRow>[] = [
    { key: "n", header: t("number"), cell: (r) => <span className="ltr font-semibold">{r.number}</span> },
    { key: "o", header: t("order"), cell: (r) => <span className="ltr">{r.order_number}</span> },
    { key: "reason", header: t("reason"), cell: (r) => t(`reasons.${r.reason}`) },
    { key: "s", header: t("status_label"), cell: (r) => <StatusBadge status={r.status} /> },
    { key: "v", header: t("value"), numeric: true, cell: (r) => f.money(r.total_value) },
    { key: "d", header: t("date"), hideOnMobile: true, cell: (r) => f.date(r.created_at) },
  ];
  return (
    <>
      <PageHeader title={t("title")} subtitle={t("store_subtitle")} />
      <Card padded={false}><DataTable columns={cols} rows={q.data} loading={q.isLoading} rowKey={(r) => r.id} onRowClick={(r) => router.push(`/app/store/orders/${r.order_id}`)} /></Card>
    </>
  );
}
