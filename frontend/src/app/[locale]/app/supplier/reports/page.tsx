"use client";

import { useTranslations } from "next-intl";
import { ReportView } from "@/components/app/reports";

export default function SupplierReports() {
  const t = useTranslations("reports");
  return <ReportView path="/reports/supplier" title={t("supplier_title")}
    kpis={[{ key: "sales", money: true }, { key: "orders" }, { key: "avg_order", money: true }, { key: "active_customers" }, { key: "new_customers" }, { key: "returns" }, { key: "returns_value", money: true }, { key: "commissions", money: true }]}
    sections={[{ key: "top_products", label: "name", value: "value" }, { key: "representatives", label: "name", value: "value" }, { key: "geography", label: "city", value: "value" }]} />;
}
