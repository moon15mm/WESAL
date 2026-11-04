"use client";

import { useTranslations } from "next-intl";
import { OrderList } from "@/components/app/orders";

export default function SupplierOrders() {
  const t = useTranslations("orders");
  return <OrderList side="supplier" title={t("title")} subtitle={t("supplier_subtitle")} />;
}
