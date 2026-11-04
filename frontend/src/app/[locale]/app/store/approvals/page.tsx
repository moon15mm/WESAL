"use client";

import { useTranslations } from "next-intl";
import { OrderList } from "@/components/app/orders";

export default function Approvals() {
  const t = useTranslations("orders");
  return <OrderList side="store" title={t("approvals_title")} subtitle={t("approvals_subtitle")} initialStatus="pending_retailer_approval,quoted,awaiting_retailer_approval" />;
}
