"use client";

import { useTranslations } from "next-intl";
import { OrderList } from "@/components/app/orders";

export default function StoreOrders() {
  const t = useTranslations("orders");
  return <OrderList side="store" title={t("title")} subtitle={t("store_subtitle")} />;
}
