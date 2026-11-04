"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { OrderList } from "@/components/app/orders";
import { Link } from "@/i18n/navigation";

export default function RepOrders() {
  const t = useTranslations("orders");
  return <OrderList side="rep" title={t("title")} subtitle={t("rep_subtitle")} actions={<Link href="/app/rep/orders/new" className="inline-flex h-10 items-center gap-2 rounded-md bg-teal-500 px-4 text-sm font-semibold text-white"><Plus className="h-4 w-4" />{t("new_rep_order")}</Link>} />;
}
