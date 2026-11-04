"use client";

import { useTranslations } from "next-intl";
import { ReportView } from "@/components/app/reports";

export default function StoreReports() {
  const t = useTranslations("reports");
  return <ReportView path="/reports/retailer" title={t("store_title")}
    kpis={[{ key: "purchases", money: true }, { key: "orders" }, { key: "completed" }, { key: "late" }]}
    sections={[{ key: "suppliers", label: "name", value: "value" }, { key: "top_products", label: "name", value: "value" }]} />;
}
