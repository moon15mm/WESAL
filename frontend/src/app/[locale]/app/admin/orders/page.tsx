"use client";

import { useTranslations } from "next-intl";
import { OrderList } from "@/components/app/orders";

export default function AdminOrders() {
  const t = useTranslations("admin");
  return <OrderList side="admin" title={t("orders_title")} />;
}
