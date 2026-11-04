"use client";

import { useTranslations } from "next-intl";
import { ReportView } from "@/components/app/reports";

export default function RepReports() {
  const t = useTranslations("reports");
  return <ReportView path="/reports/rep" title={t("rep_title")}
    kpis={[{ key: "sales", money: true }, { key: "orders_created" }, { key: "visits" }, { key: "conversion_rate", percent: true }, { key: "customers" }, { key: "orders_approved" }, { key: "commissions_total", money: true }]}
    sections={[{ key: "by_supplier", label: "name", value: "value" }, { key: "by_city", label: "city", value: "value" }]} />;
}
